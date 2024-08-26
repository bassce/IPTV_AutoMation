import os
import asyncio
import aiohttp
import sqlite3
import json
import pandas as pd
import time
import subprocess
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置文件
def load_config():
    try:
        with open("config.json", "r", encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新配置值以允许环境变量覆盖
        config['github_search']['search_query'] = os.getenv('GITHUB_SEARCH_QUERY', config['github_search']['search_query'])
        config['github_search']['search_days'] = int(os.getenv('GITHUB_SEARCH_DAYS', config['github_search']['search_days']))
        config['github_search']['github_token'] = os.getenv('GITHUB_TOKEN', config['github_search']['github_token'])

        config['source_checker']['semaphore_limit'] = int(os.getenv('SEMAPHORE_LIMIT', config['source_checker']['semaphore_limit']))
        config['source_checker']['height_limit'] = os.getenv('HEIGHT_LIMIT', config['source_checker']['height_limit'])

        # 如果环境变量是字符串，则将其转换为列表
        codec_exclude_list = os.getenv('CODEC_EXCLUDE_LIST')
        if codec_exclude_list:
            config['source_checker']['codec_exclude_list'] = codec_exclude_list.split(",")
        else:
            config['source_checker']['codec_exclude_list'] = config['source_checker']['codec_exclude_list']

        config['source_checker']['latency_limit'] = int(os.getenv('LATENCY_LIMIT', config['source_checker']['latency_limit']))
        config['source_checker']['retry_limit'] = int(os.getenv('RETRY_LIMIT', config['source_checker']['retry_limit']))

        config['scheduler']['interval_minutes'] = int(os.getenv('SCHEDULER_INTERVAL_MINUTES', config['scheduler']['interval_minutes']))
        
        return config
    except FileNotFoundError:
        logging.error("config.json file not found.")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing config.json: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error loading config.json: {e}")
        raise

config = load_config()

# 从配置文件中读取参数
DB_PATH = 'data/iptv_sources.db'
SEMAPHORE_LIMIT = config['source_checker']['semaphore_limit']
HEIGHT_LIMIT = config['source_checker']['height_limit']
CODEC_EXCLUDE_LIST = config['source_checker']['codec_exclude_list']
LATENCY_LIMIT = config['source_checker']['latency_limit']
RETRY_LIMIT = config['source_checker']['retry_limit']

semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

async def get_video_info(url):
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,codec_name',
        '-of', 'json', url
    ]
    
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        info = json.loads(result.stdout)
        if 'streams' in info and len(info['streams']) > 0:
            width = info['streams'][0].get('width', None)
            height = info['streams'][0].get('height', None)
            codec_name = info['streams'][0].get('codec_name', "Unknown")
            return int(height) if height is not None else None, codec_name
        return None, "Unknown"
    except subprocess.TimeoutExpired:
        logging.error(f"Timeout getting video info for {url}")
        return None, "Unknown"
    except Exception as e:
        logging.error(f"Error getting video info for {url}: {e}")
        return None, "Unknown"

async def check_source_async(session, source, retries=RETRY_LIMIT):
    async with semaphore:
        url = source["url"]
        for attempt in range(retries):
            try:
                logging.info(f"Starting to check source: {url} (Attempt {attempt+1})")
                start_time = time.time()
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        latency = int((time.time() - start_time) * 1000)  # 计算延迟并转换为毫秒，不保留小数位

                        # 如果延迟超过 LATENCY_LIMIT，跳过此源
                        if LATENCY_LIMIT is not None and latency > LATENCY_LIMIT:
                            logging.info(f"Skipping source due to high latency ({latency} ms): {url}")
                            return None

                        height, codec_name = await get_video_info(url)

                        # 过滤条件
                        if HEIGHT_LIMIT is not None:
                            if HEIGHT_LIMIT == 0:
                                if height is None:
                                    logging.info(f"Skipping source due to unknown height: {url}")
                                    return None
                            elif height is None or height < HEIGHT_LIMIT:
                                logging.info(f"Skipping source due to insufficient height ({height}): {url}")
                                return None

                        if CODEC_EXCLUDE_LIST is not None and codec_name in CODEC_EXCLUDE_LIST:
                            logging.info(f"Skipping source due to excluded codec ({codec_name}): {url}")
                            return None

                        logging.info(f"Checked source: {url} | Latency: {latency} ms | Height: {height if height else 'Unknown'} | Codec: {codec_name}")
                        return {
                            "url": url,
                            "latency": latency,
                            "resolution": f"{height}p" if height else "Unknown",
                            "format": codec_name,
                            "tvg_id": source["tvg_id"],
                            "tvg_name": source["tvg_name"],
                            "group_title": source["group_title"],
                            "aliasesname": source["aliasesname"],
                            "title": source["title"],
                            "id": source["id"]
                        }
                    else:
                        logging.warning(f"Non-200 response code: {response.status} for URL: {url}")
            except aiohttp.ClientConnectorError as e:
                logging.error(f"Connection error for URL {url}: {e}")
            except asyncio.TimeoutError:
                logging.error(f"Timeout for URL {url}")
            except Exception as e:
                logging.error(f"Unexpected error for URL {url}: {e}")

            await asyncio.sleep(2)  # 在重试之前等待2秒

        return None  # 如果重试失败，返回 None

async def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 清空 iptv_playlists 表中的 latency、resolution 和 format 列
    cursor.execute('UPDATE iptv_playlists SET latency = NULL, resolution = NULL, format = NULL')
    conn.commit()

    cursor.execute('SELECT id, tvg_id, tvg_name, group_title, aliasesname, title, url FROM iptv_playlists')
    sources = cursor.fetchall()
    
    filtered_sources = []
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            check_source_async(session, {
                "id": source[0],
                "tvg_id": source[1],
                "tvg_name": source[2],
                "group_title": source[3],
                "aliasesname": source[4],
                "title": source[5],
                "url": source[6]
            })
            for source in sources
        ]
        results = await asyncio.gather(*tasks)

    # 删除现有的 filtered_playlists 表（如果存在）
    cursor.execute('DROP TABLE IF EXISTS filtered_playlists')

    # 创建新的 filtered_playlists 表
    cursor.execute('''
    CREATE TABLE filtered_playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvg_id TEXT,
        tvg_name TEXT,
        group_title TEXT,
        aliasesname TEXT,
        tvordero TEXT,
        tvg_logor TEXT,
        title TEXT,
        url TEXT,
        latency INTEGER,
        resolution TEXT,
        format TEXT
    )
    ''')

    for result in results:
        if result:
            filtered_sources.append(result)
            cursor.execute('''
                UPDATE iptv_playlists
                SET latency = ?, resolution = ?, format = ?
                WHERE id = ?
            ''', (result["latency"], result["resolution"], result["format"], result["id"]))

            cursor.execute('''
                INSERT INTO filtered_playlists (tvg_id, tvg_name, group_title, aliasesname, title, url, latency, resolution, format)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (result["tvg_id"], result["tvg_name"], result["group_title"], result["aliasesname"], result["title"], result["url"], result["latency"], result["resolution"], result["format"]))

    conn.commit()
    conn.close()

    save_filtered_sources_and_m3u8_from_db("data/filtered_sources.m3u8")
    save_to_excel(filtered_sources, "data/filtered_sources.xlsx")

def save_filtered_sources_and_m3u8_from_db(filtered_m3u8):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 按照表中内容的先后顺序（默认插入顺序）读取数据
    cursor.execute('SELECT tvg_name, group_title, title, url FROM filtered_playlists ORDER BY id ASC')
    filtered_sources = cursor.fetchall()

    with open(filtered_m3u8, 'w', encoding='utf-8') as m3u8_file:
        m3u8_file.write("#EXTM3U\n")
        for source in filtered_sources:
            m3u8_file.write(f"#EXTINF:-1 tvg-name=\"{source[0]}\" group-title=\"{source[1]}\",{source[2]}\n")
            m3u8_file.write(f"{source[3]}\n")

    conn.close()


def color_cell(cell):
    if cell >= 3000:
        return 'background-color: #FF1493'  # 粉色
    elif cell > 1000:
        return 'background-color: #FFFF00'  # 黄色
    elif cell > 500:
        return 'background-color: #90EE90'  # 浅绿色
    else:
        return 'background-color: #008000'  # 绿色

def save_to_excel(filtered_sources, output_excel):
    df = pd.DataFrame(filtered_sources)
    if 'latency' in df.columns:
        styled_df = df.style.applymap(color_cell, subset=['latency'])
        styled_df.to_excel(output_excel, index=False, engine='openpyxl')
    else:
        df.to_excel(output_excel, index=False, engine='openpyxl')

if __name__ == "__main__":
    asyncio.run(main())
    # 从数据库中读取数据并生成文件
    save_filtered_sources_and_m3u8_from_db("data/filtered_sources.m3u8")

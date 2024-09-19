from logging_config import logger  # 引入日志配置
import sqlite3
import json
import subprocess
import concurrent.futures
import threading
import asyncio
import aiohttp
from calculate_score import calculate_score  # 导入 calculate_score 函数
import os

logger.info("开始执行 分辨率检测 任务")

# 读取配置文件
def load_config():
    try:
        with open("config.json", "r", encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        logger.error("config.json file not found.")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config.json: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading config.json: {e}")
        raise

config = load_config()

# 获取分辨率筛选的值
height_limit_value = config['source_checker'].get('height_limit')  # 直接获取 height_limit 的值
if height_limit_value is None:
    HEIGHT_LIMIT = None  # 保留 None 表示不做分辨率筛选
else:
    HEIGHT_LIMIT = int(os.getenv('HEIGHT_LIMIT', height_limit_value))  # 如果有值则转换为 int

# 获取环境变量 THREAD_LIMIT 的值，动态设置线程数，如果未提供则使用 CPU 核心数-1，最小为1
THREAD_LIMIT = int(os.getenv('THREAD_LIMIT', config['source_checker']['thread_limit']))
if THREAD_LIMIT == 0:
    THREAD_LIMIT = max(1, int(os.cpu_count() * 1.5))

# 从配置文件中读取参数
DB_PATH = 'data/iptv_sources.db'
LATENCY_LIMIT = int(os.getenv('LATENCY_LIMIT', config['source_checker']['latency_limit'])) / 1000  # 转换为秒
CODEC_EXCLUDE_LIST = os.getenv('CODEC_EXCLUDE_LIST', ','.join(config['source_checker']['codec_exclude_list'])).split(',')
RETRY_LIMIT = int(os.getenv('RETRY_LIMIT', config['source_checker']['retry_limit']))  # 重试次数
FAILURE_THRESHOLD = int(os.getenv('FAILURE_THRESHOLD', config['source_checker']['failure_threshold']))  # 最大失败次数阈值

lock = threading.Lock()

# HTTP HEAD 请求检测流是否可用
async def check_http_head(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(url, timeout=LATENCY_LIMIT) as response:
                if response.status == 200:
                    logger.info(f"Stream is available: {url}")
                    return True
                else:
                    logger.warning(f"Stream not available, status: {response.status} for URL: {url}")
                    return False
        except Exception as e:
            logger.error(f"HTTP HEAD request failed for {url}: {e}")
            return False

# 用 ffprobe 检测分辨率和格式
def get_video_info(url):
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,codec_name',
        '-of', 'json', url
    ]
    
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=LATENCY_LIMIT)
        info = json.loads(result.stdout)
        if 'streams' in info and len(info['streams']) > 0:
            width = info['streams'][0].get('width', 'Unknown')
            height = info['streams'][0].get('height', 'Unknown')
            codec_name = info['streams'][0].get('codec_name', 'Unknown')
            return int(height) if height != 'Unknown' else "Unknown", codec_name
        return "Unknown", "Unknown"
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout occurred for {url}")
        return "Unknown", "Unknown"
    except Exception as e:
        logger.error(f"Error getting video info for {url}: {e}")
        return "Unknown", "Unknown"

# 检测流信息的主函数
import asyncio

# 检测流信息的主函数
def test_stream(source, cursor, conn):
    url = source["url"]
    retry_count = 0

    # 创建并设置新的事件循环，适用于多线程环境
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 使用异步方式进行 HTTP HEAD 检测
    available = loop.run_until_complete(check_http_head(url))

    if not available:
        logger.info(f"Skipping further checks for {url} due to failed HTTP HEAD")
        return None

    while retry_count <= RETRY_LIMIT:
        try:
            # 获取分辨率和格式
            resolution, format = get_video_info(url)

            # 稳定性、成功率、延迟、下载速度的默认值
            stability = 1
            success_rate = 1
            latency = 0
            download_speed = 0.0
            
            # 计算分数
            score = round(calculate_score(resolution, format, latency, download_speed, stability, success_rate), 4)

            # 检查分辨率限制
            if HEIGHT_LIMIT is not None:
                if HEIGHT_LIMIT == 0:
                    if resolution == "Unknown" or resolution < 1:
                        logger.info(f"Excluding source with unknown or 0 resolution: {url}")
                        return None
                elif HEIGHT_LIMIT > 0 and (resolution == "Unknown" or resolution < HEIGHT_LIMIT):
                    logger.info(f"Excluding source with resolution below {HEIGHT_LIMIT}p: {url}")
                    return None
            
            # 检查视频格式是否在排除列表中
            if format in CODEC_EXCLUDE_LIST:
                logger.info(f"Excluding source with format {format}: {url}")
                return None

            logger.info(f"Stream OK: {url} | Resolution: {resolution} | Format: {format} | Score: {score}")
            return {
                "url": url,
                "resolution": resolution,
                "format": format,
                "tvg_id": source["tvg_id"],
                "tvg_name": source["tvg_name"],
                "group_title": source["group_title"],
                "aliasesname": source["aliasesname"],
                "tvordero": source["tvordero"],
                "tvg_logor": source["tvg_logor"],
                "title": source["title"],
                "id": source["id"],
                "latency": latency,
                "download_speed": download_speed,
                "score": score
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout occurred for {url}")
            cursor.execute('''
                UPDATE iptv_playlists
                SET failure_count = failure_count + 1, last_failed_date = datetime('now', 'localtime')
                WHERE id = ?
            ''', (source['id'],))
            conn.commit()  # 确保 conn 在此处被传递
            return None  # 在超时时立即返回，跳过后续的分辨率检查

        except Exception as e:
            retry_count += 1
            logger.error(f"Error testing stream {url}: {e}, retrying {retry_count}/{RETRY_LIMIT}...")

    logger.error(f"Failed to test stream {url} after {RETRY_LIMIT} attempts.")
    return None

def run_tests():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 新建 failed_sources 表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS failed_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvg_id TEXT,
        tvg_name TEXT,
        group_title TEXT,
        aliasesname TEXT,
        tvordero INTEGER,
        tvg_logor TEXT,
        title TEXT,
        url TEXT,
        failure_count INTEGER,
        last_failed_date TIMESTAMP
    )
    ''')

    cursor.execute('''
    INSERT OR REPLACE INTO table_metadata (table_name, created_at)
    VALUES ('failed_sources', datetime('now', 'localtime'))
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS filtered_playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvg_id TEXT,
        tvg_name TEXT,
        group_title TEXT,
        aliasesname TEXT,
        tvordero INTEGER,
        tvg_logor TEXT,
        title TEXT,
        url TEXT,
        latency INTEGER,
        resolution TEXT,
        format TEXT,
        download_speed FLOAT,
        score FLOAT,
        failure_count INTEGER DEFAULT 0,
        last_failed_date TIMESTAMP DEFAULT 0
    )
    ''')

    cursor.execute('''
    INSERT OR REPLACE INTO table_metadata (table_name, created_at)
    VALUES ('filtered_playlists', datetime('now', 'localtime'))
    ''')

    cursor.execute('''
    SELECT id, tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url, failure_count
    FROM iptv_playlists
    WHERE last_failed_date IS NOT NULL
    ''')
    sources = cursor.fetchall()

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_LIMIT) as executor:
        future_to_url = {executor.submit(test_stream, {
            "id": source[0],
            "tvg_id": source[1],
            "tvg_name": source[2],
            "group_title": source[3],
            "aliasesname": source[4],
            "tvordero": source[5],
            "tvg_logor": source[6],
            "title": source[7],
            "url": source[8],
            "failure_count": source[9]
        }, cursor, conn): source for source in sources}

        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                cursor.execute('''
                    SELECT 1 FROM filtered_playlists WHERE url = ?
                ''', (result['url'],))
                exists = cursor.fetchone()

                if not exists:
                    results.append(result)
                else:
                    logger.info(f"Skipping duplicate URL: {result['url']}")
            else:
                source_id = future_to_url[future][0]
                cursor.execute('''
                UPDATE iptv_playlists
                SET failure_count = failure_count + 1, last_failed_date = datetime('now', 'localtime')
                WHERE id = ?
                ''', (source_id,))

                cursor.execute('SELECT failure_count FROM iptv_playlists WHERE id = ?', (source_id,))
                failure_count = cursor.fetchone()[0]

                if failure_count >= FAILURE_THRESHOLD:
                    cursor.execute('''
                    INSERT INTO failed_sources (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url, failure_count, last_failed_date)
                    SELECT tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url, failure_count, last_failed_date
                    FROM iptv_playlists
                    WHERE id = ?
                    ''', (source_id,))
                    cursor.execute('DELETE FROM iptv_playlists WHERE id = ?', (source_id,))
                    logger.info(f"Source {source_id} moved to failed_sources due to exceeding failure threshold.")

    results.sort(key=lambda x: x["tvordero"])

    for result in results:
        cursor.execute('''
            UPDATE iptv_playlists
            SET resolution = ?, format = ?, failure_count = 0, last_failed_date = NULL
            WHERE id = ?
        ''', (result["resolution"], result["format"], result["id"]))

        cursor.execute('''
            INSERT INTO filtered_playlists (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url, latency, resolution, format, download_speed, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (result["tvg_id"], result["tvg_name"], result["group_title"], result["aliasesname"], result["tvordero"], result["tvg_logor"], result["title"], result["url"], result["latency"], result["resolution"], result["format"], result["download_speed"], result["score"]))

    conn.commit()
    conn.close()

    logger.info("Testing completed, results sorted by tvordero, and data saved.")

if __name__ == "__main__":
    run_tests()

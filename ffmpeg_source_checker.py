import sqlite3
import json
import subprocess
import logging
import concurrent.futures
from calculate_score import calculate_score  # 导入 calculate_score 函数

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置文件
def load_config():
    try:
        with open("config.json", "r", encoding='utf-8') as f:
            config = json.load(f)
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
THREAD_LIMIT = config['source_checker']['thread_limit']
LATENCY_LIMIT = config['source_checker']['latency_limit'] / 1000  # 转换为秒
HEIGHT_LIMIT = config['source_checker']['height_limit']
CODEC_EXCLUDE_LIST = config['source_checker']['codec_exclude_list']
RETRY_LIMIT = config['source_checker']['retry_limit']  # 重试次数

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
        logging.error(f"Timeout occurred for {url}")
        return "Unknown", "Unknown"
    except Exception as e:
        logging.error(f"Error getting video info for {url}: {e}")
        return "Unknown", "Unknown"

def test_stream(source):
    url = source["url"]
    retry_count = 0

    while retry_count < RETRY_LIMIT:
        try:
            resolution, format = get_video_info(url)
            stability = 1  # 这里可以使用实际值
            success_rate = 1  # 这里可以使用实际值
            latency = 0  # 默认值，实际值在 daily_monitor.py 中检测
            download_speed = 0.0  # 默认值，实际值在 daily_monitor.py 中检测

            # 计算评分后进行四舍五入处理
            score = round(calculate_score(resolution, format, latency, download_speed, stability, success_rate), 4)

            if HEIGHT_LIMIT is not None:
                if HEIGHT_LIMIT == 0:
                    if resolution == "Unknown" or resolution < 1:
                        logging.info(f"Excluding source with unknown or 0 resolution: {url}")
                        return None
                elif HEIGHT_LIMIT > 0 and (resolution == "Unknown" or resolution < HEIGHT_LIMIT):
                    logging.info(f"Excluding source with resolution below {HEIGHT_LIMIT}p: {url}")
                    return None
            
            if format in CODEC_EXCLUDE_LIST:
                logging.info(f"Excluding source with format {format}: {url}")
                return None

            logging.info(f"Stream OK: {url} | Resolution: {resolution} | Format: {format} | Score: {score}")
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
                "latency": latency,  # 默认值
                "download_speed": download_speed,  # 默认值
                "score": score  # 确保这个值是浮点数
            }

        except Exception as e:
            retry_count += 1
            logging.error(f"Error testing stream {url}: {e}, retrying {retry_count}/{RETRY_LIMIT}...")

    logging.error(f"Failed to test stream {url} after {RETRY_LIMIT} attempts.")
    return None

def run_tests():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 清空 iptv_playlists 表中的 resolution 和 format 列
    cursor.execute('UPDATE iptv_playlists SET resolution = NULL, format = NULL')
    conn.commit()

    cursor.execute('SELECT id, tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url FROM iptv_playlists')
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
            "url": source[8]
        }): source for source in sources}

        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                results.append(result)

    # 按照 tvordero 从小到大排序
    results.sort(key=lambda x: x["tvordero"])

    # 删除现有的 filtered_playlists 表（如果存在）
    cursor.execute('DROP TABLE IF EXISTS filtered_playlists')

    # 创建新的 filtered_playlists 表，包括评分列
    cursor.execute('''
    CREATE TABLE filtered_playlists (
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
        score FLOAT
    )
    ''')

    for result in results:
        cursor.execute('''
            UPDATE iptv_playlists
            SET resolution = ?, format = ?
            WHERE id = ?
        ''', (result["resolution"], result["format"], result["id"]))

        cursor.execute('''
            INSERT INTO filtered_playlists (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url, latency, resolution, format, download_speed, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (result["tvg_id"], result["tvg_name"], result["group_title"], result["aliasesname"], result["tvordero"], result["tvg_logor"], result["title"], result["url"], result["latency"], result["resolution"], result["format"], result["download_speed"], result["score"]))

    conn.commit()
    conn.close()

    logging.info("Testing completed, results sorted by tvordero, and data saved.")

if __name__ == "__main__":
    run_tests()

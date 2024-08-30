import sqlite3
import json
import subprocess
import logging
import time
import re
import pandas as pd
import concurrent.futures
import aiohttp
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 添加开始日志
logging.info("Starting daily_monitor.py...")

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
THREADS = config['source_checker']['thread_limit']
LATENCY_LIMIT = config['source_checker']['latency_limit'] / 1000  # 以秒为单位
RETRY_LIMIT = config['source_checker']['retry_limit']  # 重试次数

def convert_to_kb(size, unit):
    size = float(size)
    unit = unit.lower()
    if 'm' in unit:
        return size * 1024
    elif 'g' in unit:
        return size * 1024 * 1024
    elif 'k' in unit:
        return size
    else:
        return size / 1024

async def check_latency(url):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.time()
            async with session.get(url, timeout=LATENCY_LIMIT) as response:
                latency = int((time.time() - start_time) * 1000)  # 将延迟转换为毫秒并保留整数
                if response.status == 200:
                    return latency
                else:
                    logging.warning(f"Invalid response {response.status} for URL: {url}")
                    return None
        except Exception as e:
            logging.error(f"Error checking latency for URL {url}: {e}")
            return None

def get_stream_info(url, duration, threads=THREADS):
    command = [
        'ffmpeg',
        '-threads', str(threads),
        '-i', url,
        '-t', str(duration),
        '-f', 'null',
        '-loglevel', 'info',
        '-'
    ]
    try:
        start_time = time.time()
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=duration + 2)
        elapsed_time = time.time() - start_time

        # 忽略初始波动时间
        ignore_initial_seconds = 2
        effective_time = max(elapsed_time - ignore_initial_seconds, 0.5)  # 设置最小值为0.5秒

        stderr_output = result.stderr
        video_match = re.search(r'video:\s*([\d\.]+)([kKMG]?i?B)', stderr_output)
        audio_match = re.search(r'audio:\s*([\d\.]+)([kKMG]?i?B)', stderr_output)

        video_size = convert_to_kb(video_match.group(1), video_match.group(2)) if video_match else 0
        audio_size = convert_to_kb(audio_match.group(1), audio_match.group(2)) if audio_match else 0
        total_size = video_size + audio_size

        download_speed = round(total_size / effective_time) if effective_time > 0 else 0

        return {
            "download_speed": download_speed
        }

    except subprocess.TimeoutExpired:
        logging.error(f"Timeout occurred for {url}")
        return {"download_speed": 0}
    except Exception as e:
        logging.error(f"Error processing stream {url}: {e}")
        return {"download_speed": 0}

def test_stream(source):
    url = source["url"]
    latency = asyncio.run(check_latency(url))
    if latency is None or latency > LATENCY_LIMIT * 1000:
        logging.info(f"Skipping source due to high latency ({latency} ms): {url}")
        return None

    download_info = get_stream_info(url, LATENCY_LIMIT)
    logging.info(f"Stream OK: {url} | Latency: {latency} ms | Download Speed: {download_info['download_speed']} KB/s")
    return {
        "id": source["id"],
        "latency": latency,
        "download_speed": download_info["download_speed"]
    }

def run_tests():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('UPDATE filtered_playlists SET latency = NULL, download_speed = NULL')
    conn.commit()

    cursor.execute('SELECT id, url FROM filtered_playlists')
    sources = cursor.fetchall()

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        results = list(executor.map(test_stream, [{"id": source[0], "url": source[1]} for source in sources]))

    for result in results:
        if result:
            cursor.execute('''
                UPDATE filtered_playlists
                SET latency = ?, download_speed = ?
                WHERE id = ?
            ''', (result["latency"], result["download_speed"], result["id"]))

    conn.commit()

    df = pd.read_sql_query("SELECT * FROM filtered_playlists ORDER BY id", conn)
    df['download_speed'] = pd.to_numeric(df['download_speed'], errors='coerce').fillna(0)

    def highlight_speed(cell):
        try:
            value = float(cell)
            if cell <= 400:
                return 'background-color: #FF1493'
            elif cell < 600:
                return 'background-color: #FFFF00'
            elif cell < 800:
                return 'background-color: #90EE90'
            else:
                return 'background-color: #008000'
        except ValueError:
            return ''

    df_style = df.style.applymap(highlight_speed, subset=['download_speed'])
    df_style.to_excel('data/filtered_sources.xlsx', index=False)

    with open('data/filtered_sources.m3u8', 'w', encoding='utf-8') as f:
        for _, row in df.iterrows():
            f.write(f'#EXTINF:-1,{row["title"]}\n')
            f.write(f'{row["url"]}\n')

    conn.close()
    logging.info("Testing completed, results saved, and files generated.")

if __name__ == "__main__":
    run_tests()

    # 添加结束日志
    logging.info("Finished daily_monitor.py.")

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
import os
import threading  # 引入 threading 模块
from calculate_score import calculate_score, update_stability_and_success_rate  # 引入评分机制及相关函数

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
FAILURE_THRESHOLD = config['source_checker']['failure_threshold']  # 最大失败次数阈值

# 创建全局锁对象
lock = threading.Lock()

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
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=duration + 2, encoding='utf-8', errors='ignore')
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

def handle_failed_stream(source, cursor):
    with lock:  # 加锁，确保数据库操作是线程安全的
        try:
            # 将需要移动的直播源直接移动到 iptv_playlists 表中
            cursor.execute('''
            UPDATE iptv_playlists 
            SET failure_count = failure_count + 1, last_failed_date = datetime('now', 'localtime')
            WHERE url = ? AND tvg_name = ?
            ''', (source['url'], source['tvg_name']))

            # 从 filtered_playlists 表中删除这些记录
            cursor.execute('''
            DELETE FROM filtered_playlists WHERE id = ?
            ''', (source['id'],))

            logging.info(f"Source {source['id']} moved to iptv_playlists due to exceeding failure threshold.")
            
        except sqlite3.OperationalError as e:
            logging.error(f"Database operation failed: {e}")

def test_stream(source, cursor):
    url = source["url"]
    retries = 0

    while retries < RETRY_LIMIT:
        latency = asyncio.run(check_latency(url))
        if latency is None or latency > LATENCY_LIMIT * 1000:
            retries += 1
            logging.info(f"Retrying source due to high latency ({latency} ms): {url} ({retries}/{RETRY_LIMIT})")
            continue

        previous_score = source.get("score", 0)
        stability = source.get("stability", 0.9)
        success_rate = source.get("success_rate", 0.95)

        download_info = get_stream_info(url, LATENCY_LIMIT)
        logging.info(f"Stream OK: {url} | Latency: {latency} ms | Download Speed: {download_info['download_speed']} KB/s")

        # 如果下载速度为0，则认为检测失败
        if download_info["download_speed"] > 0:
            stability, success_rate = update_stability_and_success_rate(stability, success_rate, True)
            updated_score = calculate_score(
                resolution_value=source.get("resolution_value", None),
                format=source.get("format", None),
                latency=latency / 1000,
                download_speed=download_info["download_speed"] / 1024,
                stability=stability,
                success_rate=success_rate,
                previous_score=previous_score
            )

            return {
                "id": source["id"],
                "latency": latency,
                "download_speed": download_info["download_speed"],
                "stability": stability,
                "success_rate": success_rate,
                "score": updated_score
            }
        else:
            retries += 1
            logging.info(f"Retrying source due to low download speed ({download_info['download_speed']} KB/s): {url} ({retries}/{RETRY_LIMIT})")

    # 超过重试次数仍然失败，返回None
    logging.info(f"Source failed after {RETRY_LIMIT} attempts: {url}")
    return None

def run_tests():
    conn = sqlite3.connect(DB_PATH, timeout=10)  # 设置超时时间为10秒
    cursor = conn.cursor()

    try:
        # 先清空延迟和下载速度的旧数据
        cursor.execute('UPDATE filtered_playlists SET latency = NULL, download_speed = NULL')
        conn.commit()

        # 选择直播源进行测试
        cursor.execute('SELECT id, url, score FROM filtered_playlists')
        sources = cursor.fetchall()

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
            results = list(executor.map(lambda src: test_stream(src, cursor), [{"id": source[0], "url": source[1], "score": source[2]} for source in sources]))

        for index, result in enumerate(results):
            source_id = sources[index][0]  # 获取原始 source 的 id
            if result:
                # 检测成功，更新 latency、download_speed、score，并清除 last_failed_date 和 failure_count
                cursor.execute('''
                    UPDATE filtered_playlists
                    SET latency = ?, download_speed = ?, score = ?, failure_count = 0, last_failed_date = NULL
                    WHERE id = ?
                ''', (result["latency"], result["download_speed"], result["score"], result["id"]))
            else:
                # 检测失败，更新 last_failed_date 和 failure_count
                cursor.execute('''
                UPDATE filtered_playlists
                SET failure_count = failure_count + 1, last_failed_date = datetime('now', 'localtime')
                WHERE id = ?
                ''', (source_id,))

                # 检查 failure_count 是否达到阈值
                cursor.execute('SELECT failure_count FROM filtered_playlists WHERE id = ?', (source_id,))
                failure_count = cursor.fetchone()[0]

                if failure_count >= FAILURE_THRESHOLD:
                    # 获取源的 url 和 tvg_name
                    cursor.execute('SELECT url, tvg_name FROM filtered_playlists WHERE id = ?', (source_id,))
                    url, tvg_name = cursor.fetchone()

                    handle_failed_stream({"id": source_id, "url": url, "tvg_name": tvg_name}, cursor)

        # 创建或替换只读表
        cursor.execute("DROP TABLE IF EXISTS filtered_playlists_readonly")
        cursor.execute("CREATE TABLE filtered_playlists_readonly AS SELECT * FROM filtered_playlists")
        
        # 更新元数据表的创建时间
        cursor.execute('''
        INSERT OR REPLACE INTO table_metadata (table_name, created_at)
        VALUES ('filtered_playlists_readonly', datetime('now', 'localtime'))
        ''')

        conn.commit()  # 确保更改被提交

        logging.info("filtered_playlists_readonly table creation time recorded successfully.")

        # 在关闭数据库连接之前读取数据
        df = pd.read_sql_query("SELECT * FROM filtered_playlists ORDER BY id", conn)

    finally:
        # 关闭数据库连接
        conn.close()

    # 数据处理和生成Excel、M3U8文件
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

    df_style = df.style.map(highlight_speed, subset=['download_speed'])
    df_style.to_excel('data/filtered_sources.xlsx', index=False)

    with open('data/filtered_sources.m3u8', 'w', encoding='utf-8') as f:
        for _, row in df.iterrows():
            f.write(f'#EXTINF:-1,{row["title"]}\n')
            f.write(f'{row["url"]}\n')

    logging.info("Testing completed, results saved, and files generated.")

if __name__ == "__main__":
    run_tests()

    # 添加结束日志
    logging.info("Finished daily_monitor.py.")

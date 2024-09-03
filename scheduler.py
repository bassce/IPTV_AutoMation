import asyncio
import logging
import json
import os
import psutil
import sqlite3
from datetime import datetime, timedelta
import subprocess

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(asctime)s - %(message)s')

# 读取配置文件
def load_config():
    try:
        with open("config.json", "r", encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新配置值以允许环境变量覆盖
        config['github_search']['search_query'] = os.getenv('GITHUB_SEARCH_QUERY', config['github_search']['search_query'])
        config['github_search']['search_days'] = int(os.getenv('GITHUB_SEARCH_DAYS', config['github_search']['search_days']))
        config['github_search']['github_token'] = os.getenv('GITHUB_TOKEN', config['github_search']['github_token'])

        config['source_checker']['thread_limit'] = int(os.getenv('THREAD_LIMIT', config['source_checker']['thread_limit']))
        config['source_checker']['height_limit'] = os.getenv('HEIGHT_LIMIT', config['source_checker']['height_limit'])
        
        codec_exclude_list = os.getenv('CODEC_EXCLUDE_LIST')
        if codec_exclude_list:
            config['source_checker']['codec_exclude_list'] = codec_exclude_list.split(',')
        
        config['source_checker']['latency_limit'] = int(os.getenv('LATENCY_LIMIT', config['source_checker']['latency_limit']))
        config['source_checker']['retry_limit'] = int(os.getenv('RETRY_LIMIT', config['source_checker']['retry_limit']))

        config['scheduler']['interval_minutes'] = int(os.getenv('SCHEDULER_INTERVAL_MINUTES', config['scheduler']['interval_minutes']))
        config['scheduler']['failed_sources_cleanup_days'] = int(os.getenv('FAILED_SOURCES_CLEANUP_DAYS', config['scheduler']['failed_sources_cleanup_days']))
        config['scheduler']['ffmpeg_check_frequency_minutes'] = int(os.getenv('ffmpeg_check_frequency_minutes', config['scheduler']['ffmpeg_check_frequency_minutes']))

        # 新增读取 host_ip 环境变量
        config['network']['host_ip'] = os.getenv('HOST_IP', config.get('network', {}).get('host_ip', 'localhost'))
        
        return config
    except FileNotFoundError:
        logging.error("config.json file not found.")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing config.json: %s", e)
        raise
    except Exception as e:
        logging.error("Unexpected error loading config.json: %s", e)
        raise

# 使用 load_config 函数加载配置
config = load_config()

def kill_processes_by_names(names):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmdline = proc.info.get('cmdline')
        if cmdline:  # 检查 cmdline 是否为 None
            for name in names:
                if name in cmdline:
                    logging.info("Killing process %s with PID %s", proc.info['name'], proc.info['pid'])
                    proc.kill()

def table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
    return cursor.fetchone() is not None

def get_table_creation_time(table_name):
    conn = sqlite3.connect("data/iptv_sources.db")
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT created_at FROM table_metadata WHERE table_name = ?", (table_name,))
        result = cursor.fetchone()
        if result:
            return datetime.fromisoformat(result[0])
        else:
            logging.warning("No creation time found for table %s", table_name)
            return None
    except sqlite3.Error as e:
        logging.error("Error getting creation time for table %s: %s", table_name, e)
        return None
    finally:
        conn.close()

async def run_subprocess(script_name):
    logging.info("Starting %s...", script_name)
    try:
        process = await asyncio.create_subprocess_exec("python", script_name)
        await process.wait()  # 等待子进程完成
        logging.info("Finished %s.", script_name)
    except Exception as e:
        logging.error("Failed to run %s: %s", script_name, e)

async def run_daily_monitor():
    await run_subprocess("daily_monitor.py")

async def run_flask_server():
    await run_subprocess("flask_server.py")

async def run_ffmpeg_source_checker():
    await run_subprocess("ffmpeg_source_checker.py")

async def clean_failed_sources():
    conn = sqlite3.connect("data/iptv_sources.db")
    cursor = conn.cursor()

    try:
        cutoff_date = datetime.now() - timedelta(days=config['scheduler']['failed_sources_cleanup_days'])
        cursor.execute("DELETE FROM failed_sources WHERE last_failed_date IS NOT NULL AND last_failed_date < ?", (cutoff_date,))
        conn.commit()
        logging.info("Cleaned up failed sources older than %d days.", config['scheduler']['failed_sources_cleanup_days'])
    except sqlite3.Error as e:
        logging.error("Failed to clean up failed sources: %s", e)
    finally:
        conn.close()

async def check_and_run_flask():
    conn = sqlite3.connect("data/iptv_sources.db")
    cursor = conn.cursor()

    filtered_exists = table_exists(conn, "filtered_playlists")
    readonly_exists = table_exists(conn, "filtered_playlists_readonly")

    if filtered_exists and not readonly_exists:
        creation_time = get_table_creation_time("filtered_playlists")
        if creation_time:
            time_diff = datetime.now() - creation_time
            if time_diff < timedelta(hours=24):
                logging.info("filtered_playlists exists and is less than 24 hours old. Running daily_monitor.py to create filtered_playlists_readonly.")
                await run_daily_monitor()
            else:
                logging.info("filtered_playlists exists and is older than 24 hours. Running run_scheduler_tasks to reinitialize.")
                await run_scheduler_tasks()
        else:
            logging.warning("filtered_playlists table exists, but creation time not found. Initializing the project.")
            await run_scheduler_tasks()

    elif not filtered_exists and not readonly_exists:
        logging.info("Neither filtered_playlists nor filtered_playlists_readonly tables exist, initializing the project.")
        await run_scheduler_tasks()

    if readonly_exists:
        creation_time = get_table_creation_time("filtered_playlists_readonly")
        if creation_time:
            time_diff = datetime.now() - creation_time
            if time_diff > timedelta(hours=24):
                logging.info("filtered_playlists_readonly table is older than 24 hours, running daily_monitor.py first.")
                await run_daily_monitor()
        else:
            logging.warning("filtered_playlists_readonly table exists, but creation time not found. Deleting the table.")
            cursor.execute("DROP TABLE IF EXISTS filtered_playlists_readonly")
            conn.commit()

            logging.info("Running daily_monitor.py to recreate filtered_playlists_readonly table.")
            await run_daily_monitor()

            # 在重新生成表后，检查表是否存在
            if not table_exists(conn, "filtered_playlists_readonly"):
                logging.error("Failed to create filtered_playlists_readonly table, cannot start flask_server.")
                return

    # 确保表存在后再启动flask_server
    await run_flask_server()
    conn.close()

async def run_scheduler_tasks():
    logging.info("Cleaning up old failed sources before starting other tasks...")
    await clean_failed_sources()  # 添加清理任务，确保导入前的清理

    logging.info("Starting database initialization (db_setup.py)...")
    await run_subprocess("db_setup.py")

    logging.info("Starting to search and import new sources...")
    await run_subprocess("github_search.py")
    await run_subprocess("import_playlists.py")

    logging.info("Starting ffmpeg_source_checker.py...")
    await run_subprocess("ffmpeg_source_checker.py")

    logging.info("Stopping flask_server.py and daily_monitor.py if running...")
    kill_processes_by_names(["flask_server.py", "daily_monitor.py"])

    logging.info("Restarting daily_monitor.py and flask_server.py...")
    await run_daily_monitor()
    await run_flask_server()


async def schedule_daily_monitor(interval_minutes):
    while True:
        await asyncio.sleep(interval_minutes * 60)
        await run_daily_monitor()

        # 检查 flask_server.py 是否正在运行
        result = subprocess.run(['pgrep', '-f', 'flask_server.py'], stdout=subprocess.PIPE)
        if result.stdout:
            # 如果已经在运行，先杀掉再重新启动
            subprocess.run(['pkill', '-f', 'flask_server.py'])
            logging.info("Flask server stopped. Restarting...")
            await run_flask_server()
        else:
            # 如果没有运行，则直接启动
            logging.info("Flask server not running. Starting...")
            await run_flask_server()

async def schedule_ffmpeg_check():
    while True:
        await asyncio.sleep(config['scheduler']['ffmpeg_check_frequency_minutes'] * 60)
        await run_ffmpeg_source_checker()

async def schedule_failed_sources_cleanup():
    while True:
        await asyncio.sleep(config['scheduler']['failed_sources_cleanup_days'] * 86400)
        await clean_failed_sources()

def run_scheduler():
    loop = asyncio.new_event_loop()  # 创建新的事件循环以避免旧的弃用警告
    asyncio.set_event_loop(loop)
    tasks = [
        check_and_run_flask(),  # 检查表的存在性并执行相应的操作
        schedule_daily_monitor(config['scheduler']['interval_minutes']),
        schedule_ffmpeg_check(),
        schedule_failed_sources_cleanup()
    ]

    loop.run_until_complete(asyncio.gather(*tasks))

if __name__ == "__main__":
    run_scheduler()

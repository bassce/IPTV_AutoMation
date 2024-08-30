import asyncio
import logging
import json
import os
import psutil

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

        config['source_checker']['thread_limit'] = int(os.getenv('THREAD_LIMIT', config['source_checker']['thread_limit']))
        config['source_checker']['height_limit'] = os.getenv('HEIGHT_LIMIT', config['source_checker']['height_limit'])
        
        codec_exclude_list = os.getenv('CODEC_EXCLUDE_LIST')
        if codec_exclude_list:
            config['source_checker']['codec_exclude_list'] = codec_exclude_list.split(',')
        
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

# 使用 load_config 函数加载配置
config = load_config()

def kill_processes_by_names(names):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmdline = proc.info.get('cmdline')
        if cmdline:  # 检查 cmdline 是否为 None
            for name in names:
                if name in cmdline:
                    logging.info(f"Killing process {proc.info['name']} with PID {proc.info['pid']}")
                    proc.kill()

async def run_subprocess(script_name):
    logging.info(f"Starting {script_name}...")
    try:
        process = await asyncio.create_subprocess_exec("python", script_name)
        await process.wait()  # 等待子进程完成
        logging.info(f"Finished {script_name}.")
    except Exception as e:
        logging.error(f"Failed to run {script_name}: {e}")

async def run_daily_monitor():
    await run_subprocess("daily_monitor.py")

async def run_flask_server():
    await run_subprocess("flask_server.py")

async def run_scheduler_tasks():
    logging.info("Starting database initialization (db_setup.py)...")
    await run_subprocess("db_setup.py")

    logging.info("Starting to search and import new sources...")
    await run_subprocess("github_search.py")
    await run_subprocess("import_playlists.py")

    logging.info("Starting ffmpeg_source_checker.py...")
    await run_subprocess("ffmpeg_source_checker.py")

    logging.info("Starting flask_server.py and initial daily_monitor.py...")
    kill_processes_by_names(["flask_server.py", "daily_monitor.py"])
    await run_daily_monitor()
    await run_flask_server()

async def schedule_daily_monitor(interval_minutes):
    while True:
        await asyncio.sleep(interval_minutes * 60)
        await run_daily_monitor()

def run_scheduler():
    loop = asyncio.get_event_loop()
    tasks = [
        run_scheduler_tasks(),
        schedule_daily_monitor(config['scheduler']['interval_minutes'])
    ]

    loop.run_until_complete(asyncio.gather(*tasks))

if __name__ == "__main__":
    run_scheduler()


import asyncio
import json
import os
from logging_config import logger  # 使用 logging_config 中的 logger
from asyncio import Queue
from watchfiles import awatch
import psutil

logger.info("程序启动")

# 加载配置文件
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

# 加载配置
config = load_config()

# 从环境变量或配置文件中获取参数
HOST_IP = os.getenv('HOST_IP', config["network"]["host_ip"])  # 获取主机 IP
SCHEDULER_INTERVAL_MINUTES = int(os.getenv('SCHEDULER_INTERVAL_MINUTES', config['scheduler']['interval_minutes']))
FAILED_SOURCES_CLEANUP_DAYS = int(os.getenv('FAILED_SOURCES_CLEANUP_DAYS', config['scheduler']['failed_sources_cleanup_days']))
FFMPEG_CHECK_FREQUENCY_MINUTES = int(os.getenv('FFMPEG_CHECK_FREQUENCY_MINUTES', config['scheduler']['ffmpeg_check_frequency_minutes']))
SEARCH_INTERVAL_HOURS = int(os.getenv('SEARCH_INTERVAL_HOURS', config['scheduler']['search_interval_hours']))  # 获取搜索间隔
PORT = int(os.getenv('PORT', int(config["network"]["port"])))

# 创建任务队列
task_queue = Queue()

async def worker():
    """从队列中获取任务并依次执行"""
    while True:
        task = await task_queue.get()
        try:
            logger.info(f"Executing task {task}")
            await task  # 执行任务
            logger.info(f"Task {task} completed successfully")
        except Exception as e:
            logger.error(f"Error executing task {task}: {e}")
        task_queue.task_done()

async def add_task_to_queue(task):
    """添加单个任务到队列"""
    await task_queue.put(task)

async def is_process_running(script_names):
    """检查是否有给定的脚本正在运行"""
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 确保 cmdline 不为 None
            cmdline = process.info['cmdline']
            if cmdline and any(script_name in cmdline for script_name in script_names):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

async def schedule_daily_monitor():
    """定时任务：将 daily_monitor.py 放入队列"""
    monitored_scripts = [
        "daily_monitor.py",
        "ffmpeg_source_checker.py",
        "github_search.py",
        "hotel_search.py",
        "domain_batch_query.py",
        "db_setup.py",
        "import_playlists.py"
    ]
    
    while True:
        await asyncio.sleep(SCHEDULER_INTERVAL_MINUTES * 60)
        if not await is_process_running(monitored_scripts):
            await add_task_to_queue(run_subprocess("daily_monitor.py"))
            await add_task_to_queue(run_subprocess("update_emby_guide.py"))
        else:
            logger.info("有其他任务正在运行，跳过 daily_monitor.py 调度")

async def schedule_ffmpeg_source_checker():
    """定时任务：将 ffmpeg_source_checker.py 放入队列"""
    monitored_scripts = [
        "daily_monitor.py",
        "ffmpeg_source_checker.py",
        "github_search.py",
        "hotel_search.py",
        "domain_batch_query.py",
        "db_setup.py",
        "import_playlists.py"
    ]
    
    while True:
        await asyncio.sleep(FFMPEG_CHECK_FREQUENCY_MINUTES * 60)
        if not await is_process_running(monitored_scripts):
            await add_task_to_queue(run_subprocess("ffmpeg_source_checker.py"))
        else:
            logger.info("有其他任务正在运行，跳过 ffmpeg_source_checker.py 调度")

async def schedule_search_tasks():
    """定期搜索任务：每隔 SEARCH_INTERVAL_HOURS 执行一次 GitHub 和网络搜索"""
    while True:
        await asyncio.sleep(SEARCH_INTERVAL_HOURS * 3600)  # 每 SEARCH_INTERVAL_HOURS 小时执行一次
        logger.info("正在执行定期搜索任务...")
        await add_task_to_queue(run_subprocess("github_search.py"))  # 执行 GitHub 搜索
        await add_task_to_queue(run_subprocess("hotel_search.py"))  # 执行网络空间搜索
        await add_task_to_queue(run_subprocess("domain_batch_query.py"))
        await add_task_to_queue(run_subprocess("import_playlists.py")) 
        await add_task_to_queue(run_subprocess("ffmpeg_source_checker.py"))
        await add_task_to_queue(run_subprocess("daily_monitor.py"))
        await add_task_to_queue(run_subprocess("update_emby_guide.py"))
        
async def run_subprocess(script_name):
    """运行子进程"""
    logger.info(f"Starting {script_name}...")
    try:
        process = await asyncio.create_subprocess_exec("python", script_name)
        await process.wait()
        logger.info(f"Finished {script_name}.")
    except Exception as e:
        logger.error(f"Failed to run {script_name}: {e}")

async def watch_files():
    """监控文件变化，将检测到的任务加入队列"""
    paths_to_watch = ['data/user_uploaded', 'data/filter_conditions.xlsx']
    logger.info(f"启动文件监控: {paths_to_watch}")

    async for changes in awatch(*paths_to_watch):
        logger.info(f"Detected file changes: {changes}")
        await add_task_to_queue(run_subprocess("db_setup.py"))
        await add_task_to_queue(run_subprocess("import_playlists.py"))
        await add_task_to_queue(run_subprocess("ffmpeg_source_checker.py"))
        await add_task_to_queue(run_subprocess("daily_monitor.py"))
        await add_task_to_queue(run_subprocess("update_emby_guide.py"))

async def run_flask_server():
    """启动 Flask 服务器"""
    logger.info("使用 Waitress 启动 Flask 服务器...")
    try:
        process = await asyncio.create_subprocess_exec("waitress-serve", "--host", HOST_IP, "--port", str(PORT), "flask_server:app")
        logger.info(f"Flask server started successfully on {HOST_IP}:{PORT}.")
        return process
    except Exception as e:
        logger.error(f"Error starting Flask server: {e}")
        return None

async def monitor_flask_server(process):
    """监控 Flask 服务器进程，如果进程停止则重启"""
    while True:
        if process and process.returncode is not None:
            logger.error("Flask server has stopped. Restarting...")
            process = await run_flask_server()
        await asyncio.sleep(60)  # 每60秒检查一次

async def clean_failed_sources():
    """清理失败的源"""
    logger.info("正在清理废弃直播源")
    await run_subprocess("clean_failed_sources.py")
    logger.info("Failed sources cleanup completed.")

async def schedule_failed_sources_cleanup():
    """定期清理失效的源"""
    while True:
        await asyncio.sleep(FAILED_SOURCES_CLEANUP_DAYS * 86400)  # 20天执行一次
        await add_task_to_queue(clean_failed_sources())

async def run_initial_tasks():
    """执行初始化任务，并将它们放入队列"""
    logger.info("初始化...")
    await add_task_to_queue(run_subprocess("db_setup.py"))
    await add_task_to_queue(run_subprocess("github_search.py"))
    await add_task_to_queue(run_subprocess("hotel_search.py"))
    await add_task_to_queue(run_subprocess("domain_batch_query.py"))
    await add_task_to_queue(run_subprocess("import_playlists.py"))
    await add_task_to_queue(run_subprocess("ffmpeg_source_checker.py"))
    await add_task_to_queue(run_subprocess("daily_monitor.py"))
    await add_task_to_queue(run_subprocess("update_emby_guide.py"))

async def main():
    # 启动文件监控任务
    asyncio.create_task(watch_files())

    # 启动定时测速任务调度
    asyncio.create_task(schedule_daily_monitor())
    asyncio.create_task(schedule_ffmpeg_source_checker())

    # 启动定期清理失效的源任务
    asyncio.create_task(schedule_failed_sources_cleanup())

    # 启动定期搜索任务
    asyncio.create_task(schedule_search_tasks())

    # 启动 Flask 服务器
    flask_process = await run_flask_server()
    if flask_process:
        asyncio.create_task(monitor_flask_server(flask_process))

    # 创建单个 worker 协程任务
    worker_task = asyncio.create_task(worker())

    # 添加初始化任务到队列
    await run_initial_tasks()

    # 防止脚本退出，等待所有任务运行完成
    await worker_task

if __name__ == "__main__":
    asyncio.run(main())
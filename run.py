import subprocess
import threading
import asyncio
import logging
from flask_server import app, generate_m3u8_file
from scheduler import run_scheduler

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_script(script_name):
    """Helper function to run a Python script."""
    result = subprocess.run(['python', script_name], check=True)
    if result.returncode != 0:
        raise Exception(f"Failed to run {script_name}")

def start_flask():
    generate_m3u8_file()  # 生成 aggregated_channels.m3u8 文件
    app.run(host="0.0.0.0", port=5000)

def start_scheduler():
    run_scheduler()  # 启动调度任务

if __name__ == "__main__":
    try:
        # 步骤1: 运行 db_setup.py 生成数据库和表
        print("Running db_setup.py...")
        run_script('db_setup.py')

        # 步骤2: 运行 github_search.py 搜索并下载直播源
        print("Running github_search.py...")
        run_script('github_search.py')

        # 步骤3: 运行 import_playlists.py 将符合条件的直播源导入数据库
        print("Running import_playlists.py...")
        run_script('import_playlists.py')

        # 步骤4: 运行 source_checker.py 进行直播源检测并生成文件
        print("Running source_checker.py...")
        run_script('source_checker.py')

        # 步骤5: 启动 Flask 服务器和定时任务
        print("Starting Flask server and scheduler...")
        flask_thread = threading.Thread(target=start_flask)
        flask_thread.start()

        scheduler_thread = threading.Thread(target=start_scheduler)
        scheduler_thread.start()

        flask_thread.join()
        scheduler_thread.join()

    except Exception as e:
        print(f"An error occurred: {e}")

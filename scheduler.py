import time
import asyncio
import logging
import json
import os
from source_checker import main as check_sources

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
        
        # 检查环境变量，如果存在，将其分割为列表；如果不存在，保持原样
        codec_exclude_list = os.getenv('CODEC_EXCLUDE_LIST')
        if codec_exclude_list:
            config['source_checker']['codec_exclude_list'] = codec_exclude_list.split(',')
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

async def update_sources():
    while True:
        logging.info("Starting to update sources...")
        try:
            await check_sources()  # 异步调用 source_checker.py 中的检测函数
            logging.info("Finished updating sources.")
        except Exception as e:
            logging.error(f"Failed to update sources: {e}")
        
        logging.info(f"Waiting {config['scheduler']['interval_minutes']} minutes before next check...")
        await asyncio.sleep(config['scheduler']['interval_minutes'] * 60)

def run_scheduler():
    asyncio.run(update_sources())

if __name__ == "__main__":
    run_scheduler()

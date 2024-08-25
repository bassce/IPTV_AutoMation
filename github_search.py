import requests
import os
import json
import logging
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 设置下载目录
OUTPUT_DIR = os.path.join(os.getcwd(), "data", "downloaded_sources")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 读取配置文件
def load_config():
    try:
        with open("config.json", "r", encoding='utf-8') as f:
            config = json.load(f)

        # 动态获取环境变量，并覆盖配置文件中的默认值
        config['github_search']['search_query'] = os.getenv('GITHUB_SEARCH_QUERY', config['github_search']['search_query'])
        config['github_search']['search_days'] = int(os.getenv('GITHUB_SEARCH_DAYS', config['github_search']['search_days']))
        config['github_search']['github_token'] = os.getenv('GITHUB_TOKEN', config['github_search']['github_token'])

        return config
    except FileNotFoundError:
        logging.error("Configuration file 'config.json' not found.")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON configuration: {e}")
        raise

config = load_config()

# 从配置文件中获取参数
search_query = config['github_search']['search_query']
search_days = config['github_search']['search_days']
github_token = config['github_search']['github_token']

def search_github_repos(query, token, days=25):
    search_url = "https://api.github.com/search/repositories"
    days_ago = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    params = {
        "q": f"{query} created:>{days_ago}",
        "sort": "updated",
        "order": "desc"
    }
    headers = {"Authorization": f"token {token}"}
    
    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('items', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to search GitHub repositories: {e}")
        return []

def search_and_download_files(repo, token):
    contents_url = repo['contents_url'].replace('{+path}', '')
    headers = {"Authorization": f"token {token}"}
    
    try:
        response = requests.get(contents_url, headers=headers)
        response.raise_for_status()
        contents = response.json()
        
        for content in contents:
            if content['type'] == 'file' and content['name'].endswith(('.m3u', '.m3u8', '.txt')):
                download_and_save_file(content['download_url'], content['name'], headers)
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to access contents of the repository {repo['name']}: {e}")

def download_and_save_file(file_url, file_name, headers):
    try:
        response = requests.get(file_url, headers=headers)
        response.raise_for_status()
        
        save_path = os.path.join(OUTPUT_DIR, file_name)
        
        with open(save_path, 'wb') as file:
            file.write(response.content)
        
        logging.info(f"Saved {file_name} to {save_path}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download {file_name}: {e}")
    except OSError as e:
        logging.error(f"Failed to save {file_name}: {e}")

def download_sources():
    queries = [q.strip() for q in search_query.split(",")]
    
    for query in queries:
        logging.info(f"Searching GitHub repositories for query: {query}")
        repos = search_github_repos(query, github_token, search_days)
        if repos:
            for repo in repos:
                search_and_download_files(repo, github_token)
        else:
            logging.info(f"No repositories found for query: {query}")

if __name__ == "__main__":
    download_sources()

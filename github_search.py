import requests
import os
import json
import logging
from datetime import datetime, timedelta
import shutil
from dateutil import parser
from logging_config import logger

# 设置文件大小阈值 (3MB)
FILE_SIZE_THRESHOLD = 3 * 1024 * 1024  # 3MB

# 日志信息
logger.info("开始执行 GitHub 搜索任务")

# 设置下载目录
OUTPUT_DIR = os.path.join(os.getcwd(), "data", "downloaded_sources")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 读取配置文件
def load_config():
    try:
        with open("config.json", "r", encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Configuration file 'config.json' not found.")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON configuration: {e}")
        raise

config = load_config()

# 优先从环境变量读取参数，如果不存在则使用配置文件中的值
search_query = os.getenv('GITHUB_SEARCH_QUERY', config['github_search']['search_query'])
search_days = int(os.getenv('GITHUB_SEARCH_DAYS', config['github_search']['search_days']))
github_token = os.getenv('GITHUB_TOKEN', config['github_search']['github_token'])

# 调整后的 GitHub 仓库搜索函数，确保正确传递 search_days 参数
def search_github_repos(query, token, days):
    search_url = "https://api.github.com/search/repositories"
    days_ago = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    params = {
        "q": f"{query} pushed:>{days_ago}",
        "sort": "updated",
        "order": "desc"
    }
    headers = {"Authorization": f"token {token}"}
    
    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('items', []), days_ago
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to search GitHub repositories: {e}")
        return [], days_ago

# 使用 commits API 获取文件的最后修改日期
def get_file_last_modified(repo, file_path, token):
    commits_url = f"https://api.github.com/repos/{repo['owner']['login']}/{repo['name']}/commits"
    params = {"path": file_path}
    headers = {"Authorization": f"token {token}"}
    
    try:
        response = requests.get(commits_url, headers=headers, params=params)
        response.raise_for_status()
        commits = response.json()
        
        if commits:
            # 获取最近一次提交的日期
            last_commit = commits[0]
            last_modified_str = last_commit['commit']['committer']['date']
            last_modified = parser.isoparse(last_modified_str)
            logging.info(f"GitHub 返回的文件 {file_path} 的最后修改日期: {last_modified}")
            return last_modified
        else:
            logging.warning(f"No commits found for {file_path}")
            return datetime.now()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get file commits info: {e}")
        return datetime.now()

# 检查文件大小
def get_file_size(file_url, headers):
    try:
        # 通过 HEAD 请求获取文件的大小
        response = requests.head(file_url, headers=headers)
        response.raise_for_status()
        
        file_size = int(response.headers.get('Content-Length', 0))
        logging.info(f"获取文件大小: {file_url} | 大小: {file_size} 字节")
        
        return file_size
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get file size for {file_url}: {e}")
        return 0  # 返回 0 表示文件大小未知

# 下载并保存文件，并设置文件的最后修改日期
def download_and_save_file(file_url, file_name, headers, last_modified):
    try:
        response = requests.get(file_url, headers=headers)
        response.raise_for_status()

        save_path = os.path.join(OUTPUT_DIR, file_name)
        
        with open(save_path, 'wb') as file:
            file.write(response.content)
        
        # 获取下载后的本地文件大小
        local_file_size = os.path.getsize(save_path)

        # 检查文件大小是否超过阈值
        if local_file_size > FILE_SIZE_THRESHOLD:
            logging.info(f"文件 {file_name} 本地大小为 {local_file_size} 字节，超过阈值 {FILE_SIZE_THRESHOLD} 字节，删除文件")
            os.remove(save_path)  # 删除超过阈值的文件
            return
        
        # 修改文件的创建和修改日期
        os.utime(save_path, (last_modified.timestamp(), last_modified.timestamp()))
        
        logging.info(f"Saved {file_name} with last modified date {last_modified} to {save_path}, 本地文件大小: {local_file_size} 字节")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download {file_name}: {e}")
    except OSError as e:
        logging.error(f"Failed to save {file_name}: {e}")

# 查找并下载仓库中的文件，过滤修改日期在 search_days 内的文件
def search_and_download_files(repo, token, days_ago):
    contents_url = repo['contents_url'].replace('{+path}', '')
    headers = {"Authorization": f"token {token}"}
    
    try:
        response = requests.get(contents_url, headers=headers)
        response.raise_for_status()
        contents = response.json()
        
        # 将 days_ago 转换为系统本地时间
        cutoff_date = datetime.strptime(days_ago, '%Y-%m-%d')
        
        for content in contents:
            if content['type'] == 'file' and content['name'].endswith(('.m3u', '.m3u8', '.txt')):
                # 获取文件最后修改日期
                last_modified = get_file_last_modified(repo, content['path'], token)
                
                # 将 last_modified 转换为不带时区的时间
                last_modified_naive = last_modified.replace(tzinfo=None)
                
                # 只下载最后修改日期在 search_days 天内的文件
                if last_modified_naive >= cutoff_date:
                    download_and_save_file(content['download_url'], content['name'], headers, last_modified)
                else:
                    logging.info(f"文件 {content['name']} 的最后修改日期早于 {days_ago}，跳过下载")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to access contents of the repository {repo['name']}: {e}")

# 查询 GitHub 速率限制信息
def log_rate_limit(token):
    rate_limit_url = "https://api.github.com/rate_limit"
    headers = {"Authorization": f"token {token}"}
    
    try:
        response = requests.get(rate_limit_url, headers=headers)
        response.raise_for_status()
        rate_limit_info = response.json()
        
        core_info = rate_limit_info['resources']['core']
        limit = core_info['limit']
        remaining = core_info['remaining']
        reset_time = datetime.fromtimestamp(core_info['reset']).strftime('%Y-%m-%d %H:%M:%S')

        logging.info(f"GitHub API 速率限制: 每小时可用请求次数={limit}, 剩余可用次数={remaining}, 重置时间={reset_time}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get rate limit info: {e}")

# 清空 downloaded_sources 文件夹
def clear_downloaded_sources():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)  # 删除文件夹及其内容
        os.makedirs(OUTPUT_DIR)  # 重新创建空文件夹
        logging.info(f"Cleared contents of {OUTPUT_DIR}")
    else:
        os.makedirs(OUTPUT_DIR)  # 如果文件夹不存在，创建它

# 下载源文件的主函数
def download_sources():
    # 在开始下载前清空文件夹
    clear_downloaded_sources()

    queries = [q.strip() for q in search_query.split(",")]
    
    for query in queries:
        logging.info(f"搜索关键字: {query}")
        repos, days_ago = search_github_repos(query, github_token, search_days)
        if repos:
            for repo in repos:
                search_and_download_files(repo, github_token, days_ago)
        else:
            logging.info(f"No repositories found for query: {query}")
    
    # 查询并记录 GitHub API 的速率限制信息
    log_rate_limit(github_token)

if __name__ == "__main__":
    download_sources()

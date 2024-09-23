import time
import base64
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import re
import json
import os
import sqlite3
import chardet
from logging_config import logger  # 引入日志配置

logger.info("开始执行 hotel搜索 任务")

# 从 config.json 读取参数
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

config = load_config()

# 优先读取环境变量，如果没有则使用 config.json 中的值
SUBDIVISIONS = os.getenv('SUBDIVISION', config["search_params"]["subdivision"]).split(",")
KEYWORDS = os.getenv('KEYWORDS', config["search_params"]["keywords"])

# 设置保存路径为项目根目录下的 /data/hotel_search
output_dir = 'data/hotel_search'
os.makedirs(output_dir, exist_ok=True)

# 设置 SQLite 数据库路径
db_path = 'data/iptv_sources.db'

# 初始化 SQLite 数据库连接
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 创建或重置 hotel_search_url 表
def setup_hotel_search_url_table():
    cursor.execute('''CREATE TABLE IF NOT EXISTS hotel_search_url (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT,
                        url TEXT UNIQUE,  -- 添加 UNIQUE 约束
                        source TEXT
                    )''')
    conn.commit()

setup_hotel_search_url_table()

# 设置浏览器选项
chrome_options = Options()
chrome_options.add_argument('--headless')  # 无头浏览器模式
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--incognito')

# 封装关闭浏览器函数
def close_driver(driver):
    try:
        driver.quit()  # 关闭浏览器
        driver.service.stop()  # 停止 chromedriver 服务
    except Exception as e:
        logger.error(f"Error closing Chrome and Chromedriver: {e}")

def search_fofa(keyword, subdivision):
    """通过 FOFA 进行搜索并返回页面内容"""
    query = f'"{keyword}" && country="CN" && region="{subdivision}"'
    query_base64 = base64.b64encode(query.encode('utf-8')).decode('utf-8')
    fofa_base_url = f"https://fofa.info/result?qbase64={query_base64}"
    driver.get(fofa_base_url)
    time.sleep(6)  # 等待页面加载
    page_content = driver.page_source
    logger.info(f"FOFA search results for {keyword} in {subdivision} loaded.")
    return page_content

def search_zoomeye(keyword, subdivision):
    """通过 ZoomEye 进行搜索并返回页面内容"""
    zoomeye_base_url = f'https://www.zoomeye.org/searchResult?q=%2F{keyword}%20%2Bcountry%3A%22CN%22%20%2Bsubdivisions%3A%22{subdivision}%22'
    driver.get(zoomeye_base_url)
    time.sleep(6)  # 等待页面加载
    page_content = driver.page_source
    logger.info(f"ZoomEye search results for {keyword} in {subdivision} loaded.")
    return page_content

def extract_urls(page_content):
    """从页面内容中提取 IPTV 相关的 URL"""
    pattern = r"http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"  # 匹配 IP 地址和端口的 URL
    urls = re.findall(pattern, page_content)
    unique_urls = list(set(urls))  # 去重
    return unique_urls

def detect_encoding(content):
    """检测内容的编码格式"""
    result = chardet.detect(content)
    encoding = result.get('encoding', 'utf-8')
    return encoding

def process_zhgxtv(url):
    """处理 'ZHGXTV' 关键字搜索出来的 URL 并读取文件"""
    json_url = f"{url}/ZHGXTV/Public/json/live_interface.txt"
    try:
        response = requests.get(json_url, timeout=10)
        encoding = detect_encoding(response.content)
        content = response.content.decode(encoding)
        processed_urls = []
        base_url = url.rstrip("/")  # 确保 base_url 以正确格式结尾

        for line in content.splitlines():
            if ',' in line:
                name, stream_url = line.split(',')
                
                # 如果 URL 没有 http:// 或 https://，则添加 base_url
                if not stream_url.startswith("http://") and not stream_url.startswith("https://"):
                    stream_url = f"{base_url}{stream_url}"
                else:
                    # 将已有的 http:// 或 https:// 的 IP:Port 部分替换为 base_url
                    stream_url = re.sub(r"https?://[\d\.]+(:\d+)?", base_url, stream_url)

                # 将处理后的结果加入列表
                processed_urls.append(f"{name},{stream_url}")

        return processed_urls
    except (requests.exceptions.RequestException, UnicodeDecodeError) as e:
        logger.error(f"Request failed for {json_url}: {e}")
        return None

def process_iptv_live(url):
    """处理 'iptv/live/zh_cn.js' 关键字搜索出来的 URL 并提取 JSON 中的信息"""
    json_url = f"{url}/iptv/live/1000.json?key=txiptv"
    try:
        response = requests.get(json_url, timeout=10)
        json_data = response.json()
        processed_urls = []
        base_url = url.rstrip("/")  # 确保 base_url 以正确格式结尾
        if "data" in json_data:
            for item in json_data["data"]:
                typename = item.get("typename", "")
                name = item.get("name", "")
                stream_url = item.get("url", "")

                # 处理无前缀的 URL
                if not stream_url.startswith("http://") and not stream_url.startswith("https://"):
                    stream_url = f"{base_url}{stream_url}"
                else:
                    # 替换已有的 http:// 或 https:// 的 IP:Port 部分为 base_url
                    stream_url = re.sub(r"https?://[\d\.]+(:\d+)?", base_url, stream_url)

                # 保存为 M3U8 格式
                if typename and name and stream_url:
                    processed_urls.append(f"{name},{stream_url}")
        return processed_urls
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        logger.error(f"Request failed for {json_url}: {e}")
        return None

def insert_url_to_db(keyword, url, source):
    """将搜索结果插入到数据库的 hotel_search_url 表中，忽略重复 URL"""
    try:
        cursor.execute("INSERT OR IGNORE INTO hotel_search_url (keyword, url, source) VALUES (?, ?, ?)", (keyword, url, source))
        conn.commit()
    except sqlite3.IntegrityError:
        logger.warning(f"URL already exists in the database: {url}")

# 覆盖 ZHGXTV.m3u 和 KUTV.m3u 文件
with open(os.path.join(output_dir, "ZHGXTV.m3u"), "w", encoding='utf-8') as m3u:
    m3u.write("") 

with open(os.path.join(output_dir, "KUTV.m3u"), "w", encoding='utf-8') as m3u:
    m3u.write("") 

try:    
    # 初始化 WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    
    # 遍历每个地区和关键词执行搜索和处理
    for subdivision in SUBDIVISIONS:
        for keyword in KEYWORDS:
            logger.info(f"Processing keyword: {keyword} in {subdivision}")
            
            # 搜索 FOFA 并提取 URL
            fofa_content = search_fofa(keyword, subdivision)
            fofa_urls = extract_urls(fofa_content)
            logger.info(f"Fofa URLs for {keyword} in {subdivision}: {fofa_urls}")

            # 搜索 ZoomEye 并提取 URL
            zoomeye_content = search_zoomeye(keyword, subdivision)
            zoomeye_urls = extract_urls(zoomeye_content)
            logger.info(f"ZoomEye URLs for {keyword} in {subdivision}: {zoomeye_urls}")

            # 合并所有找到的 URL
            all_urls = set(fofa_urls + zoomeye_urls)  # 去重合并

            # 保存所有搜索结果到数据库
            for url in all_urls:
                source = "FOFA" if url in fofa_urls else "ZoomEye"
                insert_url_to_db(keyword, url, source)

            # 如果关键字是 "iptv/live/zh_cn.js"，处理并保存为 KUTV.m3u 格式
            if keyword == "iptv/live/zh_cn.js":
                with open(os.path.join(output_dir, "KUTV.m3u"), "a", encoding='utf-8') as m3u:
                    for url in all_urls:
                        processed_data = process_iptv_live(url)
                        if processed_data:
                            for line in processed_data:
                                m3u.write(line + "\n")
            
            # 如果关键字是 "ZHGXTV"，处理并保存为 ZHGXTV.m3u 格式
            if keyword == "ZHGXTV":
                with open(os.path.join(output_dir, "ZHGXTV.m3u"), "a", encoding='utf-8') as m3u:
                    for url in all_urls:
                        processed_data = process_zhgxtv(url)
                        if processed_data:
                            for line in processed_data:
                                m3u.write(line + "\n")

finally:
    # 无论是否发生异常，都会执行关闭操作
    close_driver(driver)  # 确保 driver 被正确关闭
    conn.close()
    logger.info("All searches and processing completed.")

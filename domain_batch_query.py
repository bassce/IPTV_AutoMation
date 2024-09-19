import sqlite3
import re
import requests
from bs4 import BeautifulSoup
from logging_config import logger  # 引入日志配置
import os

logger.info("开始执行 域名批量查询和替换任务")

# 定义从IP138查询IP对应域名的函数
def get_domains_for_ip(ip_address):
    url = f"https://site.ip138.com/{ip_address}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    domain_list = []

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        result_section = soup.find('ul', id='list')
        if result_section:
            for li in result_section.find_all('li'):
                domain_link = li.find('a')
                if domain_link:
                    domain = domain_link.get_text().strip()
                    domain_list.append(domain)

        return domain_list

    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {e}")
        return domain_list

# 从URL中提取IP地址
def extract_ip_from_url(url):
    match = re.match(r'http://([0-9\.]+):?[0-9]*', url)
    if match:
        return match.group(1)
    return None

# 创建新的域名结果表
def create_domain_results_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS domain_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,  -- 确保URL唯一
            domains TEXT  -- 以逗号分隔的域名列表
        )
    ''')

# 将对应IP的直播源移动到 domain.m3u，并替换为域名
def move_and_replace_ip_in_m3u(m3u_files, ip_to_domain_map, domain_m3u_path):
    with open(domain_m3u_path, 'a', encoding='utf-8') as domain_m3u:  # 'a' 以追加方式打开文件
        for file in m3u_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                updated_lines = []
                for line in lines:
                    if any(ip in line for ip in ip_to_domain_map.keys()):
                        # 查找IP并替换为域名
                        for ip, domain in ip_to_domain_map.items():
                            line = re.sub(rf'http://{ip}(:\d+)?', f'http://{domain}', line)
                        # 将匹配的行移动到 domain.m3u
                        domain_m3u.write(line)
                    else:
                        updated_lines.append(line)

                # 保存更新后的文件
                with open(file, 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)

                logger.info(f"文件 {file} 中匹配的IP已移动到 {domain_m3u_path} 并替换为域名")
            except Exception as e:
                logger.error(f"处理文件 {file} 失败: {e}")

# 处理数据库中的URLs
def process_urls():
    db_file = os.path.join('data', 'iptv_sources.db')  # 定义数据库路径
    hotel_search_folder = os.path.join('data', 'hotel_search')  # 文件夹路径
    m3u_files = [os.path.join(hotel_search_folder, 'ZHGXTV.m3u'), os.path.join(hotel_search_folder, 'KUTV.m3u')]
    domain_m3u_path = os.path.join(hotel_search_folder, 'domain.m3u')

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 创建新的 domain_results 表
        create_domain_results_table(cursor)

        # 读取hotel_search_url表中的所有URL
        cursor.execute("SELECT id, url FROM hotel_search_url")
        rows = cursor.fetchall()

        ip_to_domain_map = {}

        for row in rows:
            url_id, url = row
            ip_address = extract_ip_from_url(url)

            if ip_address:
                logger.info(f"正在查询IP地址 {ip_address} 对应的域名...")
                domain_list = get_domains_for_ip(ip_address)

                if domain_list:
                    # 检查是否已有相同的URL
                    cursor.execute("SELECT id FROM domain_results WHERE url = ?", (url,))
                    result = cursor.fetchone()

                    if result:
                        # 更新记录
                        cursor.execute("UPDATE domain_results SET ip_address = ?, domains = ? WHERE url = ?",
                                       (ip_address, ', '.join(domain_list), url))
                        # 删除 ZHGXTV.m3u 和 KUTV.m3u 中的直播源
                        move_and_replace_ip_in_m3u(m3u_files, {ip_address: domain_list[0]}, domain_m3u_path)
                        logger.info(f"更新了URL {url} 对应的域名为 {domain_list[0]}")
                    else:
                        # 插入新记录
                        cursor.execute("INSERT INTO domain_results (ip_address, url, domains) VALUES (?, ?, ?)",
                                       (ip_address, url, ', '.join(domain_list)))
                        move_and_replace_ip_in_m3u(m3u_files, {ip_address: domain_list[0]}, domain_m3u_path)
                        logger.info(f"插入了新URL {url} 和对应域名 {domain_list[0]}")

                    conn.commit()

                else:
                    logger.warning(f"没有找到IP地址 {ip_address} 的域名")

    except sqlite3.Error as e:
        logger.error(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    process_urls()

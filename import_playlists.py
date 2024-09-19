import os
import re
import sqlite3
import glob
import concurrent.futures
from difflib import SequenceMatcher
from logging_config import logger  # 引入日志配置

logger.info("开始执行 直播源导入 任务")

def extract_text(line):
    """提取#EXTINF标签中的频道名称"""
    tvg_name_match = re.search(r'tvg-name="([^"]+)"', line)
    group_title_match = re.search(r'group-title="([^"]+)"', line)
    title_match = re.search(r',\s*([^,]+)$', line)

    tvg_name = tvg_name_match.group(1).strip() if tvg_name_match else None
    group_title = group_title_match.group(1).strip() if group_title_match else None
    title = title_match.group(1).strip() if title_match else tvg_name  # 优先使用提取的 title，如果没有则使用 tvg_name

    logger.debug(f"Extracted values: tvg_name={tvg_name}, group_title={group_title}, title={title}")

    return tvg_name, group_title, title

def similarity(a, b):
    """计算两个字符串的相似度"""
    return SequenceMatcher(None, a, b).ratio()

def normalize_text(text):
    """规范化文本，移除特殊字符如 '-', ' ' 等"""
    if text:
        return re.sub(r'[-\s]', '', text.strip())
    return text

def match_tvg_name(text, sources):
    """增强匹配，首先尝试完整匹配，然后进行相似度比较"""
    text = normalize_text(text)  # 对输入的频道名称进行规范化
    potential_matches = []

    # 逐字匹配，记录所有可能的匹配
    for tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor in sources:
        normalized_tvg_name = normalize_text(tvg_name)  # 对数据库中的频道名称进行规范化
        if normalized_tvg_name and normalized_tvg_name in text:
            potential_matches.append((tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor))

    # 如果有多个可能的匹配，进一步计算相似度
    if len(potential_matches) > 1:
        best_match = max(potential_matches, key=lambda x: similarity(normalize_text(x[1]), text))
        return best_match

    # 如果只有一个匹配，直接返回
    if potential_matches:
        return potential_matches[0]

    # 如果没有找到匹配，返回None
    return None

def reset_scores_if_table_exists(cursor):
    """如果 filtered_playlists 表存在，清零评分"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='filtered_playlists'")
    table_exists = cursor.fetchone() is not None

    if table_exists:
        logger.info("Table filtered_playlists exists. Resetting scores...")
        cursor.execute('UPDATE filtered_playlists SET score = 0')
        logger.info("Scores reset successfully.")
    else:
        logger.info("Table filtered_playlists does not exist. Skipping score reset.")

def process_file(file, sources, failed_sources_set):
    """处理单个文件并返回处理结果"""
    try:
        with open(file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_tvg_info = None
        title = None
        results = []

        for line in lines:
            line = line.strip()

            # 检查是否是#EXTINF开头的行
            if line.startswith("#EXTINF"):
                tvg_name, group_title, title = extract_text(line)
                if tvg_name or title:
                    current_tvg_info = match_tvg_name(tvg_name or title, sources)

            # 处理没有#EXTINF标签，直接为“频道名称,URL”的行
            elif ',' in line:
                parts = line.split(',', 1)
                title = parts[0].strip()
                url = parts[1].strip()
                current_tvg_info = match_tvg_name(title, sources)
                if current_tvg_info and (title, url) not in failed_sources_set:
                    tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor = current_tvg_info
                    results.append((tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url))

            # 处理URL行
            elif current_tvg_info and line and not line.startswith("#"):
                if (title, line) not in failed_sources_set:
                    tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor = current_tvg_info
                    results.append((tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, line))

        return results

    except Exception as e:
        logger.error(f"Error processing file {file}: {e}")
        return []

def import_playlists():
    db_file = os.path.join('data', 'iptv_sources.db')
    playlists_folders = [os.path.join('data', 'downloaded_sources'), os.path.join('data', 'user_uploaded'), os.path.join('data', 'hotel_search')]

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 检查 failed_sources 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='failed_sources'")
        failed_sources_exists = cursor.fetchone() is not None

        # 获取 failed_sources 中的所有 name 和 url 组合
        failed_sources_set = set()
        if failed_sources_exists:
            cursor.execute('SELECT title, url FROM failed_sources')
            failed_sources_set = set(cursor.fetchall())

        # 重置评分，如果 filtered_playlists 表存在
        reset_scores_if_table_exists(cursor)

        # 创建元数据表，如果不存在则创建
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS table_metadata (
            table_name TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 创建新的表结构，添加 failure_count 和 last_failed_date 列
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS iptv_playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tvg_id TEXT,
            tvg_name TEXT,
            group_title TEXT,
            aliasesname TEXT,
            tvordero INTEGER,
            tvg_logor TEXT,
            title TEXT,
            url TEXT,
            latency INTEGER,
            resolution TEXT,
            format TEXT,
            failure_count INTEGER DEFAULT 0,
            last_failed_date TIMESTAMP DEFAULT 0,
            UNIQUE(url)
        )
        ''')

        # 插入或更新表的创建时间到元数据表中
        cursor.execute('''
        INSERT OR REPLACE INTO table_metadata (table_name, created_at)
        VALUES ('iptv_playlists', datetime('now', 'localtime'))
        ''')

        # 获取所有的TV源数据
        cursor.execute('SELECT tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor FROM iptv_sources')
        sources = cursor.fetchall()

        all_results = []  # 用于存储所有文件的处理结果

        # 使用 ThreadPoolExecutor 并行处理文件
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for folder in playlists_folders:
                files = glob.glob(os.path.join(folder, '*.*'))
                for file in files:
                    if file.lower().endswith(('.m3u', '.m3u8', '.txt')):
                        futures.append(executor.submit(process_file, file, sources, failed_sources_set))

            # 收集每个线程的返回结果
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())

        # 批量插入数据库
        cursor.executemany('''
            INSERT OR IGNORE INTO iptv_playlists (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url, failure_count, last_failed_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        ''', all_results)

        # 提交更改
        conn.commit()
        logger.info(f"所有直播源节目单已成功导入到数据库中，插入了 {len(all_results)} 条记录。")
    except sqlite3.Error as e:
        logger.error(f"数据库错误: {e}")
    except Exception as e:
        logger.error(f"发生错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import_playlists()

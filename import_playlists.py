import os
import re
import sqlite3
import glob
from difflib import SequenceMatcher
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_text(line):
    """提取#EXTINF标签中的频道名称"""
    match = re.search(r',(.*)', line)
    return match.group(1).strip() if match else None

def similarity(a, b):
    """计算两个字符串的相似度"""
    return SequenceMatcher(None, a, b).ratio()

def match_tvg_name(text, sources):
    """增强匹配，首先尝试完整匹配，然后进行相似度比较"""
    potential_matches = []
    
    # 逐字匹配，记录所有可能的匹配
    for tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor in sources:
        if tvg_name in text:
            potential_matches.append((tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor))

    # 如果有多个可能的匹配，进一步计算相似度
    if len(potential_matches) > 1:
        best_match = max(potential_matches, key=lambda x: similarity(x[1], text))
        return best_match

    # 如果只有一个匹配，直接返回
    if potential_matches:
        return potential_matches[0]

    # 如果没有找到匹配，返回None
    return None

def import_playlists():
    # 定义数据库文件路径
    db_file = os.path.join('data', 'iptv_sources.db')
    playlists_folder = os.path.join('data', 'downloaded_sources')

    # 连接到SQLite数据库
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 清空旧数据
        cursor.execute('DROP TABLE IF EXISTS iptv_playlists')

        # 创建新的表结构
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
            latency TEXT,
            resolution TEXT,
            format TEXT,
            UNIQUE(url)  -- 添加唯一约束，防止重复
        )
        ''')

        # 获取所有的TV源数据
        cursor.execute('SELECT tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor FROM iptv_sources')
        sources = cursor.fetchall()

        # 读取所有M3U、M3U8或TXT文件
        for file in glob.glob(os.path.join(playlists_folder, '*.*')):
            if file.lower().endswith(('.m3u', '.m3u8', '.txt')):
                with open(file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                title = None
                current_tvg_info = None

                for line in lines:
                    line = line.strip()

                    if line.startswith("#EXTINF"):
                        title = extract_text(line)
                        current_tvg_info = match_tvg_name(line, sources)
                    
                    elif "," in line and "http" in line:
                        # 支持 `频道名称,URL` 这种形式的解析
                        title, url = line.split(",", 1)
                        title = title.strip()
                        url = url.strip()
                        current_tvg_info = match_tvg_name(title, sources)
                        if current_tvg_info:
                            tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor = current_tvg_info
                            cursor.execute('''
                            INSERT OR IGNORE INTO iptv_playlists (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url))

                    elif line and not line.startswith("#"):
                        # 处理URL行
                        if current_tvg_info:
                            tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor = current_tvg_info
                            cursor.execute('''
                            INSERT OR IGNORE INTO iptv_playlists (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (tvg_id, tvg_name, group_title, aliasesname, tvordero, tvg_logor, title, line))

        # 提交更改
        conn.commit()
        logging.info("所有直播源节目单已成功导入到数据库中。")
    except sqlite3.Error as e:
        logging.error(f"数据库错误: {e}")
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        # 确保关闭连接
        if conn:
            conn.close()

if __name__ == "__main__":
    import_playlists()

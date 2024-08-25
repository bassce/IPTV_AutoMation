import pandas as pd
import sqlite3
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义文件路径
excel_file = os.path.join('data', 'filter_conditions.xlsx')
db_file = os.path.join('data', 'iptv_sources.db')

try:
    # 检查 Excel 文件是否存在
    if not os.path.exists(excel_file):
        logging.error(f"Excel file not found: {excel_file}")
        raise FileNotFoundError(f"Excel file not found: {excel_file}")

    # 读取Excel文件
    df = pd.read_excel(excel_file)
    
    # 检查数据是否为空
    if df.empty:
        logging.error(f"Excel file {excel_file} is empty.")
        raise ValueError(f"Excel file {excel_file} is empty.")
    
    # 连接SQLite数据库（如果数据库不存在则会创建）
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 如果表存在，删除旧表
    cursor.execute('DROP TABLE IF EXISTS iptv_sources')

    # 创建表结构
    cursor.execute('''
    CREATE TABLE iptv_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvg_id TEXT,
        tvg_name TEXT NOT NULL,
        group_title TEXT,
        aliasesname TEXT,
        tvordero INTEGER,
        tvg_logor TEXT
    )
    ''')

    # 将DataFrame中的数据插入到SQLite表中
    df.to_sql('iptv_sources', conn, if_exists='replace', index=False)

    # 提交更改并关闭连接
    conn.commit()
    logging.info(f"Data from {excel_file} has been successfully imported into {db_file}.")
    
except (FileNotFoundError, ValueError) as e:
    logging.error(f"Error: {e}")
except Exception as e:
    logging.error(f"Unexpected error: {e}")
finally:
    if 'conn' in locals():
        conn.close()

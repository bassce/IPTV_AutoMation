import pandas as pd
import sqlite3
import os
from logging_config import logger  # 使用外部的日志配置

logger.info("开始执行 频道名称导入 任务")

# 定义文件路径
excel_file = os.path.join('data', 'filter_conditions.xlsx')
db_file = os.path.join('data', 'iptv_sources.db')

def import_excel_to_db(excel_file, db_file):
    try:
        # 检查 Excel 文件是否存在
        if not os.path.exists(excel_file):
            logger.error(f"Excel file not found: {excel_file}")
            raise FileNotFoundError(f"Excel file not found: {excel_file}")

        # 读取Excel文件
        df = pd.read_excel(excel_file)

        # 检查数据是否为空
        if df.empty:
            logger.error(f"Excel file {excel_file} is empty.")
            raise ValueError(f"Excel file {excel_file} is empty.")

        # 连接SQLite数据库（如果数据库不存在则会创建）
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 创建元数据表，如果不存在则创建
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS table_metadata (
            table_name TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

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

        # 插入或更新表的创建时间到元数据表中
        cursor.execute('''
        INSERT OR REPLACE INTO table_metadata (table_name, created_at)
        VALUES ('iptv_sources', datetime('now', 'localtime'))
        ''')

        # 提交更改并关闭连接
        conn.commit()
        logger.info(f"Data from {excel_file} has been successfully imported into {db_file}.")

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    import_excel_to_db(excel_file, db_file)

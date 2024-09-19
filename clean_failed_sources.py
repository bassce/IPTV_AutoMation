import sqlite3
from logging_config import logger  # 引入日志配置

logger.info("开始执行 废弃直播源清理 任务")

# 连接数据库
db_path = 'data/iptv_sources.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def clean_failed_sources():
    """删除并重新创建 failed_sources 表"""
    logger.info("Dropping and recreating failed_sources table...")

    # 删除 failed_sources 表
    cursor.execute('DROP TABLE IF EXISTS failed_sources')

    # 重新创建 failed_sources 表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS failed_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvg_id TEXT,
        tvg_name TEXT,
        group_title TEXT,
        aliasesname TEXT,
        tvordero INTEGER,
        tvg_logor TEXT,
        title TEXT,
        url TEXT,
        failure_count INTEGER,
        last_failed_date TIMESTAMP
    )
    ''')

    # 更新表的创建时间元数据
    cursor.execute('''
    INSERT OR REPLACE INTO table_metadata (table_name, created_at)
    VALUES ('failed_sources', datetime('now', 'localtime'))
    ''')

    # 提交更改
    conn.commit()
    logger.info("Failed sources table has been recreated successfully.")

if __name__ == "__main__":
    clean_failed_sources()
    conn.close()

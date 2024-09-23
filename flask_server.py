from waitress import serve
from flask import Flask, redirect, send_file
import pandas as pd
import os
import sqlite3
import json
from logging_config import logger  # 使用项目中的日志配置

logger.info("启动 flask服务器")

app = Flask(__name__)

# 加载配置文件
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
    except Exception as e:
        logger.error(f"Unexpected error loading config.json: {e}")
        raise

config = load_config()
HOST_IP = os.getenv('HOST_IP', config["network"]["host_ip"])  # 读取 host_ip 配置
PORT = int(os.getenv('PORT', int(config["network"]["port"])))

def get_channel_sources(aliasesname):
    try:
        conn = sqlite3.connect("data/filtered_sources_readonly.db")
        query = """
        SELECT * FROM filtered_playlists_readonly
        WHERE aliasesname = ?
        AND download_speed > 0
        AND latency IS NOT NULL
        ORDER BY score DESC  -- 根据评分机制选择直播源
        """
        df = pd.read_sql_query(query, conn, params=(aliasesname,))
        
        if not df.empty:
            return df
        else:
            logger.warning(f"No valid sources found for {aliasesname}")
            return None
    except Exception as e:
        logger.error(f"Failed to get channel sources for {aliasesname}: {e}")
        return None
    finally:
        conn.close()

@app.route('/<aliasesname>')
def redirect_channel(aliasesname):
    sources = get_channel_sources(aliasesname)
    if sources is not None:
        for _, source in sources.iterrows():
            try:
                url = source['url']
                logger.info(f"Attempting to redirect {aliasesname} to {url}")
                return redirect(url)
            except Exception as e:
                logger.warning(f"Failed to redirect {aliasesname} to {url}: {e}")
                continue  # 如果无法播放，继续尝试下一个源
        logger.error(f"All sources for {aliasesname} failed.")
        return "All sources failed", 500
    else:
        logger.warning(f"Channel not found: {aliasesname}")
        return "Channel not found", 404

@app.route('/aggregated_channels.m3u8')
def serve_m3u8():
    try:
        m3u8_path = 'data/aggregated_channels.m3u8'
        if os.path.exists(m3u8_path):
            logger.info("Serving aggregated_channels.m3u8 file")
            return send_file(m3u8_path)
        else:
            logger.error(f"M3U8 file not found: {m3u8_path}")
            return "M3U8 file not found", 404
    except Exception as e:
        logger.error(f"Error serving M3U8 file: {e}")
        return "Internal server error", 500

if __name__ == "__main__": 
    try:
        # 使用 Waitress 启动 Flask 服务器，host 设置为 HOST_IP
        logger.info("Starting Flask server with Waitress...")
        serve(app, host=HOST_IP, port=PORT, threads=2)  # 可根据需求调整 threads 参数
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}")

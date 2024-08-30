from flask import Flask, redirect, send_file
import pandas as pd
import os
import logging
import socket
import sqlite3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

def get_channel_sources(aliasesname):
    try:
        conn = sqlite3.connect("data/iptv_sources.db")
        query = """
        SELECT * FROM filtered_playlists
        WHERE aliasesname = ?
        AND download_speed > 0
        AND latency IS NOT NULL
        ORDER BY download_speed DESC
        """
        df = pd.read_sql_query(query, conn, params=(aliasesname,))
        
        if not df.empty:
            return df
        else:
            logging.warning(f"No valid sources found for {aliasesname}")
            return None
    except Exception as e:
        logging.error(f"Failed to get channel sources for {aliasesname}: {e}")
        return None
    finally:
        conn.close()

@app.route('/<aliasesname>')
def redirect_channel(aliasesname):
    sources = get_channel_sources(aliasesname)
    if sources is not None:
        for _, source in sources.iterrows():
            try:
                # 尝试重定向到每个源
                url = source['url']
                logging.info(f"Redirecting {aliasesname} to {url}")
                return redirect(url)
            except Exception as e:
                # 如果重定向失败，尝试下一个源
                logging.warning(f"Failed to redirect {aliasesname} to {url}: {e}")
                continue
        logging.error(f"All sources for {aliasesname} failed.")
        return "All sources failed", 500
    else:
        logging.warning(f"Channel not found: {aliasesname}")
        return "Channel not found", 404

def generate_m3u8_file():
    try:
        conn = sqlite3.connect("data/iptv_sources.db")
        df = pd.read_sql_query("""
        SELECT * FROM filtered_playlists
        WHERE download_speed > 0
        AND latency IS NOT NULL
        ORDER BY tvordero ASC
        """, conn)

        m3u8_path = 'data/aggregated_channels.m3u8'

        with open(m3u8_path, 'w', encoding='utf-8') as m3u8_file:
            m3u8_file.write("#EXTM3U\n")
            unique_channels = set()

            for _, row in df.iterrows():
                aliasesname = row['aliasesname']
                if aliasesname not in unique_channels:
                    m3u8_file.write(f"#EXTINF:-1 tvg-name=\"{row['tvg_name']}\" group-title=\"{row['group_title']}\",{row['title']}\n")
                    m3u8_file.write(f"http://{get_host_ip()}:5000/{row['aliasesname']}\n")
                    unique_channels.add(aliasesname)
                    logging.info(f"Added channel to M3U8: {row['title']} with URL path /{row['aliasesname']}")

        logging.info(f"Generated {m3u8_path} file successfully.")
    except sqlite3.DatabaseError as db_err:
        logging.error(f"Database error while generating M3U8 file: {db_err}")
    except Exception as e:
        logging.error(f"Error generating M3U8 file: {e}")
    finally:
        conn.close()

def get_host_ip():
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except Exception as e:
        logging.error(f"Failed to get host IP: {e}")
        return 'localhost'

@app.route('/aggregated_channels.m3u8')
def serve_m3u8():
    try:
        m3u8_path = 'data/aggregated_channels.m3u8'
        if os.path.exists(m3u8_path):
            logging.info("Serving aggregated_channels.m3u8 file")
            return send_file(m3u8_path)
        else:
            logging.error(f"M3U8 file not found: {m3u8_path}")
            return "M3U8 file not found", 404
    except Exception as e:
        logging.error(f"Error serving M3U8 file: {e}")
        return "Internal server error", 500

if __name__ == "__main__":
    generate_m3u8_file()  # 生成总的 M3U8 文件
    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logging.error(f"Failed to start Flask server: {e}")

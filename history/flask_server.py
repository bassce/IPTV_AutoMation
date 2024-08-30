from flask import Flask, redirect, send_file
import pandas as pd
import os
import logging
import socket
import sqlite3

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

def get_channel_url(aliasesname):
    try:
        df = pd.read_sql_query('SELECT * FROM filtered_playlists ORDER BY latency ASC', "sqlite:///data/iptv_sources.db")
        filtered_df = df[df['aliasesname'] == aliasesname]
        
        if not filtered_df.empty:
            selected_source = filtered_df.iloc[0]
            logging.info(f"Selected source for {aliasesname}: URL={selected_source['url']}, "
                         f"Latency={selected_source['latency']}ms, Resolution={selected_source['resolution']}, "
                         f"Format={selected_source['format']}")
            return selected_source['url']
        else:
            logging.warning(f"No source found for {aliasesname}")
            return None
    except Exception as e:
        logging.error(f"Failed to get channel URL for {aliasesname}: {e}")
        return None

def generate_m3u8_file():
    try:
        df = pd.read_sql_query('SELECT * FROM filtered_playlists', "sqlite:///data/iptv_sources.db")
        unique_channels = set()
        m3u8_path = 'data/aggregated_channels.m3u8'

        with open(m3u8_path, 'w', encoding='utf-8') as m3u8_file:
            m3u8_file.write("#EXTM3U\n")
            for _, row in df.iterrows():
                if row['aliasesname'] not in unique_channels:
                    m3u8_file.write(f"#EXTINF:-1 tvg-name=\"{row['tvg_name']}\" group-title=\"{row['group_title']}\",{row['title']}\n")
                    m3u8_file.write(f"http://{get_host_ip()}:5000/{row['aliasesname']}\n")
                    unique_channels.add(row['aliasesname'])
                    logging.info(f"Added channel to M3U8: {row['title']} with URL path /{row['aliasesname']}")

        logging.info(f"Generated {m3u8_path} file successfully.")
    except sqlite3.DatabaseError as db_err:
        logging.error(f"Database error while generating M3U8 file: {db_err}")
    except Exception as e:
        logging.error(f"Error generating M3U8 file: {e}")

def get_host_ip():
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except Exception as e:
        logging.error(f"Failed to get host IP: {e}")
        return 'localhost'

@app.route('/<aliasesname>')
def redirect_channel(aliasesname):
    url = get_channel_url(aliasesname)
    if url:
        logging.info(f"Redirecting {aliasesname} to {url}")
        return redirect(url)
    else:
        logging.warning(f"Channel not found: {aliasesname}")
        return "Channel not found", 404

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

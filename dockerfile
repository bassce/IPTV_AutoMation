# 使用轻量级的 Python 3.12 slim 镜像作为基础
FROM python:3.12.5-slim

# 设置工作目录
WORKDIR /app

# 更新包列表并安装系统依赖
RUN apt-get update \
    && apt-get install -y unzip wget ffmpeg bash sqlite3 libnss3 libxss1 libappindicator3-1 libasound2 xdg-utils fonts-liberation libcurl4 ca-certificates \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && pip install --upgrade pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data

# 下载 Chrome 和 ChromeDriver
RUN wget -O /app/chrome-linux64.zip https://storage.googleapis.com/chrome-for-testing-public/128.0.6613.137/linux64/chrome-linux64.zip \
    && wget -O /app/chromedriver-linux64.zip https://storage.googleapis.com/chrome-for-testing-public/128.0.6613.137/linux64/chromedriver-linux64.zip

# 解压 Chrome 和 ChromeDriver
RUN unzip /app/chrome-linux64.zip -d /usr/local/bin/ \
    && unzip /app/chromedriver-linux64.zip -d /usr/local/bin/ \
    && ln -sf /usr/local/bin/chrome-linux64/chrome /usr/bin/google-chrome \
    && ln -sf /usr/local/bin/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && rm /app/chrome-linux64.zip /app/chromedriver-linux64.zip

# 将 requirements.txt 复制到容器中并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将项目的其余文件复制到容器中
COPY . .

# 设置宿主机与容器的共享目录
VOLUME /app/data

# 添加 Docker 参数作为环境变量
ENV GITHUB_SEARCH_QUERY="直播源,iptv" \
    GITHUB_SEARCH_DAYS=3 \
    GITHUB_TOKEN="" \
    THREADS=0 \
    THREAD_LIMIT=0 \
    HEIGHT_LIMIT=1080 \
    CODEC_EXCLUDE_LIST=Unknown \
    LATENCY_LIMIT=3000 \
    RETRY_LIMIT=0 \
    FAILURE_THRESHOLD=6 \
    SCHEDULER_INTERVAL_MINUTES=30 \
    SEARCH_INTERVAL_HOURS=24 \
    FAILED_SOURCES_CLEANUP_DAYS=20 \
    ffmpeg_check_frequency_minutes=360 \
    HOST_IP="" \
    SUBDIVISION="Henan,Hubei"

# 设置入口脚本权限
RUN chmod +x /app/entrypoint.sh

# 设置启动命令
ENTRYPOINT ["/app/entrypoint.sh"]

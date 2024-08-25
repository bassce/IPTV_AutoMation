# 使用轻量级的 Python 3.12 Alpine 镜像作为基础
FROM python:3.12-alpine

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    make \
    && apk add --no-cache \
    ffmpeg \
    bash \
    sqlite \
    && pip install --upgrade pip

# 将requirements.txt复制到容器中
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将项目的其余文件复制到容器中
COPY config.json .
COPY db_setup.py .
COPY flask_server.py .
COPY github_search.py .
COPY import_playlists.py .
COPY run.py .
COPY scheduler.py .
COPY source_checker.py .
COPY data/filter_conditions.xlsx /filter_conditions.xlsx

# 添加 Docker 参数作为环境变量
ENV GITHUB_SEARCH_QUERY="直播源"
ENV GITHUB_SEARCH_DAYS=25
ENV GITHUB_TOKEN="your_github_token"
ENV SEMAPHORE_LIMIT=20
ENV HEIGHT_LIMIT=null
ENV CODEC_EXCLUDE_LIST=Unknown
ENV LATENCY_LIMIT=3000
ENV RETRY_LIMIT=1
ENV SCHEDULER_INTERVAL_MINUTES=30

# 创建data播放列表目录并复制默认文件
RUN mkdir -p /app/data

# 设置宿主机与容器的共享目录
VOLUME /app/data

# 复制入口脚本并赋予执行权限
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 设置启动命令
ENTRYPOINT ["/entrypoint.sh"]

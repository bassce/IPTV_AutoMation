# 使用轻量级的 Python 3.12 Alpine 镜像作为基础
FROM python:3.12.5-alpine

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖并升级pip
RUN apk add --no-cache --virtual .build-deps \
    build-base gcc musl-dev libffi-dev openssl-dev make \
    && apk add --no-cache ffmpeg bash sqlite \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && pip install --upgrade pip \
    && mkdir -p /app/data # 创建data目录，

# 将requirements.txt复制到容器中并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 删除构建依赖项以减少镜像大小
RUN apk del .build-deps

# 将项目的其余文件复制到容器中
COPY . .

# 设置宿主机与容器的共享目录
VOLUME /app/data

# 添加 Docker 参数作为环境变量
ENV GITHUB_SEARCH_QUERY="直播源" \
    GITHUB_SEARCH_DAYS=25 \
    GITHUB_TOKEN="" \
    THREAD_LIMIT=8 \
    HEIGHT_LIMIT=null \
    CODEC_EXCLUDE_LIST=Unknown \
    LATENCY_LIMIT=5000 \
    RETRY_LIMIT=1 \
    SCHEDULER_INTERVAL_MINUTES=30 \
    SEARCH_INTERVAL_DAYS=2 \
    HOST_IP="" \
    FAILURE_THRESHOLD=12 \
    FAILED_SOURCES_CLEANUP_DAYS=20 \
    FFMPEG_CHECK_FREQUENCY_HOURS=6

# 设置入口脚本权限
RUN chmod +x /app/entrypoint.sh

# 设置启动命令
ENTRYPOINT ["/app/entrypoint.sh"]

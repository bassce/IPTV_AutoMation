#!/bin/sh

# 如果宿主机挂载的目录没有 filter_conditions.xlsx 文件，则复制默认的 filter_conditions.xlsx
if [ ! -f /app/data/filter_conditions.xlsx ]; then
    cp /app/filter_conditions.xlsx /app/data/filter_conditions.xlsx
fi

# 创建必要的目录，如果它们不存在
if mkdir -p /app/data/user_uploaded; then
    echo "Directory /app/data/user_uploaded created successfully."
else
    echo "Failed to create directory /app/data/user_uploaded." >&2
    exit 1  # 终止脚本并返回错误码
fi

# 直接启动 scheduler.py 并将日志保存到 scheduler_log.txt 中
exec python scheduler.py
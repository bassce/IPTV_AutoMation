#!/bin/sh

# 如果宿主机挂载的目录没有filter_conditions.xlsx文件，则复制默认的 filter_conditions.xlsx
if [ ! -f /app/data/filter_conditions.xlsx ]; then
    cp /app/filter_conditions.xlsx /app/data/filter_conditions.xlsx
fi

# 定义重启间隔（以秒为单位）
RESTART_INTERVAL=$((SEARCH_INTERVAL_DAYS * 24 * 60 * 60))

# 无限循环
while true; do
    # 启动应用
    python scheduler.py
    
    # 等待指定的间隔时间后重新启动
    sleep $RESTART_INTERVAL
done

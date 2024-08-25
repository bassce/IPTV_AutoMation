#!/bin/sh

# 如果宿主机挂载的目录没有filter_conditions.xlsx文件，则复制默认的 filter_conditions.xlsx
if [ ! -f /app/data/filter_conditions.xlsx ]; then
    cp /filter_conditions.xlsx /app/data/filter_conditions.xlsx
fi

# 启动应用
exec python run.py


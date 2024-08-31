# IPTV_AutoMation

IPTV_AutoMation 是一款由 ChatGPT 使用 Python 编写的 IPTV 自动化工具，用于定期搜索 IPTV 资源、检测节目源质量、聚合网关，并实现推流管理。

## 功能简介

- **关键字搜索 IPTV 资源**: 从 GitHub 搜索包含“直播源”关键字的仓库，自动下载后缀为 `.m3u`、`.m3u8`、`.txt` 的节目源，筛选最近 25 天内发布或推送的内容并保存。
- **节目源质量检测**: 检测指定文件夹内的节目源延迟、视频分辨率和下载速度，并根据筛选条件提取符合要求的节目源，按 IPTV 规范格式保存。
- **Flask 服务器**: 使用 Flask 创建指定频道的固定网址，让网址跳转到符合条件的节目源中速度最快的源。

## 文件结构目录

```
iptv_automation/
│
├── data/
│   ├── filter_conditions.xlsx         # Excel 文件，存储筛选条件，初始数据来源
│   ├── iptv_sources.db                # SQLite 数据库文件，存储 Excel 数据导入的结果
│   ├── downloaded_sources/            # 下载的节目源文件存放目录
│   ├── filtered_sources.xlsx          # 筛选后可播放的直播源
│   ├── filtered_sources.m3u8          # 筛选后可播放的直播源（M3U8 格式）
│   └── aggregated_channels.m3u8       # Flask 服务器生成的直播源列表
│
├── github_search.py                   # GitHub 搜索和下载模块
├── db_setup.py                        # 频道列表模块，将 Excel 频道模板导入到 SQLite 的 `iptv_sources` 表中
├── import_playlists.py                # 将 GitHub 搜索下载的直播源导入 SQLite 的 `iptv_playlists` 表中
├── calculate_score.py                 # 直播源评分机制
├── ffmpeg_source_checker.py           # IPTV 源初步筛选，调用 ffmpeg 检测直播源的延迟、分辨率和视频格式，并保存到 SQLite 的 `filtered_playlists` 表中
├── daily_monitor.py                   # 延迟和下载速度检测模块，对 `filtered_playlists` 表中的直播源进行检测
├── flask_server.py                    # Flask 服务器模块，生成本地固定频道网址，根据评分机制选择最优质频道
├── scheduler.py                       # 定期检测和更新模块
├── requirements.txt                   # Python 依赖库列表
├── config.json                        # 项目核心参数配置文件
├── entrypoint.sh                      # 启用脚本
└── filter_conditions.xlsx             # filter_conditions.xlsx 备份，Docker 镜像默认从它复制到 data 文件夹中
```

## Docker 环境参数

| 参数 | 说明 | 默认值 |
| ---- | ---- | ---- |
| GITHUB_SEARCH_QUERY | 搜索关键字，可以填写多个关键字（如：直播源,IPTV） | 直播源 |
| GITHUB_SEARCH_DAYS | 搜索天数，从当前日期向前推 | 25 天 |
| GITHUB_TOKEN | GitHub token，用于 API 访问 | Your_GITHUB_TOKEN |
| THREAD_LIMIT | 多线程数，根据网络和设备性能自行调整 | 10 |
| HEIGHT_LIMIT | 分辨率筛选（null 保存全部, 0 保存除 Unknown 外全部, 大于 0 的值不保存低于该值的分辨率） | null |
| CODEC_EXCLUDE_LIST | 排除的视频格式列表 | Unknown |
| LATENCY_LIMIT | 延迟检测时间限制（建议在 5000-10000 ms 之间） | 5000 ms |
| RETRY_LIMIT | 检测失败后的重试次数 | 1 |
| SCHEDULER_INTERVAL_MINUTES | 定期检测间隔时间 | 30 分钟 |
| SEARCH_INTERVAL_DAYS | 项目重启间隔天数 | 2 天 |
| /app/data | 数据存储文件夹（用于存放下载和检测的直播源文件） | 可映射到宿主机 |

## 生成的节目单下载地址

- `http://127.0.0.1:5000/aggregated_channels.m3u8`
- `http://localhost:5000/aggregated_channels.m3u8`

## 网络选择

建议选择 `host` 或 `macvlan` 模式，并启用 `IPV6`。

---

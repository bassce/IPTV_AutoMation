# IPTV_AutoMation

IPTV_AutoMation 是受[flyfishes/IPTV-M3U-Checker2](https://github.com/flyfishes/IPTV-M3U-Checker2)、[AmbitiousJun/iptv-server](https://github.com/AmbitiousJun/iptv-server)和[ssili126/tv](https://github.com/ssili126/tv)项目启发，由 ChatGPT 使用 Python 编写的 IPTV 自动化工具，用于定期搜索 IPTV 资源、检测节目源质量、聚合网关，并实现局域网推流管理。主要用于emby、plex等自建媒体服务器使用。仅支持 x86 架构。


## 功能简介

- **搜索 IPTV 资源**: 从 GitHub 和网络空间搜索引擎搜索包含“直播源”关键字的直播源，筛选最近推送的直播源文件并下载保存。
- **节目源质量检测**: 检测搜索下载的直播源和用户自行导入的直播源，根据延迟、视频分辨率、下载速度和连通性为直播源评分，将可用的直播源保存为m3u8文件。
- **Flask 服务器**: 使用 Flask 生成局域网播放文件，在播放时根据频道自动选择评分最高的直播源跳转播放。


## 文件结构目录

```
iptv_automation/
│
├── data/
│   ├── downloaded_sources/            # github下载的直播源文件保存目录
│   ├── user_uploaded/                 # 用户手动保存直播源的目录
│   ├── hotel_search/                  # 网络空间搜索引擎搜索的直播源保存目录
│   ├── logs/                          # 日志保存目录
│   ├── filter_conditions.xlsx         # Excel 文件，存储频道名称列表
│   ├── iptv_sources.db                # SQLite 数据库文件，存储项目运行的数据
│   ├── filtered_sources.xlsx          # Excel 文件，检测筛选后可播放的直播源列表
│   ├── filtered_sources.m3u8          # 检测筛选后可播放的直播源文件
│   └── aggregated_channels.m3u8       # 用于局域网播放的可自行切换最优直播源的文件
│
├── github_search.py                   # GitHub 搜索和下载模块
├── hotel_search.py                    # 网络空间搜索引擎搜索和下载模块
├── db_setup.py                        # 频道列表模块，将 Excel 频道模板导入到 SQLite 的 `iptv_sources` 表中
├── import_playlists.py                # 将 GitHub 搜索下载的直播源导入 SQLite 的 `iptv_playlists` 表中
├── calculate_score.py                 # 直播源评分机制
├── ffmpeg_source_checker.py           # IPTV 源初步筛选，调用 ffmpeg 检测直播源的延迟、分辨率和视频格式，并保存到 SQLite 的 `filtered_playlists` 表中
├── daily_monitor.py                   # 延迟和下载速度检测模块，对 `filtered_playlists` 表中的直播源进行检测
├── flask_server.py                    # Flask 服务器模块，生成本地固定频道网址，根据评分机制选择最优质频道
├── clean_failed_sources.py            # 废弃直播源清理模块，对 SQLite 的 `failed_sources` 表进行重置
├── scheduler.py                       # 初始化、定期检测、文件监测和定时更新模块
├── logging_config.py                  # 日志记录模块
├── requirements.txt                   # Python 依赖库列表
├── config.json                        # 项目核心参数配置文件
├── entrypoint.sh                      # 启用脚本
└── filter_conditions.xlsx             # filter_conditions.xlsx 备份，Docker 镜像默认从它复制到 data 文件夹中
```


## `docker-compose.yml` 示例
```yaml
version: '3.8'

services:
  iptv_automation:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: iptv_automation_container
    environment:
      GITHUB_SEARCH_QUERY: "直播源,iptv"
      GITHUB_SEARCH_DAYS: 3
      GITHUB_TOKEN: ""  # 在此处添加你的 GitHub Token
      THREADS: 0
      THREAD_LIMIT: 0
      HEIGHT_LIMIT: 1080
      CODEC_EXCLUDE_LIST: "Unknown"
      LATENCY_LIMIT: 3000
      RETRY_LIMIT: 0
      FAILURE_THRESHOLD: 6
      SCHEDULER_INTERVAL_MINUTES: 30
      SEARCH_INTERVAL_HOURS: 4
      FAILED_SOURCES_CLEANUP_DAYS: 20
      ffmpeg_check_frequency_minutes: 360
      HOST_IP: ""  # 这里可以指定主机的 IP 地址，因为是 host 模式
      SUBDIVISION: "Henan,Hubei"
    volumes:
      - ./data:/app/data  # 将主机的 ./data 目录映射到容器中的 /app/data
    network_mode: "host"  # 使用 host 网络模式
    restart: unless-stopped  # 配置自动重启策略
```


## Docker 环境参数

| 参数 | 默认值 | 可用值 |
| ---- | ---- | ---- |
| GITHUB_SEARCH_QUERY | `直播源,iptv` | 可设置为任意文字 |
| GITHUB_SEARCH_DAYS | `10` | `10`,`15`,`20` 等任意整数 |
| GITHUB_TOKEN | ` ` | 必填 |
| THREADS | `0` | 不大于宿主机 CPU 2倍的线程数 |
| THREAD_LIMIT | `0` | 不大于宿主机 CPU 2倍的线程数 |
| HEIGHT_LIMIT | `1080` | `null` 保存全部, `0` 保存除 Unknown 外全部, 大于 `0` 的任意整数 不保存低于该值的分辨率 |
| CODEC_EXCLUDE_LIST | `Unknown` | `Unknown`,`hevc`,`h264` 等等 |
| LATENCY_LIMIT | `3000` | 建议在 `2000`-`10000` ms 之间 |
| RETRY_LIMIT | `0` | 任意整数 |
| FAILURE_THRESHOLD | `6` | 任意整数 |
| SCHEDULER_INTERVAL_MINUTES | `30` | 任意整数 |
| SEARCH_INTERVAL_HOURS | `4` | 任意整数 |
| FAILED_SOURCES_CLEANUP_DAYS | `20` | 任意整数 |
| ffmpeg_check_frequency_minutes | `360` | 任意整数 |
| HOST_IP | ` ` | 主机IP |
| SUBDIVISION | `Henan,Hubei` | 建议保留你所在省的名称即可，首字母大写 |
| /app/data | ./data | 宿主机映射路径，自行修改 |


### 参数说明

1. **GITHUB_SEARCH_QUERY**
   - **类型**: `字符串`
   - **说明**: 在 GitHub 上进行搜索的关键词。该查询参数将被用来搜索 GitHub 项目中的文件、仓库等。
   - **作用**: 当项目运行 `github_search.py` 脚本时，GitHub API 会根据此关键词在公开仓库中查找后缀为`.m3u`、`.m3u8`、`.txt`的文件。推荐关键字：`iptv`,`直播源`,`高清电视`,`电视直播`,`tv`,`央视`,`卫视`,`4k直播`等等。如果不想使用github搜索，输入任意字符即可。
   - **示例**: `"直播源,iptv,高清电视"`

2. **GITHUB_SEARCH_DAYS**
   - **类型**: `整数`
   - **说明**: 这是 GitHub 搜索文件的最后更新日期限制。它决定了只搜索在指定天数内更新的文件。
   - **作用**: 搜索的文件必须是在过去 `GITHUB_SEARCH_DAYS` 天内更新的。建议数值`3`。数值越大，搜索出来的（废弃）直播源越多，项目定期对直播源检测花费的时间也就越长。
   - **示例**: `30`（表示搜索过去 3 天内更新的仓库内的后缀为`.m3u`、`.m3u8`、`.txt`的文件）

3. **GITHUB_TOKEN**
   - **类型**: `字符串`
   - **说明**: GitHub API 的访问令牌。[申请地址](https://github.com/settings/tokens)
   - **作用**: 没有令牌的情况下，GitHub API 的调用频率为60 次请求/小时。使用令牌允许 API 请求的频率为5000 次请求/小时，并获得更多的权限。注意，这里的次数不是脚本运行的次数，而是通过api访问的次数，关键字越多，仓库越多、文件越多访问的次数就会越多
   - **示例**: `"ghp_XXXXXXXXXXXXXXXXXXXXXX"`（GitHub 提供的个人访问令牌）

4. **THREADS**
   - **类型**: `整数`
   - **说明**: 设置最大线程数，用于控制下载速度检测任务的（多）线程数量。
   - **作用**: 原则不宜超过最大值CPU线程数的2倍，过大的线程数可能会导致并发访问某个IP下的直播源，因连接数过多无法测出真实的实时速率；超出CPU线程数可能会降低IO速度；过低的线程数在应对上万的直播源会花费更多时间检测，如果`SCHEDULER_INTERVAL_MINUTES`、`ffmpeg_check_frequency_minutes`设置时间较短，可能会造成大量任务堆积。默认的`0`代表宿主机CPU的线程数。在7个线程情况下2000个直播源测速需要20-30分钟（AMD Ryzen V1500B），docker启动初始化运行完毕才会生成可用m3u8文件。
   - **示例**: `8`（表示最多允许 8 个任务同时执行）

5. **THREAD_LIMIT**
   - **类型**: `整数`
   - **说明**: 设置最大线程数，用于控制视频分辨率检测任务的（多）线程数量。
   - **作用**: 原则不宜超过最大值CPU线程数的2倍，过大的线程数可能会导致并发访问某个IP下的直播源，因连接数过多无法测出真实的实时速率；超出CPU线程数可能会降低IO速度；过低的线程数在应对上万的直播源会花费更多时间检测，如果`SCHEDULER_INTERVAL_MINUTES`、`ffmpeg_check_frequency_minutes`设置时间较短，可能会造成大量任务堆积。默认的`0`代表宿主机CPU的线程数的1.5倍。在7个线程情况下34137个直播源分辨率检测需要40分钟（AMD Ryzen V1500B）
   - **示例**: `8`（表示最多允许 8 个任务同时执行）

6. **HEIGHT_LIMIT**
   - **类型**: `整数`
   - **说明**: 设置视频流的最大允许分辨率高度（单位为像素）。
   - **作用**: 在流媒体检测过程中，任何低于此分辨率的视频流将被过滤掉。例如，`HEIGHT_LIMIT=1080` 将过滤掉所有分辨率低于 1080p 的视频流。
   - **示例**: `1080`（表示允许的最高分辨率为 1080p）

7. **CODEC_EXCLUDE_LIST**
   - **类型**: `字符串（逗号分隔）`
   - **说明**: 视频编码格式排除列表，这些编码格式的视频流将被忽略。
   - **作用**: 在流媒体检测时，任何使用此列表中编码格式的视频流将被排除。例如，如果 `CODEC_EXCLUDE_LIST` 包含 `Unknown`，则所有编码格式为 `Unknown` （也就是检测不到直播源信息）的流将被忽略。
   - **示例**: `"Unknown"`（表示排除编码格式为 `Unknown` 的流）

8. **LATENCY_LIMIT**
   - **类型**: `整数`
   - **说明**: 指定检测视频流时允许的最大延迟时间，单位为毫秒。
   - **作用**: 在检测视频流时，任何延迟超过此值的流都会被排除。这有助于确保只选择低延迟的视频流，以提高频道切换速度。
   - **示例**: `3000`（表示延迟超过 3000 毫秒的流将被排除）

9. **RETRY_LIMIT**
   - **类型**: `整数`
   - **说明**: 视频流检测失败时允许的最大重试次数。
   - **作用**: 如果检测任务失败，系统将最多重试 `RETRY_LIMIT` 次。超过此次数后，流将被标记为失败并跳过。
   - **示例**: `1`（表示失败后最多重试 1 次）

10. **FAILURE_THRESHOLD**
   - **类型**: `整数`
   - **说明**: 允许视频流检测失败的最大次数。
   - **作用**: 如果某个视频流的检测失败次数达到该值，该流将被移至废弃源列表，并不会再进行检测。
   - **示例**: `6`（表示检测失败 6 次后该流将被移除）

11. **SCHEDULER_INTERVAL_MINUTES**
    - **类型**: `整数`
    - **说明**: 定时任务的执行间隔，单位为分钟。
    - **作用**: 该参数控制定时评分机制的运行频率。例如，设置为 `30` 表示每 30 分钟会触发一次检测任务。建议设置30-60分钟。
    - **示例**: `30`（表示调度器每 30 分钟执行一次检测任务）

12. **SEARCH_INTERVAL_HOURS**
    - **类型**: `整数`
    - **说明**: 控制 GitHub 搜索任务的执行间隔，单位为小时。
    - **作用**: 该参数控制项目中定期进行 GitHub 搜索、网络空间搜索引擎搜索任务的运行频率。设置为 `4` 表示每 4 小时执行一次搜索。
    - **示例**: `4`（表示每 4 小时搜索一次）

13. **FAILED_SOURCES_CLEANUP_DAYS**
    - **类型**: `整数`
    - **说明**: 定期清理失败源的时间间隔，单位为天。
    - **作用**: 系统会定期清理检测失败（废弃）的源，这个参数设置了清理的时间间隔。例如，设置为 `20` 表示每 20 天清理一次失败的源。
    - **示例**: `20`（表示每 20 天执行一次清理任务）

14. **ffmpeg_check_frequency_minutes**
    - **类型**: `整数`
    - **说明**: FFMPEG 检测任务的执行间隔，单位为分钟。
    - **作用**: 该参数控制 FFMPEG 检测任务的运行频率。主要是用于处理检测失败（废弃）的直播源。
    - **示例**: `360`（表示每 6 小时运行一次 FFMPEG 检测任务）

15. **HOST_IP**
    - **类型**: `字符串`
    - **说明**: Flask 服务器绑定的主机 IP 地址，用于指定服务器监听的 IP 地址。
    - **作用**: 该参数指定 Flask 服务器的 IP 地址，默认为 `0.0.0.0` 监听所有接口。该参数必须正确设置为项目运行主机的IP，否则无法实现局域网推流管理。
    - **示例**: `"192.168.10.15"`

16. **SUBDIVISION**
    - **类型**: `字符串（逗号分隔）`
    - **说明**: 网络空间搜索任务中使用的地理区域划分，用于限制搜索的地理范围。
    - **作用**: 该参数用于 ZoomEye 或其他网络空间搜索工具，指定搜索结果所在的地理区域。例如，设置为 `"Henan,Hubei"` 表示只搜索来自河南和湖北的直播源。
    - **示例**: `"Henan,Hubei"`（表示只搜索河南和湖北的网络空间资源）


## 局域网播放文件的下载地址

- `http://HOST_IP:5000/aggregated_channels.m3u8`



## 网络选择

建议选择 `host` 或 `macvlan` 模式，并启用 `IPV6`。


## 评分机制：

1. **延迟（Latency）** - **权重：0.3**
   - 延迟是指从请求到响应的时间，延迟越低，得分越高。
   - 评分公式：`latency_score = max(0, 1 - (latency / max_latency))`
     - `max_latency` 被设置为 10 秒，意味着 10 秒以上的延迟会得到最低分，而低于 10 秒的延迟则按比例评分。
   - **影响**：延迟越低，得分越高，满分为 1。

2. **下载速度（Download Speed）** - **权重：0.3**
   - 下载速度直接影响视频的播放质量，速度越高，播放越流畅。
   - 评分公式：`download_speed_score = min(download_speed / max_download_speed, 1)`
     - `max_download_speed` 被设定为 80 Mbps，下载速度越接近这个上限，得分越高。
   - **影响**：下载速度越高，得分越高，满分为 1。

3. **分辨率（Resolution）** - **权重：0.15**
   - 分辨率代表视频的画质，分辨率越高，得分越高。
   - 分辨率得分映射：
     - 480p：0.5
     - 576p：1.0
     - 720p：1.5
     - 1080p：2.0
     - 2K：2.5
     - 4K：3.0
     - Unknown：0.5
   - **影响**：高分辨率的视频得分更高，最高可达 3.0。

4. **视频编码格式（Format）** - **权重：0.1**
   - 视频编码格式的效率和兼容性也会影响评分。
   - 格式得分映射：
     - HEVC（h265）：1.2
     - H.264：1.0
     - AVS2：0.8
     - MPEG2：0.7
     - CAVS：0.5
     - Unknown：0.1
   - **影响**：格式越高效，得分越高。

5. **稳定性（Stability）** - **权重：0.075**
   - 稳定性反映直播源的连接可靠性，通过成功率和失败率调整。
   - 评分公式：
     - 成功时：`min(previous_stability + 0.01, 1.0)`
     - 失败时：`max(previous_stability - 0.05, 0.0)`
   - **影响**：稳定性越高，评分越高。

6. **成功率（Success Rate）** - **权重：0.075**
   - 成功率代表直播源的连接成功率，连接成功越多，得分越高。
   - 评分公式：
     - 成功时：`min(previous_success_rate + 0.01, 1.0)`
     - 失败时：`max(previous_success_rate - 0.05, 0.0)`
   - **影响**：成功率越高，得分越高。

### 评分公式：

```python
score = (weight_latency * latency_score +
         weight_download_speed * download_speed_score +
         weight_resolution * resolution_score +
         weight_format * format_score +
         weight_stability * stability +
         weight_success_rate * success_rate)
```

### 各因素的权重：
- **延迟（Latency）**：0.3
- **下载速度（Download Speed）**：0.3
- **分辨率（Resolution）**：0.08
- **视频格式（Format）**：0.07
- **稳定性（Stability）**：0.15
- **成功率（Success Rate）**：0.1

- **延迟** 和 **下载速度** 是评分机制中权重最高的两个因素，各占 30%。
- **分辨率** 和 **格式** 会影响视频的质量，分辨率权重为 8%，格式权重为 7%。
- **稳定性** 和 **成功率** 稳定性权重为 15%，成功率权重为 10%，用于反映直播源的可靠性和连接成功情况。

- 最终评分为加权平均值，并结合之前的评分进行累计，通过这些因素的加权评分，最终生成一个综合得分，评估直播源的整体质量。


## 直播源废弃机制：
- 直播源根据 `ffmpeg_check_frequency_minutes` 参数值定期对数据库 iptv_playlists 的直播源进行检测。

   - 当连续 `FAILURE_THRESHOLD` 次检测失败后将废弃该直播源，保存到数据库 failed_sources 表中， failed_sources 表会在 `FAILED_SOURCES_CLEANUP_DAYS` 后清空，期间新导入的直播源如和 failed_sources 表中相同，直接废弃。

   - 检测成功的直播源进入数据库 filtered_playlists 表中，然后根据 `SCHEDULER_INTERVAL_MINUTES` 参数值定期检测延迟和下载速度，当连续 `FAILURE_THRESHOLD` 次失败后退回 iptv_playlists 表再次进入循环。
---

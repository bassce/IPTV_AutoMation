# IPTV_AutoMation
一款由Chatgpt（Python）编写的实现iptv资源定期搜索、节目源质量检测、聚合网关、推流转件。
软件主要实现以下功能：
    - 从GITHUB搜索包含关键字"直播源"，后缀是".m3u"、"m3u8"、"txt"，发布或推送日期在"20"天以内的节目源，自动下载并保存。
    - 检测指定文件夹内的节目源延迟、视频分辨率和下载速度，根据筛选条件提取符合条件的节目源并按照IPTV节目源规范格式保存。
    - 用Flask服务器创建指定频道的固定网址，让固定网址跳转到符合条件节目源中速度最快的源。
    - 用SRT实现频道固定网址的推流，借用服务器的上传流量实现外网观看。
    - 定期检测符合条件的节目源，当某一个频道的节目源全部失效的时候从GITHUB再次搜索符合条件的并替换。
结构目录：
iptv_project/
│
├── data/
│   ├── filter_conditions.xlsx   # Excel文件，存储筛选条件，初始数据来源
│   ├── iptv_sources.db          # SQLite数据库文件，存储Excel数据导入的结果
│   ├── downloaded_sources/      # 下载的节目源文件存放目录
    ├── filtered_sources.xlsx    # 存储筛选后可播放直播源
    ├── filtered_sources.m3u8    # 存储筛选后可播放直播源
    └── aggregated_channels.m3u8 # flask_server生成的直播源列表

│
├── github_search.py             # GitHub搜索和下载模块
├── source_checker.py            # IPTV源检测模块（延迟、分辨率、速度）
├── flask_server.py              # Flask服务器模块，用于频道跳转
├── scheduler.py                 # 定期检测和更新模块
├── db_setup.py                  # Excel频道模板导入SQLite的脚本
├── import_playlists.py          # 下载的节目源导入SQLite
├── requirements.txt             # Python依赖库列表
├── config.json                  # 项目相关可调整参数
└── run.py                       # 项目入口脚本，启动Flask和定期更新任务

可用参数：
    分辨率：
        - None（默认）全部保存
        - 0 除Unknown以外全部保存
        - 大于0的任意整数 不保存低于参数的分辨率，如"720"，即不保存720P以下分辨率的直播源

    视屏格式：
        - None（默认）保存所有直播源
        - "Unknown","hevc","h264" 不保存h264、hevc以及Unknown的直播源

    限制并发请求的数量：

    延迟:
        - 2000（默认）延迟高于2000的不再检测

    GITHUB_TOKEN
        - Your_GITHUB_TOKEN（默认） 修改为你的GitHub token

    搜索关键字：
        - 直播源（默认）可以写成 直播源,IPTV

    搜索天数
        - 25（默认值） 由today向前推25天
    
    重复检测次数
        - 1（默认）连接失败后重复检测的次数

    定期检测间隔时间：
        - 30（分钟，默认） 定期对可用直播源进行延迟检测

    生成列表下载地址
        - http://192.168.8.3:5000/download_m3u8
    

        

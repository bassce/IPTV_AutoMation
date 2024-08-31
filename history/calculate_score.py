def calculate_score(resolution_value, format, latency, download_speed, stability, success_rate):
    # 分辨率值到字符串的映射
    resolution_map = {
        480: "480p",
        576: "576p",
        720: "720p",
        1080: "1080p",
        1440: "2K",
        2160: "4K"
    }

    # 根据数据库中的数值转换为字符串
    resolution = resolution_map.get(resolution_value, "Unknown")

    # 以下代码保持不变，使用转换后的字符串进行评分
    # 权重设定
    weight_latency = 0.3
    weight_download_speed = 0.3
    weight_resolution = 0.2
    weight_format = 0.1
    weight_stability = 0.05
    weight_success_rate = 0.05

    # 分辨率评分映射
    resolution_scores = {
        "480p": 1.0,
        "576p": 1.5,
        "720p": 2.0,
        "1080p": 3.0,
        "2K": 4.0,
        "4K": 5.0,
        "Unknown": 1.0
    }

    # 格式评分映射
    format_scores = {
        "hevc": 1.2,
        "h264": 1.0,
        "avs2": 0.8,
        "mpeg2video": 0.7,
        "cavs": 0.5,
        "Unknown": 0.1
    }

    # 获取分辨率和格式分数
    resolution_score = resolution_scores.get(resolution, 1.0)
    format_score = format_scores.get(format, 0.1)

    # 假设延迟和下载速度评分范围为0到1
    max_latency = 10.0  # 最大延迟（秒）
    max_download_speed = 40.0  # 最大下载速度（Mbps）

    latency_score = max(0, 1 - (latency / max_latency))  # 延迟越低，分数越高
    download_speed_score = min(download_speed / max_download_speed, 1)  # 下载速度越高，分数越高

    # 计算总评分
    score = (weight_latency * latency_score +
             weight_download_speed * download_speed_score +
             weight_resolution * resolution_score +
             weight_format * format_score +
             weight_stability * stability +
             weight_success_rate * success_rate)

    return score

# 示例调用
score = calculate_score(
    resolution_value=1080,  # 数值输入
    format="hevc",
    latency=4.0,          # 秒
    download_speed=16.0,  # Mbps
    stability=0.9,        # 稳定性评分（0到1）
    success_rate=0.95     # 成功率（0到1）
)
print(f"总评分: {score}")

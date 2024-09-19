def initialize_stability_and_success_rate():
    # 初始化默认的稳定性和成功率
    initial_stability = 0.9
    initial_success_rate = 0.95
    return initial_stability, initial_success_rate

def update_stability_and_success_rate(previous_stability, previous_success_rate, success):
    if success:
        # 如果成功，可以微调增加稳定性和成功率
        new_stability = min(previous_stability + 0.01, 1.0)
        new_success_rate = min(previous_success_rate + 0.01, 1.0)
    else:
        # 如果失败，可以适当降低稳定性和成功率
        new_stability = max(previous_stability - 0.05, 0.0)
        new_success_rate = max(previous_success_rate - 0.05, 0.0)
    
    return new_stability, new_success_rate

def calculate_score(resolution_value, format, latency, download_speed, stability, success_rate, previous_score=0):
    # 分辨率值到字符串的映射
    resolution_map = {
        480: "480p",
        576: "576p",
        720: "720p",
        1080: "1080p",
        1440: "2K",
        2160: "4K"
    }

    resolution = resolution_map.get(resolution_value, "Unknown")

    # 权重设定
    weight_latency = 0.3
    weight_download_speed = 0.3
    weight_resolution = 0.08
    weight_format = 0.07
    weight_stability = 0.15
    weight_success_rate = 0.1

    # 分辨率评分映射
    resolution_scores = {
        "480p": 0.5,
        "576p": 1.0,
        "720p": 1.5,
        "1080p": 2.0,
        "2K": 2.5,
        "4K": 3.0,
        "Unknown": 0.5
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

    resolution_score = resolution_scores.get(resolution, 1.0)
    format_score = format_scores.get(format, 0.1)

    max_latency = 10.0  # 最大延迟（秒）
    max_download_speed = 80.0  # 最大下载速度（Mbps）

    latency_score = max(0, 1 - (latency / max_latency))  # 延迟越低，分数越高
    download_speed_score = min(download_speed / max_download_speed, 1)  # 下载速度越高，分数越高

    score = (weight_latency * latency_score +
             weight_download_speed * download_speed_score +
             weight_resolution * resolution_score +
             weight_format * format_score +
             weight_stability * stability +
             weight_success_rate * success_rate)

    total_score = round(previous_score + score, 4)  # 结合之前的评分并保留4位小数

    return total_score

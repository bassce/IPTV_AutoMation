import subprocess
import time
import re

def convert_to_kb(size, unit):
    size = float(size)
    unit = unit.lower()
    if 'm' in unit:
        return size * 1024
    elif 'g' in unit:
        return size * 1024 * 1024
    elif 'k' in unit:
        return size
    else:
        return size / 1024

def test_download_speed(url, duration=10, threads=4, ignore_initial_seconds=2):
    command = [
        'ffmpeg',
        '-threads', str(threads),
        '-i', url,
        '-t', str(duration),
        '-f', 'null',
        '-loglevel', 'info',
        '-'
    ]
    try:
        start_time = time.time()
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=duration + 2)
        elapsed_time = time.time() - start_time

        # 忽略初始波动时间
        effective_time = max(elapsed_time - ignore_initial_seconds, 0.001)

        stderr_output = result.stderr
        video_match = re.search(r'video:\s*([\d\.]+)([kKMG]?i?B)', stderr_output)
        audio_match = re.search(r'audio:\s*([\d\.]+)([kKMG]?i?B)', stderr_output)

        video_size = convert_to_kb(video_match.group(1), video_match.group(2)) if video_match else 0
        audio_size = convert_to_kb(audio_match.group(1), audio_match.group(2)) if audio_match else 0
        total_size = video_size + audio_size

        download_speed = round(total_size / effective_time) if effective_time > 0 else 0

        return {
            "total_size_kb": total_size,
            "elapsed_time_s": elapsed_time,
            "effective_time_s": effective_time,
            "download_speed_kb_s": download_speed
        }

    except subprocess.TimeoutExpired:
        return {"error": "Timeout occurred"}
    except Exception as e:
        return {"error": str(e)}

# 示例使用
url = "https://livestream-bt.nmtv.cn/nmtv/2314general.m3u8?txSecret=dc348a27bd36fe1bd63562af5e7269ea&txTime=771EF880"  # 替换为实际的直播源URL
test_result = test_download_speed(url)
print(test_result)

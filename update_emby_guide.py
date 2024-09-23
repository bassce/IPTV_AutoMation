import requests
import os

# 从环境变量中获取 Emby server URL 和 API key
EMBY_SERVER_URL = os.getenv('EMBY_SERVER_URL')
API_KEY = os.getenv('API_KEY')

# 检查是否有必要的环境变量
if not EMBY_SERVER_URL or not API_KEY:
    print("EMBY_SERVER_URL or API_KEY is not set. Skipping guide refresh.")
else:
    # 获取 Emby 的 "Refresh Guide" 任务 ID
    def get_refresh_guide_task_id():
        try:
            response = requests.get(
                f'{EMBY_SERVER_URL}/emby/ScheduledTasks',
                params={'api_key': API_KEY}
            )
            response.raise_for_status()
            tasks = response.json()

            # 遍历所有任务，找到与 "Refresh Guide" 相关的任务 ID
            for task in tasks:
                if task['Name'] == 'Refresh Guide':
                    return task['Id']
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching scheduled tasks: {e}")
            return None

    # 触发 "Refresh Guide" 任务
    def trigger_refresh_guide(task_id):
        try:
            response = requests.post(
                f'{EMBY_SERVER_URL}/emby/ScheduledTasks/Running/{task_id}',
                params={'api_key': API_KEY}
            )
            response.raise_for_status()
            print("Guide refresh triggered successfully!")
        except requests.exceptions.RequestException as e:
            print(f"Error triggering guide refresh: {e}")

    if __name__ == '__main__':
        task_id = get_refresh_guide_task_id()
        if task_id:
            print(f"Found 'Refresh Guide' task with ID: {task_id}")
            trigger_refresh_guide(task_id)
        else:
            print("Could not find 'Refresh Guide' task.")

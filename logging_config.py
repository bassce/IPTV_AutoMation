import logging
import os
from logging.handlers import RotatingFileHandler

# 检查并创建 logs 目录
log_dir = './data/logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 设置日志轮转的文件大小和保留的文件数量
log_file = os.path.join(log_dir, 'project.log')

# 创建一个 RotatingFileHandler
handler = RotatingFileHandler(
    filename=log_file,  # 日志文件路径
    maxBytes=5 * 1024 * 1024,  # 每个日志文件最大5MB
    backupCount=3,  # 最多保留3个备份日志文件
    encoding='utf-8',  # 设置编码格式为 utf-8
    delay=True  # 等到日志写入时才创建文件
)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# 获取 logger 对象并配置
logger = logging.getLogger()
logger.setLevel(logging.INFO)  # 设置日志等级为 INFO
logger.addHandler(handler)

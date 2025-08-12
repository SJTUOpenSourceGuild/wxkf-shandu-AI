import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger("my_logger")
logger.setLevel(logging.DEBUG)

# 创建文件处理器（FileHandler），指定文件名
# 按时间切割（每天午夜切割，保留 7 天日志）
file_handler = TimedRotatingFileHandler("./logs/app.log", when="midnight", interval=1, backupCount=7)  # 默认模式为 'a'（追加）
file_handler.setLevel(logging.DEBUG)  # 设置处理器的日志级别

# 定义日志格式
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# 将处理器添加到 Logger
logger.addHandler(file_handler)

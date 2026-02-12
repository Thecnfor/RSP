"""
全局日志处理系统 - 任务控制中心专用版
功能：全静默控制台，仅输出持久化文件日志
"""

import logging
import os
import tomllib
from datetime import datetime

# --- 默认配置 (当 config.toml 读取失败时使用) ---
DEFAULT_LOG_DIR = r"x:\share\ksp\logs"
DEFAULT_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
DEFAULT_DATE_FMT = "%Y-%m-%d %H:%M:%S"
CONFIG_PATH = r"x:\share\ksp\config.toml"


class MissionLogger:
    _initialized = False

    @classmethod
    def _load_config(cls):
        """独立读取配置以避免循环导入"""
        try:
            with open(CONFIG_PATH, "rb") as f:
                config = tomllib.load(f)
                return config.get("logging", {})
        except:
            return {}

    @classmethod
    def setup_logger(cls):
        if cls._initialized:
            return

        cfg = cls._load_config()

        # 获取配置参数
        log_dir = cfg.get("log_dir", DEFAULT_LOG_DIR)
        log_format = cfg.get("log_format", DEFAULT_FORMAT)
        date_format = cfg.get("date_format", DEFAULT_DATE_FMT)
        log_level = cfg.get("log_level", "INFO").upper()
        console_out = cfg.get("console_output", False)

        # 1. 确保日志目录存在
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # 2. 生成带时间戳的唯一文件名 (每次启动都不同)
        # 格式: mission_20240211_143005.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"mission_{timestamp}.log")

        # 3. 配置根日志器
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        # 4. 创建文件处理器 (使用普通 FileHandler 保证单次启动唯一性)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(log_format, date_format))

        # 5. 清除现有的处理器
        if logger.hasHandlers():
            logger.handlers.clear()

        # 6. 添加处理器
        logger.addHandler(file_handler)

        # 如果配置要求，添加控制台输出
        if console_out:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(log_format, date_format))
            logger.addHandler(console_handler)

        cls._initialized = True
        logging.info(
            f"--- 航天控制系统启动 | 日志文件: {os.path.basename(log_file)} ---"
        )


# 自动初始化
MissionLogger.setup_logger()


def Rlogger(name):
    """
    获取带命名的 logger 实例
    用法：logger = Rlogger("OrbitalCalc")
    """
    return logging.getLogger(name)

"""
Utility 模块：航天任务支持工具包
"""

# 1. 内部转发 (Promotion)
from .log import Rlogger
from .utils import Utils
from .config import config
from .dashboard import Dashboard

# 2. 定义对外暴露的接口
__all__ = [
    "Rlogger",
    "Utils",
    "config",
    "Dashboard"
]

# 3. 蓝桥杯进阶知识点：
# 当外部使用 `from utility import *` 时，只有 __all__ 列表里的成员会被导入。
# 这能有效防止内部临时变量（如 os, sys 等）污染调用者的命名空间。
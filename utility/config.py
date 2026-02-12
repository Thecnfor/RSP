"""
全局配置加载器
"""

import tomllib
from .log import Rlogger

CONFIG_PATH = r"x:\share\ksp\config.toml"


def Tomlconfig():
    """全局配置加载器"""
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        Rlogger("Config").error(f"【配置加载失败】请检查 {CONFIG_PATH}: {e}")
        return {}


# 预加载全局单例配置
config = Tomlconfig()

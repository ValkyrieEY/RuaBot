"""数据源 - 获取运行时间等信息"""
from datetime import datetime
import sys
import os

# 尝试从框架获取启动时间
CURRENT_TIMEZONE = datetime.now().astimezone().tzinfo

_framework_start_time: datetime | None = None


def set_framework_start_time(start_time: datetime):
    """设置框架启动时间（由插件主文件调用）"""
    global _framework_start_time
    _framework_start_time = start_time


def get_framework_start_time() -> datetime:
    """获取框架启动时间点"""
    global _framework_start_time
    if _framework_start_time is None:
        # 如果未设置，使用当前时间（作为后备）
        _framework_start_time = datetime.now(CURRENT_TIMEZONE)
    return _framework_start_time


def get_bot_uptime() -> int:
    """获取 Bot 运行时长（秒）"""
    start_time = get_framework_start_time()
    current_time = datetime.now(CURRENT_TIMEZONE)
    delta = current_time - start_time

    return int(delta.total_seconds())


def format_uptime(total_seconds: int) -> str:
    """将 Bot 运行时长转换为可读形式"""
    hours = total_seconds // 3600
    if hours >= 24:
        days, remaining_hours = divmod(hours, 24)
        return f"已运行 {days} 天 {remaining_hours} 小时"
    else:
        minutes = (total_seconds % 3600) // 60
        return f"已运行 {hours} 时 {minutes} 分"


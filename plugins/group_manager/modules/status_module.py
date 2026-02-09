"""运行状态模块"""

import platform
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class StatusModule:
    """运行状态模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
        
        # 记录启动时间
        self.start_time = time.time()
        
        # 记录消息处理统计
        self.message_count = 0
        self.message_count_by_day = {}  # {日期: 消息数}
    
    def record_message(self):
        """记录处理的消息"""
        self.message_count += 1
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.message_count_by_day:
            self.message_count_by_day[today] = 0
        self.message_count_by_day[today] += 1
    
    def get_uptime(self) -> str:
        """获取在线时长"""
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        if days > 0:
            return f"{days}天{hours}小时{minutes}分钟"
        elif hours > 0:
            return f"{hours}小时{minutes}分钟{seconds}秒"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"
    
    def get_cpu_usage(self) -> str:
        """获取CPU使用率"""
        if not PSUTIL_AVAILABLE:
            return "psutil未安装，无法获取CPU使用率"
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            result = f"CPU使用率: {cpu_percent:.1f}%\n"
            result += f"CPU核心数: {cpu_count}\n"
            if cpu_freq:
                result += f"CPU频率: {cpu_freq.current:.0f} MHz"
            return result
        except Exception as e:
            return f"获取CPU信息失败: {e}"
    
    def get_memory_usage(self) -> str:
        """获取内存使用率"""
        if not PSUTIL_AVAILABLE:
            return "psutil未安装，无法获取内存使用率"
        
        try:
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            
            total_gb = memory.total / (1024 ** 3)
            used_gb = memory.used / (1024 ** 3)
            available_gb = memory.available / (1024 ** 3)
            process_mb = process_memory.rss / (1024 ** 2)
            
            result = f"系统内存使用率: {memory.percent:.1f}%\n"
            result += f"总内存: {total_gb:.2f} GB\n"
            result += f"已用内存: {used_gb:.2f} GB\n"
            result += f"可用内存: {available_gb:.2f} GB\n"
            result += f"本进程内存: {process_mb:.2f} MB"
            return result
        except Exception as e:
            return f"获取内存信息失败: {e}"
    
    def get_disk_usage(self) -> str:
        """获取磁盘使用率"""
        if not PSUTIL_AVAILABLE:
            return "psutil未安装，无法获取磁盘使用率"
        
        try:
            # Windows 使用 C: 盘，Linux/Mac 使用 /
            if platform.system() == "Windows":
                disk_path = "C:"
            else:
                disk_path = "/"
            
            disk_usage = psutil.disk_usage(disk_path)
            
            total_gb = disk_usage.total / (1024 ** 3)
            used_gb = disk_usage.used / (1024 ** 3)
            free_gb = disk_usage.free / (1024 ** 3)
            
            result = f"磁盘使用率: {disk_usage.percent:.1f}%\n"
            result += f"总容量: {total_gb:.2f} GB\n"
            result += f"已用: {used_gb:.2f} GB\n"
            result += f"可用: {free_gb:.2f} GB"
            return result
        except Exception as e:
            return f"获取磁盘信息失败: {e}"
    
    def get_message_stats(self) -> str:
        """获取处理消息数统计"""
        today = datetime.now().strftime('%Y-%m-%d')
        today_count = self.message_count_by_day.get(today, 0)
        
        result = f"总处理消息数: {self.message_count}\n"
        result += f"今日处理消息数: {today_count}"
        return result
    
    def get_plugin_status(self) -> str:
        """获取插件状态"""
        try:
            # 获取插件列表（这里需要根据实际情况调整）
            result = "插件状态:\n"
            result += f"运行时长: {self.get_uptime()}\n"
            result += f"系统: {platform.system()} {platform.release()}\n"
            result += f"Python版本: {platform.python_version()}"
            return result
        except Exception as e:
            return f"获取插件状态失败: {e}"
    
    async def handle_command(self, event: Dict, raw_message: str) -> bool:
        """处理运行状态相关命令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        
        # 只有主人和管理员可以使用
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        raw_message = raw_message.strip()
        
        if raw_message == "CPU使用率":
            try:
                cpu_info = self.get_cpu_usage()
                await self.api.send_group_msg(group_id, cpu_info)
            except Exception as e:
                await self.api.send_group_msg(group_id, f"获取CPU使用率失败: {e}")
            return True
        
        elif raw_message == "内存使用率":
            try:
                memory_info = self.get_memory_usage()
                await self.api.send_group_msg(group_id, memory_info)
            except Exception as e:
                await self.api.send_group_msg(group_id, f"获取内存使用率失败: {e}")
            return True
        
        elif raw_message == "磁盘使用率":
            try:
                disk_info = self.get_disk_usage()
                await self.api.send_group_msg(group_id, disk_info)
            except Exception as e:
                await self.api.send_group_msg(group_id, f"获取磁盘使用率失败: {e}")
            return True
        
        elif raw_message == "在线时长":
            try:
                uptime = self.get_uptime()
                await self.api.send_group_msg(group_id, f"在线时长: {uptime}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"获取在线时长失败: {e}")
            return True
        
        elif raw_message == "处理消息数":
            try:
                stats = self.get_message_stats()
                await self.api.send_group_msg(group_id, stats)
            except Exception as e:
                await self.api.send_group_msg(group_id, f"获取消息统计失败: {e}")
            return True
        
        elif raw_message == "插件状态":
            try:
                status = self.get_plugin_status()
                await self.api.send_group_msg(group_id, status)
            except Exception as e:
                await self.api.send_group_msg(group_id, f"获取插件状态失败: {e}")
            return True
        
        return False


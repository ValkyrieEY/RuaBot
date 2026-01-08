"""QQ名片点赞插件 - 适配自 Xiaoyi_QQ

功能：
- 给用户QQ名片点赞10次
- 每天限制10次
- 支持"赞我"、"超我"、"超湿我"触发词
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Dict, Any


class LikePlugin:
    """QQ名片点赞插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        self._update_config(config)
        self.user_data = {}
    
    def _update_config(self, config: Dict[str, Any]):
        """更新配置
        
        Args:
            config: 新的配置字典
        """
        self.config = config
        self.bot_name = config.get('bot_name', '机器人')
        self.reminder = config.get('reminder', '')
    
    async def on_load(self):
        """插件加载时调用"""
        # 从存储加载数据
        data_bytes = await self.api.get_storage('like_data')
        if data_bytes:
            try:
                self.user_data = json.loads(data_bytes.decode('utf-8'))
                self.api.log("info", f"已加载 {len(self.user_data)} 个用户的数据")
            except Exception as e:
                self.api.log("error", f"加载数据失败: {e}")
                self.user_data = {}
        else:
            self.user_data = {}
        
        self.api.log("info", "QQ名片点赞插件加载成功")
    
    async def on_unload(self):
        """插件卸载时调用"""
        # 保存数据到存储
        try:
            data_bytes = json.dumps(self.user_data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('like_data', data_bytes)
            self.api.log("info", "数据已保存")
        except Exception as e:
            self.api.log("error", f"保存数据失败: {e}")
    
    async def on_event(self, event_name: str, data: Dict[str, Any]):
        """处理事件"""
        if event_name == "onebot.message":
            await self.handle_message(data)
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件"""
        try:
            message_type = event.get('message_type')  # 'private' or 'group'
            raw_message = event.get('raw_message', '').strip()
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            
            # 处理"赞我"
            if raw_message == "赞我":
                await self.handle_like(user_id, group_id, message_type, "赞")
                return
            
            # 处理"超我"或"超湿我"
            elif raw_message in ["超我", "超湿我"]:
                await self.handle_like(user_id, group_id, message_type, "超")
                return
            
            # 处理"点赞信息"
            elif raw_message == f"{self.reminder}点赞信息":
                await self.handle_like_info(user_id, group_id, message_type)
                return
            
            # 处理"超信息"
            elif raw_message == f"{self.reminder}超信息":
                await self.handle_like_info(user_id, group_id, message_type, is_cha=True)
                return
        
        except Exception as e:
            self.api.log("error", f"处理消息时出错: {e}")
    
    def can_like_today(self, user_id: int) -> bool:
        """检查今天是否可以点赞"""
        user_id_str = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if user_id_str not in self.user_data:
            self.user_data[user_id_str] = {"last_date": today, "count": 0}
            return True
        
        if self.user_data[user_id_str].get("last_date") != today:
            self.user_data[user_id_str] = {"last_date": today, "count": 0}
            return True
        
        return self.user_data[user_id_str].get("count", 0) < 10
    
    def get_remaining_likes(self, user_id: int) -> int:
        """获取剩余点赞次数"""
        user_id_str = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if user_id_str not in self.user_data or self.user_data[user_id_str].get("last_date") != today:
            return 10
        
        return 10 - self.user_data[user_id_str].get("count", 0)
    
    def record_like(self, user_id: int, times: int = 1):
        """记录点赞"""
        user_id_str = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if user_id_str not in self.user_data or self.user_data[user_id_str].get("last_date") != today:
            self.user_data[user_id_str] = {"last_date": today, "count": times}
        else:
            self.user_data[user_id_str]["count"] = self.user_data[user_id_str].get("count", 0) + times
        
        # 异步保存数据
        asyncio.create_task(self._save_data())
    
    async def _save_data(self):
        """保存数据到存储"""
        try:
            data_bytes = json.dumps(self.user_data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('like_data', data_bytes)
        except Exception as e:
            self.api.log("error", f"保存数据失败: {e}")
    
    def get_like_info(self, user_id: int) -> str:
        """获取点赞信息"""
        user_id_str = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if user_id_str not in self.user_data or self.user_data[user_id_str].get("last_date") != today:
            return "你今天还没有被点过赞哦！今日还可点赞10次~"
        
        count = self.user_data[user_id_str].get("count", 0)
        return f"你今天已被点赞 {count} 次！\n剩余可点赞次数: {10 - count}次"
    
    async def handle_like(self, user_id: int, group_id: int, message_type: str, action_type: str):
        """处理点赞请求"""
        if not self.can_like_today(user_id):
            msg = f"今天已经给你点过10次{'赞' if action_type == '赞' else '超'}啦，明天再来吧~ (๑•́ ₃ •̀๑)"
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, msg)
            elif message_type == 'group':
                await self.api.send_group_msg(group_id, msg)
            return
        
        try:
            # 执行点赞（循环55次，但只记录10次）
            success_count = 0
            max_attempts = 55
            daily_limit_reached = False
            
            for i in range(max_attempts):
                try:
                    result = await self.api.send_like(user_id, times=1)
                    if result and result.get('success'):
                        success_count += 1
                    else:
                        error = result.get('error', '') if result else 'Unknown error'
                        error_str = str(error)
                        # 检查是否是QQ平台每日点赞上限（retcode 1200）
                        if '1200' in error_str or '点赞数已达上限' in error_str or '已达上限' in error_str:
                            # QQ平台每日点赞上限
                            daily_limit_reached = True
                            self.api.log("info", f"达到QQ平台每日点赞上限，已成功点赞 {success_count} 次")
                            break
                        else:
                            self.api.log("warning", f"点赞失败: {error}")
                except Exception as e:
                    error_str = str(e)
                    # 检查是否是QQ平台每日点赞上限（retcode 1200）
                    if '1200' in error_str or '点赞数已达上限' in error_str or '已达上限' in error_str:
                        # QQ平台每日点赞上限
                        daily_limit_reached = True
                        self.api.log("info", f"达到QQ平台每日点赞上限，已成功点赞 {success_count} 次")
                        break
                    else:
                        self.api.log("warning", f"点赞异常: {e}")
                
                # 如果已经成功10次，也停止（避免超过限制）
                if success_count >= 10:
                    break
                
                delay = random.uniform(0.1, 0.5)
                await asyncio.sleep(delay)
            
            # 记录点赞（实际成功次数，最多10次）
            actual_likes = min(success_count, 10)
            self.record_like(user_id, actual_likes)
            
            remaining = self.get_remaining_likes(user_id)
            
            if action_type == "赞":
                if daily_limit_reached:
                    success_msg = f"成功给你的名片点赞{actual_likes}次啦！{self.bot_name}最喜欢你啦！记得回赞哦！(◍•ᴗ•◍)❤\n（已达到QQ平台每日点赞上限，无法继续点赞）"
                else:
                    success_msg = f"成功给你的名片点赞{actual_likes}次啦！{self.bot_name}最喜欢你啦！记得回赞哦！(◍•ᴗ•◍)❤"
            else:
                if daily_limit_reached:
                    success_msg = f"已经为你超了{actual_likes}下哦，记得回捏~ (◍•ᴗ•◍)❤\n（已达到QQ平台每日点赞上限，无法继续点赞）"
                else:
                    success_msg = f"已经为你超了{actual_likes}下哦，记得回捏~ (◍•ᴗ•◍)❤"
            
            if remaining > 0:
                success_msg += f"\n今日还可{'点赞' if action_type == '赞' else '超'}{remaining}次"
            else:
                success_msg += f"\n今日{'点赞' if action_type == '赞' else '超'}已达上限啦~"
            
            # 发送成功消息
            if message_type == 'private':
                await self.api.send_private_msg(user_id, success_msg)
            elif message_type == 'group':
                await self.api.send_group_msg(group_id, success_msg)
                
                # 在群里@用户
                at_msg = f"[CQ:at,qq={user_id}] 你的名片已获得{self.bot_name}的10次{'点赞' if action_type == '赞' else '超'}！(≧▽≦)/"
                await self.api.send_group_msg(group_id, at_msg)
        
        except Exception as e:
            self.api.log("error", f"{'点赞' if action_type == '赞' else '超'}操作失败: {e}")
            error_msg = f"{'点赞' if action_type == '赞' else '超'}失败啦...可能是机器人没有权限(｡•́︿•̀｡) 错误: {str(e)}"
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, error_msg)
            elif message_type == 'group':
                await self.api.send_group_msg(group_id, error_msg)
    
    async def handle_like_info(self, user_id: int, group_id: int, message_type: str, is_cha: bool = False):
        """处理点赞信息查询"""
        info = self.get_like_info(user_id)
        if is_cha:
            info = info.replace("点赞", "超").replace("赞", "超")
        
        if message_type == 'private':
            await self.api.send_private_msg(user_id, info)
        elif message_type == 'group':
            await self.api.send_group_msg(group_id, info)


# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 实例
        config: 插件配置
        
    Returns:
        Plugin 实例
    """
    plugin = LikePlugin(api, config)
    await plugin.on_load()
    return plugin


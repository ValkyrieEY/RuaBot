"""SoGood 评价插件 - 适配自 Xiaoyi_QQ

功能：
- 评价用户今天的表现（随机评分）
- 发电功能（对某人表达内心深处的诉求）
"""

import asyncio
import json
import random
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class UserInfo:
    """用户信息"""
    goodness: int
    time: int
    
    @property
    def level(self) -> str:
        """根据评分返回等级"""
        if 0 <= self.goodness <= 20:
            return "嗯~今天表现不乖，下次一定要听话哦"
        elif 20 < self.goodness <= 40:
            return "看着顺眼"
        elif 40 < self.goodness <= 60:
            return "亲爱的太棒啦！"
        elif 60 < self.goodness <= 80:
            return "来，抱一个~嗯~"
        else:
            return "👍_ _ _👍"
    
    @classmethod
    def build(cls) -> "UserInfo":
        """创建新的用户信息（随机评分）"""
        return cls(random.randint(0, 100), int(time.time()))


class SoGoodPlugin:
    """SoGood 评价插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        self.reminder = config.get('reminder', '')
        self.users: Dict[str, UserInfo] = {}
        self.words: list = []
    
    async def on_load(self):
        """插件加载时调用"""
        # 加载用户数据
        data_bytes = await self.api.get_storage('user_scores')
        if data_bytes:
            try:
                data = json.loads(data_bytes.decode('utf-8'))
                # 重建 UserInfo 对象
                for user_id, info in data.items():
                    self.users[user_id] = UserInfo(info['goodness'], info['time'])
                self.api.log("info", f"已加载 {len(self.users)} 个用户的评分数据")
            except Exception as e:
                self.api.log("error", f"加载用户数据失败: {e}")
                self.users = {}
        else:
            self.users = {}
        
        # 加载发电词汇
        words_bytes = await self.api.get_storage('words')
        if words_bytes:
            try:
                words_data = json.loads(words_bytes.decode('utf-8'))
                self.words = words_data.get('ele', [])
                self.api.log("info", f"已加载 {len(self.words)} 条发电词汇")
            except Exception as e:
                self.api.log("warning", f"加载发电词汇失败: {e}，使用默认词汇")
                self.words = self._get_default_words()
        else:
            self.words = self._get_default_words()
            # 保存默认词汇
            await self._save_words()
        
        self.api.log("info", "SoGood 评价插件加载成功")
    
    def _get_default_words(self) -> list:
        """获取默认发电词汇"""
        return [
            "{target_name}，你今天真棒！",
            "{target_name}，我好喜欢你~",
            "{target_name}，你太可爱了！",
            "{target_name}，你是我心中的小太阳~",
            "{target_name}，今天也要加油哦！"
        ]
    
    async def _save_words(self):
        """保存发电词汇"""
        try:
            words_data = {"ele": self.words}
            data_bytes = json.dumps(words_data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('words', data_bytes)
        except Exception as e:
            self.api.log("error", f"保存发电词汇失败: {e}")
    
    async def on_unload(self):
        """插件卸载时调用"""
        # 保存用户数据
        try:
            data = {}
            for user_id, info in self.users.items():
                data[user_id] = {
                    'goodness': info.goodness,
                    'time': info.time
                }
            data_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('user_scores', data_bytes)
            self.api.log("info", "用户评分数据已保存")
        except Exception as e:
            self.api.log("error", f"保存用户数据失败: {e}")
    
    async def on_event(self, event_name: str, data: Dict[str, Any]):
        """处理事件"""
        if event_name == "onebot.message":
            await self.handle_message(data)
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件"""
        try:
            message_type = event.get('message_type')
            raw_message = event.get('raw_message', '')
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            message = event.get('message', [])  # 消息段数组
            message_id = event.get('message_id')  # 消息ID（用于回复）
            
            # 处理"今天棒不棒"
            if "今天棒不棒" in raw_message:
                await self.handle_rating(user_id, group_id, message_type, raw_message, message)
                return
            
            # 处理"发电"
            if raw_message.startswith(f"{self.reminder}发电"):
                await self.handle_power(user_id, group_id, message_type, raw_message, message, message_id)
                return
        
        except Exception as e:
            self.api.log("error", f"处理消息时出错: {e}")
    
    async def handle_rating(self, user_id: int, group_id: int, message_type: str, raw_message: str, message: list):
        """处理评分请求"""
        name = ""
        target_uin = None
        
        # 检查是否是"我"
        if "我" in raw_message:
            name = "\n你"
            target_uin = str(user_id)
        else:
            # 尝试从消息中获取@的用户
            if isinstance(message, list):
                for msg_part in message:
                    if isinstance(msg_part, dict) and msg_part.get('type') == 'at':
                        target_uin = str(msg_part.get('data', {}).get('qq', ''))
                        break
        
        # 如果找不到，使用发送者ID
        if not target_uin:
            target_uin = str(user_id)
            name = "\n你"
        
        # 获取或创建用户信息
        if target_uin not in self.users:
            self.users[target_uin] = UserInfo.build()
            # 异步保存
            asyncio.create_task(self._save_user_data())
        
        user_info = self.users[target_uin]
        
        # 构建回复消息
        if message_type == 'group':
            reply = f"[CQ:at,qq={target_uin}]{name}今天的分数: {user_info.goodness}\n评级: {user_info.level}"
            result = await self.api.send_group_msg(group_id, reply)
        else:
            reply = f"{name}今天的分数: {user_info.goodness}\n评级: {user_info.level}"
            result = await self.api.send_private_msg(user_id, reply)
        
        if result.get('success'):
            self.api.log("info", f"已回复评分: {target_uin} = {user_info.goodness}")
        else:
            self.api.log("error", f"发送评分消息失败: {result.get('error')}")
    
    async def handle_power(self, user_id: int, group_id: int, message_type: str, raw_message: str, message: list, message_id: Optional[int] = None):
        """处理发电请求"""
        target_uin = None
        tag = ""
        
        # 尝试从消息中获取@的用户
        if isinstance(message, list):
            for msg_part in message:
                if isinstance(msg_part, dict) and msg_part.get('type') == 'at':
                    target_uin = int(msg_part.get('data', {}).get('qq', 0))
                    break
        
        if target_uin:
            # 获取用户昵称
            try:
                result = await self.api.get_stranger_info(target_uin)
                if result.get('success'):
                    user_data = result.get('data', {})
                    if isinstance(user_data, dict):
                        tag = f"@{user_data.get('nickname', str(target_uin))}"
                    else:
                        tag = f"@{target_uin}"
                else:
                    tag = f"@{target_uin}"
            except Exception as e:
                self.api.log("warning", f"获取用户信息失败: {e}")
                tag = f"@{target_uin}"
        else:
            # 从消息中提取名字
            tag = raw_message.replace(f"{self.reminder}发电", "", 1).strip()
            if not tag:
                tag = "你"
        
        # 随机选择一条发电词汇
        if self.words:
            word = random.choice(self.words).replace("{target_name}", tag)
        else:
            word = f"{tag}，你今天真棒！"
        
        # 发送消息
        if message_type == 'group':
            # 如果有 message_id，尝试回复原消息
            if message_id:
                reply_msg = f"[CQ:reply,id={message_id}]{word}"
            else:
                reply_msg = word
            result = await self.api.send_group_msg(group_id, reply_msg)
        else:
            result = await self.api.send_private_msg(user_id, word)
        
        if result.get('success'):
            self.api.log("info", f"已发送发电消息: {tag}")
        else:
            self.api.log("error", f"发送发电消息失败: {result.get('error')}")
    
    async def _save_user_data(self):
        """保存用户数据"""
        try:
            data = {}
            for user_id, info in self.users.items():
                data[user_id] = {
                    'goodness': info.goodness,
                    'time': info.time
                }
            data_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('user_scores', data_bytes)
        except Exception as e:
            self.api.log("error", f"保存用户数据失败: {e}")


# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 实例
        config: 插件配置
        
    Returns:
        Plugin 实例
    """
    plugin = SoGoodPlugin(api, config)
    await plugin.on_load()
    return plugin


"""数据管理器 - 负责所有数据的存储和读取"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class DataManager:
    """群管插件数据管理器"""
    
    def __init__(self, api):
        """初始化数据管理器
        
        Args:
            api: PluginAPI 实例
        """
        self.api = api
        
        # 数据存储目录
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # 授权数据
        self.group_auth: Dict[str, Dict] = {}  # {group_id: {authorized: bool, expire_date: str, auto_leave: bool}}
        
        # 权限数据
        self.permissions: Dict[str, Dict] = {}  # {group_id: {owners: [], admins: [], managers: []}}
        
        # 入群设置
        self.join_settings: Dict[str, Dict] = {}  # {group_id: {welcome_enabled: bool, mute_enabled: bool, ...}}
        
        # 入群验证
        self.verify_settings: Dict[str, Dict] = {}  # {group_id: {enabled: bool, verify_type: str, time: int}}
        self.verify_users: Dict[str, Dict] = {}  # {group_id: {user_id: timestamp}}
        
        # 刷屏检测
        self.spam_settings: Dict[str, Dict] = {}  # {group_id: {enabled: bool, times: int, window: int}}
        self.spam_records: Dict[str, Dict] = {}  # {group_id: {user_id: [timestamps]}}
        
        # 基础群管设置
        self.basic_settings: Dict[str, Dict] = {}  # {group_id: {kick_blacklist: bool, leave_blacklist: bool, ...}}
        
        # 撤回自身设置
        self.recall_self_settings: Dict[str, Dict] = {}  # {group_id: {enabled: bool, interval: int}}
        
        # 警告系统
        self.warnings: Dict[str, Dict] = {}  # {group_id: {user_id: count}}
        self.warning_settings: Dict[str, Dict] = {}  # {group_id: {max_warnings: int, action: str}}
        
        # 留言反馈
        self.messages: List[Dict] = []  # [{id: int, user_id: int, group_id: int, content: str, type: str, time: str}]
        self.feedback_settings: Dict[str, Dict] = {}  # {group_id: {enabled: bool, notify_enabled: bool}}
        
        # 名片系统
        self.card_locks: Dict[str, Dict] = {}  # {group_id: {user_id: card_name}}
        self.card_settings: Dict[str, Dict] = {}  # {group_id: {auto_rename: bool, prefix: str}}
        
        # 黑白名单
        self.blacklist: Dict[str, List] = {'global': [], 'groups': {}}  # 黑名单
        self.whitelist: Dict[str, List] = {'global': [], 'groups': {}}  # 白名单
        self.blacklist_actions: Dict[str, str] = {'global': '提示', 'groups': {}}  # 黑名单处理方式 {group_id: '提示'/'禁言'/'踢出'}
        
        # 违禁词
        self.banned_words: Dict[str, Dict] = {
            'global': {'fuzzy': {}, 'exact': {}},
            'groups': {}  # {group_id: {fuzzy: {}, exact: {}}}
        }
        
        # 问答系统
        self.qa_system: Dict[str, Dict] = {
            'global': {'fuzzy': {}, 'exact': {}, 'enabled': True},
            'groups': {}  # {group_id: {fuzzy: {}, exact: {}, enabled: True}}
        }
        
        # 撤回/禁言/踢出系统
        self.recall_settings: Dict[str, Dict] = {}  # {group_id: {image: bool, voice: bool, ...}}
        self.mute_settings: Dict[str, Dict] = {}
        self.kick_settings: Dict[str, Dict] = {}
        
        # 提示系统
        self.notification_settings: Dict[str, Dict] = {}  # {group_id: {join: bool, leave: bool, ...}}
        
        # 卡密系统
        self.card_keys: Dict[str, Dict] = {}  # {key: {days: int, used: bool, used_by: str, used_time: str}}
        
        # 头衔系统
        self.title_settings: Dict[str, Dict] = {}  # {group_id: {auto_enabled: bool, banned_words: []}}
        
        # 回复设置
        self.reply_settings: Dict[str, Dict] = {}  # {group_id: {at_reply: bool, silent_mode: bool}}
        
        # 消息记录（用于批量撤回）
        self.message_records: Dict[str, List] = {}  # {group_id: [{message_id: int, time: str, user_id: int}]}
    
    async def load_all_data(self):
        """加载所有数据"""
        try:
            # 加载授权数据
            data = await self._load_json('group_auth')
            self.group_auth = data if data else {}
            
            # 加载权限数据
            data = await self._load_json('permissions')
            self.permissions = data if data else {}
            
            # 加载入群设置
            data = await self._load_json('join_settings')
            self.join_settings = data if data else {}
            
            # 加载验证设置
            data = await self._load_json('verify_settings')
            self.verify_settings = data if data else {}
            
            data = await self._load_json('verify_users')
            self.verify_users = data if data else {}
            
            # 加载刷屏检测
            data = await self._load_json('spam_settings')
            self.spam_settings = data if data else {}
            
            data = await self._load_json('spam_records')
            self.spam_records = data if data else {}
            
            # 加载警告系统
            data = await self._load_json('warnings')
            self.warnings = data if data else {}
            
            data = await self._load_json('warning_settings')
            self.warning_settings = data if data else {}
            
            # 加载留言反馈
            data = await self._load_json('messages')
            self.messages = data if data else []
            
            data = await self._load_json('feedback_settings')
            self.feedback_settings = data if data else {}
            
            # 加载名片系统
            data = await self._load_json('card_locks')
            self.card_locks = data if data else {}
            
            data = await self._load_json('card_settings')
            self.card_settings = data if data else {}
            
            # 加载黑白名单
            data = await self._load_json('blacklist')
            self.blacklist = data if data else {'global': [], 'groups': {}}
            
            data = await self._load_json('whitelist')
            self.whitelist = data if data else {'global': [], 'groups': {}}
            
            # 加载黑名单处理方式
            data = await self._load_json('blacklist_actions')
            self.blacklist_actions = data if data else {'global': '提示', 'groups': {}}
            
            # 加载违禁词
            data = await self._load_json('banned_words')
            self.banned_words = data if data else {'global': {'fuzzy': {}, 'exact': {}}, 'groups': {}}
            
            # 加载问答系统
            data = await self._load_json('qa_system')
            self.qa_system = data if data else {'global': {'fuzzy': {}, 'exact': {}, 'enabled': True}, 'groups': {}}
            
            # 加载撤回/禁言/踢出设置
            data = await self._load_json('recall_settings')
            self.recall_settings = data if data else {}
            
            data = await self._load_json('mute_settings')
            self.mute_settings = data if data else {}
            
            data = await self._load_json('kick_settings')
            self.kick_settings = data if data else {}
            
            # 加载提示系统
            data = await self._load_json('notification_settings')
            self.notification_settings = data if data else {}
            
            # 加载卡密系统
            data = await self._load_json('card_keys')
            self.card_keys = data if data else {}
            
            # 加载头衔系统
            data = await self._load_json('title_settings')
            self.title_settings = data if data else {}
            
            # 加载回复设置
            data = await self._load_json('reply_settings')
            self.reply_settings = data if data else {}
            
            # 加载基础群管设置
            data = await self._load_json('basic_settings')
            self.basic_settings = data if data else {}
            
            # 加载撤回自身设置
            data = await self._load_json('recall_self_settings')
            self.recall_self_settings = data if data else {}
            
            # 加载消息记录
            data = await self._load_json('message_records')
            self.message_records = data if data else {}
            
            self.api.log("info", "所有数据加载完成")
        except Exception as e:
            self.api.log("error", f"加载数据失败: {e}")
    
    async def save_all_data(self):
        """保存所有数据"""
        try:
            await self._save_json('group_auth', self.group_auth)
            await self._save_json('permissions', self.permissions)
            await self._save_json('join_settings', self.join_settings)
            await self._save_json('verify_settings', self.verify_settings)
            await self._save_json('verify_users', self.verify_users)
            await self._save_json('spam_settings', self.spam_settings)
            await self._save_json('warnings', self.warnings)
            await self._save_json('warning_settings', self.warning_settings)
            await self._save_json('messages', self.messages)
            await self._save_json('feedback_settings', self.feedback_settings)
            await self._save_json('card_locks', self.card_locks)
            await self._save_json('card_settings', self.card_settings)
            await self._save_json('blacklist', self.blacklist)
            await self._save_json('whitelist', self.whitelist)
            await self._save_json('blacklist_actions', self.blacklist_actions)
            await self._save_json('banned_words', self.banned_words)
            await self._save_json('qa_system', self.qa_system)
            await self._save_json('recall_settings', self.recall_settings)
            await self._save_json('mute_settings', self.mute_settings)
            await self._save_json('kick_settings', self.kick_settings)
            await self._save_json('notification_settings', self.notification_settings)
            await self._save_json('card_keys', self.card_keys)
            await self._save_json('title_settings', self.title_settings)
            await self._save_json('reply_settings', self.reply_settings)
            await self._save_json('spam_records', self.spam_records)
            await self._save_json('basic_settings', self.basic_settings)
            await self._save_json('recall_self_settings', self.recall_self_settings)
            
            # 保存消息记录（限制每个群最多保存1000条，避免文件过大）
            # 清理旧记录
            cleaned_records = {}
            for group_id, records in self.message_records.items():
                # 只保留最近1000条记录
                cleaned_records[group_id] = records[-1000:] if len(records) > 1000 else records
            await self._save_json('message_records', cleaned_records)
            
            self.api.log("info", "所有数据保存完成")
        except Exception as e:
            self.api.log("error", f"保存数据失败: {e}")
    
    async def _load_json(self, key: str) -> Optional[Any]:
        """从JSON文件加载数据"""
        try:
            file_path = self.data_dir / f"{key}.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.api.log("warning", f"加载{key}数据失败: {e}")
            return None
    
    async def _save_json(self, key: str, data: Any):
        """保存数据到JSON文件"""
        try:
            file_path = self.data_dir / f"{key}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.api.log("error", f"保存{key}数据失败: {e}")


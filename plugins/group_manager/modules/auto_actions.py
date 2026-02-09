"""违禁词检测、撤回、禁言、踢出系统模块"""

from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class BannedWordsModule:
    """违禁词检测模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理违禁词指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        group_id_str = str(group_id)
        
        # 开/关违禁检测
        if command in ["开违禁检测", "关违禁检测"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            if group_id_str not in self.data_manager.banned_words['groups']:
                self.data_manager.banned_words['groups'][group_id_str] = {
                    'enabled': True, 'fuzzy': {}, 'exact': {}, 'mute_duration': 600
                }
            
            enabled = command.startswith("开")
            self.data_manager.banned_words['groups'][group_id_str]['enabled'] = enabled
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}违禁检测")
            return True
        
        # 加模糊违禁词/加精准违禁词 (本群)
        elif raw_message.startswith(("加模糊", "加精准")) and "违禁词" in raw_message:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            is_fuzzy = raw_message.startswith("加模糊")
            
            # 提取类型和词
            parts = raw_message.split("违禁词")
            if len(parts) < 2:
                return False
            
            type_part = parts[0]  # 如 "加模糊撤回"
            words_part = parts[1].strip()  # 违禁词列表
            
            # 提取处罚类型
            if "撤回踢出" in type_part:
                action = "撤回踢出"
            elif "撤回禁言" in type_part:
                action = "撤回禁言"
            elif "撤回" in type_part:
                action = "撤回"
            else:
                action = "撤回"
            
            # 分割多个词
            words = utils.split_list_by_separator(words_part, '|')
            if not words:
                await self.api.send_group_msg(group_id, "请输入违禁词，多个用|分割")
                return True
            
            # 初始化
            if group_id_str not in self.data_manager.banned_words['groups']:
                self.data_manager.banned_words['groups'][group_id_str] = {
                    'enabled': True, 'fuzzy': {}, 'exact': {}, 'mute_duration': 600
                }
            
            word_type = 'fuzzy' if is_fuzzy else 'exact'
            for word in words:
                self.data_manager.banned_words['groups'][group_id_str][word_type][word] = action
            
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已添加{len(words)}个{'模糊' if is_fuzzy else '精准'}违禁词")
            return True
        
        # 全局违禁词（主人和管理员）
        elif raw_message.startswith("全局") and ("加模糊" in raw_message or "加精准" in raw_message):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作全局违禁词")
                return True
            
            is_fuzzy = "加模糊" in raw_message
            parts = raw_message.split("违禁词")
            if len(parts) < 2:
                return False
            
            type_part = parts[0]
            words_part = parts[1].strip()
            
            if "撤回踢出" in type_part:
                action = "撤回踢出"
            elif "撤回禁言" in type_part:
                action = "撤回禁言"
            else:
                action = "撤回"
            
            words = utils.split_list_by_separator(words_part, '|')
            word_type = 'fuzzy' if is_fuzzy else 'exact'
            
            for word in words:
                self.data_manager.banned_words['global'][word_type][word] = action
            
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已添加{len(words)}个全局{'模糊' if is_fuzzy else '精准'}违禁词")
            return True
        
        # 删模糊违禁词/删精准违禁词 (本群)
        elif raw_message.startswith(("删模糊", "删精准")) and "违禁词" in raw_message:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            is_fuzzy = raw_message.startswith("删模糊")
            
            # 提取词
            parts = raw_message.split("违禁词")
            if len(parts) < 2:
                return False
            
            words_part = parts[1].strip()
            words = utils.split_list_by_separator(words_part, '|')
            if not words:
                await self.api.send_group_msg(group_id, "请输入违禁词，多个用|分割")
                return True
            
            if group_id_str not in self.data_manager.banned_words['groups']:
                await self.api.send_group_msg(group_id, "本群暂无违禁词")
                return True
            
            word_type = 'fuzzy' if is_fuzzy else 'exact'
            deleted_count = 0
            for word in words:
                if word in self.data_manager.banned_words['groups'][group_id_str][word_type]:
                    del self.data_manager.banned_words['groups'][group_id_str][word_type][word]
                    deleted_count += 1
            
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已删除{deleted_count}个{'模糊' if is_fuzzy else '精准'}违禁词")
            return True
        
        # 删全局模糊违禁词/删全局精准违禁词
        elif raw_message.startswith("全局") and ("删模糊" in raw_message or "删精准" in raw_message):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作全局违禁词")
                return True
            
            is_fuzzy = "删模糊" in raw_message
            parts = raw_message.split("违禁词")
            if len(parts) < 2:
                return False
            
            words_part = parts[1].strip()
            words = utils.split_list_by_separator(words_part, '|')
            if not words:
                await self.api.send_group_msg(group_id, "请输入违禁词，多个用|分割")
                return True
            
            word_type = 'fuzzy' if is_fuzzy else 'exact'
            deleted_count = 0
            for word in words:
                if word in self.data_manager.banned_words['global'][word_type]:
                    del self.data_manager.banned_words['global'][word_type][word]
                    deleted_count += 1
            
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已删除{deleted_count}个全局{'模糊' if is_fuzzy else '精准'}违禁词")
            return True
        
        # 查询模糊/精准违禁词列表 (本群)
        elif raw_message.startswith(("查询模糊", "查询精准")) and "违禁词列表" in raw_message:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            is_fuzzy = raw_message.startswith("查询模糊")
            word_type = 'fuzzy' if is_fuzzy else 'exact'
            
            if group_id_str not in self.data_manager.banned_words['groups']:
                await self.api.send_group_msg(group_id, f"本群暂无{'模糊' if is_fuzzy else '精准'}违禁词")
                return True
            
            words_dict = self.data_manager.banned_words['groups'][group_id_str].get(word_type, {})
            if not words_dict:
                await self.api.send_group_msg(group_id, f"本群暂无{'模糊' if is_fuzzy else '精准'}违禁词")
                return True
            
            msg = f"本群{'模糊' if is_fuzzy else '精准'}违禁词列表（共{len(words_dict)}个）\n"
            for word, action in list(words_dict.items())[:20]:
                msg += f"  {word} -> {action}\n"
            if len(words_dict) > 20:
                msg += f"  ... 还有{len(words_dict)-20}个\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 查询全局模糊/精准违禁词列表
        elif raw_message.startswith("全局") and ("查询模糊" in raw_message or "查询精准" in raw_message) and "违禁词列表" in raw_message:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以查询全局违禁词")
                return True
            
            is_fuzzy = "查询模糊" in raw_message
            word_type = 'fuzzy' if is_fuzzy else 'exact'
            
            words_dict = self.data_manager.banned_words['global'].get(word_type, {})
            if not words_dict:
                await self.api.send_group_msg(group_id, f"全局暂无{'模糊' if is_fuzzy else '精准'}违禁词")
                return True
            
            msg = f"全局{'模糊' if is_fuzzy else '精准'}违禁词列表（共{len(words_dict)}个）\n"
            for word, action in list(words_dict.items())[:20]:
                msg += f"  {word} -> {action}\n"
            if len(words_dict) > 20:
                msg += f"  ... 还有{len(words_dict)-20}个\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 设置违禁检测禁言时间+时间
        elif raw_message.startswith("设置违禁检测禁言时间"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            time_str = raw_message.replace("设置违禁检测禁言时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "时间格式错误")
                return True
            
            if group_id_str not in self.data_manager.banned_words['groups']:
                self.data_manager.banned_words['groups'][group_id_str] = {
                    'enabled': True, 'fuzzy': {}, 'exact': {}, 'mute_duration': 600
                }
            
            self.data_manager.banned_words['groups'][group_id_str]['mute_duration'] = seconds
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已设置违禁检测禁言时长为 {utils.format_time(seconds)}")
            return True
        
        # 开/关全局违禁检测
        elif command in ["开全局违禁检测", "关全局违禁检测"]:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作全局违禁检测")
                return True
            
            enabled = command.startswith("开")
            if 'enabled' not in self.data_manager.banned_words['global']:
                self.data_manager.banned_words['global']['enabled'] = True
            
            self.data_manager.banned_words['global']['enabled'] = enabled
            await self.data_manager._save_json('banned_words', self.data_manager.banned_words)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}全局违禁检测")
            return True
        
        return False
    
    async def check_banned_words(self, event: Dict) -> bool:
        """检查消息中是否包含违禁词"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            raw_message = event.get('raw_message', '')
            message_id = event.get('message_id')
            
            # 跳过有权限的用户
            if self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            group_id_str = str(group_id)
            
            # 检查群违禁词
            if group_id_str in self.data_manager.banned_words['groups']:
                group_banned = self.data_manager.banned_words['groups'][group_id_str]
                if not group_banned.get('enabled', True):
                    return False
                
                # 检查精准匹配
                for word, action in group_banned.get('exact', {}).items():
                    if utils.check_exact_match(raw_message, word):
                        await self._handle_banned_word(group_id, user_id, message_id, action, group_banned)
                        return True
                
                # 检查模糊匹配
                for word, action in group_banned.get('fuzzy', {}).items():
                    if utils.check_fuzzy_match(raw_message, word):
                        await self._handle_banned_word(group_id, user_id, message_id, action, group_banned)
                        return True
            
            # 检查全局违禁词
            for word, action in self.data_manager.banned_words['global']['exact'].items():
                if utils.check_exact_match(raw_message, word):
                    await self._handle_banned_word(group_id, user_id, message_id, action)
                    return True
            
            for word, action in self.data_manager.banned_words['global']['fuzzy'].items():
                if utils.check_fuzzy_match(raw_message, word):
                    await self._handle_banned_word(group_id, user_id, message_id, action)
                    return True
            
            return False
        
        except Exception as e:
            self.api.log("error", f"检查违禁词失败: {e}")
            return False
    
    async def _handle_banned_word(self, group_id: int, user_id: int, message_id: int, action: str, settings: Dict = None):
        """处理违禁词"""
        try:
            # 撤回消息
            if message_id:
                await self.api.call_api('delete_msg', {'message_id': message_id})
            
            # 执行处罚
            if action == "撤回禁言" or action == "撤回踢出":
                mute_duration = settings.get('mute_duration', 600) if settings else 600
                await self.api.call_api('set_group_ban', {
                    'group_id': group_id,
                    'user_id': user_id,
                    'duration': mute_duration
                })
                
                if action == "撤回踢出":
                    await self.api.call_api('set_group_kick',
                        group_id=group_id,
                        user_id=user_id,
                        reject_add_request=False
                    )
        
        except Exception as e:
            self.api.log("error", f"处理违禁词失败: {e}")


class AutoActionModule:
    """自动撤回/禁言/踢出系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_recall_command(self, event: Dict, command: str) -> bool:
        """处理撤回系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        if group_id_str not in self.data_manager.recall_settings:
            self.data_manager.recall_settings[group_id_str] = {
                'notify': False,
                'phone': False,
                'file': False,
                'voice': False,
                'red_packet': False,
                'video': False,
                'image': False,
                'link': False
            }
        
        settings = self.data_manager.recall_settings[group_id_str]
        
        # 开/关各类撤回
        type_map = {
            "号码撤回": "phone",
            "文件撤回": "file",
            "语音撤回": "voice",
            "红包撤回": "red_packet",
            "视频撤回": "video",
            "图片撤回": "image",
            "链接撤回": "link",
            "撤回通知": "notify"
        }
        
        for cmd_name, setting_key in type_map.items():
            if command in [f"开{cmd_name}", f"关{cmd_name}"]:
                enabled = command.startswith("开")
                settings[setting_key] = enabled
                await self.data_manager._save_json('recall_settings', self.data_manager.recall_settings)
                await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}{cmd_name}")
                return True
        
        # 查看撤回配置
        if command == "查看撤回配置":
            msg = f"""撤回系统配置
撤回通知：{'开' if settings.get('notify') else '关'}
号码撤回：{'开' if settings.get('phone') else '关'}
文件撤回：{'开' if settings.get('file') else '关'}
语音撤回：{'开' if settings.get('voice') else '关'}
红包撤回：{'开' if settings.get('red_packet') else '关'}
视频撤回：{'开' if settings.get('video') else '关'}
图片撤回：{'开' if settings.get('image') else '关'}
链接撤回：{'开' if settings.get('link') else '关'}"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 批量撤回+条数
        if raw_message.startswith("批量撤回"):
            count = utils.extract_number_from_text(raw_message)
            if not count:
                await self.api.send_group_msg(group_id, "请指定条数")
                return True
            
            if count <= 0 or count > 100:
                await self.api.send_group_msg(group_id, "撤回条数必须在1-100之间")
                return True
            
            # 获取最近的消息记录（从撤回系统或消息历史中）
            # 这里需要从OneBot API获取最近的消息
            try:
                # 尝试获取最近的消息列表
                # 注意：OneBot API可能不支持直接获取消息列表，需要自己记录
                # 这里实现一个简单的方案：记录最近的消息ID
                group_id_str = str(group_id)
                
                # 初始化消息记录（如果不存在）
                if not hasattr(self.data_manager, 'message_records'):
                    self.data_manager.message_records = {}
                
                if group_id_str not in self.data_manager.message_records:
                    self.data_manager.message_records[group_id_str] = []
                
                # 获取最近的消息记录（按时间倒序）
                records = self.data_manager.message_records.get(group_id_str, [])
                
                if len(records) < count:
                    await self.api.send_group_msg(group_id, f"只能撤回最近{len(records)}条消息，请减少撤回条数")
                    return True
                
                # 获取最近count条消息的ID（从新到旧）
                recent_records = records[-count:]
                recent_records.reverse()  # 从旧到新撤回
                
                # 批量撤回
                success_count = 0
                failed_count = 0
                
                for record in recent_records:
                    message_id = record.get('message_id')
                    if message_id:
                        try:
                            await self.api.call_api('delete_msg', message_id=message_id)
                            success_count += 1
                            # 从记录中移除已撤回的消息
                            if record in self.data_manager.message_records[group_id_str]:
                                self.data_manager.message_records[group_id_str].remove(record)
                        except Exception as e:
                            failed_count += 1
                            self.api.log("warning", f"撤回消息失败: {message_id}, 错误: {e}")
                
                # 保存更新后的记录
                await self.data_manager._save_json('message_records', self.data_manager.message_records)
                
                if success_count > 0:
                    msg = f"已撤回{success_count}条消息"
                    if failed_count > 0:
                        msg += f"，{failed_count}条撤回失败"
                    await self.api.send_group_msg(group_id, msg)
                else:
                    await self.api.send_group_msg(group_id, "撤回失败，可能是消息已过期或不存在")
                
            except Exception as e:
                self.api.log("error", f"批量撤回失败: {e}")
                await self.api.send_group_msg(group_id, f"批量撤回失败: {e}")
            
            return True
        
        return False
    
    async def handle_mute_command(self, event: Dict, command: str) -> bool:
        """处理禁言系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        if group_id_str not in self.data_manager.mute_settings:
            self.data_manager.mute_settings[group_id_str] = {
                'notify': False,
                'phone': False,
                'file': False,
                'voice': False,
                'red_packet': False,
                'video': False,
                'image': False,
                'link': False,
                'mute_duration': 600
            }
        
        settings = self.data_manager.mute_settings[group_id_str]
        
        # 开/关各类禁言
        type_map = {
            "号码禁言": "phone",
            "文件禁言": "file",
            "语音禁言": "voice",
            "红包禁言": "red_packet",
            "视频禁言": "video",
            "图片禁言": "image",
            "链接禁言": "link",
            "禁言通知": "notify"
        }
        
        for cmd_name, setting_key in type_map.items():
            if command in [f"开{cmd_name}", f"关{cmd_name}"]:
                enabled = command.startswith("开")
                settings[setting_key] = enabled
                await self.data_manager._save_json('mute_settings', self.data_manager.mute_settings)
                await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}{cmd_name}")
                return True
        
        # 查看禁言配置
        if command == "查看禁言配置":
            msg = f"""禁言系统配置
禁言通知：{'开' if settings.get('notify') else '关'}
号码禁言：{'开' if settings.get('phone') else '关'}
文件禁言：{'开' if settings.get('file') else '关'}
语音禁言：{'开' if settings.get('voice') else '关'}
红包禁言：{'开' if settings.get('red_packet') else '关'}
视频禁言：{'开' if settings.get('video') else '关'}
图片禁言：{'开' if settings.get('image') else '关'}
链接禁言：{'开' if settings.get('link') else '关'}
禁言时长：{utils.format_time(settings.get('mute_duration', 600))}"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 设置禁言处理时间+分钟
        if raw_message.startswith("设置禁言处理时间"):
            time_str = raw_message.replace("设置禁言处理时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "时间格式错误")
                return True
            
            settings['mute_duration'] = seconds
            await self.data_manager._save_json('mute_settings', self.data_manager.mute_settings)
            await self.api.send_group_msg(group_id, f"已设置禁言时长为 {utils.format_time(seconds)}")
            return True
        
        return False
    
    async def handle_kick_command(self, event: Dict, command: str) -> bool:
        """处理踢出系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        if group_id_str not in self.data_manager.kick_settings:
            self.data_manager.kick_settings[group_id_str] = {
                'notify': False,
                'phone': False,
                'file': False,
                'voice': False,
                'video': False,
                'image': False,
                'link': False,
                'qr_code': False
            }
        
        settings = self.data_manager.kick_settings[group_id_str]
        
        # 开/关各类踢出
        type_map = {
            "号码踢出": "phone",
            "文件踢出": "file",
            "语音踢出": "voice",
            "视频踢出": "video",
            "图片踢出": "image",
            "链接踢出": "link",
            "二维码踢出": "qr_code",
            "踢出通知": "notify"
        }
        
        for cmd_name, setting_key in type_map.items():
            if command in [f"开{cmd_name}", f"关{cmd_name}"]:
                enabled = command.startswith("开")
                settings[setting_key] = enabled
                await self.data_manager._save_json('kick_settings', self.data_manager.kick_settings)
                await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}{cmd_name}")
                return True
        
        # 查看踢出配置
        if command == "查看踢出配置":
            msg = f"""踢出系统配置
踢出通知：{'开' if settings.get('notify') else '关'}
号码踢出：{'开' if settings.get('phone') else '关'}
文件踢出：{'开' if settings.get('file') else '关'}
语音踢出：{'开' if settings.get('voice') else '关'}
视频踢出：{'开' if settings.get('video') else '关'}
图片踢出：{'开' if settings.get('image') else '关'}
链接踢出：{'开' if settings.get('link') else '关'}
二维码踢出：{'开' if settings.get('qr_code') else '关'}"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        return False
    
    async def check_auto_actions(self, event: Dict):
        """检查并执行自动操作"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            raw_message = event.get('raw_message', '')
            message_id = event.get('message_id')
            
            # 跳过有权限的用户
            if self.permission_manager.has_group_permission(user_id, group_id):
                return
            
            group_id_str = str(group_id)
            
            # 检查撤回设置
            recall_settings = self.data_manager.recall_settings.get(group_id_str, {})
            mute_settings = self.data_manager.mute_settings.get(group_id_str, {})
            kick_settings = self.data_manager.kick_settings.get(group_id_str, {})
            
            should_recall = False
            should_mute = False
            should_kick = False
            
            # 检查号码
            if utils.contains_phone_number(raw_message):
                if recall_settings.get('phone'): should_recall = True
                if mute_settings.get('phone'): should_mute = True
                if kick_settings.get('phone'): should_kick = True
            
            # 检查链接
            if utils.contains_url(raw_message):
                if recall_settings.get('link'): should_recall = True
                if mute_settings.get('link'): should_mute = True
                if kick_settings.get('link'): should_kick = True
            
            # 检查图片
            if utils.has_cq_code(raw_message, 'image'):
                if recall_settings.get('image'): should_recall = True
                if mute_settings.get('image'): should_mute = True
                if kick_settings.get('image'): should_kick = True
            
            # 检查视频
            if utils.has_cq_code(raw_message, 'video'):
                if recall_settings.get('video'): should_recall = True
                if mute_settings.get('video'): should_mute = True
                if kick_settings.get('video'): should_kick = True
            
            # 检查语音
            if utils.has_cq_code(raw_message, 'record'):
                if recall_settings.get('voice'): should_recall = True
                if mute_settings.get('voice'): should_mute = True
                if kick_settings.get('voice'): should_kick = True
            
            # 检查文件
            if utils.has_cq_code(raw_message, 'file'):
                if recall_settings.get('file'): should_recall = True
                if mute_settings.get('file'): should_mute = True
                if kick_settings.get('file'): should_kick = True
            
            # 执行操作
            if should_recall and message_id:
                await self.api.call_api('delete_msg', {'message_id': message_id})
                if recall_settings.get('notify'):
                    await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 消息已被自动撤回")
            
            if should_mute:
                mute_duration = mute_settings.get('mute_duration', 600)
                await self.api.call_api('set_group_ban', {
                    'group_id': group_id,
                    'user_id': user_id,
                    'duration': mute_duration
                })
                if mute_settings.get('notify'):
                    await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 已被自动禁言")
            
            if should_kick:
                await self.api.call_api('set_group_kick',
                    group_id=group_id,
                    user_id=user_id,
                    reject_add_request=False
                )
                if kick_settings.get('notify'):
                    await self.api.send_group_msg(group_id, f"用户 {user_id} 已被自动踢出")
        
        except Exception as e:
            self.api.log("error", f"执行自动操作失败: {e}")


"""入群验证模块"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class JoinVerifyModule:
    """入群验证模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
        self.pending_verifications = {}  # {group_id: {user_id: {type, answer, time}}}
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理入群验证指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        # 初始化设置
        if group_id_str not in self.data_manager.verify_settings:
            self.data_manager.verify_settings[group_id_str] = {
                'enabled': False,
                'verify_type': '发言',  # 发言/数字/算数
                'timeout': 60,  # 验证超时时间（秒）
                'whitelist': []  # 免验证用户
            }
        
        settings = self.data_manager.verify_settings[group_id_str]
        
        # 开/关入群验证
        if command in ["开入群验证", "关入群验证"]:
            enabled = command == "开入群验证"
            settings['enabled'] = enabled
            await self.data_manager._save_json('verify_settings', self.data_manager.verify_settings)
            await self.api.send_group_msg(group_id, f"✅ 已{'开启' if enabled else '关闭'}入群验证")
            return True
        
        # 切换发言验证
        elif command == "切换发言验证":
            settings['verify_type'] = '发言'
            await self.data_manager._save_json('verify_settings', self.data_manager.verify_settings)
            await self.api.send_group_msg(group_id, "✅ 已切换为发言验证（新成员发言即通过）")
            return True
        
        # 切换数字验证
        elif command == "切换数字验证":
            settings['verify_type'] = '数字'
            await self.data_manager._save_json('verify_settings', self.data_manager.verify_settings)
            await self.api.send_group_msg(group_id, "✅ 已切换为数字验证（新成员需发送指定数字）")
            return True
        
        # 切换算数验证
        elif command == "切换算数验证":
            settings['verify_type'] = '算数'
            await self.data_manager._save_json('verify_settings', self.data_manager.verify_settings)
            await self.api.send_group_msg(group_id, "✅ 已切换为算数验证（新成员需计算数学题）")
            return True
        
        # 查看验证配置
        elif command == "查看验证配置":
            msg = f"""📋 入群验证配置
验证状态：{'开启' if settings.get('enabled') else '关闭'}
验证类型：{settings.get('verify_type', '发言')}
超时时间：{settings.get('timeout', 60)}秒
免验证用户：{len(settings.get('whitelist', []))}人"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 免验证@QQ/+QQ
        elif raw_message.startswith("免验证"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(event.get('message', []))
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "❌ 请指定QQ号")
                return True
            
            if 'whitelist' not in settings:
                settings['whitelist'] = []
            
            if target_qq not in settings['whitelist']:
                settings['whitelist'].append(target_qq)
                await self.data_manager._save_json('verify_settings', self.data_manager.verify_settings)
                await self.api.send_group_msg(group_id, f"✅ 已将 {target_qq} 加入免验证名单")
            else:
                await self.api.send_group_msg(group_id, f"该用户已在免验证名单中")
            return True
        
        # 设置验证时间+时间
        elif raw_message.startswith("设置验证时间"):
            time_str = raw_message.replace("设置验证时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "❌ 时间格式错误")
                return True
            
            settings['timeout'] = seconds
            await self.data_manager._save_json('verify_settings', self.data_manager.verify_settings)
            await self.api.send_group_msg(group_id, f"✅ 已设置验证超时时间为 {utils.format_time(seconds)}")
            return True
        
        return False
    
    async def handle_group_increase(self, event: Dict):
        """处理群成员增加事件（发起验证）"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            
            group_id_str = str(group_id)
            settings = self.data_manager.verify_settings.get(group_id_str, {})
            
            if not settings.get('enabled'):
                return
            
            # 检查免验证名单
            if user_id in settings.get('whitelist', []):
                return
            
            verify_type = settings.get('verify_type', '发言')
            timeout = settings.get('timeout', 60)
            
            # 先禁言用户
            await self.api.call_api('set_group_ban', {
                'group_id': group_id,
                'user_id': user_id,
                'duration': timeout + 10  # 多禁言10秒，防止超时
            })
            
            if group_id not in self.pending_verifications:
                self.pending_verifications[group_id] = {}
            
            if verify_type == '发言':
                # 发言验证：发言即通过
                self.pending_verifications[group_id][user_id] = {
                    'type': '发言',
                    'time': datetime.now()
                }
                msg = f"[CQ:at,qq={user_id}] 欢迎加入本群！\n请在{timeout}秒内发言完成验证（已临时禁言，验证后自动解除）"
                await self.api.send_group_msg(group_id, msg)
            
            elif verify_type == '数字':
                # 数字验证：随机生成4位数字
                code = random.randint(1000, 9999)
                self.pending_verifications[group_id][user_id] = {
                    'type': '数字',
                    'answer': str(code),
                    'time': datetime.now()
                }
                msg = f"[CQ:at,qq={user_id}] 欢迎加入本群！\n请在{timeout}秒内发送以下数字完成验证：\n{code}"
                await self.api.send_group_msg(group_id, msg)
            
            elif verify_type == '算数':
                # 算数验证：随机生成简单算术题
                a = random.randint(1, 20)
                b = random.randint(1, 20)
                op = random.choice(['+', '-'])
                
                if op == '+':
                    answer = a + b
                    question = f"{a}+{b}"
                else:
                    # 确保结果为正数
                    if a < b:
                        a, b = b, a
                    answer = a - b
                    question = f"{a}-{b}"
                
                self.pending_verifications[group_id][user_id] = {
                    'type': '算数',
                    'answer': str(answer),
                    'time': datetime.now()
                }
                msg = f"[CQ:at,qq={user_id}] 欢迎加入本群！\n请在{timeout}秒内计算并发送答案：\n{question}=?"
                await self.api.send_group_msg(group_id, msg)
            
            # 启动超时检查
            asyncio.create_task(self._check_verify_timeout(group_id, user_id, timeout))
        
        except Exception as e:
            self.api.log("error", f"发起入群验证失败: {e}")
    
    async def check_verification(self, event: Dict) -> bool:
        """检查消息是否为验证回复"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            raw_message = event.get('raw_message', '').strip()
            
            if group_id not in self.pending_verifications:
                return False
            
            if user_id not in self.pending_verifications[group_id]:
                return False
            
            verification = self.pending_verifications[group_id][user_id]
            verify_type = verification['type']
            
            # 检查是否超时
            group_id_str = str(group_id)
            settings = self.data_manager.verify_settings.get(group_id_str, {})
            timeout = settings.get('timeout', 60)
            
            if datetime.now() - verification['time'] > timedelta(seconds=timeout):
                # 超时，踢出
                await self._verification_failed(group_id, user_id)
                return True
            
            # 验证答案
            if verify_type == '发言':
                # 发言验证：任何发言都通过
                await self._verification_success(group_id, user_id)
                return True
            
            elif verify_type == '数字':
                # 数字验证：检查是否匹配
                if raw_message == verification['answer']:
                    await self._verification_success(group_id, user_id)
                    return True
                else:
                    await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 验证码错误，请重试")
                    return True
            
            elif verify_type == '算数':
                # 算数验证：检查答案
                if raw_message == verification['answer']:
                    await self._verification_success(group_id, user_id)
                    return True
                else:
                    await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 答案错误，请重试")
                    return True
            
            return False
        
        except Exception as e:
            self.api.log("error", f"检查验证失败: {e}")
            return False
    
    async def _verification_success(self, group_id: int, user_id: int):
        """验证成功"""
        try:
            # 解除禁言
            await self.api.call_api('set_group_ban', {
                'group_id': group_id,
                'user_id': user_id,
                'duration': 0
            })
            
            # 发送成功消息
            await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 验证成功！欢迎加入本群~ ✅")
            
            # 移除验证记录
            if group_id in self.pending_verifications:
                if user_id in self.pending_verifications[group_id]:
                    del self.pending_verifications[group_id][user_id]
        
        except Exception as e:
            self.api.log("error", f"处理验证成功失败: {e}")
    
    async def _verification_failed(self, group_id: int, user_id: int):
        """验证失败"""
        try:
            # 踢出用户
            await self.api.call_api('set_group_kick', {
                'group_id': group_id,
                'user_id': user_id,
                'reject_add_request': False
            })
            
            # 发送失败消息
            await self.api.send_group_msg(group_id, f"用户 {user_id} 验证超时，已被踢出")
            
            # 移除验证记录
            if group_id in self.pending_verifications:
                if user_id in self.pending_verifications[group_id]:
                    del self.pending_verifications[group_id][user_id]
        
        except Exception as e:
            self.api.log("error", f"处理验证失败失败: {e}")
    
    async def _check_verify_timeout(self, group_id: int, user_id: int, timeout: int):
        """检查验证超时"""
        await asyncio.sleep(timeout)
        
        # 检查是否还在待验证列表中
        if group_id in self.pending_verifications:
            if user_id in self.pending_verifications[group_id]:
                # 超时，踢出
                await self._verification_failed(group_id, user_id)


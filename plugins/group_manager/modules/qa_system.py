"""问答系统模块"""

from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class QAModule:
    """问答系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理问答系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        group_id_str = str(group_id) if group_id else None
        
        # 开/关问答
        if command in ["开问答", "关问答"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            enabled = command == "开问答"
            if group_id_str not in self.data_manager.qa_system['groups']:
                self.data_manager.qa_system['groups'][group_id_str] = {
                    'fuzzy': {}, 'exact': {}, 'enabled': enabled
                }
            else:
                self.data_manager.qa_system['groups'][group_id_str]['enabled'] = enabled
            
            await self.data_manager._save_json('qa_system', self.data_manager.qa_system)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}问答系统")
            return True
        
        # 精准问xx答xx
        elif "精准问" in raw_message and "答" in raw_message:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            # 解析问题和答案
            parts = raw_message.split("答")
            if len(parts) != 2:
                await self.api.send_group_msg(group_id, "格式错误，格式：精准问xx答xx")
                return True
            
            question = parts[0].replace("精准问", "").strip()
            answer = parts[1].strip()
            
            if not question or not answer:
                await self.api.send_group_msg(group_id, "问题或答案不能为空")
                return True
            
            if group_id_str not in self.data_manager.qa_system['groups']:
                self.data_manager.qa_system['groups'][group_id_str] = {
                    'fuzzy': {}, 'exact': {}, 'enabled': True
                }
            
            self.data_manager.qa_system['groups'][group_id_str]['exact'][question] = answer
            await self.data_manager._save_json('qa_system', self.data_manager.qa_system)
            await self.api.send_group_msg(group_id, f"已添加精准问答\n问：{question}\n答：{answer}")
            return True
        
        # 模糊问xx答xx
        elif "模糊问" in raw_message and "答" in raw_message:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            parts = raw_message.split("答")
            if len(parts) != 2:
                await self.api.send_group_msg(group_id, "格式错误，格式：模糊问xx答xx")
                return True
            
            question = parts[0].replace("模糊问", "").strip()
            answer = parts[1].strip()
            
            if not question or not answer:
                await self.api.send_group_msg(group_id, "问题或答案不能为空")
                return True
            
            if group_id_str not in self.data_manager.qa_system['groups']:
                self.data_manager.qa_system['groups'][group_id_str] = {
                    'fuzzy': {}, 'exact': {}, 'enabled': True
                }
            
            self.data_manager.qa_system['groups'][group_id_str]['fuzzy'][question] = answer
            await self.data_manager._save_json('qa_system', self.data_manager.qa_system)
            await self.api.send_group_msg(group_id, f"已添加模糊问答\n问：{question}\n答：{answer}")
            return True
        
        # 删精准问/删模糊问
        elif raw_message.startswith(("删精准问", "删模糊问")):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            is_exact = raw_message.startswith("删精准问")
            question = raw_message.replace("删精准问" if is_exact else "删模糊问", "").strip()
            
            if not question:
                await self.api.send_group_msg(group_id, "请指定问题")
                return True
            
            if group_id_str in self.data_manager.qa_system['groups']:
                qa_type = 'exact' if is_exact else 'fuzzy'
                if question in self.data_manager.qa_system['groups'][group_id_str][qa_type]:
                    del self.data_manager.qa_system['groups'][group_id_str][qa_type][question]
                    await self.data_manager._save_json('qa_system', self.data_manager.qa_system)
                    await self.api.send_group_msg(group_id, f"已删除{'精准' if is_exact else '模糊'}问答：{question}")
                else:
                    await self.api.send_group_msg(group_id, "未找到该问答")
            return True
        
        # 全局问答（主人和管理员）
        elif raw_message.startswith("全局") and ("精准问" in raw_message or "模糊问" in raw_message):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作全局问答")
                return True
            
            if "答" not in raw_message:
                return False
            
            is_exact = "精准问" in raw_message
            parts = raw_message.split("答")
            if len(parts) != 2:
                return False
            
            question = parts[0].replace("全局", "").replace("精准问" if is_exact else "模糊问", "").strip()
            answer = parts[1].strip()
            
            if not question or not answer:
                await self.api.send_group_msg(group_id, "问题或答案不能为空")
                return True
            
            qa_type = 'exact' if is_exact else 'fuzzy'
            self.data_manager.qa_system['global'][qa_type][question] = answer
            await self.data_manager._save_json('qa_system', self.data_manager.qa_system)
            await self.api.send_group_msg(group_id, f"已添加全局{'精准' if is_exact else '模糊'}问答")
            return True
        
        return False
    
    async def check_and_answer(self, event: Dict) -> bool:
        """检查消息并自动回答"""
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not group_id:
            return False
        
        group_id_str = str(group_id)
        
        # 检查是否启用
        if group_id_str in self.data_manager.qa_system['groups']:
            if not self.data_manager.qa_system['groups'][group_id_str].get('enabled', True):
                return False
        
        # 先检查精准匹配（群）
        if group_id_str in self.data_manager.qa_system['groups']:
            exact_qa = self.data_manager.qa_system['groups'][group_id_str].get('exact', {})
            if raw_message in exact_qa:
                await self.api.send_group_msg(group_id, exact_qa[raw_message])
                return True
        
        # 检查精准匹配（全局）
        if raw_message in self.data_manager.qa_system['global']['exact']:
            await self.api.send_group_msg(group_id, self.data_manager.qa_system['global']['exact'][raw_message])
            return True
        
        # 检查模糊匹配（群）
        if group_id_str in self.data_manager.qa_system['groups']:
            fuzzy_qa = self.data_manager.qa_system['groups'][group_id_str].get('fuzzy', {})
            for question, answer in fuzzy_qa.items():
                if question in raw_message:
                    await self.api.send_group_msg(group_id, answer)
                    return True
        
        # 检查模糊匹配（全局）
        for question, answer in self.data_manager.qa_system['global']['fuzzy'].items():
            if question in raw_message:
                await self.api.send_group_msg(group_id, answer)
                return True
        
        return False


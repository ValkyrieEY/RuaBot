"""邀请统计机器人插件 - 适配自 Xiaoyi_QQ

功能：
- 统计群成员邀请人数，数据存储在json
- 支持"邀请记录"指令查询自己的邀请记录
- 支持"清空邀请记录"指令（仅管理员可用）
- 支持私聊"导出统计"指令（仅指定管理员可用）
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional


class InviteStatsPlugin:
    """邀请统计插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        self._update_config(config)
        
        # 数据结构：{group_id: {inviter_qq: {invited_users: {user_qq: {join_time, status, leave_time}}}}}
        self.invite_data = {}
        
        # 月度奖励记录：{group_id: {user_id: cumulative_rank_reward}}
        self.monthly_rewards: Dict[str, Dict[str, int]] = {}
    
    def _update_config(self, config: Dict[str, Any]):
        """更新配置
        
        Args:
            config: 新的配置字典
        """
        self.config = config
        self.admin_qq = int(config.get('admin_qq', '3302727375'))
        # 启用的群列表（为空则所有群都启用）
        enabled_groups_config = config.get('enabled_groups', [])
        if enabled_groups_config:
            self.enabled_groups = set(str(g) for g in enabled_groups_config)
        else:
            self.enabled_groups = set()  # 空集合表示所有群都启用
        # SMTP配置
        self.smtp_host = config.get('smtp_host', 'smtp.qq.com')
        self.smtp_port = int(config.get('smtp_port', 587))
        self.smtp_user = config.get('smtp_user', '').strip()
        self.smtp_password = config.get('smtp_password', '').strip()
        self.smtp_from = config.get('smtp_from', '').strip()
        self.smtp_to = config.get('smtp_to', '').strip()
    
    async def on_load(self):
        """插件加载时调用"""
        # 从存储加载邀请数据
        data_bytes = await self.api.get_storage('invite_data')
        if data_bytes:
            try:
                self.invite_data = json.loads(data_bytes.decode('utf-8'))
                # 统计数据
                total_inviters = sum(len(group_data) for group_data in self.invite_data.values())
                total_invited = sum(
                    len(invited_users) 
                    for group_data in self.invite_data.values() 
                    for invited_users in group_data.values()
                )
                self.api.log("info", f"✅ 已加载邀请数据: {len(self.invite_data)}个群, {total_inviters}个邀请人, {total_invited}条邀请记录")
            except Exception as e:
                self.api.log("error", f"❌ 加载邀请数据失败: {e}")
                self.invite_data = {}
        else:
            self.api.log("info", "📝 首次运行，暂无历史邀请数据")
            self.invite_data = {}
        
        # 从存储加载月度奖励数据
        rewards_bytes = await self.api.get_storage('monthly_rewards')
        if rewards_bytes:
            try:
                self.monthly_rewards = json.loads(rewards_bytes.decode('utf-8'))
                self.api.log("info", f"✅ 已加载月度奖励数据: {len(self.monthly_rewards)}个群")
            except Exception as e:
                self.api.log("error", f"❌ 加载月度奖励数据失败: {e}")
                self.monthly_rewards = {}
        else:
            self.monthly_rewards = {}
        
        self.api.log("info", "邀请统计插件加载成功")
    
    async def on_unload(self):
        """插件卸载时调用"""
        # 保存数据到存储
        await self._save_data()
        self.api.log("info", "邀请统计插件已卸载")
    
    async def _save_data(self):
        """保存数据到存储"""
        try:
            # 保存邀请数据
            data_bytes = json.dumps(self.invite_data, ensure_ascii=False, indent=2).encode('utf-8')
            success = await self.api.set_storage('invite_data', data_bytes)
            if success:
                # 统计当前数据
                total_groups = len(self.invite_data)
                total_inviters = sum(len(group_data) for group_data in self.invite_data.values())
                total_invited = sum(
                    len(invited_users) 
                    for group_data in self.invite_data.values() 
                    for invited_users in group_data.values()
                )
                self.api.log("info", f"💾 邀请数据已保存: {total_groups}个群, {total_inviters}个邀请人, {total_invited}条记录")
            else:
                self.api.log("error", "❌ 邀请数据保存失败: set_storage 返回 False")
            
            # 保存月度奖励数据
            rewards_bytes = json.dumps(self.monthly_rewards, ensure_ascii=False, indent=2).encode('utf-8')
            rewards_success = await self.api.set_storage('monthly_rewards', rewards_bytes)
            if rewards_success:
                total_reward_users = sum(len(users) for users in self.monthly_rewards.values())
                self.api.log("info", f"💾 月度奖励数据已保存: {len(self.monthly_rewards)}个群, {total_reward_users}个用户")
            else:
                self.api.log("error", "❌ 月度奖励数据保存失败")
                
        except Exception as e:
            self.api.log("error", f"❌ 保存数据异常: {e}")
    
    async def _safe_send_group_msg(self, group_id: int, message: str):
        """安全地发送群消息（捕获超时错误）"""
        try:
            # 使用更短的超时时间（5秒），避免长时间等待
            result = await asyncio.wait_for(
                self.api.send_group_msg(group_id, message),
                timeout=5.0
            )
            # 成功返回 {'message_id': int}，有 message_id 就是成功
            if result and 'message_id' in result:
                self.api.log("debug", f"发送群消息成功: message_id={result['message_id']}")
            elif isinstance(result, dict) and result.get('error'):
                self.api.log("warning", f"发送群消息失败: {result.get('error')}")
        except asyncio.TimeoutError:
            # 超时不算错误，消息可能已经发送成功
            self.api.log("debug", f"发送群消息超时（5秒），但消息可能已发送成功")
        except Exception as e:
            self.api.log("error", f"发送群消息异常: {e}")
    
    async def on_event_context(self, ctx):
        """处理事件上下文"""
        if ctx.event_name == "message.received":
            # 处理消息事件
            event_data = ctx.event_data
            asyncio.create_task(self.handle_message(event_data))
            return ctx
        elif ctx.event_name == "notice.received":
            # 处理通知事件
            event_data = ctx.event_data
            asyncio.create_task(self.handle_notice(event_data))
            return ctx
        return None
    
    def is_group_enabled(self, group_id: int) -> bool:
        """检查群是否启用此插件
        
        Args:
            group_id: 群号
            
        Returns:
            是否启用
        """
        # 如果enabled_groups为空，则所有群都启用
        if not self.enabled_groups:
            return True
        return str(group_id) in self.enabled_groups
    
    async def handle_notice(self, event: Dict[str, Any]):
        """处理通知事件（群成员增减）"""
        try:
            group_id = event.get('group_id')
            
            # 检查群是否启用此插件
            if not self.is_group_enabled(group_id):
                return
            
            notice_type = event.get('notice_type')
            
            # 群成员增加
            if notice_type == 'group_increase':
                await self.handle_member_join(event)
            
            # 群成员减少
            elif notice_type == 'group_decrease':
                await self.handle_member_leave(event)
        
        except Exception as e:
            self.api.log("error", f"处理通知事件时出错: {e}")
    
    async def handle_member_join(self, event: Dict[str, Any]):
        """处理群成员加入事件"""
        try:
            group_id = str(event.get('group_id'))
            user_id = str(event.get('user_id'))
            operator_id = str(event.get('operator_id', ''))  # 邀请人
            sub_type = event.get('sub_type', '')  # approve(同意入群) 或 invite(被邀请)
            
            # 只统计被邀请进群的情况
            if sub_type == 'invite' and operator_id:
                # 初始化群数据
                if group_id not in self.invite_data:
                    self.invite_data[group_id] = {}
                
                # 初始化邀请人数据
                if operator_id not in self.invite_data[group_id]:
                    self.invite_data[group_id][operator_id] = {}
                
                # 记录被邀请人信息
                join_time = datetime.now().strftime("%Y年%m月%d日%H时%M分%S秒")
                self.invite_data[group_id][operator_id][user_id] = {
                    'join_time': join_time,
                    'status': '存在',
                    'leave_time': None
                }
                
                # 保存数据
                await self._save_data()
                
                self.api.log("info", f"✅ 记录邀请: 群{group_id}, {operator_id}邀请了{user_id}")
        
        except Exception as e:
            self.api.log("error", f"处理群成员加入事件时出错: {e}")
    
    async def handle_member_leave(self, event: Dict[str, Any]):
        """处理群成员离开事件"""
        try:
            group_id = str(event.get('group_id'))
            user_id = str(event.get('user_id'))
            
            # 检查这个人是否是被邀请进群的
            if group_id in self.invite_data:
                for inviter_id, invited_users in self.invite_data[group_id].items():
                    if user_id in invited_users:
                        # 更新状态为退群
                        leave_time = datetime.now().strftime("%Y年%m月%d日%H时%M分%S秒")
                        self.invite_data[group_id][inviter_id][user_id]['status'] = '退群'
                        self.invite_data[group_id][inviter_id][user_id]['leave_time'] = leave_time
                        
                        # 保存数据
                        await self._save_data()
                        
                        self.api.log("info", f"✅ 更新退群: 群{group_id}, {user_id}退出(由{inviter_id}邀请)")
                        break
        
        except Exception as e:
            self.api.log("error", f"处理群成员离开事件时出错: {e}")
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件"""
        try:
            message_type = event.get('message_type')  # 'private' or 'group'
            raw_message = event.get('raw_message', '').strip()
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            
            # 处理群消息
            if message_type == 'group':
                # 检查群是否启用此插件
                if not self.is_group_enabled(group_id):
                    return
                
                # 查询邀请记录 - 使用 create_task 异步处理，不阻塞
                if raw_message == "邀请记录":
                    asyncio.create_task(self.handle_query_invite(user_id, group_id))
                    return
                
                # 清空邀请记录（仅管理员可用）- 使用 create_task 异步处理
                elif raw_message == "清空邀请记录":
                    asyncio.create_task(self.handle_clear_invite(user_id, group_id))
                    return
                
                # 月度结算（仅管理员可用）- 使用 create_task 异步处理
                elif raw_message == "月度结算":
                    asyncio.create_task(self.handle_monthly_settlement(user_id, group_id))
                    return
            
            # 处理私聊消息
            elif message_type == 'private':
                # 导出统计（仅管理员可用）- 使用 create_task 异步处理
                if raw_message == "导出统计":
                    asyncio.create_task(self.handle_export_stats(user_id))
                    return
        
        except Exception as e:
            self.api.log("error", f"处理消息时出错: {e}")
    
    async def handle_query_invite(self, user_id: int, group_id: int):
        """处理查询邀请记录"""
        try:
            group_id_str = str(group_id)
            user_id_str = str(user_id)
            
            # 检查是否有邀请记录
            if group_id_str not in self.invite_data or user_id_str not in self.invite_data[group_id_str]:
                msg = f"[CQ:at,qq={user_id}]\n\n你还没有邀请记录哦~"
                # 使用 create_task 异步发送，不等待响应
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
                return
            
            # 获取邀请数据
            invited_users = self.invite_data[group_id_str][user_id_str]
            
            # 统计数据
            total_invited = len(invited_users)  # 总共邀请人数
            valid_count = sum(1 for user_data in invited_users.values() if user_data['status'] == '存在')  # 有效人数
            left_count = total_invited - valid_count  # 退群人数
            invite_reward = valid_count * 1000  # 邀请奖励
            
            # 获取排名和排行奖励
            rank, rank_reward = await self.get_user_rank(group_id_str, user_id_str)
            
            # 构建回复消息
            msg = f"[CQ:at,qq={user_id}]\n"
            msg += "---------------------------------------\n"
            msg += f"共邀请：{total_invited}人\n"
            msg += f"有效人数：{valid_count}人\n"
            msg += f"退群人数：{left_count}人\n"
            msg += f"邀请奖励：{invite_reward}泡点\n"
            
            # 🔥 只有达到排行榜要求（有效人数 >= 10）且在前十名才显示排行奖励
            if rank > 0 and rank <= 10:
                msg += f"排行奖励：第{rank}名：{rank_reward}泡点\n"
            
            msg += "---------------------------------------"
            
            # 使用 create_task 异步发送，不等待响应
            asyncio.create_task(self._safe_send_group_msg(group_id, msg))
            self.api.log("info", f"用户{user_id}查询邀请记录：总{total_invited}，有效{valid_count}")
        
        except Exception as e:
            self.api.log("error", f"查询邀请记录失败: {e}")
            # 使用 create_task 异步发送错误消息
            asyncio.create_task(self._safe_send_group_msg(group_id, "查询失败，请稍后再试~"))
    
    async def get_user_rank(self, group_id_str: str, user_id_str: str) -> tuple:
        """获取用户排名和排行奖励
        
        Returns:
            (rank, reward): 排名和奖励泡点（0表示未达到排行榜要求）
        """
        try:
            if group_id_str not in self.invite_data:
                return (0, 0)
            
            # 构建排名列表：[(user_id, valid_count, total_invited)]
            # 🔥 只有有效人数 >= 10 的用户才能进入排行榜
            rank_list = []
            for inviter_id, invited_users in self.invite_data[group_id_str].items():
                valid_count = sum(1 for user_data in invited_users.values() if user_data['status'] == '存在')
                total_invited = len(invited_users)
                
                # 🔥 最低要求：有效人数 >= 10 才能进入排行榜
                if valid_count >= 10:
                    rank_list.append((inviter_id, valid_count, total_invited))
            
            # 排序：先按有效人数降序，再按总邀请人数降序（确保没有并列）
            rank_list.sort(key=lambda x: (x[1], x[2]), reverse=True)
            
            # 查找用户排名
            for i, (inviter_id, _, _) in enumerate(rank_list, start=1):
                if inviter_id == user_id_str:
                    rank = i
                    # 计算排行奖励
                    if rank == 1:
                        reward = 30000
                    elif rank == 2:
                        reward = 20000
                    elif rank == 3:
                        reward = 10000
                    elif rank <= 10:
                        reward = 5000
                    else:
                        reward = 0
                    return (rank, reward)
            
            # 🔥 未进入排行榜（有效人数 < 10）
            return (0, 0)
        
        except Exception as e:
            self.api.log("error", f"获取用户排名失败: {e}")
            return (0, 0)
    
    async def handle_clear_invite(self, user_id: int, group_id: int):
        """处理清空邀请记录（仅管理员可用）"""
        try:
            # 检查是否是管理员
            if user_id != self.admin_qq:
                msg = "只有管理员才能清空邀请记录哦~"
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
                return
            
            # 清空本群的邀请记录
            group_id_str = str(group_id)
            if group_id_str in self.invite_data:
                self.invite_data[group_id_str] = {}
                await self._save_data()
                
                msg = "已清空本群所有邀请记录！"
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
                self.api.log("info", f"群{group_id}的邀请记录已被管理员{user_id}清空")
            else:
                msg = "本群还没有邀请记录哦~"
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
        
        except asyncio.TimeoutError:
            self.api.log("warning", f"获取群成员信息超时")
            asyncio.create_task(self._safe_send_group_msg(group_id, "操作超时，请稍后再试~"))
        except Exception as e:
            self.api.log("error", f"清空邀请记录失败: {e}")
            asyncio.create_task(self._safe_send_group_msg(group_id, "清空失败，请稍后再试~"))
    
    async def handle_monthly_settlement(self, user_id: int, group_id: int):
        """处理月度结算（仅管理员可用）"""
        try:
            group_id_str = str(group_id)
            
            # 检查是否是管理员
            if user_id != self.admin_qq:
                msg = "只有管理员才能执行月度结算哦~"
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
                return
            
            # 检查是否有邀请数据
            if group_id_str not in self.invite_data or not self.invite_data[group_id_str]:
                msg = "本群还没有邀请记录，无需结算~"
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
                return
            
            # 初始化月度奖励记录（如果不存在）
            if not hasattr(self, 'monthly_rewards'):
                self.monthly_rewards = {}
            if group_id_str not in self.monthly_rewards:
                self.monthly_rewards[group_id_str] = {}
            
            # 计算排行榜（有效人数 >= 10）
            rank_list = []
            for inviter_id, invited_users in self.invite_data[group_id_str].items():
                valid_count = sum(1 for user_data in invited_users.values() if user_data['status'] == '存在')
                total_invited = len(invited_users)
                
                if valid_count >= 10:
                    rank_list.append((inviter_id, valid_count, total_invited))
            
            # 排序
            rank_list.sort(key=lambda x: (x[1], x[2]), reverse=True)
            
            if not rank_list:
                msg = "本群暂无符合排行榜要求的成员（需有效人数≥10人）~"
                asyncio.create_task(self._safe_send_group_msg(group_id, msg))
                return
            
            # 生成结算报告
            from datetime import datetime
            settlement_time = datetime.now().strftime("%Y年%m月%d日")
            
            report = f"月底结算\n"
            report += "="*40 + "\n"
            
            settlement_data = []
            
            # 前10名
            for i, (inviter_id, valid_count, total_invited) in enumerate(rank_list[:10], start=1):
                # 计算奖励
                if i == 1:
                    rank_reward = 30000
                    rank_name = "第一名"
                elif i == 2:
                    rank_reward = 20000
                    rank_name = "第二名"
                elif i == 3:
                    rank_reward = 10000
                    rank_name = "第三名"
                elif i == 4:
                    rank_name = "第四名"
                    rank_reward = 5000
                elif i == 5:
                    rank_name = "第五名"
                    rank_reward = 5000
                elif i == 6:
                    rank_name = "第六名"
                    rank_reward = 5000
                elif i == 7:
                    rank_name = "第七名"
                    rank_reward = 5000
                elif i == 8:
                    rank_name = "第八名"
                    rank_reward = 5000
                elif i == 9:
                    rank_name = "第九名"
                    rank_reward = 5000
                elif i == 10:
                    rank_name = "第十名"
                    rank_reward = 5000
                else:
                    rank_reward = 0
                    rank_name = "其他"
                
                # 计算邀请奖励
                invite_reward = valid_count * 1000
                
                # 记录结算数据
                if inviter_id not in self.monthly_rewards[group_id_str]:
                    self.monthly_rewards[group_id_str][inviter_id] = 0
                
                # 累加排行奖励
                self.monthly_rewards[group_id_str][inviter_id] += rank_reward
                
                report += f"{rank_name}：{inviter_id}，邀请人数{total_invited}人，有效人数{valid_count}人，邀请奖励{invite_reward}，排行奖励{rank_reward}\n"
                
                settlement_data.append({
                    'rank': i,
                    'user_id': inviter_id,
                    'valid_count': valid_count,
                    'invite_reward': invite_reward,
                    'rank_reward': rank_reward
                })
            
            # 10名之后的（有效人数≥10但未进前10）
            if len(rank_list) > 10:
                report += "\n【其他符合条件的成员】\n"
                for i, (inviter_id, valid_count, total_invited) in enumerate(rank_list[10:], start=11):
                    invite_reward = valid_count * 1000
                    report += f"其他：{inviter_id}，邀请人数{total_invited}人，有效人数{valid_count}人，邀请奖励{invite_reward}，排行奖励0\n"
            
            report += "="*40
            
            # 保存数据
            await self._save_data()
            
            # 发送结算报告
            asyncio.create_task(self._safe_send_group_msg(group_id, report))
            
            self.api.log("info", f"群{group_id}完成月度结算，前{len(settlement_data)}名获得排行奖励")
        
        except asyncio.TimeoutError:
            self.api.log("warning", f"获取群成员信息超时")
            asyncio.create_task(self._safe_send_group_msg(group_id, "操作超时，请稍后再试~"))
        except Exception as e:
            self.api.log("error", f"月度结算失败: {e}")
            import traceback
            self.api.log("error", traceback.format_exc())
            asyncio.create_task(self._safe_send_group_msg(group_id, "结算失败，请稍后再试~"))
    
    async def handle_export_stats(self, user_id: int):
        """处理导出统计（仅管理员可用）"""
        try:
            # 检查权限
            if user_id != self.admin_qq:
                msg = "你没有权限导出统计数据~"
                asyncio.create_task(self._safe_send_private_msg(user_id, msg))
                return
            
            # 生成导出内容
            export_content = self.generate_export_content()
            
            # 检查SMTP配置
            if not all([self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from, self.smtp_to]):
                self.api.log("warning", "SMTP配置不完整，使用分段发送")
                await self._send_content_as_messages(user_id, export_content, f"invite_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                return
            
            # 保存到临时文件
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"invite_stats_{timestamp}.txt"
            filepath = os.path.join(temp_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(export_content)
            
            self.api.log("info", f"已生成导出文件: {filepath} (大小: {os.path.getsize(filepath)} 字节)")
            
            # 使用SMTP发送邮件
            try:
                success = await self._send_email_with_attachment(
                    filepath=filepath,
                    filename=filename,
                    subject=f"邀请统计数据 - {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
                    body="邀请统计数据已生成，请查看附件。"
                )
                
                if success:
                    asyncio.create_task(self._safe_send_private_msg(user_id, "✅ 统计数据已通过邮件发送！请查收邮箱。"))
                else:
                    raise Exception("邮件发送失败")
                    
            except Exception as e:
                self.api.log("error", f"邮件发送失败: {e}")
                import traceback
                self.api.log("error", traceback.format_exc())
                # 降级为分段发送
                self.api.log("info", "邮件发送失败，尝试分段发送内容")
                await self._send_content_as_messages(user_id, export_content, filename)
        
        except Exception as e:
            self.api.log("error", f"导出统计失败: {e}")
            import traceback
            self.api.log("error", traceback.format_exc())
            asyncio.create_task(self._safe_send_private_msg(user_id, "导出失败，请稍后再试~"))
    
    async def _send_email_with_attachment(self, filepath: str, filename: str, subject: str, body: str) -> bool:
        """通过SMTP发送带附件的邮件
        
        Args:
            filepath: 文件路径
            filename: 文件名
            subject: 邮件主题
            body: 邮件正文
            
        Returns:
            True if successful
        """
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        
        def send_email_sync():
            """同步发送邮件（在线程中执行）"""
            try:
                # 创建邮件
                msg = MIMEMultipart()
                msg['From'] = self.smtp_from
                msg['To'] = self.smtp_to
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                # 添加附件
                with open(filepath, 'rb') as f:
                    attachment = MIMEBase('application', 'octet-stream')
                    attachment.set_payload(f.read())
                    encoders.encode_base64(attachment)
                    attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}'
                    )
                    msg.attach(attachment)
                
                # 连接SMTP服务器并发送
                if self.smtp_port == 465:
                    # SSL连接
                    server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
                else:
                    # TLS连接
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                    server.starttls()
                
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                server.quit()
                
                return True
            except Exception as e:
                self.api.log("error", f"SMTP发送邮件异常: {e}")
                import traceback
                self.api.log("error", traceback.format_exc())
                return False
        
        # 在线程池中执行同步的SMTP操作
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = loop.run_in_executor(executor, send_email_sync)
            return await future
    
    async def _send_content_as_messages(self, user_id: int, content: str, filename: str):
        """将内容分段发送为消息"""
        try:
            # 发送提示
            asyncio.create_task(self._safe_send_private_msg(
                user_id, 
                f"📊 统计数据报告 - {filename}\n{'='*40}"
            ))
            
            # 等待一下，确保消息顺序
            await asyncio.sleep(0.5)
            
            # 将内容分段（每段最多500个字符）
            max_length = 500
            lines = content.split('\n')
            current_chunk = ""
            
            for line in lines:
                # 如果加上这行会超过限制，先发送当前块
                if len(current_chunk) + len(line) + 1 > max_length and current_chunk:
                    asyncio.create_task(self._safe_send_private_msg(user_id, current_chunk))
                    await asyncio.sleep(0.3)  # 避免发送过快
                    current_chunk = ""
                
                current_chunk += line + '\n'
            
            # 发送最后一块
            if current_chunk:
                asyncio.create_task(self._safe_send_private_msg(user_id, current_chunk))
            
            # 发送完成提示
            await asyncio.sleep(0.5)
            asyncio.create_task(self._safe_send_private_msg(
                user_id,
                f"{'='*40}\n✅ 统计数据发送完成！\n\n💡 提示：完整文件保存在：\n{os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp', filename))}"
            ))
            
        except Exception as e:
            self.api.log("error", f"分段发送内容失败: {e}")
    
    async def _safe_send_private_msg(self, user_id: int, message: str):
        """安全地发送私聊消息（捕获超时错误）"""
        try:
            # 使用更短的超时时间（5秒），避免长时间等待
            result = await asyncio.wait_for(
                self.api.send_private_msg(user_id, message),
                timeout=5.0
            )
            # 成功返回 {'message_id': int}，有 message_id 就是成功
            if result and 'message_id' in result:
                self.api.log("debug", f"发送私聊消息成功: message_id={result['message_id']}")
            elif isinstance(result, dict) and result.get('error'):
                self.api.log("warning", f"发送私聊消息失败: {result.get('error')}")
        except asyncio.TimeoutError:
            # 超时不算错误，消息可能已经发送成功
            self.api.log("debug", f"发送私聊消息超时（5秒），但消息可能已发送成功")
        except Exception as e:
            self.api.log("error", f"发送私聊消息异常: {e}")
    
    def generate_export_content(self) -> str:
        """生成导出内容"""
        lines = []
        
        # 遍历所有群
        for group_id, group_data in self.invite_data.items():
            lines.append(f"\n{'='*50}")
            lines.append(f"群号：{group_id}")
            lines.append(f"{'='*50}\n")
            
            # 🔥 生成排行榜（只包含有效人数 >= 10 的用户）
            rank_list = []
            for inviter_id, invited_users in group_data.items():
                valid_count = sum(1 for user_data in invited_users.values() if user_data['status'] == '存在')
                total_invited = len(invited_users)
                
                if valid_count >= 10:
                    rank_list.append((inviter_id, valid_count, total_invited))
            
            # 排序
            rank_list.sort(key=lambda x: (x[1], x[2]), reverse=True)
            
            # 显示排行榜
            if rank_list:
                lines.append("【排行榜 TOP 10】（有效人数≥10人）")
                lines.append("-" * 50)
                for i, (inviter_id, valid_count, total_invited) in enumerate(rank_list[:10], start=1):
                    if i == 1:
                        reward = 30000
                    elif i == 2:
                        reward = 20000
                    elif i == 3:
                        reward = 10000
                    elif i <= 10:
                        reward = 5000
                    else:
                        reward = 0
                    
                    lines.append(f"第{i}名：{inviter_id} | 有效{valid_count}人 | 共邀请{total_invited}人 | 奖励{reward}泡点")
                lines.append("")
            
            # 遍历每个邀请人的详细数据
            lines.append("【详细邀请记录】")
            lines.append("-" * 50)
            
            for inviter_id, invited_users in group_data.items():
                # 统计数据
                total_invited = len(invited_users)
                valid_count = sum(1 for user_data in invited_users.values() if user_data['status'] == '存在')
                left_count = total_invited - valid_count
                invite_reward = valid_count * 1000
                
                lines.append("\n" + "="*50)
                lines.append(f"邀请人：{inviter_id}")
                lines.append(f"累计邀请：{total_invited}人 | 有效：{valid_count}人 | 退群：{left_count}人")
                lines.append(f"邀请奖励：{invite_reward}泡点")
                
                # 显示排名信息
                if valid_count >= 10:
                    # 查找排名
                    for i, (uid, _, _) in enumerate(rank_list, start=1):
                        if uid == inviter_id:
                            if i == 1:
                                reward = 30000
                            elif i == 2:
                                reward = 20000
                            elif i == 3:
                                reward = 10000
                            elif i <= 10:
                                reward = 5000
                            else:
                                reward = 0
                            lines.append(f"排行奖励：第{i}名 - {reward}泡点")
                            break
                else:
                    lines.append(f"排行奖励：未达到要求（需有效人数≥10人）")
                
                lines.append("-" * 50)
                
                # 列出所有被邀请的用户
                for idx, (invited_id, user_data) in enumerate(invited_users.items(), start=1):
                    status = user_data['status']
                    join_time = user_data['join_time']
                    leave_time = user_data.get('leave_time', '')
                    
                    line = f"  {idx}. {invited_id} | 加入时间：{join_time} | 状态：{status}"
                    if leave_time:
                        line += f" | 退群时间：{leave_time}"
                    
                    lines.append(line)
        
        if not lines:
            lines.append("暂无邀请记录")
        
        return '\n'.join(lines)


# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 实例
        config: 插件配置
        
    Returns:
        Plugin 实例
    """
    plugin = InviteStatsPlugin(api, config)
    await plugin.on_load()
    return plugin


import random
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import aiofiles
from typing import Dict, Any

class DailyBubblePointsPlugin:
    def __init__(self, api, config):
        self.api = api
        self.config = config
        self.plugin_name = "daily_bubble_points"
        
        # 数据存储目录
        self.data_dir = Path("data") / self.plugin_name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录文件路径
        self.record_file = self.data_dir / "bubble_points_record.json"
        self.weekly_record_file = self.data_dir / "weekly_record.json"
        
        # 加载数据
        self.daily_records = self._load_daily_records()
        self.weekly_records = self._load_weekly_records()
        
        # 当前周标识（年+周数）
        self.current_week_key = self._get_current_week_key()
        
        # SMTP配置
        self._update_smtp_config(config)
        
        # ⚡ 性能优化：批量写入机制
        self._pending_save_daily = False  # 标记是否有待保存的数据
        self._pending_save_weekly = False
        self._save_lock = asyncio.Lock()  # 防止并发写入
        self._batch_save_task = None  # 批量保存任务

    def _log_error(self, message: str):
        """简单的错误记录方法"""
        print(f"[ERROR] [daily_bubble_points] {message}", flush=True)
        
    def _log_info(self, message: str):
        """简单的信息记录方法"""
        print(f"[INFO] [daily_bubble_points] {message}", flush=True)
    
    def _update_smtp_config(self, config: Dict[str, Any]):
        """更新SMTP配置
        
        Args:
            config: 新的配置字典
        """
        self.smtp_host = config.get('smtp_host', 'smtp.qq.com')
        self.smtp_port = int(config.get('smtp_port', 587))
        self.smtp_user = config.get('smtp_user', '').strip()
        self.smtp_password = config.get('smtp_password', '').strip()
        self.smtp_from = config.get('smtp_from', '').strip()
        self.smtp_to = config.get('smtp_to', '').strip()
    
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
        import concurrent.futures
        
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
                self._log_error(f"SMTP邮件发送失败: {e}")
                return False
        
        # 在线程池中执行同步的SMTP操作
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = loop.run_in_executor(executor, send_email_sync)
            return await future
    
    async def _send_content_as_messages(self, user_id: str, content: str, filename: str):
        """将内容分段发送为消息"""
        try:
            # 发送提示
            await self.api.send_private_msg(
                user_id=user_id, 
                message=f"📊 泡点统计数据报告 - {filename}\n{'='*40}"
            )
            
            # 等待一下，确保消息顺序
            await asyncio.sleep(0.5)
            
            # 将内容分段（每段最多500个字符）
            max_length = 500
            lines = content.split('\n')
            current_chunk = ""
            
            for line in lines:
                # 如果加上这行会超过限制，先发送当前块
                if len(current_chunk) + len(line) + 1 > max_length and current_chunk:
                    await self.api.send_private_msg(user_id=user_id, message=current_chunk)
                    await asyncio.sleep(0.3)  # 避免发送过快
                    current_chunk = ""
                
                current_chunk += line + '\n'
            
            # 发送最后一块
            if current_chunk:
                await self.api.send_private_msg(user_id=user_id, message=current_chunk)
            
            # 发送完成提示
            await self.api.send_private_msg(user_id=user_id, message=f"\n✅ 数据报告发送完毕！共 {len(lines)} 行数据。")
            
        except Exception as e:
            self._log_error(f"分段发送内容失败: {e}")
            # 尝试直接发送原始消息
            try:
                await self.api.send_private_msg(user_id=user_id, message=f"数据报告 ({filename}): {content[:200]}...")
            except:
                pass

    def _get_current_week_key(self):
        """获取当前周的标识符（年+周数）"""
        now = datetime.now()
        year, week_num, _ = now.isocalendar()
        return f"{year}_week_{week_num}"

    def _load_daily_records(self):
        """加载每日记录"""
        if self.record_file.exists():
            try:
                with open(self.record_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self._log_error(f"加载每日记录失败: {e}")
                return {}
        return {}

    async def _save_daily_records_async(self):
        """异步保存每日记录 - 避免阻塞事件循环"""
        async with self._save_lock:
            try:
                data = json.dumps(self.daily_records, ensure_ascii=False, indent=2)
                async with aiofiles.open(self.record_file, 'w', encoding='utf-8') as f:
                    await f.write(data)
                self._pending_save_daily = False
            except Exception as e:
                self._log_error(f"异步保存每日记录失败: {e}")

    def _mark_daily_dirty(self):
        """标记每日记录需要保存"""
        self._pending_save_daily = True

    def _save_daily_records(self):
        """同步保存每日记录 - 仅用于初始化和卸载"""
        try:
            with open(self.record_file, 'w', encoding='utf-8') as f:
                json.dump(self.daily_records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log_error(f"保存每日记录失败: {e}")

    def _load_weekly_records(self):
        """加载每周记录"""
        if self.weekly_record_file.exists():
            try:
                with open(self.weekly_record_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self._log_error(f"加载每周记录失败: {e}")
                return {}
        return {}

    async def _save_weekly_records_async(self):
        """异步保存每周记录 - 避免阻塞事件循环"""
        async with self._save_lock:
            try:
                data = json.dumps(self.weekly_records, ensure_ascii=False, indent=2)
                async with aiofiles.open(self.weekly_record_file, 'w', encoding='utf-8') as f:
                    await f.write(data)
                self._pending_save_weekly = False
            except Exception as e:
                self._log_error(f"异步保存每周记录失败: {e}")

    def _mark_weekly_dirty(self):
        """标记每周记录需要保存"""
        self._pending_save_weekly = True

    def _save_weekly_records(self):
        """同步保存每周记录 - 仅用于初始化和卸载"""
        try:
            with open(self.weekly_record_file, 'w', encoding='utf-8') as f:
                json.dump(self.weekly_records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log_error(f"保存每周记录失败: {e}")

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        # 从当前配置中获取管理员QQ号，而不是使用初始化时的值
        current_admin_qq = str(self.config.get('admin_qq', '2477194503'))
        return str(user_id) == current_admin_qq
    
    def _is_enabled_group(self, group_id: str) -> bool:
        """检查群是否启用插件"""
        enabled_groups = self.config.get('enabled_groups', [])
        # 如果enabled_groups为空，则所有群都启用
        if not enabled_groups:
            return True
        return str(group_id) in enabled_groups

    def _get_today_key(self):
        """获取今天的日期键"""
        return datetime.now().strftime("%Y-%m-%d")

    def _check_participated_today(self, user_id: str) -> bool:
        """检查用户今天是否已参与"""
        today_key = self._get_today_key()
        user_records = self.daily_records.get(str(user_id), {})
        return today_key in user_records

    async def _batch_save_loop(self):
        """⚡ 批量保存循环 - 每10秒检查并保存待保存的数据"""
        while True:
            try:
                await asyncio.sleep(10)  # 每10秒执行一次
                
                # 检查是否有待保存的数据
                if self._pending_save_daily:
                    self._log_info("批量保存：保存每日记录")
                    await self._save_daily_records_async()
                
                if self._pending_save_weekly:
                    self._log_info("批量保存：保存每周记录")
                    await self._save_weekly_records_async()
                    
            except asyncio.CancelledError:
                # 插件卸载时，执行最后一次保存
                self._log_info("批量保存任务取消，执行最后一次保存")
                if self._pending_save_daily:
                    await self._save_daily_records_async()
                if self._pending_save_weekly:
                    await self._save_weekly_records_async()
                break
            except Exception as e:
                self._log_error(f"批量保存循环错误: {e}")

    async def _start_batch_save_task(self):
        """启动批量保存任务"""
        if self._batch_save_task is None:
            self._batch_save_task = asyncio.create_task(self._batch_save_loop())
            self._log_info("⚡ 批量保存任务已启动（每10秒保存一次）")

    async def _stop_batch_save_task(self):
        """停止批量保存任务"""
        if self._batch_save_task is not None:
            self._batch_save_task.cancel()
            try:
                await self._batch_save_task
            except asyncio.CancelledError:
                pass
            self._batch_save_task = None
            self._log_info("批量保存任务已停止")

    async def _update_weekly_record(self, user_id: str, points: int):
        """更新周累计记录 - 使用批量保存"""
        week_key = self._get_current_week_key()
        if week_key not in self.weekly_records:
            self.weekly_records[week_key] = {}
        
        user_weekly_points = self.weekly_records[week_key].get(str(user_id), 0)
        self.weekly_records[week_key][str(user_id)] = user_weekly_points + points
        
        # 标记为待保存，不立即写入
        self._mark_weekly_dirty()

    def _check_special_rules(self, number: int) -> tuple:
        """检查特殊规则并返回额外奖励"""
        extra_points = 0
        rule_name = ""
        
        num_str = str(number).zfill(3)  # 补齐到3位数
        
        # 检查豹子号（三位数相同）
        if len(set(num_str)) == 1:
            extra_points = 666
            rule_name = "豹子号奖励"
        # 检查顺子号（连续递增，不循环）
        elif self._is_straight_sequence(num_str):
            extra_points = 222
            rule_name = "顺子号奖励"
        
        return extra_points, rule_name
    
    def _is_straight_sequence(self, num_str: str) -> bool:
        """检查是否为连续递增序列（123, 234, 345, 456, 567, 678, 789）"""
        if len(num_str) < 3:
            return False
            
        # 检查每一位是否比前一位大1
        for i in range(len(num_str) - 1):
            current_digit = int(num_str[i])
            next_digit = int(num_str[i + 1])
            
            # 如果不是连续递增，返回False
            if next_digit != current_digit + 1:
                return False
            
            # 确保不超过9（避免循环）
            if next_digit > 9:
                return False
                
        return True

    def _get_blessing_message(self, points: int) -> str:
        """根据获得的点数返回祝福语"""
        if points < 100:
            return "下次继续努力哦~"
        elif points < 200:
            return "不错呢，加油加油！"
        elif points < 300:
            return "表现良好，继续保持！"
        elif points < 400:
            return "越来越棒了！"
        elif points < 500:
            return "厉害厉害！"
        elif points < 600:
            return "太强了！"
        else:
            return "哇塞！大赢家！"

    async def handle_command(self, message: str, user_id: str, group_id: str = None):
        """处理命令"""
        if message == "我爱小狐仙":
            return await self.handle_daily_participation(user_id, group_id)
        elif message == "本周泡点":
            return await self.handle_weekly_points_query(user_id, group_id)
        elif message == "导出泡点记录":
            return await self.handle_export_records(user_id, group_id)
        elif message == "周结算泡点记录":
            return await self.handle_weekly_settlement(user_id, group_id)
        elif message == "清空泡点记录":
            return await self.handle_clear_records(user_id, group_id)
        
        return None

    async def handle_daily_participation(self, user_id: str, group_id: str = None):
        """处理每日参与"""
        if self._check_participated_today(user_id):
            # 在群聊中添加艾特
            if group_id:
                return f"[CQ:at,qq={user_id}] 你今天已经参与过了，明天再来吧"
            return "你今天已经参与过了，明天再来吧"
        
        # 生成随机泡点
        min_points = self.config.get("bubble_range_min", 1)
        max_points = self.config.get("bubble_range_max", 666)
        base_points = random.randint(min_points, max_points)
        
        # 检查特殊规则
        extra_points, rule_name = self._check_special_rules(base_points)
        
        # 记录今天的参与
        today_key = self._get_today_key()
        if str(user_id) not in self.daily_records:
            self.daily_records[str(user_id)] = {}
        
        self.daily_records[str(user_id)][today_key] = {
            "points": base_points,
            "extra_points": extra_points,
            "rule_name": rule_name,
            "timestamp": datetime.now().isoformat()
        }
        
        # ⚡ 标记为待保存，不立即写入（批量保存）
        self._mark_daily_dirty()
        
        # 更新周累计记录（也是批量保存）
        total_points = base_points + extra_points
        await self._update_weekly_record(user_id, total_points)
        
        # 构造回复消息
        blessing_msg = self._get_blessing_message(base_points)
        response = f"今日获得随机泡点({min_points}-{max_points})：{base_points}，额外泡点：{extra_points}"
        if rule_name:
            response += f"\n触发特殊规则：{rule_name}"
        response += f"\n{blessing_msg}"
        
        # 在群聊中添加艾特
        if group_id:
            response = f"[CQ:at,qq={user_id}] {response}"
        
        return response

    async def handle_weekly_points_query(self, user_id: str, group_id: str = None):
        """查询本周累计泡点"""
        week_key = self._get_current_week_key()
        weekly_points = self.weekly_records.get(week_key, {}).get(str(user_id), 0)
        
        response = f"你本周累计泡点为：{weekly_points}"
        
        # 在群聊中添加艾特
        if group_id:
            response = f"[CQ:at,qq={user_id}] {response}"
        
        return response

    async def handle_export_records(self, user_id: str, group_id: str = None):
        """导出泡点记录（仅管理员）"""
        if not self._is_admin(user_id):
            return "权限不足，只有管理员可以执行此操作"
        
        try:
            # 导出为文本格式
            export_text = []
            
            # 获取当前周的所有用户记录
            week_key = self._get_current_week_key()
            
            # 获取这一周的7天日期
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())  # 本周周一
            
            for user_id_str, records in self.daily_records.items():
                # 获取用户一周内的记录，按星期几组织
                week_days = [0] * 7  # 初始化为7个0，代表周一到周日
                
                # 遍历这一周的7天
                for i in range(7):
                    day_date = start_of_week + timedelta(days=i)
                    day_str = day_date.strftime("%Y-%m-%d")
                    
                    # 如果用户在这一天有记录，则添加点数
                    if day_str in records:
                        day_record = records[day_str]
                        points = day_record["points"] + day_record["extra_points"]
                        week_days[i] = points  # i=0是周一，i=6是周日
                
                # 计算总点数
                total_points = sum(week_days)
                
                # 格式：XX|第1次获得泡点值|第2次获得泡点值|...|第7次获得泡点值|总共泡点值|
                record_line = f"{user_id_str}|{'|'.join(map(str, week_days))}|{total_points}|"
                export_text.append(record_line)
            
            export_content = '\n'.join(export_text)
            
            # 检查SMTP配置
            if not all([self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from, self.smtp_to]):
                # SMTP配置不完整，使用分段发送
                filename = f"daily_bubble_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                await self._send_content_as_messages(user_id, export_content, filename)
                return "✅ 已通过私聊分段发送统计数据"
            
            # 保存到临时文件
            temp_dir = self.data_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"daily_bubble_export_{timestamp}.txt"
            filepath = temp_dir / filename
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(export_content)
            
            self._log_info(f"已生成导出文件: {filepath} (大小: {len(export_content.encode('utf-8'))} 字节)")
            
            # 使用SMTP发送邮件
            try:
                success = await self._send_email_with_attachment(
                    filepath=str(filepath),
                    filename=filename,
                    subject=f"每日泡点统计数据 - {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
                    body="每日泡点统计数据已生成，请查看附件。"
                )
                
                if success:
                    await self.api.send_private_msg(user_id=user_id, message="✅ 统计数据已通过邮件发送！请查收邮箱。")
                else:
                    raise Exception("邮件发送失败")
                    
            except Exception as e:
                self._log_error(f"邮件发送失败: {e}")
                # 降级为分段发送
                self._log_info("邮件发送失败，尝试分段发送内容")
                await self._send_content_as_messages(user_id, export_content, filename)
        
        except Exception as e:
            self._log_error(f"导出记录失败: {e}")
            await self.api.send_private_msg(user_id=user_id, message="导出失败，请稍后再试~")

    async def handle_weekly_settlement(self, user_id: str, group_id: str = None):
        """周结算泡点记录（仅管理员）"""
        if not self._is_admin(user_id):
            return "权限不足，只有管理员可以执行此操作"
        
        try:
            week_key = self._get_current_week_key()
            weekly_data = self.weekly_records.get(week_key, {})
            
            if not weekly_data:
                return "本周暂无泡点记录"
            
            # 按泡点数降序排列
            sorted_data = sorted(weekly_data.items(), key=lambda x: x[1], reverse=True)
            
            result = []
            for rank, (user_id_str, points) in enumerate(sorted_data, 1):
                result.append(f"第{rank}名 {user_id_str}，你本周累计泡点为：{points}")
            
            return "\n".join(result)
            
        except Exception as e:
            self._log_error(f"周结算失败: {e}")
            return f"周结算失败：{str(e)}"

    async def handle_clear_records(self, user_id: str, group_id: str = None):
        """清空泡点记录（仅管理员）"""
        if not self._is_admin(user_id):
            return "权限不足，只有管理员可以执行此操作"
        
        # 清空记录
        self.daily_records = {}
        self.weekly_records = {}
        self._save_daily_records()
        self._save_weekly_records()
        
        return "泡点记录已清空"

    async def on_message(self, event):
        """处理消息事件"""
        try:
            message = event.get("raw_message", "")
            user_id = str(event.get("user_id", ""))
            group_id = event.get("group_id")
            
            # 检查是否是命令
            if message in ["我爱小狐仙", "本周泡点", "导出泡点记录", "周结算泡点记录", "清空泡点记录"]:
                response = await self.handle_command(message, user_id, group_id)
                if response:
                    # 发送回复
                    if group_id:
                        await self.api.send_group_msg(group_id=group_id, message=response)
                    else:
                        await self.api.send_private_msg(user_id=user_id, message=response)
                    return True  # 表示已处理，不再传递给其他插件
            
        except Exception as e:
            self._log_error(f"处理消息事件失败: {e}")
            # 确保异常不会阻止其他插件处理消息
            return False
    
    async def on_event_context(self, ctx):
        """处理带有上下文的事件 - 适配框架的新事件处理机制"""
        try:
            # 启动批量保存任务（首次调用时）
            if self._batch_save_task is None:
                await self._start_batch_save_task()
            
            # 检查是否是消息事件
            if ctx.event_name == "message.received":
                event_data = ctx.event_data
                message = event_data.get("raw_message", "")
                user_id = str(event_data.get("user_id", ""))
                group_id = event_data.get("group_id")
                
                # 添加调试日志
                self._log_info(f"收到消息: '{message}', 用户: {user_id}, 群组: {group_id}")
                self._log_info(f"群组 {group_id} 是否启用: {self._is_enabled_group(group_id) if group_id else 'N/A'}")
                
                # 如果是私聊消息，直接处理
                if not group_id:
                    if message in ["我爱小狐仙", "本周泡点", "导出泡点记录", "周结算泡点记录", "清空泡点记录"]:
                        response = await self.handle_command(message, user_id, group_id)
                        if response:
                            await self.api.send_private_msg(user_id=user_id, message=response)
                            ctx.prevented = True
                            return ctx
                    return ctx  # 关键：即使不是关注的命令也要返回ctx
                
                # 如果是群消息，检查群是否启用插件
                if not self._is_enabled_group(group_id):
                    return ctx  # 返回上下文而不是False
                
                # 检查是否是命令
                if message in ["我爱小狐仙", "本周泡点", "导出泡点记录", "周结算泡点记录", "清空泡点记录"]:
                    response = await self.handle_command(message, user_id, group_id)
                    if response:
                        # 发送回复
                        await self.api.send_group_msg(group_id=group_id, message=response)
                        # 修改上下文，标记消息已被处理
                        ctx.prevented = True
                        return ctx
                    else:
                        return ctx  # 即使没有响应也要返回ctx
                else:
                    return ctx  # 不是插件关注的命令，也要返回ctx
            
            return ctx  # 不是消息事件，也要返回ctx
        
        except Exception as e:
            self._log_error(f"处理事件上下文失败: {e}")
            return ctx  # 异常情况下也要返回ctx
                
        except Exception as e:
            self._log_error(f"处理事件上下文失败: {e}")
            return ctx

    async def on_unload(self):
        """插件卸载时的清理工作"""
        try:
            # 停止批量保存任务（会执行最后一次保存）
            await self._stop_batch_save_task()
            
            # 确保所有数据已保存
            self._save_daily_records()
            self._save_weekly_records()
            self._log_info("每日泡点插件数据已保存")
        except Exception as e:
            self._log_error(f"保存数据失败: {e}")

# 插件入口函数
async def init_plugin(api, config):
    """初始化插件"""
    plugin = DailyBubblePointsPlugin(api, config)
    return plugin
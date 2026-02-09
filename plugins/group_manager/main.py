import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from utils.data_manager import DataManager
from utils.permission_manager import PermissionManager
from modules import (
    AuthorizationModule,
    PermissionModule,
    BasicManageModule,
    BlackWhiteListModule,
    QAModule,
    JoinSettingsModule,
    JoinVerifyModule,
    SpamDetectionModule,
    WarningModule,
    BannedWordsModule,
    AutoActionModule,
    MessageFeedbackModule,
    CardSystemModule,
    RemoteModule,
    NotificationModule,
    CardKeyModule,
    TitleModule,
    ProfileModule,
    NotificationSettingsModule,
    RecallSelfModule,
    ReplySettingsModule,
    OwnerModule,
    StatusModule
)


class GroupManagerPlugin:
    """小依群管插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        
        # 初始化数据管理器
        self.data_manager = DataManager(api)
        
        # 初始化权限管理器
        self.permission_manager = PermissionManager(api, self.data_manager)
        
        # 从配置中设置主人和管理员
        owner_qq = config.get('owner_qq', '')
        if owner_qq:
            try:
                # 如果是字符串，转换为整数
                if isinstance(owner_qq, str):
                    owner_qq = int(owner_qq.strip()) if owner_qq.strip() else 0
                elif isinstance(owner_qq, int):
                    pass  # 已经是整数
                else:
                    owner_qq = 0
                
                if owner_qq > 0:
                    self.permission_manager.set_owners([owner_qq])
                    api.log("info", f"主人QQ: {owner_qq}")
            except (ValueError, AttributeError) as e:
                api.log("warning", f"主人QQ号格式错误: {owner_qq}, 错误: {e}")
        else:
            api.log("warning", "主人QQ未配置，请在插件设置中配置")
        
        # 处理管理员列表
        admin_list_config = config.get('admin_qq_list', [])
        admin_list = []
        if admin_list_config:
            try:
                # admin_qq_list 现在必须是数组类型（字符串数组）
                if isinstance(admin_list_config, list):
                    # 转换为整数列表（配置中存储为字符串）
                    admin_list = [int(qq) if isinstance(qq, str) else int(qq) for qq in admin_list_config if qq]
                else:
                    api.log("warning", f"管理员QQ号列表格式错误，应为数组类型: {admin_list_config}")
                
                if admin_list:
                    self.permission_manager.set_admins(admin_list)
                    api.log("info", f"管理员: {admin_list}")
            except (ValueError, TypeError) as e:
                api.log("warning", f"管理员QQ号列表格式错误: {admin_list_config}, 错误: {e}")
        else:
            api.log("info", "管理员列表为空")
        
        # 初始化功能模块
        self.auth_module = AuthorizationModule(api, self.data_manager, self.permission_manager)
        self.perm_module = PermissionModule(api, self.data_manager, self.permission_manager)
        self.basic_module = BasicManageModule(api, self.data_manager, self.permission_manager)
        self.blacklist_module = BlackWhiteListModule(api, self.data_manager, self.permission_manager)
        self.qa_module = QAModule(api, self.data_manager, self.permission_manager)
        self.join_settings_module = JoinSettingsModule(api, self.data_manager, self.permission_manager)
        self.join_verify_module = JoinVerifyModule(api, self.data_manager, self.permission_manager)
        self.spam_module = SpamDetectionModule(api, self.data_manager, self.permission_manager)
        self.warning_module = WarningModule(api, self.data_manager, self.permission_manager)
        self.banned_words_module = BannedWordsModule(api, self.data_manager, self.permission_manager)
        self.auto_action_module = AutoActionModule(api, self.data_manager, self.permission_manager)
        self.message_feedback_module = MessageFeedbackModule(api, self.data_manager, self.permission_manager)
        self.card_system_module = CardSystemModule(api, self.data_manager, self.permission_manager)
        self.remote_module = RemoteModule(api, self.data_manager, self.permission_manager)
        self.notification_module = NotificationModule(api, self.data_manager, self.permission_manager)
        self.cardkey_module = CardKeyModule(api, self.data_manager, self.permission_manager)
        self.title_module = TitleModule(api, self.data_manager, self.permission_manager)
        self.profile_module = ProfileModule(api, self.data_manager, self.permission_manager)
        self.notification_settings_module = NotificationSettingsModule(api, self.data_manager, self.permission_manager)
        self.recall_self_module = RecallSelfModule(api, self.data_manager, self.permission_manager)
        self.reply_settings_module = ReplySettingsModule(api, self.data_manager, self.permission_manager)
        self.owner_module = OwnerModule(api, self.data_manager, self.permission_manager)
        self.status_module = StatusModule(api, self.data_manager, self.permission_manager)
        
        # 菜单文本
        self.main_menu = """小依群管
----------
授权中心 入群设置
权限管理 基础群管
入群验证 刷屏检测
资料修改 撤回自身
警告系统 留言反馈
提示系统 名片系统
黑白名单 违禁检测
问答系统 撤回系统
禁言系统 踢出系统
远程系统 主人权限
通知系统 运行状态
卡密系统 头衔系统
插件设置 等待更新
----------
Made By RuaBot"""
        
        self.auth_menu = """授权中心
-----
授权本群
查询本群授权
删除本群授权
-
本群开机/关机
增加授权+天数
减少授权+天数
-
开/关到期自动退群
开/关到期通知主人
开/关到期通知提醒
-
Tips：+ 不用带"""
        
        self.perm_menu = """权限管理
-----
我的身份
查询身份+QQ
-
同步管理权限
查询群管列表
清空群管列表
-
加/删群管+QQ
加/删群主+QQ
加/删管理员+QQ
-
Tips：+ 不用带"""
        
        self.basic_menu = """基础群管
-----
清屏
踢+QQ
上/下管理+QQ
禁言@QQ+时间
解除禁言+QQ
截图桌面
-
全群禁言
全群解禁
-
开/关踢出拉黑
开/关退群拉黑
开/关踢出撤回
开/关菜单权限
一键踢出黑名单
-
Tips：+ 不用带"""
        
        self.blacklist_menu = """黑白名单
-----
[本群]
删黑@QQ/删黑+QQ
加白@QQ/加白+QQ
删白@QQ/删白+QQ
加黑@QQ/加黑+QQ#原因
查询黑名单列表
清空黑名单列表
查询白名单列表
清空白名单列表
-
设置黑名单提示/禁言/踢出
-
[全局]
全局删黑@QQ/删黑+QQ
全局加白@QQ/加白+QQ
全局删白@QQ/删白+QQ
全局加黑@QQ/加黑+QQ#原因
查询全局黑名单列表
清空全局黑名单列表
查询全局白名单列表
清空全局白名单列表
-
设置全局黑名单提示/禁言/踢出"""
        
        self.join_settings_menu = """入群设置
-----
开/关入群提示
开/关入群禁言
开/关入群审核
开/关入群私聊
-
开/关入群改名片
查看入群设置变量
-
设置入群禁言时间+时间
设置入群提示内容+内容
设置入群私聊内容+内容
设置入群名片前缀+前缀
设置入群最低等级+级数
设置入群自动/同意/拒绝/忽略"""
        
        self.join_verify_menu = """入群验证
----
开入群验证
关入群验证
-
切换发言验证
切换数字验证
切换算数验证
查看验证配置
-
免验证@QQ/+QQ
设置验证时间+时间
-
Tips：+ 不用带"""
        
        self.spam_menu = """刷屏检测
-
开刷屏提示
关刷屏提示
-
开刷屏检测
关刷屏检测
-
查看检测配置
-
设置检测次数+次数
设置检测时间+时间
设置禁言时间+时间
-
设置刷屏处罚+<类型>
<类型>替换为撤回、
撤回禁言、撤回踢出"""
        
        self.qa_menu = """问答系统
-----
[本群]
开/关问答
删/精准问xx
删/模糊问xx
模糊问xx答xx
精准问xx答xx
查询模糊问答列表
查询精准问答列表
清空模糊问答列表
清空精准问答列表
-
[全局]
开/关全局问答
删/全局精准问xx
删/全局模糊问xx
全局模糊问xx答xx
全局精准问xx答xx
查询全局模糊问答列表
查询全局精准问答列表
清空全局模糊问答列表
清空全局精准问答列表"""
        
        self.recall_menu = """撤回系统
-----
撤回@QQ+条数
批量撤回+条数
-
开/关撤回通知
开/关号码撤回
开/关文件撤回
开/关语音撤回
开/关红包撤回
开/关视频撤回
开/关图片撤回
开/关链接撤回
-
查看撤回配置
-
Tips：+ 不用带"""
        
        self.mute_menu = """禁言系统
-----
开/关禁言通知
开/关号码禁言
开/关文件禁言
开/关语音禁言
开/关红包禁言
开/关视频禁言
开/关图片禁言
开/关链接禁言
-
查看禁言配置
-
设置禁言处理时间+分钟
-
Tips：+ 不用带"""
        
        self.kick_menu = """踢出系统
-----
开/关踢出通知
开/关号码踢出
开/关文件踢出
开/关语音踢出
开/关视频踢出
开/关图片踢出
开/关链接踢出
开/关二维码踢出
-
查看踢出配置
-
Tips：+ 不用带"""
        
        self.profile_menu = """资料修改
-
修改个签+内容
修改昵称+内容
-
仅主人使用
修改机器人自身资料"""
        
        self.warning_menu = """警告系统
-----
警告@
我的警告
查看警告
清空警告
-
开/关警告通知
开/关警告查询
-
设置警告执行类型+类型
设置警告限制次数+内容
设置警告禁言时间+时间
-
Tip:  类型->禁言|踢出"""
        
        self.feedback_menu = """留言反馈
-----
开/关留言反馈
开/关留言通知
留言/反馈#内容
-
删除留言/反馈#ID
查看留言/反馈#ID
查看留言/反馈列表
清空留言/反馈列表
-
Tips：+ 不用带"""
        
        self.card_menu = """名片系统
------
开/关发言改名
-
改名@QQ+名片
取消锁定@QQ/+QQ
锁定名片@QQ+名片
-
查看锁定成员列表
设置发言名片前缀+前缀
查看发言名片前缀
-
Tips：+ 不用带"""
        
        self.notification_settings_menu = """提示系统
-----
开/关入群提示
开/关退群提示
-
开/关上管提示
开/关下管提示
-
开/关被踢提示
开/关被禁提示
开/关解禁提示
开/关改名提示"""
        
        self.recall_self_menu = """撤回自身
-
开/关撤回自身
设置撤回间隔（秒）
-
Tip：默认关闭，时间默认60"""
        
        self.reply_settings_menu = """回复设置
----
开艾特发送
关艾特发送
开静默模式
关静默模式"""
        
        self.owner_menu = """主人权限
----
插件版本
框架版本
变量列表
重启插件
退出本群
-
Tips：主人权限"""
        
        self.plugin_settings_menu = """插件设置
----
设置机器被加同意
设置机器被加拒绝
设置机器被加忽略
设置机器被邀同意
设置机器被邀拒绝
设置机器被邀忽略
-
开/关机器上管通知
开/关机器下管通知
开/关机器被加通知
开/关机器被踢通知
开/关机器被禁通知"""
        
        self.status_menu = """运行状态
----
CPU使用率
内存使用率
磁盘使用率
-
在线时长
处理消息数
插件状态"""
        
        self.banned_menu = """违禁检测
-----
[本群]
开/关违禁检测
加模糊<类型>违禁词x
加精准<类型>违禁词x
删模糊<类型>违禁词x
删精准<类型>违禁词x
查询模糊<类型>违禁词列表
查询精准<类型>违禁词列表
-
[全局]
开/关全局违禁检测
加全局模糊<类型>违禁词x
加全局精准<类型>违禁词x
删全局模糊<类型>违禁词x
删全局精准<类型>违禁词x
查询全局模糊<类型>违禁词列表
查询全局精准<类型>违禁词列表
-
设置违禁检测禁言时间+时间
-
Tips：<类型>：撤回、撤回禁言、撤回踢出
tip：多个用|分割"""
        
        self.remote_menu = """远程系统
-
远程全体禁言+群号
远程全体解禁+群号
-
远程踢出#群号#QQ
远程解禁#群号#QQ
-
远程发送#群号#内容
远程禁言#群号#QQ#时间
-
Tips：+ 不用带"""
        
        self.notification_menu = """通知系统
-
艾特全体+内容
艾特管理+内容
-
Tips：+ 不用带"""
        
        self.cardkey_menu = """卡密系统
----
清空卡密
-
生成月卡+数量
生成季卡+数量
生成年卡+数量
查询卡密+卡密
使用卡密+卡密
-
清空已使用卡密
导出未使用卡密
-
生成卡密时间#数量
-
Tips：+ 不用带"""
        
        self.title_menu = """头衔系统
-
开自助头衔
关自助头衔
-
授头衔@QQ+头衔
申请头衔+头衔
-
恢复群成员默认头衔
-
添加头衔违禁词+内容
删除头衔违禁词+内容
-
查看头衔违禁词列表
清空头衔违禁词列表"""
    
    async def on_load(self):
        """插件加载时调用"""
        # 加载所有数据
        await self.data_manager.load_all_data()
        
        self.api.log("info", "小依群管插件加载成功")
        self.api.log("info", f"主人QQ: {self.permission_manager.owners}")
        self.api.log("info", f"管理员: {self.permission_manager.admins}")
        
        # 检查是否有待发送的重启成功消息
        try:
            import json
            import time
            from pathlib import Path
            plugin_dir = Path(__file__).parent
            data_dir = plugin_dir / "data"
            reload_info_file = data_dir / "reload_info.json"
            
            if reload_info_file.exists():
                try:
                    with open(reload_info_file, 'r', encoding='utf-8') as f:
                        reload_info = json.load(f)
                    
                    group_id = reload_info.get('group_id')
                    user_id = reload_info.get('user_id')
                    timestamp = reload_info.get('timestamp', 0)
                    
                    # 检查时间戳，如果超过30秒，可能是旧的重启信息，忽略
                    if time.time() - timestamp < 30:
                        # 发送重启成功消息
                        await self.api.send_group_msg(group_id, "插件重启成功")
                    
                    # 删除重启信息文件
                    reload_info_file.unlink()
                except Exception as e:
                    self.api.log("warning", f"处理重启信息失败: {e}")
                    # 如果处理失败，也删除文件，避免重复处理
                    try:
                        if reload_info_file.exists():
                            reload_info_file.unlink()
                    except:
                        pass
        except Exception as e:
            self.api.log("warning", f"检查重启信息时出错: {e}")
    
    async def on_unload(self):
        """插件卸载时调用"""
        # 保存所有数据
        await self.data_manager.save_all_data()
        self.api.log("info", "小依群管插件已卸载")
    
    async def send_reply(self, group_id: int, message: str, user_id: int = None):
        """发送回复消息（支持艾特发送和静默模式）
        
        Args:
            group_id: 群号
            message: 消息内容
            user_id: 发送者QQ号（用于@）
        """
        # 检查静默模式
        if self.reply_settings_module.is_silent_mode_enabled(group_id):
            return  # 静默模式，不发送任何回复
        
        # 检查艾特发送
        if user_id and self.reply_settings_module.is_at_reply_enabled(group_id):
            message = f"[CQ:at,qq={user_id}]\n{message}"
        
        result = await self.api.send_group_msg(group_id, message)
        
        # 如果启用了撤回自身，记录消息ID并延迟撤回
        group_id_str = str(group_id)
        settings = self.data_manager.recall_self_settings.get(group_id_str, {})
        if settings.get('enabled', False) and result:
            # result可能是dict，包含message_id
            message_id = None
            if isinstance(result, dict):
                message_id = result.get('message_id')
            elif isinstance(result, (int, str)):
                message_id = result
            
            if message_id:
                await self.recall_self_module.handle_message_sent({
                    'group_id': group_id,
                    'message_id': message_id,
                    'user_id': user_id
                })
    
    async def on_event_context(self, ctx):
        """处理事件上下文"""
        if ctx.event_name == "message.received":
            # 从事件上下文获取消息数据
            event_data = ctx.event_data
            # 快速返回，异步处理消息（避免阻塞事件处理）
            asyncio.create_task(self.handle_message(event_data))
            return ctx
        elif ctx.event_name == "notice.received":
            # 从事件上下文获取通知数据
            event_data = ctx.event_data
            # 快速返回，异步处理通知（避免阻塞事件处理）
            asyncio.create_task(self.handle_notice(event_data))
            return ctx
        return None
    
    async def handle_notice(self, event: Dict[str, Any]):
        """处理通知事件（入群、退群等）"""
        try:
            notice_type = event.get('notice_type')
            
            # 群成员增加
            if notice_type == 'group_increase':
                # 入群设置处理
                await self.join_settings_module.handle_group_increase(event)
                # 入群验证处理
                await self.join_verify_module.handle_group_increase(event)
        
        except Exception as e:
            self.api.log("error", f"处理通知事件时出错: {e}")
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件"""
        try:
            message_type = event.get('message_type')
            if message_type != 'group':
                return  # 只处理群消息
            
            # 记录消息ID（用于批量撤回）
            group_id = event.get('group_id')
            message_id = event.get('message_id')
            user_id = event.get('user_id')
            if group_id and message_id:
                group_id_str = str(group_id)
                if group_id_str not in self.data_manager.message_records:
                    self.data_manager.message_records[group_id_str] = []
                
                from datetime import datetime
                self.data_manager.message_records[group_id_str].append({
                    'message_id': message_id,
                    'user_id': user_id,
                    'time': datetime.now().isoformat()
                })
                
                # 限制每个群最多保存1000条记录
                if len(self.data_manager.message_records[group_id_str]) > 100:
                    self.data_manager.message_records[group_id_str] = self.data_manager.message_records[group_id_str][-1000:]
            
            # 记录消息到状态模块（用于统计）
            self.status_module.record_message()
            
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            raw_message = event.get('raw_message', '').strip()
            
            self.api.log("debug", f"收到群消息: {raw_message}, 来自用户: {user_id}, 群: {group_id}")
            
            # 检查群是否授权
            if not self.auth_module.is_group_authorized(group_id):
                # 只有主人或管理员的指令才处理
                if not self.permission_manager.is_owner_or_admin(user_id):
                    # 给出友好提示
                    if raw_message in ["菜单", "授权本群", "本群开机", "查询本群授权", "授权中心", 
                                      "权限管理", "基础群管", "黑白名单", "问答系统",
                                      "入群设置", "入群验证", "刷屏检测", "警告系统"]:
                        await self.api.send_group_msg(group_id, "❌ 本群未授权/未开机\n请联系机器人主人使用\"授权本群\"或\"本群开机\"指令启用插件")
                    return
                
                # 只处理授权相关指令和菜单查看（主人和管理员）
                if raw_message not in ["授权本群", "本群开机", "查询本群授权", "授权中心", "菜单"]:
                    return
            
            # 检查黑名单并执行处理
            if self.blacklist_module.is_in_blacklist(user_id, group_id):
                # 在白名单中的除外
                if not self.blacklist_module.is_in_whitelist(user_id, group_id):
                    await self.blacklist_module.handle_blacklist_user(user_id, group_id, event)
                    return
            
            # 菜单指令
            if raw_message == "菜单":
                await self.send_reply(group_id, self.main_menu, user_id)
                return
            
            # 子菜单指令
            if raw_message == "授权中心":
                await self.send_reply(group_id, self.auth_menu, user_id)
                return
            
            elif raw_message == "权限管理":
                await self.send_reply(group_id, self.perm_menu, user_id)
                return
            
            elif raw_message == "基础群管":
                await self.send_reply(group_id, self.basic_menu, user_id)
                return
            
            elif raw_message == "黑白名单":
                await self.send_reply(group_id, self.blacklist_menu, user_id)
                return
            
            elif raw_message == "入群设置":
                await self.send_reply(group_id, self.join_settings_menu, user_id)
                return
            
            elif raw_message == "入群验证":
                await self.send_reply(group_id, self.join_verify_menu, user_id)
                return
            
            elif raw_message == "刷屏检测":
                await self.send_reply(group_id, self.spam_menu, user_id)
                return
            
            elif raw_message == "警告系统":
                await self.send_reply(group_id, self.warning_menu, user_id)
                return
            
            elif raw_message == "留言反馈":
                await self.send_reply(group_id, self.feedback_menu, user_id)
                return
            
            elif raw_message == "名片系统":
                await self.send_reply(group_id, self.card_menu, user_id)
                return
            
            elif raw_message == "问答系统":
                await self.send_reply(group_id, self.qa_menu, user_id)
                return
            
            elif raw_message == "撤回系统":
                await self.send_reply(group_id, self.recall_menu, user_id)
                return
            
            elif raw_message == "禁言系统":
                await self.send_reply(group_id, self.mute_menu, user_id)
                return
            
            elif raw_message == "踢出系统":
                await self.send_reply(group_id, self.kick_menu, user_id)
                return
            
            elif raw_message == "资料修改":
                await self.send_reply(group_id, self.profile_menu, user_id)
                return
            
            elif raw_message == "提示系统":
                await self.send_reply(group_id, self.notification_settings_menu, user_id)
                return
            
            elif raw_message == "撤回自身":
                await self.send_reply(group_id, self.recall_self_menu, user_id)
                return
            
            elif raw_message == "回复设置":
                await self.send_reply(group_id, self.reply_settings_menu, user_id)
                return
            
            elif raw_message == "主人权限":
                await self.send_reply(group_id, self.owner_menu, user_id)
                return
            
            elif raw_message == "插件设置":
                await self.send_reply(group_id, self.plugin_settings_menu, user_id)
                return
            
            elif raw_message == "运行状态":
                await self.send_reply(group_id, self.status_menu, user_id)
                return
            
            elif raw_message == "违禁检测":
                await self.send_reply(group_id, self.banned_menu, user_id)
                return
            
            elif raw_message == "远程系统":
                await self.send_reply(group_id, self.remote_menu, user_id)
                return
            
            elif raw_message == "通知系统":
                await self.send_reply(group_id, self.notification_menu, user_id)
                return
            
            elif raw_message == "卡密系统":
                await self.send_reply(group_id, self.cardkey_menu, user_id)
                return
            
            elif raw_message == "头衔系统":
                await self.send_reply(group_id, self.title_menu, user_id)
                return
            
            # 尝试各个模块的指令处理
            # 授权中心
            if await self.auth_module.handle_command(event, raw_message):
                return
            
            # 权限管理
            if await self.perm_module.handle_command(event, raw_message):
                return
            
            # 基础群管
            if await self.basic_module.handle_command(event, raw_message):
                return
            
            # 黑白名单
            if await self.blacklist_module.handle_command(event, raw_message):
                return
            
            # 入群设置
            if await self.join_settings_module.handle_command(event, raw_message):
                return
            
            # 入群验证
            if await self.join_verify_module.handle_command(event, raw_message):
                return
            
            # 检查验证回复
            if await self.join_verify_module.check_verification(event):
                return
            
            # 刷屏检测
            if await self.spam_module.handle_command(event, raw_message):
                return
            
            # 警告系统
            if await self.warning_module.handle_command(event, raw_message):
                return
            
            # 违禁词检测（先检查指令）
            if await self.banned_words_module.handle_command(event, raw_message):
                return
            
            # 撤回系统指令
            if await self.auto_action_module.handle_recall_command(event, raw_message):
                return
            
            # 禁言系统指令
            if await self.auto_action_module.handle_mute_command(event, raw_message):
                return
            
            # 踢出系统指令
            if await self.auto_action_module.handle_kick_command(event, raw_message):
                return
            
            # 留言反馈
            if await self.message_feedback_module.handle_command(event, raw_message):
                return
            
            # 名片系统
            if await self.card_system_module.handle_command(event, raw_message):
                return
            
            # 远程系统
            if await self.remote_module.handle_command(event, raw_message):
                return
            
            # 通知系统
            if await self.notification_module.handle_command(event, raw_message):
                return
            
            # 卡密系统
            if await self.cardkey_module.handle_command(event, raw_message):
                return
            
            # 头衔系统
            if await self.title_module.handle_command(event, raw_message):
                return
            
            # 资料修改
            if await self.profile_module.handle_command(event, raw_message):
                return
            
            # 提示系统
            if await self.notification_settings_module.handle_command(event, raw_message):
                return
            
            # 撤回自身
            if await self.recall_self_module.handle_command(event, raw_message):
                return
            
            # 回复设置
            if await self.reply_settings_module.handle_command(event, raw_message):
                return
            
            # 主人权限
            if await self.owner_module.handle_command(event, raw_message):
                return
            
            # 运行状态
            if await self.status_module.handle_command(event, raw_message):
                return
            
            # 问答系统指令
            if await self.qa_module.handle_command(event, raw_message):
                return
            
            # 自动检测和处理（在最后执行）
            # 违禁词检测
            if await self.banned_words_module.check_banned_words(event):
                return
            
            # 刷屏检测
            await self.spam_module.check_spam(event)
            
            # 自动撤回/禁言/踢出
            await self.auto_action_module.check_auto_actions(event)
            
            # 问答系统自动回复（最后检查）
            await self.qa_module.check_and_answer(event)
        
        except Exception as e:
            self.api.log("error", f"处理消息时出错: {e}")


# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 实例
        config: 插件配置
        
    Returns:
        Plugin 实例
    """
    plugin = GroupManagerPlugin(api, config)
    await plugin.on_load()
    return plugin


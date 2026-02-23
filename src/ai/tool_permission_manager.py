"""Tool permission manager with AI and admin dual approval mechanism."""

import asyncio
import random
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.logger import get_logger
from ..core.database import get_database_manager
from ..core.models.tool_permission import ToolPermission, AdminUser, ToolApprovalLog
from .llm_client import LLMClient

logger = get_logger(__name__)


class ToolPermissionManager:
    """Manages tool permissions with dual approval (AI + Admin) mechanism."""
    
    def __init__(self):
        """Initialize tool permission manager."""
        self.db_manager = get_database_manager()
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}  # {approval_code: approval_data}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Start cleanup task for expired approvals
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background task to clean up expired approvals."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_approvals())
    
    async def _cleanup_expired_approvals(self):
        """Clean up expired pending approvals (runs every 1 minute)."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every 1 minute
                current_time = datetime.utcnow()
                expired_codes = []
                
                async with self._lock:
                    for code, data in self._pending_approvals.items():
                        expire_time = data.get('expire_time')
                        if expire_time and current_time > expire_time:
                            expired_codes.append(code)
                    
                    # Remove expired approvals
                    for code in expired_codes:
                        data = self._pending_approvals.pop(code)
                        log_id = data.get('log_id')
                        if log_id:
                            # Update log as expired
                            async with self.db_manager.session() as session:
                                await session.execute(
                                    update(ToolApprovalLog).where(
                                        ToolApprovalLog.id == log_id
                                    ).values(
                                        final_approved=False,
                                        final_reason="审核已过期（10分钟未响应）"
                                    )
                                )
                                await session.commit()
                        logger.info(f"Cleaned up expired approval: {code}")
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
    
    async def check_tool_permission(
        self,
        tool_name: str,
        user_qq: str,
        tool_args: Dict[str, Any],
        chat_type: str,
        chat_id: str,
        user_nickname: Optional[str] = None,
        llm_client: Optional[LLMClient] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """Check if a tool can be used by the user.
        
        Returns dual approval mechanism:
        1. AI审核：判断工具使用是否合理
        2. 管理员审核：判断用户是否有权限
        
        Args:
            tool_name: Tool name
            user_qq: User QQ number
            tool_args: Tool arguments
            chat_type: 'group' or 'private'
            chat_id: Group ID or QQ number
            user_nickname: User nickname
            llm_client: LLM client for AI approval
            
        Returns:
            (approved: bool, reason: str, log_id: Optional[int])
        """
        async with self._lock:
            try:
                # 1. Get tool permission configuration
                async with self.db_manager.session() as session:
                    result = await session.execute(
                        select(ToolPermission).where(ToolPermission.tool_name == tool_name)
                    )
                    tool_perm = result.scalar_one_or_none()
                
                # If no permission config, allow by default
                if not tool_perm:
                    logger.debug(f"Tool {tool_name} has no permission config, allowing by default")
                    return (True, "工具无需权限", None)
                
                # 2. Check if user is in allowed list (only if requires_permission is True)
                if tool_perm.requires_permission:
                    if user_qq not in tool_perm.allowed_users:
                        reason = f"用户 {user_qq} 不在工具 {tool_name} 的允许列表中"
                        logger.warning(reason)
                        
                        # Create audit log
                        log_id = await self._create_approval_log(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            user_qq=user_qq,
                            user_nickname=user_nickname,
                            chat_type=chat_type,
                            chat_id=chat_id,
                            final_approved=False,
                            final_reason=reason
                        )
                        
                        return (False, reason, log_id)
                else:
                    # requires_permission is False, skip user whitelist check
                    logger.debug(f"Tool {tool_name} does not require user whitelist check")
                
                # 3. AI Approval (if required and LLM client available)
                ai_approved = None
                ai_reason = None
                
                if tool_perm.requires_ai_approval:
                    # If no LLM client provided, try to get from group/user config
                    if not llm_client:
                        logger.info(f"LLM client not provided, trying to get from {chat_type} config for {chat_id}")
                        try:
                            from ..core.database import get_database_manager
                            from .llm_client import LLMClient
                            from .model_manager import ModelManager
                            
                            db_manager = get_database_manager()
                            model_manager = ModelManager(db_manager)
                            
                            # Get AI config for the group/user
                            config_type = 'group' if chat_type == 'group' else 'user'
                            ai_config = await db_manager.get_ai_config(config_type, chat_id)
                            
                            # If no group/user config, try global config
                            if not ai_config:
                                ai_config = await db_manager.get_ai_config('global', None)
                            
                            # Try to get decision model first, fallback to main model
                            model_uuid = None
                            if ai_config:
                                # First try decision_model_uuid from config
                                decision_model_uuid = ai_config.config.get('decision_model_uuid') if ai_config.config else None
                                if decision_model_uuid:
                                    model_uuid = decision_model_uuid
                                    logger.info(f"Using decision model for AI approval: {model_uuid}")
                                else:
                                    # Fallback to main model
                                    model_uuid = ai_config.model_uuid
                                    logger.info(f"Using main model for AI approval: {model_uuid}")
                            
                            if not model_uuid:
                                default_model = await db_manager.get_default_llm_model()
                                if default_model:
                                    model_uuid = default_model.uuid
                            
                            if model_uuid:
                                model_data = await model_manager.get_model_with_secret(model_uuid)
                                if model_data:
                                    api_key = model_data.get('api_key', '')
                                    base_url = model_data.get('base_url', 'https://api.openai.com/v1')
                                    model_name = model_data.get('model_name', 'gpt-3.5-turbo')
                                    provider = model_data.get('provider', 'openai')
                                    
                                    api_format = model_data.get('config', {}).get('api_format', 'openai')
                                    llm_client = LLMClient(
                                        api_key=api_key,
                                        base_url=base_url,
                                        model_name=model_name,
                                        provider=provider,
                                        api_format=api_format
                                    )
                                    logger.info(f"Created LLM client for decision model from {config_type} config: {model_name}")
                        except Exception as e:
                            logger.error(f"Failed to get LLM client from config: {e}", exc_info=True)
                    
                    if not llm_client:
                        logger.warning(f"AI approval required for tool {tool_name} but llm_client is None")
                        # If AI approval is required but no LLM client, reject
                        reason = "AI审核已启用但LLM客户端不可用"
                        log_id = await self._create_approval_log(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            user_qq=user_qq,
                            user_nickname=user_nickname,
                            chat_type=chat_type,
                            chat_id=chat_id,
                            ai_approved=False,
                            ai_reason=reason,
                            final_approved=False,
                            final_reason=reason
                        )
                        return (False, reason, log_id)
                    
                    logger.info(f"Performing AI approval for tool {tool_name}")
                    ai_approved, ai_reason = await self._ai_approval(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        user_qq=user_qq,
                        chat_type=chat_type,
                        chat_id=chat_id,
                        llm_client=llm_client
                    )
                    
                    logger.info(f"AI approval result for {tool_name}: approved={ai_approved}, reason={ai_reason}")
                    
                    if not ai_approved:
                        # Build detailed reason for AI rejection
                        if ai_reason and ai_reason != "未知原因":
                            reason = f"AI审核拒绝：{ai_reason}"
                        else:
                            reason = f"AI审核拒绝：工具使用不合理或不安全"
                        logger.warning(f"AI rejected tool {tool_name}: {ai_reason}")
                        
                        log_id = await self._create_approval_log(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            user_qq=user_qq,
                            user_nickname=user_nickname,
                            chat_type=chat_type,
                            chat_id=chat_id,
                            ai_approved=False,
                            ai_reason=ai_reason or "未知原因",
                            final_approved=False,
                            final_reason=reason
                        )
                        
                        return (False, reason, log_id)
                
                # 4. Admin Approval (if required)
                if tool_perm.requires_admin_approval:
                    # Create pending approval log
                    log_id = await self._create_approval_log(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        user_qq=user_qq,
                        user_nickname=user_nickname,
                        chat_type=chat_type,
                        chat_id=chat_id,
                        ai_approved=ai_approved,
                        ai_reason=ai_reason,
                        final_approved=False,
                        final_reason="等待管理员审核"
                    )
                    
                    # Generate random approval code
                    approval_code = f"{random.randint(100000, 999999)}"
                    expire_time = datetime.utcnow() + timedelta(minutes=10)
                    
                    # Store pending approval
                    self._pending_approvals[approval_code] = {
                        'log_id': log_id,
                        'tool_name': tool_name,
                        'tool_args': tool_args,
                        'user_qq': user_qq,
                        'user_nickname': user_nickname,
                        'chat_id': chat_id,
                        'chat_type': chat_type,
                        'ai_approved': ai_approved,
                        'ai_reason': ai_reason,
                        'expire_time': expire_time,
                        'approval_code': approval_code
                    }
                    
                    # Send approval request message to group
                    await self._send_approval_request_message(
                        chat_type=chat_type,
                        chat_id=chat_id,
                        user_qq=user_qq,
                        user_nickname=user_nickname,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        approval_code=approval_code,
                        ai_reason=ai_reason
                    )
                    
                    logger.info(f"Tool {tool_name} requires admin approval, code={approval_code}, log_id={log_id}")
                    return (False, f"工具 {tool_name} 需要管理员审核，请在群里查看审核请求", log_id)
                
                # 5. All checks passed
                log_id = await self._create_approval_log(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    user_qq=user_qq,
                    user_nickname=user_nickname,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    ai_approved=ai_approved,
                    ai_reason=ai_reason,
                    final_approved=True,
                    final_reason="权限检查通过"
                )
                
                logger.info(f"Tool {tool_name} approved for user {user_qq}")
                return (True, "权限检查通过", log_id)
                
            except Exception as e:
                logger.error(f"Failed to check tool permission: {e}", exc_info=True)
                return (False, f"权限检查失败: {str(e)}", None)
    
    async def _send_approval_request_message(
        self,
        chat_type: str,
        chat_id: str,
        user_qq: str,
        user_nickname: Optional[str],
        tool_name: str,
        tool_args: Dict[str, Any],
        approval_code: str,
        ai_reason: Optional[str]
    ):
        """Send approval request message to group."""
        try:
            # Only send to group chats
            if chat_type != 'group':
                logger.info("Approval request only sent in group chats")
                return
            
            # Get OneBot adapter
            from ..core.app import get_app
            app = get_app()
            if not app or not hasattr(app, 'onebot_adapter'):
                logger.error("OneBot adapter not available")
                return
            
            onebot = app.onebot_adapter
            
            # Format tool arguments for display
            args_str = ""
            for key, value in tool_args.items():
                if key.startswith('_'):  # Skip internal parameters
                    continue
                args_str += f"\n  - {key}: {value}"
            if not args_str:
                args_str = "\n  无"
            
            # Build approval message
            user_display = f"{user_qq}"
            if user_nickname:
                user_display = f"{user_nickname}({user_qq})"
            
            message = f"""━━━━━ 工具使用审核 ━━━━━
【申请用户】{user_display}
【工具名称】{tool_name}
【工具参数】{args_str}"""
            
            # Always show AI approval result if AI approval was performed
            if ai_reason:
                message += f"\n【AI 审核】✅ {ai_reason}"
            else:
                # If AI approval was required but no reason, show a default message
                message += f"\n【AI 审核】✅ 已通过（未提供详细理由）"
            
            message += f"""

10分钟内有效
通过请回复：通过_{approval_code}
拒绝请无视此消息
━━━━━━━━━━━━━━━"""
            
            # Send message to group
            await onebot.send_message(chat_id, message, "group")
            logger.info(f"Sent approval request to group {chat_id}, code={approval_code}")
            
        except Exception as e:
            logger.error(f"Failed to send approval request message: {e}", exc_info=True)
    
    async def handle_approval_response(
        self,
        admin_qq: str,
        message: str,
        chat_id: str
    ) -> Optional[Dict[str, Any]]:
        """Handle admin approval response from group message.
        
        Args:
            admin_qq: Admin QQ number
            message: Message content (e.g., "通过_123456")
            chat_id: Group ID where the message was sent
            
        Returns:
            Result dict or None if not an approval message
        """
        try:
            # Check if message is an approval response
            if not message.startswith("通过_"):
                return None
            
            # Extract approval code
            parts = message.split("_", 1)
            if len(parts) != 2:
                return None
            
            approval_code = parts[1].strip()
            
            # Check if code exists
            async with self._lock:
                if approval_code not in self._pending_approvals:
                    logger.warning(f"Invalid approval code: {approval_code} (may have been processed already)")
                    # Don't return error message - the approval might have been processed by another request
                    # This prevents duplicate error messages when there's a race condition
                    return None
                
                approval_data = self._pending_approvals[approval_code]
                
                # Verify the approval is for this group
                if approval_data['chat_id'] != chat_id:
                    logger.warning(f"Approval code {approval_code} not for this group")
                    return None
                
                # Remove from pending BEFORE approval to prevent duplicate processing
                # This ensures the code can only be used once
                del self._pending_approvals[approval_code]
                
                # Check if admin has permission
                success = await self.admin_approve_tool(
                    log_id=approval_data['log_id'],
                    admin_qq=admin_qq,
                    approved=True,
                    reason=f"管理员 {admin_qq} 通过审核"
                )
                
                if success:
                    # Execute the tool now
                    result = await self._execute_approved_tool(approval_data)
                    
                    # Build detailed result message
                    if result.get('success', False):
                        tool_result_msg = result.get('message', '工具执行成功')
                        return {
                            'success': True,
                            'message': f"✅ 审核通过，工具已执行\n工具: {approval_data['tool_name']}\n用户: {approval_data['user_qq']}\n结果: {tool_result_msg}",
                            'execution_result': result
                        }
                    else:
                        error_msg = result.get('error', '未知错误')
                        return {
                            'success': False,
                            'message': f"❌ 审核通过，但工具执行失败\n工具: {approval_data['tool_name']}\n错误: {error_msg}",
                            'execution_result': result
                        }
                else:
                    # Get tool danger level for error message
                    async with self.db_manager.session() as session:
                        result = await session.execute(
                            select(ToolPermission).where(
                                ToolPermission.tool_name == approval_data['tool_name']
                            )
                        )
                        tool_perm = result.scalar_one_or_none()
                        
                        if tool_perm:
                            tool_danger_level = tool_perm.danger_level
                            result = await session.execute(
                                select(AdminUser).where(AdminUser.qq_number == admin_qq)
                            )
                            admin = result.scalar_one_or_none()
                            if admin:
                                admin_level = admin.permission_level
                                return {
                                    'success': False,
                                    'message': f"❌ 权限不足：您需要权限等级 {tool_danger_level} 才能审核此工具（危险等级 {tool_danger_level}），您当前权限等级为 {admin_level}"
                                }
                    
                    return {
                        'success': False,
                        'message': f"❌ 您没有审核此工具的权限"
                    }
        
        except Exception as e:
            logger.error(f"Failed to handle approval response: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"处理审核失败: {str(e)}"
            }
    
    async def _execute_approved_tool(self, approval_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool after admin approval."""
        try:
            from .tools import AITools
            
            result = await AITools.call_tool(
                tool_name=approval_data['tool_name'],
                arguments=approval_data['tool_args'],
                user_qq=approval_data['user_qq'],
                chat_type=approval_data['chat_type'],
                chat_id=approval_data['chat_id'],
                user_nickname=approval_data.get('user_nickname'),
                skip_permission_check=True  # Already approved
            )
            
            # Update execution status in log
            await self.mark_tool_executed(
                log_id=approval_data['log_id'],
                success=result.get('success', False),
                result=str(result)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute approved tool: {e}", exc_info=True)
            await self.mark_tool_executed(
                log_id=approval_data['log_id'],
                success=False,
                result=f"执行失败: {str(e)}"
            )
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _ai_approval(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        user_qq: str,
        chat_type: str,
        chat_id: str,
        llm_client: LLMClient
    ) -> Tuple[bool, str]:
        """AI审核工具使用是否合理.
        
        Returns:
            (approved: bool, reason: str)
        """
        try:
            # Build AI approval prompt
            from .prompts import build_tool_permission_prompt
            prompt = build_tool_permission_prompt(tool_name, tool_args, user_qq, chat_type, chat_id)
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=500,  # Increased from 300 to allow complete JSON response
                stream=False
            )
            
            # Extract response text from different possible formats
            # The LLM client may return the raw API response or a parsed response
            response_text = ""
            content_text = ""
            reasoning_text = ""
            
            # Check if response is the raw API response (from choices[0].message)
            if isinstance(response, dict):
                # First, try to get from parsed response format
                content_text = response.get("content", "") or ""
                reasoning_text = response.get("reasoning_content", "") or ""
                
                # If empty, check if it's the raw API response format
                if not content_text and not reasoning_text:
                    # Check for choices[0].message format (raw API response)
                    if "choices" in response:
                        choices = response.get("choices", [])
                        if choices and isinstance(choices[0], dict):
                            message = choices[0].get("message", {})
                            if isinstance(message, dict):
                                content_text = message.get("content", "") or ""
                                reasoning_text = message.get("reasoning_content", "") or ""
                
                # Use content or reasoning_content
                response_text = content_text or reasoning_text
            else:
                response_text = str(response)
            
            logger.debug(f"AI approval response - content: {content_text[:200] if content_text else 'empty'}, reasoning: {reasoning_text[:200] if reasoning_text else 'empty'}")
            
            # Parse AI response
            import re
            import json
            from json_repair import repair_json
            
            # Try to find JSON in response
            # First, try to find JSON with "approved" field (this is what we're looking for)
            json_match = re.search(r'\{[^}]*"approved"[^}]*\}', response_text, re.DOTALL)
            if not json_match:
                # Try to find JSON with "reason" field
                json_match = re.search(r'\{[^}]*"reason"[^}]*\}', response_text, re.DOTALL)
            if not json_match:
                # Try to find any JSON object that looks like our approval response
                # Match JSON objects that contain both approved and reason, or at least one of them
                json_match = re.search(r'\{[^}]*"(?:approved|reason)"[^}]*\}', response_text, re.DOTALL)
            if not json_match:
                # Last resort: try to find JSON in reasoning_content if it wasn't in content
                if reasoning_text and not content_text:
                    json_match = re.search(r'\{[^}]*"approved"[^}]*\}', reasoning_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                logger.debug(f"Found JSON in AI approval response: {json_str[:500]}")
                try:
                    result = json.loads(json_str)
                    logger.debug(f"Successfully parsed JSON: {result}")
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error: {e}, trying to repair...")
                    try:
                        logger.debug("Trying to repair JSON...")
                        repaired_json = repair_json(json_str)
                        logger.debug(f"Repaired JSON: {repaired_json[:500]}")
                        result = json.loads(repaired_json)
                    except Exception as repair_error:
                        logger.warning(f"Failed to repair JSON: {repair_error}, original JSON: {json_str[:500]}")
                        result = None
                
                if result:
                    approved = result.get('approved', False)
                    reason = result.get('reason', '未知原因')
                    logger.info(f"AI approval parsed: approved={approved}, reason={reason}")
                    return (approved, reason)
                else:
                    logger.warning(f"JSON matched but could not parse: {json_str[:500]}")
            
            # Fallback: approve by default if cannot parse
            logger.warning(f"Failed to parse AI approval response, approving by default.")
            logger.warning(f"Full response text (first 1000 chars): {response_text[:1000]}")
            logger.warning(f"Content field: {content_text[:500] if content_text else 'empty'}")
            logger.warning(f"Reasoning field: {reasoning_text[:500] if reasoning_text else 'empty'}")
            return (True, "AI审核解析失败，默认通过")
            
        except Exception as e:
            logger.error(f"AI approval failed: {e}", exc_info=True)
            # On error, approve by default to avoid blocking
            return (True, f"AI审核失败: {str(e)}，默认通过")
    
    async def admin_approve_tool(
        self,
        log_id: int,
        admin_qq: str,
        approved: bool,
        reason: Optional[str] = None
    ) -> bool:
        """管理员审批工具使用.
        
        Args:
            log_id: Approval log ID
            admin_qq: Admin QQ number
            approved: Whether approved
            reason: Approval/rejection reason
            
        Returns:
            True if successful
        """
        try:
            # Check if admin has permission
            async with self.db_manager.session() as session:
                result = await session.execute(
                    select(AdminUser).where(
                        AdminUser.qq_number == admin_qq,
                        AdminUser.is_active == True
                    )
                )
                admin = result.scalar_one_or_none()
                
                if not admin:
                    logger.warning(f"User {admin_qq} is not an admin")
                    return False
                
                # Get approval log
                result = await session.execute(
                    select(ToolApprovalLog).where(ToolApprovalLog.id == log_id)
                )
                log = result.scalar_one_or_none()
                
                if not log:
                    logger.warning(f"Approval log {log_id} not found")
                    return False
                
                # Get tool permission config to check danger level
                result = await session.execute(
                    select(ToolPermission).where(ToolPermission.tool_name == log.tool_name)
                )
                tool_perm = result.scalar_one_or_none()
                
                # Check if admin can approve this tool (by tool name)
                # can_approve_all_tools means can approve all tool names, but still need to check danger level
                if not admin.can_approve_all_tools:
                    if log.tool_name not in admin.approved_tools:
                        logger.warning(f"Admin {admin_qq} cannot approve tool {log.tool_name}")
                        return False
                
                # Check danger level: admin permission level must >= tool danger level
                # This check applies to ALL admins, regardless of can_approve_all_tools
                if tool_perm:
                    tool_danger_level = tool_perm.danger_level
                    admin_permission_level = admin.permission_level
                    
                    if admin_permission_level < tool_danger_level:
                        logger.warning(
                            f"Admin {admin_qq} (level {admin_permission_level}) cannot approve "
                            f"tool {log.tool_name} (danger level {tool_danger_level})"
                        )
                        return False
                else:
                    # If no tool permission config, allow by default (no danger level restriction)
                    logger.debug(f"Tool {log.tool_name} has no permission config, allowing approval")
                
                # Update approval log
                await session.execute(
                    update(ToolApprovalLog).where(
                        ToolApprovalLog.id == log_id
                    ).values(
                        admin_approved=approved,
                        admin_qq=admin_qq,
                        admin_reason=reason,
                        final_approved=approved,
                        final_reason=reason or ("管理员批准" if approved else "管理员拒绝"),
                        approved_at=datetime.utcnow() if approved else None
                    )
                )
                
                # Update admin statistics
                if approved:
                    await session.execute(
                        update(AdminUser).where(
                            AdminUser.qq_number == admin_qq
                        ).values(
                            total_approvals=AdminUser.total_approvals + 1,
                            last_active_at=datetime.utcnow()
                        )
                    )
                else:
                    await session.execute(
                        update(AdminUser).where(
                            AdminUser.qq_number == admin_qq
                        ).values(
                            total_rejections=AdminUser.total_rejections + 1,
                            last_active_at=datetime.utcnow()
                        )
                    )
                
                await session.commit()
            
            logger.info(f"Admin {admin_qq} {'approved' if approved else 'rejected'} tool request {log_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to admin approve tool: {e}", exc_info=True)
            return False
    
    async def _create_approval_log(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        user_qq: str,
        chat_type: str,
        chat_id: str,
        user_nickname: Optional[str] = None,
        ai_approved: Optional[bool] = None,
        ai_reason: Optional[str] = None,
        admin_approved: Optional[bool] = None,
        admin_qq: Optional[str] = None,
        admin_reason: Optional[str] = None,
        final_approved: bool = False,
        final_reason: Optional[str] = None
    ) -> int:
        """Create approval audit log.
        
        Keeps only the latest 10 logs by deleting older ones.
        
        Returns:
            Log ID
        """
        from sqlalchemy import select, delete, desc, func
        
        async with self.db_manager.session() as session:
            # Create new log
            log = ToolApprovalLog(
                tool_name=tool_name,
                tool_args=tool_args,
                user_qq=user_qq,
                user_nickname=user_nickname,
                chat_type=chat_type,
                chat_id=chat_id,
                ai_approved=ai_approved,
                ai_reason=ai_reason,
                admin_approved=admin_approved,
                admin_qq=admin_qq,
                admin_reason=admin_reason,
                final_approved=final_approved,
                final_reason=final_reason
            )
            session.add(log)
            await session.flush()  # Flush to get the ID
            
            # Keep only the latest 10 logs
            # Get the ID of the 10th newest log (if exists)
            count_query = select(func.count(ToolApprovalLog.id))
            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0
            
            if total_count > 10:
                # Get the ID of the 10th newest log
                query = select(ToolApprovalLog.id).order_by(desc(ToolApprovalLog.created_at)).offset(9).limit(1)
                result = await session.execute(query)
                tenth_log_id = result.scalar()
                
                if tenth_log_id:
                    # Delete all logs older than the 10th newest
                    delete_query = delete(ToolApprovalLog).where(ToolApprovalLog.id < tenth_log_id)
                    await session.execute(delete_query)
                    logger.debug(f"Deleted old approval logs, keeping only the latest 10")
            
            await session.commit()
            await session.refresh(log)
            return log.id
    
    async def mark_tool_executed(
        self,
        log_id: int,
        success: bool,
        result: Optional[str] = None
    ) -> bool:
        """Mark tool as executed in approval log.
        
        Args:
            log_id: Approval log ID
            success: Whether execution was successful
            result: Execution result message
            
        Returns:
            True if successful
        """
        try:
            async with self.db_manager.session() as session:
                await session.execute(
                    update(ToolApprovalLog).where(
                        ToolApprovalLog.id == log_id
                    ).values(
                        executed=True,
                        execution_success=success,
                        execution_result=result,
                        executed_at=datetime.utcnow()
                    )
                )
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to mark tool executed: {e}", exc_info=True)
            return False


# Global tool permission manager
_tool_permission_manager: Optional[ToolPermissionManager] = None


def get_tool_permission_manager() -> ToolPermissionManager:
    """Get or create global tool permission manager."""
    global _tool_permission_manager
    if _tool_permission_manager is None:
        _tool_permission_manager = ToolPermissionManager()
    return _tool_permission_manager

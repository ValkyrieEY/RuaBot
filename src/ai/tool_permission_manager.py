"""Tool permission manager with AI and admin dual approval mechanism."""

import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
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
        self._pending_approvals: Dict[int, Dict[str, Any]] = {}  # {log_id: approval_data}
        self._lock = asyncio.Lock()
    
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
                if not tool_perm or not tool_perm.requires_permission:
                    logger.debug(f"Tool {tool_name} does not require permission")
                    return (True, "工具无需权限", None)
                
                # 2. Check if user is in allowed list
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
                
                # 3. AI Approval (if required and LLM client available)
                ai_approved = None
                ai_reason = None
                
                if tool_perm.requires_ai_approval and llm_client:
                    ai_approved, ai_reason = await self._ai_approval(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        user_qq=user_qq,
                        chat_type=chat_type,
                        chat_id=chat_id,
                        llm_client=llm_client
                    )
                    
                    if not ai_approved:
                        reason = f"AI拒绝：{ai_reason}"
                        logger.warning(f"AI rejected tool {tool_name}: {ai_reason}")
                        
                        log_id = await self._create_approval_log(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            user_qq=user_qq,
                            user_nickname=user_nickname,
                            chat_type=chat_type,
                            chat_id=chat_id,
                            ai_approved=False,
                            ai_reason=ai_reason,
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
                    
                    # Store pending approval
                    self._pending_approvals[log_id] = {
                        'tool_name': tool_name,
                        'tool_args': tool_args,
                        'user_qq': user_qq,
                        'chat_id': chat_id,
                        'chat_type': chat_type
                    }
                    
                    logger.info(f"Tool {tool_name} requires admin approval, log_id={log_id}")
                    return (False, f"工具 {tool_name} 需要管理员审核，审核ID: {log_id}", log_id)
                
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
            prompt = f"""你是一个安全审核助手，需要判断以下工具调用是否合理和安全。

**工具信息**
- 工具名称: {tool_name}
- 工具参数: {tool_args}

**用户信息**
- 用户QQ: {user_qq}
- 聊天类型: {chat_type}
- 聊天ID: {chat_id}

**审核要求**
请判断这个工具调用是否:
1. 符合工具的正常使用场景
2. 参数是否合理（例如禁言时长不过分、不针对管理员等）
3. 没有明显的恶意或滥用倾向

请以 JSON 格式输出：
{{
  "approved": true/false,
  "reason": "批准或拒绝的理由（简短说明）"
}}
"""
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=300,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            # Parse AI response
            import re
            import json
            from json_repair import repair_json
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    result = json.loads(repair_json(json_str))
                
                approved = result.get('approved', False)
                reason = result.get('reason', '未知原因')
                
                return (approved, reason)
            
            # Fallback: approve by default if cannot parse
            logger.warning("Failed to parse AI approval response, approving by default")
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
                
                # Check if admin can approve this tool
                if not admin.can_approve_all_tools:
                    if log.tool_name not in admin.approved_tools:
                        logger.warning(f"Admin {admin_qq} cannot approve tool {log.tool_name}")
                        return False
                
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
            
            # Remove from pending approvals
            if log_id in self._pending_approvals:
                del self._pending_approvals[log_id]
            
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
        
        Returns:
            Log ID
        """
        async with self.db_manager.session() as session:
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


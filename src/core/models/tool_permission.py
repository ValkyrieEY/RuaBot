"""Tool permission management database models."""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ToolPermission(Base):
    """Tool permission configuration.
    
    Defines which tools require special permissions and who can approve them.
    """
    __tablename__ = 'tool_permissions'
    
    # Primary key
    tool_name = Column(String(255), primary_key=True, nullable=False)
    
    # Permission settings
    requires_permission = Column(Boolean, nullable=False, default=False)  # 是否需要权限
    requires_admin_approval = Column(Boolean, nullable=False, default=False)  # 是否需要管理员审核
    requires_ai_approval = Column(Boolean, nullable=False, default=True)  # 是否需要AI审核（默认开启）
    
    # Allowed users (JSON array of QQ numbers)
    allowed_users = Column(JSON, nullable=False, default=list)  # 允许使用的QQ列表
    
    # Tool metadata
    tool_category = Column(String(100), nullable=True)  # 工具分类
    tool_description = Column(Text, nullable=True)  # 工具描述
    danger_level = Column(Integer, nullable=False, default=0)  # 危险等级 (0-5)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ToolPermission(tool='{self.tool_name}', requires={self.requires_permission})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'tool_name': self.tool_name,
            'requires_permission': self.requires_permission,
            'requires_admin_approval': self.requires_admin_approval,
            'requires_ai_approval': self.requires_ai_approval,
            'allowed_users': self.allowed_users,
            'tool_category': self.tool_category,
            'tool_description': self.tool_description,
            'danger_level': self.danger_level,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AdminUser(Base):
    """Administrator QQ users who can approve tool usage.
    
    These users have authority to approve dangerous tool operations.
    """
    __tablename__ = 'admin_users'
    
    # Primary key
    qq_number = Column(String(20), primary_key=True, nullable=False)
    
    # Admin info
    nickname = Column(String(255), nullable=True)  # 昵称
    permission_level = Column(Integer, nullable=False, default=1)  # 权限等级 (1=普通管理, 2=超级管理)
    is_active = Column(Boolean, nullable=False, default=True)  # 是否启用
    
    # Approval settings
    can_approve_all_tools = Column(Boolean, nullable=False, default=False)  # 可以审批所有工具
    approved_tools = Column(JSON, nullable=False, default=list)  # 可以审批的工具列表
    
    # Statistics
    total_approvals = Column(Integer, nullable=False, default=0)  # 总审批次数
    total_rejections = Column(Integer, nullable=False, default=0)  # 总拒绝次数
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, nullable=True)  # 最后活跃时间
    
    def __repr__(self):
        return f"<AdminUser(qq='{self.qq_number}', level={self.permission_level}, active={self.is_active})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'qq_number': self.qq_number,
            'nickname': self.nickname,
            'permission_level': self.permission_level,
            'is_active': self.is_active,
            'can_approve_all_tools': self.can_approve_all_tools,
            'approved_tools': self.approved_tools,
            'total_approvals': self.total_approvals,
            'total_rejections': self.total_rejections,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_active_at': self.last_active_at.isoformat() if self.last_active_at else None,
        }


class ToolApprovalLog(Base):
    """Tool approval audit log.
    
    Records all tool approval/rejection decisions for security auditing.
    """
    __tablename__ = 'tool_approval_logs'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Tool call info
    tool_name = Column(String(255), nullable=False, index=True)
    tool_args = Column(JSON, nullable=True)  # 工具参数
    
    # User info
    user_qq = Column(String(20), nullable=False, index=True)  # 请求用户
    user_nickname = Column(String(255), nullable=True)
    
    # Chat info
    chat_type = Column(String(20), nullable=False)  # 'group' or 'private'
    chat_id = Column(String(255), nullable=False, index=True)  # 群号或QQ号
    
    # AI approval
    ai_approved = Column(Boolean, nullable=True)  # AI是否批准
    ai_reason = Column(Text, nullable=True)  # AI的理由
    
    # Admin approval
    admin_approved = Column(Boolean, nullable=True)  # 管理员是否批准
    admin_qq = Column(String(20), nullable=True)  # 审批管理员QQ
    admin_reason = Column(Text, nullable=True)  # 管理员的理由
    
    # Final decision
    final_approved = Column(Boolean, nullable=False)  # 最终是否批准
    final_reason = Column(Text, nullable=True)  # 最终理由
    
    # Execution result
    executed = Column(Boolean, nullable=False, default=False)  # 是否已执行
    execution_success = Column(Boolean, nullable=True)  # 执行是否成功
    execution_result = Column(Text, nullable=True)  # 执行结果
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)  # 批准时间
    executed_at = Column(DateTime, nullable=True)  # 执行时间
    
    def __repr__(self):
        return f"<ToolApprovalLog(id={self.id}, tool='{self.tool_name}', approved={self.final_approved})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'tool_name': self.tool_name,
            'tool_args': self.tool_args,
            'user_qq': self.user_qq,
            'user_nickname': self.user_nickname,
            'chat_type': self.chat_type,
            'chat_id': self.chat_id,
            'ai_approved': self.ai_approved,
            'ai_reason': self.ai_reason,
            'admin_approved': self.admin_approved,
            'admin_qq': self.admin_qq,
            'admin_reason': self.admin_reason,
            'final_approved': self.final_approved,
            'final_reason': self.final_reason,
            'executed': self.executed,
            'execution_success': self.execution_success,
            'execution_result': self.execution_result,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
        }


"""模块初始化"""

from .authorization import AuthorizationModule
from .permission import PermissionModule
from .basic_manage import BasicManageModule
from .blacklist import BlackWhiteListModule
from .qa_system import QAModule
from .join_settings import JoinSettingsModule
from .join_verify import JoinVerifyModule
from .spam_warning import SpamDetectionModule, WarningModule
from .auto_actions import BannedWordsModule, AutoActionModule
from .other_modules import (
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
    OwnerModule
)
from .status_module import StatusModule

__all__ = [
    'AuthorizationModule',
    'PermissionModule', 
    'BasicManageModule',
    'BlackWhiteListModule',
    'QAModule',
    'JoinSettingsModule',
    'JoinVerifyModule',
    'SpamDetectionModule',
    'WarningModule',
    'BannedWordsModule',
    'AutoActionModule',
    'MessageFeedbackModule',
    'CardSystemModule',
    'RemoteModule',
    'NotificationModule',
    'CardKeyModule',
    'TitleModule',
    'ProfileModule',
    'NotificationSettingsModule',
    'RecallSelfModule',
    'ReplySettingsModule',
    'OwnerModule',
    'StatusModule'
]


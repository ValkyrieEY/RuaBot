"""AI系统检测器 - 检测AI扩展是否可用。

这个模块负责检测AI系统是否已安装并可用。
AI系统是可选的，框架可以在没有AI的情况下正常运行。
"""

import os
import importlib.util
from pathlib import Path
from typing import Optional
from .logger import get_logger

logger = get_logger(__name__)


class AIDetector:
    """AI系统检测器。"""
    
    def __init__(self):
        self._ai_available: Optional[bool] = None
        self._ai_module_path: Optional[Path] = None
    
    def is_ai_available(self) -> bool:
        """检测AI系统是否可用。
        
        Returns:
            True如果AI系统可用，否则False
        """
        if self._ai_available is not None:
            return self._ai_available
        
        try:
            # 检查AI模块目录是否存在
            ai_dir = Path(__file__).parent.parent / "ai"
            if not ai_dir.exists():
                logger.info("AI系统未安装：ai目录不存在")
                self._ai_available = False
                return False
            
            # 检查关键AI模块是否存在
            required_modules = [
                "message_handler.py",
                "ai_database.py",
                "ai_manager.py"
            ]
            
            for module_name in required_modules:
                module_path = ai_dir / module_name
                if not module_path.exists():
                    logger.info(f"AI系统不完整：缺少 {module_name}")
                    self._ai_available = False
                    return False
            
            # 尝试导入AI消息处理器
            try:
                from ..ai.message_handler import AIMessageHandler
                logger.info("AI系统已检测到并可用")
                self._ai_available = True
                self._ai_module_path = ai_dir
                return True
            except ImportError as e:
                logger.warning(f"AI系统模块导入失败: {e}")
                self._ai_available = False
                return False
                
        except Exception as e:
            logger.error(f"AI系统检测失败: {e}", exc_info=True)
            self._ai_available = False
            return False
    
    def get_ai_module_path(self) -> Optional[Path]:
        """获取AI模块路径。
        
        Returns:
            AI模块路径，如果不可用返回None
        """
        if self.is_ai_available():
            return self._ai_module_path
        return None
    
    def reset(self):
        """重置检测状态（用于重新检测）。"""
        self._ai_available = None
        self._ai_module_path = None


# 全局AI检测器实例
_ai_detector: Optional[AIDetector] = None


def get_ai_detector() -> AIDetector:
    """获取全局AI检测器实例。
    
    Returns:
        AIDetector实例
    """
    global _ai_detector
    if _ai_detector is None:
        _ai_detector = AIDetector()
    return _ai_detector


def is_ai_available() -> bool:
    """快捷方法：检测AI系统是否可用。
    
    Returns:
        True如果AI系统可用，否则False
    """
    return get_ai_detector().is_ai_available()


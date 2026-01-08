"""Thread pool manager for AI message processing."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from ..core.logger import get_logger

logger = get_logger(__name__)


class ThreadPoolManager:
    """Thread pool manager for CPU-bound or blocking operations."""
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize thread pool manager.
        
        Args:
            max_workers: Maximum number of worker threads (default: 5)
        """
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        self._initialized = False
    
    def initialize(self):
        """Initialize the thread pool executor."""
        with self._lock:
            if not self._initialized:
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="ai_worker"
                )
                self._initialized = True
                logger.info(f"Thread pool initialized with {self.max_workers} workers")
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool executor."""
        with self._lock:
            if self._executor and self._initialized:
                self._executor.shutdown(wait=wait)
                self._executor = None
                self._initialized = False
                logger.info("Thread pool shutdown")
    
    async def run_in_executor(self, func, *args, **kwargs):
        """
        Run a function in the thread pool.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            Result of the function execution
        """
        if not self._initialized:
            self.initialize()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args, **kwargs)
    
    @property
    def executor(self) -> Optional[ThreadPoolExecutor]:
        """Get the thread pool executor."""
        return self._executor
    
    @property
    def is_initialized(self) -> bool:
        """Check if thread pool is initialized."""
        return self._initialized


# Global thread pool manager instance
_thread_pool_manager: Optional[ThreadPoolManager] = None


def get_thread_pool_manager(max_workers: int = 5) -> ThreadPoolManager:
    """Get or create the global thread pool manager."""
    global _thread_pool_manager
    if _thread_pool_manager is None:
        _thread_pool_manager = ThreadPoolManager(max_workers=max_workers)
        _thread_pool_manager.initialize()
    return _thread_pool_manager


def shutdown_thread_pool(wait: bool = True):
    """Shutdown the global thread pool manager."""
    global _thread_pool_manager
    if _thread_pool_manager:
        _thread_pool_manager.shutdown(wait=wait)
        _thread_pool_manager = None


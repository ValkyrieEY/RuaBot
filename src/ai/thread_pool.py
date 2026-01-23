"""Thread pool manager for AI message processing."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
from ..core.logger import get_logger

logger = get_logger(__name__)


class ThreadPoolManager:
    """Thread pool manager for CPU-bound or blocking operations."""
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize thread pool manager.
        
        Args:
            max_workers: Maximum number of worker threads (default: None, uses system default)
        """
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        self._initialized = False
        
        # Statistics
        self._total_tasks = 0
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._active_tasks = 0
        self._init_time = None
    
    def initialize(self):
        """Initialize the thread pool executor."""
        with self._lock:
            if not self._initialized:
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="ai_worker"
                )
                self._initialized = True
                self._init_time = time.time()
                worker_info = f"{self.max_workers} workers" if self.max_workers else "system-managed workers"
                logger.info(f"Thread pool initialized with {worker_info}")
    
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
        
        with self._lock:
            self._total_tasks += 1
            self._active_tasks += 1
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, func, *args, **kwargs)
            with self._lock:
                self._completed_tasks += 1
            return result
        except Exception as e:
            with self._lock:
                self._failed_tasks += 1
            logger.error(f"Thread pool task failed: {e}")
            raise
        finally:
            with self._lock:
                self._active_tasks -= 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get thread pool statistics."""
        with self._lock:
            uptime = time.time() - self._init_time if self._init_time else 0
            # Get actual worker count from the executor
            actual_workers = self.max_workers
            if actual_workers is None and self._executor:
                # When max_workers is None, ThreadPoolExecutor uses: min(32, (os.cpu_count() or 1) + 4)
                import os
                actual_workers = min(32, (os.cpu_count() or 1) + 4)
            return {
                "max_workers": actual_workers or 0,
                "max_workers_auto": self.max_workers is None,
                "initialized": self._initialized,
                "total_tasks": self._total_tasks,
                "completed_tasks": self._completed_tasks,
                "failed_tasks": self._failed_tasks,
                "active_tasks": self._active_tasks,
                "success_rate": (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0,
                "uptime_seconds": uptime
            }
    
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


def get_thread_pool_manager(max_workers: Optional[int] = None) -> ThreadPoolManager:
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

"""Blocking task pool manager for framework-wide synchronous work."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)


class BlockingTaskPoolManager:
    """Shared thread pool for blocking file/process/synchronous work."""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers
        self.effective_max_workers = self._resolve_max_workers(max_workers)
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        self._initialized = False

        self._total_tasks = 0
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._active_tasks = 0
        self._init_time: Optional[float] = None

    @staticmethod
    def _resolve_max_workers(max_workers: Optional[int]) -> int:
        """Resolve configured worker count, where 0/None means auto."""
        if max_workers is not None:
            try:
                parsed = int(max_workers)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                pass
        return min(32, (os.cpu_count() or 1) + 4)

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._executor = ThreadPoolExecutor(
                max_workers=self.effective_max_workers,
                thread_name_prefix="blocking_worker",
            )
            self._initialized = True
            self._init_time = time.time()
            worker_info = (
                f"{self.effective_max_workers} workers (configured)"
                if self.max_workers and int(self.max_workers) > 0
                else f"{self.effective_max_workers} workers (auto)"
            )
            logger.info(f"Blocking task pool initialized with {worker_info}")

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            if self._executor and self._initialized:
                self._executor.shutdown(wait=wait)
                self._executor = None
                self._initialized = False
                logger.info("Blocking task pool shutdown")

    async def run_in_executor(self, func, *args, **kwargs):
        """Run a blocking callable in the shared executor."""
        if not self._initialized:
            self.initialize()

        with self._lock:
            self._total_tasks += 1
            self._active_tasks += 1

        try:
            loop = asyncio.get_event_loop()
            call = partial(func, *args, **kwargs) if kwargs else partial(func, *args)
            result = await loop.run_in_executor(self._executor, call)
            with self._lock:
                self._completed_tasks += 1
            return result
        except Exception as e:
            with self._lock:
                self._failed_tasks += 1
            logger.error(f"Blocking task pool task failed: {e}")
            raise
        finally:
            with self._lock:
                self._active_tasks -= 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._init_time if self._init_time else 0
            live_workers = 0
            if self._executor is not None and hasattr(self._executor, "_threads"):
                try:
                    live_workers = len(self._executor._threads)  # type: ignore[attr-defined]
                except Exception:
                    live_workers = 0
            return {
                "max_workers": self.effective_max_workers,
                "max_workers_auto": not (self.max_workers and int(self.max_workers) > 0),
                "configured_max_workers": int(self.max_workers or 0),
                "live_workers": live_workers,
                "initialized": self._initialized,
                "total_tasks": self._total_tasks,
                "completed_tasks": self._completed_tasks,
                "failed_tasks": self._failed_tasks,
                "active_tasks": self._active_tasks,
                "success_rate": (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0,
                "uptime_seconds": uptime,
            }

    @property
    def is_initialized(self) -> bool:
        return self._initialized


_blocking_task_pool_manager: Optional[BlockingTaskPoolManager] = None


def get_blocking_task_pool_manager(max_workers: Optional[int] = None) -> BlockingTaskPoolManager:
    """Get or create the shared blocking task pool manager."""
    global _blocking_task_pool_manager
    if _blocking_task_pool_manager is None:
        if max_workers is None:
            try:
                from .config import get_config

                max_workers = getattr(get_config(), "blocking_task_pool_max_workers", 0)
            except Exception:
                max_workers = 0
        _blocking_task_pool_manager = BlockingTaskPoolManager(max_workers=max_workers)
        _blocking_task_pool_manager.initialize()
    return _blocking_task_pool_manager


def shutdown_blocking_task_pool(wait: bool = True) -> None:
    """Shutdown the shared blocking task pool manager."""
    global _blocking_task_pool_manager
    if _blocking_task_pool_manager:
        _blocking_task_pool_manager.shutdown(wait=wait)
        _blocking_task_pool_manager = None


async def run_in_blocking_pool(func, *args, **kwargs):
    """Execute a blocking callable in the shared blocking task pool."""
    return await get_blocking_task_pool_manager().run_in_executor(func, *args, **kwargs)

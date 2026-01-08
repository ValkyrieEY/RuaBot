"""Dream Scheduler - Schedules periodic dream maintenance cycles.

Complete implementation inspired by RuaBot's dream scheduler.
Supports:
1. Periodic execution with configurable intervals
2. Time window restrictions (e.g., only dream at night)
3. Graceful shutdown
4. Error handling and retry logic
5. Statistics tracking
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime

from src.core.logger import get_logger
from ..llm_client import LLMClient
from .dream_agent import run_dream_cycle_once
from .dream_generator import generate_dream_summary

logger = get_logger(__name__)


class DreamScheduler:
    """Scheduler for periodic dream maintenance cycles."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        bot_name: str = "小易",
        first_delay_seconds: int = 60,
        interval_minutes: int = 30,
        dream_start_hour: int = 0,
        dream_end_hour: int = 6,
        enabled: bool = True
    ):
        """Initialize dream scheduler.
        
        Args:
            llm_client: LLM client for dream agent
            bot_name: Bot name
            first_delay_seconds: Delay before first dream cycle (seconds)
            interval_minutes: Interval between dream cycles (minutes)
            dream_start_hour: Start hour for dream time window (0-23)
            dream_end_hour: End hour for dream time window (0-23)
            enabled: Whether dream scheduler is enabled
        """
        self.llm_client = llm_client
        self.bot_name = bot_name
        self.first_delay_seconds = first_delay_seconds
        self.interval_seconds = interval_minutes * 60
        self.dream_start_hour = dream_start_hour
        self.dream_end_hour = dream_end_hour
        self.enabled = enabled
        
        self._stop_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None
        
        # Statistics
        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.total_iterations = 0
        self.total_cost_seconds = 0.0
        self.last_cycle_time: Optional[float] = None
        
        logger.info(
            f"[Dream] 调度器初始化: 首次延迟={first_delay_seconds}s, "
            f"间隔={interval_minutes}min, 时间窗口={dream_start_hour}:00-{dream_end_hour}:00"
        )
    
    def is_in_dream_time(self) -> bool:
        """Check if current time is in the allowed dream time window.
        
        Returns:
            True if in dream time, False otherwise
        """
        current_hour = datetime.now().hour
        
        if self.dream_start_hour <= self.dream_end_hour:
            # Normal case: e.g., 0:00 - 6:00
            return self.dream_start_hour <= current_hour < self.dream_end_hour
        else:
            # Wrap-around case: e.g., 22:00 - 6:00
            return current_hour >= self.dream_start_hour or current_hour < self.dream_end_hour
    
    async def run_once(self) -> Optional[Dict[str, Any]]:
        """Run one dream cycle.
        
        Returns:
            Maintenance results or None if failed
        """
        try:
            self.total_cycles += 1
            
            # Check if in dream time
            if not self.is_in_dream_time():
                logger.debug("[Dream] 当前时间不在允许做梦的时间段内，跳过")
                return None
            
            # Run dream cycle
            logger.info(f"[Dream] 开始第 {self.total_cycles} 次梦境周期")
            
            result = await run_dream_cycle_once(
                llm_client=self.llm_client,
                bot_name=self.bot_name
            )
            
            if result:
                self.successful_cycles += 1
                self.total_iterations += result.get('iterations', 0)
                self.total_cost_seconds += result.get('cost_seconds', 0.0)
                self.last_cycle_time = time.time()
                
                logger.info(
                    f"[Dream] 第 {self.total_cycles} 次周期完成: "
                    f"chat_id={result.get('chat_id')}, "
                    f"迭代={result.get('iterations')}, "
                    f"耗时={result.get('cost_seconds', 0):.1f}s"
                )
                
                return result
            else:
                self.failed_cycles += 1
                logger.warning(f"[Dream] 第 {self.total_cycles} 次周期失败或跳过")
                return None
                
        except Exception as e:
            self.failed_cycles += 1
            logger.error(f"[Dream] 第 {self.total_cycles} 次周期异常: {e}", exc_info=True)
            return None
    
    async def start(self, stop_event: Optional[asyncio.Event] = None):
        """Start the dream scheduler.
        
        Args:
            stop_event: Optional event to signal scheduler to stop
        """
        if not self.enabled:
            logger.info("[Dream] 调度器已禁用，不启动")
            return
        
        self._stop_event = stop_event or asyncio.Event()
        
        logger.info(
            f"[Dream] 调度器启动: 首次延迟 {self.first_delay_seconds}s, "
            f"之后每隔 {self.interval_seconds}s ({self.interval_seconds // 60} 分钟) 运行一次"
        )
        
        try:
            # Initial delay
            logger.info(f"[Dream] 等待 {self.first_delay_seconds}s 后开始首次梦境周期...")
            await asyncio.sleep(self.first_delay_seconds)
            
            # Main loop
            while True:
                if self._stop_event.is_set():
                    logger.info("[Dream] 收到停止信号，结束调度器循环")
                    break
                
                start_ts = time.time()
                
                # Run one cycle
                await self.run_once()
                
                # Calculate sleep time
                elapsed = time.time() - start_ts
                to_sleep = max(0.0, self.interval_seconds - elapsed)
                
                logger.debug(f"[Dream] 等待 {to_sleep:.1f}s 后进行下一次周期")
                
                # Sleep with interrupt support
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=to_sleep
                    )
                    # If wait succeeds, stop_event was set
                    logger.info("[Dream] 收到停止信号，结束调度器循环")
                    break
                except asyncio.TimeoutError:
                    # Timeout is normal, continue loop
                    pass
                    
        except asyncio.CancelledError:
            logger.info("[Dream] 调度器任务被取消，准备退出")
            raise
        except Exception as e:
            logger.error(f"[Dream] 调度器异常: {e}", exc_info=True)
        finally:
            self._log_statistics()
    
    def start_background(self) -> asyncio.Task:
        """Start the scheduler in background as an asyncio task.
        
        Returns:
            The asyncio Task
        """
        if self._task and not self._task.done():
            logger.warning("[Dream] 调度器已在运行")
            return self._task
        
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self.start(self._stop_event))
        
        logger.info("[Dream] 调度器已在后台启动")
        return self._task
    
    async def stop(self):
        """Stop the scheduler gracefully."""
        if self._stop_event:
            logger.info("[Dream] 发送停止信号到调度器...")
            self._stop_event.set()
        
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
                logger.info("[Dream] 调度器已停止")
            except asyncio.TimeoutError:
                logger.warning("[Dream] 调度器停止超时，取消任务")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
    
    def _log_statistics(self):
        """Log scheduler statistics."""
        avg_iterations = self.total_iterations / self.successful_cycles if self.successful_cycles > 0 else 0
        avg_cost = self.total_cost_seconds / self.successful_cycles if self.successful_cycles > 0 else 0
        
        logger.info(
            f"[Dream] 调度器统计:\n"
            f"  总周期数: {self.total_cycles}\n"
            f"  成功: {self.successful_cycles}\n"
            f"  失败: {self.failed_cycles}\n"
            f"  总迭代数: {self.total_iterations}\n"
            f"  平均迭代数: {avg_iterations:.1f}\n"
            f"  总耗时: {self.total_cost_seconds:.1f}s\n"
            f"  平均耗时: {avg_cost:.1f}s"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics.
        
        Returns:
            Statistics dict
        """
        avg_iterations = self.total_iterations / self.successful_cycles if self.successful_cycles > 0 else 0
        avg_cost = self.total_cost_seconds / self.successful_cycles if self.successful_cycles > 0 else 0
        
        return {
            'enabled': self.enabled,
            'total_cycles': self.total_cycles,
            'successful_cycles': self.successful_cycles,
            'failed_cycles': self.failed_cycles,
            'total_iterations': self.total_iterations,
            'avg_iterations': avg_iterations,
            'total_cost_seconds': self.total_cost_seconds,
            'avg_cost_seconds': avg_cost,
            'last_cycle_time': self.last_cycle_time,
            'is_running': self._task is not None and not self._task.done() if self._task else False
        }


# Global scheduler instance
_dream_scheduler: Optional[DreamScheduler] = None


def get_dream_scheduler() -> Optional[DreamScheduler]:
    """Get global dream scheduler instance.
    
    Returns:
        DreamScheduler instance or None if not initialized
    """
    return _dream_scheduler


def init_dream_scheduler(
    llm_client: LLMClient,
    bot_name: str = "小易",
    first_delay_seconds: int = 60,
    interval_minutes: int = 30,
    dream_start_hour: int = 0,
    dream_end_hour: int = 6,
    enabled: bool = True
) -> DreamScheduler:
    """Initialize global dream scheduler.
    
    Args:
        llm_client: LLM client
        bot_name: Bot name
        first_delay_seconds: Delay before first cycle
        interval_minutes: Interval between cycles
        dream_start_hour: Start hour for dream time window
        dream_end_hour: End hour for dream time window
        enabled: Whether scheduler is enabled
        
    Returns:
        Initialized DreamScheduler instance
    """
    global _dream_scheduler
    
    _dream_scheduler = DreamScheduler(
        llm_client=llm_client,
        bot_name=bot_name,
        first_delay_seconds=first_delay_seconds,
        interval_minutes=interval_minutes,
        dream_start_hour=dream_start_hour,
        dream_end_hour=dream_end_hour,
        enabled=enabled
    )
    
    logger.info("[Dream] 全局调度器已初始化")
    return _dream_scheduler


async def start_dream_scheduler(
    llm_client: LLMClient,
    bot_name: str = "小易",
    first_delay_seconds: Optional[int] = None,
    interval_seconds: Optional[int] = None,
    stop_event: Optional[asyncio.Event] = None
) -> None:
    """Convenience function to start dream scheduler (backward compatible).
    
    Args:
        llm_client: LLM client
        bot_name: Bot name
        first_delay_seconds: Delay before first cycle (seconds)
        interval_seconds: Interval between cycles (seconds)
        stop_event: Optional stop event
    """
    # Convert seconds to minutes for interval
    interval_minutes = (interval_seconds // 60) if interval_seconds else 30
    first_delay = first_delay_seconds if first_delay_seconds else 60
    
    scheduler = DreamScheduler(
        llm_client=llm_client,
        bot_name=bot_name,
        first_delay_seconds=first_delay,
        interval_minutes=interval_minutes
    )
    
    await scheduler.start(stop_event)


"""Plugin interceptor system for high-privilege plugins.

This module provides an interceptor system that allows plugins to:
- Intercept and modify messages before they are sent
- Intercept and modify events before they are dispatched
- Block messages or events
- Monitor all plugin operations

Performance Optimization:
- Parallel execution: Interceptors run concurrently when possible
- Smart merging: Results are intelligently merged based on priority
- Circuit breaker: Failed interceptors are temporarily disabled
- Adaptive timeout: Dynamic timeout based on interceptor history
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import time
from collections import defaultdict

from ..core.logger import get_logger

logger = get_logger(__name__)


class InterceptorType(str, Enum):
    """Interceptor type."""
    MESSAGE = "message"  # Intercept message sending
    EVENT = "event"  # Intercept event dispatching


class ExecutionMode(str, Enum):
    """Execution mode for interceptors."""
    SERIAL = "serial"  # Execute sequentially (safe but slow)
    PARALLEL = "parallel"  # Execute concurrently (fast but may have conflicts)
    HYBRID = "hybrid"  # Smart execution based on dependencies (recommended)


@dataclass
class InterceptorResult:
    """Result of interceptor execution."""
    
    # Whether to continue processing (False = block)
    allow: bool = True
    
    # Modified data (None = no modification)
    modified_data: Optional[Dict[str, Any]] = None
    
    # Reason for blocking (if allow=False)
    block_reason: Optional[str] = None
    
    # Execution time in seconds
    execution_time: float = 0.0
    
    def is_blocked(self) -> bool:
        """Check if operation is blocked."""
        return not self.allow
    
    def is_modified(self) -> bool:
        """Check if data was modified."""
        return self.modified_data is not None


@dataclass
class InterceptorStats:
    """Statistics for an interceptor."""
    
    plugin_id: str
    total_calls: int = 0
    total_failures: int = 0
    total_timeouts: int = 0
    avg_execution_time: float = 0.0
    last_execution_time: float = 0.0
    consecutive_failures: int = 0
    is_circuit_open: bool = False  # Circuit breaker status
    circuit_open_until: float = 0.0  # Timestamp when circuit will close
    
    def update_success(self, execution_time: float):
        """Update stats after successful execution."""
        self.total_calls += 1
        self.consecutive_failures = 0
        self.last_execution_time = execution_time
        # Moving average
        self.avg_execution_time = (
            (self.avg_execution_time * (self.total_calls - 1) + execution_time) / self.total_calls
        )
    
    def update_failure(self, is_timeout: bool = False):
        """Update stats after failure."""
        self.total_calls += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        if is_timeout:
            self.total_timeouts += 1
    
    def should_open_circuit(self, threshold: int = 3) -> bool:
        """Check if circuit breaker should open."""
        return self.consecutive_failures >= threshold
    
    def open_circuit(self, duration: float = 30.0):
        """Open circuit breaker."""
        self.is_circuit_open = True
        self.circuit_open_until = time.time() + duration
        logger.warning(
            f"Circuit breaker opened for {self.plugin_id} "
            f"(failures: {self.consecutive_failures}, duration: {duration}s)"
        )
    
    def try_close_circuit(self) -> bool:
        """Try to close circuit breaker if cooldown period has passed."""
        if self.is_circuit_open and time.time() >= self.circuit_open_until:
            self.is_circuit_open = False
            self.consecutive_failures = 0
            logger.info(f"Circuit breaker closed for {self.plugin_id}")
            return True
        return False
    
    def get_adaptive_timeout(self, base_timeout: float = 3.0, max_timeout: float = 10.0) -> float:
        """Calculate adaptive timeout based on historical performance."""
        if self.avg_execution_time == 0.0:
            return base_timeout
        # Use 3x average time as timeout, but cap at max_timeout
        adaptive = min(self.avg_execution_time * 3, max_timeout)
        return max(adaptive, base_timeout)  # Never go below base_timeout


class MessageInterceptor(ABC):
    """Base class for message interceptors.
    
    Intercepts messages before they are sent to OneBot API.
    """
    
    def __init__(self, plugin_id: str, priority: int = 100):
        """Initialize interceptor.
        
        Args:
            plugin_id: ID of the plugin registering this interceptor (author/name)
            priority: Priority (lower = earlier execution)
        """
        self.plugin_id = plugin_id
        self.priority = priority
    
    @abstractmethod
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        """Intercept a message before sending.
        
        Args:
            action: API action name (e.g., 'send_group_msg', 'send_private_msg')
            params: Message parameters
            source_plugin: ID of plugin that initiated the message (if from plugin)
        
        Returns:
            InterceptorResult with allow/modified_data
        """
        pass


class EventInterceptor(ABC):
    """Base class for event interceptors.
    
    Intercepts events before they are dispatched to plugins.
    """
    
    def __init__(self, plugin_id: str, priority: int = 100):
        """Initialize interceptor.
        
        Args:
            plugin_id: ID of the plugin registering this interceptor (author/name)
            priority: Priority (lower = earlier execution)
        """
        self.plugin_id = plugin_id
        self.priority = priority
    
    @abstractmethod
    async def intercept_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str] = None
    ) -> InterceptorResult:
        """Intercept an event before dispatching.
        
        Args:
            event_name: Event name (e.g., 'onebot.message')
            event_data: Event data
            source: Event source
        
        Returns:
            InterceptorResult with allow/modified_data
        """
        pass


class InterceptorRegistry:
    """Registry for managing interceptors with optimized execution.
    
    Features:
    - Parallel execution for independent interceptors
    - Circuit breaker pattern for failing interceptors
    - Adaptive timeouts based on historical performance
    - Smart result merging with conflict resolution
    """
    
    def __init__(self, execution_mode: ExecutionMode = ExecutionMode.HYBRID):
        """Initialize registry.
        
        Args:
            execution_mode: Execution mode (SERIAL, PARALLEL, or HYBRID)
        """
        self._message_interceptors: list[MessageInterceptor] = []
        self._event_interceptors: list[EventInterceptor] = []
        self._execution_mode = execution_mode
        self._stats: Dict[str, InterceptorStats] = {}
        self._base_timeout = 3.0  # Base timeout in seconds
        self._max_timeout = 10.0  # Maximum timeout in seconds
        self._circuit_breaker_threshold = 3  # Failures before opening circuit
        self._circuit_breaker_duration = 30.0  # Circuit open duration in seconds
    
    def _get_stats(self, plugin_id: str) -> InterceptorStats:
        """Get or create stats for an interceptor."""
        if plugin_id not in self._stats:
            self._stats[plugin_id] = InterceptorStats(plugin_id=plugin_id)
        return self._stats[plugin_id]
    
    def register_message_interceptor(self, interceptor: MessageInterceptor):
        """Register a message interceptor.
        
        Args:
            interceptor: MessageInterceptor instance
        """
        self._message_interceptors.append(interceptor)
        # Sort by priority (lower priority = earlier execution)
        self._message_interceptors.sort(key=lambda x: x.priority)
    
    def register_event_interceptor(self, interceptor: EventInterceptor):
        """Register an event interceptor.
        
        Args:
            interceptor: EventInterceptor instance
        """
        self._event_interceptors.append(interceptor)
        # Sort by priority (lower priority = earlier execution)
        self._event_interceptors.sort(key=lambda x: x.priority)
    
    def unregister_message_interceptor(self, plugin_id: str) -> bool:
        """Unregister all message interceptors for a plugin.
        
        Args:
            plugin_id: Plugin ID
        
        Returns:
            True if any interceptors were removed
        """
        before = len(self._message_interceptors)
        self._message_interceptors = [
            i for i in self._message_interceptors if i.plugin_id != plugin_id
        ]
        return len(self._message_interceptors) < before
    
    def unregister_event_interceptor(self, plugin_id: str) -> bool:
        """Unregister all event interceptors for a plugin.
        
        Args:
            plugin_id: Plugin ID
        
        Returns:
            True if any interceptors were removed
        """
        before = len(self._event_interceptors)
        self._event_interceptors = [
            i for i in self._event_interceptors if i.plugin_id != plugin_id
        ]
        return len(self._event_interceptors) < before
    
    def unregister_all(self, plugin_id: str):
        """Unregister all interceptors for a plugin.
        
        Args:
            plugin_id: Plugin ID
        """
        self.unregister_message_interceptor(plugin_id)
        self.unregister_event_interceptor(plugin_id)
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Run all message interceptors with optimized parallel execution.
        
        This implementation uses a hybrid approach:
        1. Group interceptors by priority (same priority can run in parallel)
        2. Execute each priority group with asyncio.gather()
        3. Apply circuit breaker pattern to skip failing interceptors
        4. Use adaptive timeouts based on historical performance
        5. Smart merge results with conflict resolution
        
        Performance characteristics:
        - Best case: O(1) if all interceptors can run in parallel
        - Worst case: O(n) if all have different priorities (serial execution)
        - Typical case: O(log n) with priority grouping
        
        Args:
            action: API action name
            params: Message parameters
            source_plugin: Source plugin ID
        
        Returns:
            Tuple of (allow, modified_params)
        """
        if not self._message_interceptors:
            return (True, params.copy())
        
        start_time = time.time()
        current_params = params.copy()
        
        # Group interceptors by priority for parallel execution
        priority_groups = self._group_by_priority(self._message_interceptors)
        
        logger.debug(
            f"Processing {len(self._message_interceptors)} message interceptors "
            f"in {len(priority_groups)} priority groups (mode: {self._execution_mode})"
        )
        
        # Process each priority group
        for priority, interceptors in priority_groups:
            # Check if we should execute in parallel
            if self._execution_mode == ExecutionMode.PARALLEL or \
               (self._execution_mode == ExecutionMode.HYBRID and len(interceptors) > 1):
                # Parallel execution for this priority group
                allow, current_params = await self._execute_parallel_message(
                    interceptors, action, current_params, source_plugin
                )
            else:
                # Serial execution for this priority group
                allow, current_params = await self._execute_serial_message(
                    interceptors, action, current_params, source_plugin
                )
            
            # If any interceptor blocks, stop processing
            if not allow:
                logger.debug(f"Message blocked by priority group {priority}")
                return (False, current_params)
        
        total_time = time.time() - start_time
        logger.debug(
            f"Message interception completed in {total_time:.3f}s "
            f"({len(self._message_interceptors)} interceptors)"
        )
        
        return (True, current_params)
    
    def _group_by_priority(self, interceptors: List) -> List[Tuple[int, List]]:
        """Group interceptors by priority for parallel execution.
        
        Returns:
            List of (priority, [interceptors]) tuples, sorted by priority
        """
        groups = defaultdict(list)
        for interceptor in interceptors:
            groups[interceptor.priority].append(interceptor)
        
        # Sort by priority (lower = earlier execution)
        return sorted(groups.items(), key=lambda x: x[0])
    
    async def _execute_parallel_message(
        self,
        interceptors: List[MessageInterceptor],
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute interceptors in parallel (same priority group only).
        
        IMPORTANT: This should only be called for interceptors with the SAME priority.
        They all receive the SAME input params and their results are merged.
        
        This is correct because:
        - Same priority = no dependency between interceptors
        - They can safely run in parallel on the same input
        - Results are merged by priority (but since all same priority, merge is safe)
        
        Args:
            interceptors: List of interceptors with SAME priority
            action: API action
            params: Current parameters (shared input for all)
            source_plugin: Source plugin ID
        
        Returns:
            Tuple of (allow, merged_params)
        """
        # Filter out interceptors with open circuits
        active_interceptors = []
        for interceptor in interceptors:
            stats = self._get_stats(interceptor.plugin_id)
            stats.try_close_circuit()
            
            if stats.is_circuit_open:
                logger.debug(
                    f"Skipping interceptor {interceptor.plugin_id} (circuit breaker open)"
                )
                continue
            
            active_interceptors.append(interceptor)
        
        if not active_interceptors:
            return (True, params)
        
        # All interceptors in this group receive the SAME params (because same priority)
        # This is the key insight: same priority = no dependency = can use same input
        input_params = params.copy()
        
        # Create tasks for all interceptors
        tasks = []
        for interceptor in active_interceptors:
            stats = self._get_stats(interceptor.plugin_id)
            timeout = stats.get_adaptive_timeout(self._base_timeout, self._max_timeout)
            
            task = asyncio.create_task(
                self._execute_single_interceptor_message(
                    interceptor, action, input_params, source_plugin, timeout
                )
            )
            tasks.append((interceptor, task, timeout))
        
        # Wait for all tasks concurrently
        results = await asyncio.gather(
            *[task for _, task, _ in tasks],
            return_exceptions=True
        )
        
        # Process results
        all_allow = True
        modified_params_list = []
        
        for (interceptor, _, timeout), result in zip(tasks, results):
            stats = self._get_stats(interceptor.plugin_id)
            
            if isinstance(result, Exception):
                # Handle exception
                logger.error(
                    f"Error in message interceptor {interceptor.plugin_id}: {result}",
                    exc_info=result
                )
                stats.update_failure(is_timeout=isinstance(result, asyncio.TimeoutError))
                
                # Open circuit breaker if threshold reached
                if stats.should_open_circuit(self._circuit_breaker_threshold):
                    stats.open_circuit(self._circuit_breaker_duration)
            
            elif isinstance(result, InterceptorResult):
                # Successful execution
                stats.update_success(result.execution_time)
                
                # Check if blocked
                if result.is_blocked():
                    logger.debug(f"Message blocked by interceptor {interceptor.plugin_id}")
                    return (False, input_params)
                
                # Collect modifications
                if result.is_modified():
                    modified_params_list.append(result.modified_data)
        
        # Merge all modifications from same priority group
        # Since they all processed the same input, we merge their changes
        merged_params = input_params
        for modified_data in modified_params_list:
            merged_params = self._merge_params(merged_params, modified_data)
        
        return (all_allow, merged_params)
    
    async def _execute_single_interceptor_message(
        self,
        interceptor: MessageInterceptor,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str],
        timeout: float
    ) -> InterceptorResult:
        """Execute a single interceptor with timeout.
        
        Returns:
            InterceptorResult with execution time
        """
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                interceptor.intercept_message(action, params, source_plugin),
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(
                f"Interceptor {interceptor.plugin_id} timed out after {timeout:.2f}s"
            )
            raise
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Error in interceptor {interceptor.plugin_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _execute_serial_message(
        self,
        interceptors: List[MessageInterceptor],
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute interceptors serially (one after another).
        
        This method maintains data dependency: each interceptor receives
        the modified params from the previous one.
        
        Args:
            interceptors: List of interceptors to execute
            action: API action
            params: Current parameters
            source_plugin: Source plugin ID
        
        Returns:
            Tuple of (allow, modified_params)
        """
        current_params = params.copy()
        
        for interceptor in interceptors:
            stats = self._get_stats(interceptor.plugin_id)
            stats.try_close_circuit()
            
            # Skip if circuit breaker is open
            if stats.is_circuit_open:
                logger.debug(
                    f"Skipping interceptor {interceptor.plugin_id} (circuit breaker open)"
                )
                continue
            
            timeout = stats.get_adaptive_timeout(self._base_timeout, self._max_timeout)
            
            try:
                result = await self._execute_single_interceptor_message(
                    interceptor, action, current_params, source_plugin, timeout
                )
                
                stats.update_success(result.execution_time)
                
                # Check if blocked
                if result.is_blocked():
                    logger.debug(f"Message blocked by interceptor {interceptor.plugin_id}")
                    return (False, current_params)
                
                # Apply modification
                if result.is_modified():
                    current_params = result.modified_data
                    logger.debug(
                        f"Interceptor {interceptor.plugin_id} modified params "
                        f"(execution time: {result.execution_time:.3f}s)"
                    )
            
            except Exception as e:
                stats.update_failure(is_timeout=isinstance(e, asyncio.TimeoutError))
                
                # Open circuit breaker if threshold reached
                if stats.should_open_circuit(self._circuit_breaker_threshold):
                    stats.open_circuit(self._circuit_breaker_duration)
                
                # Continue with current params
                continue
        
        return (True, current_params)
    
    def _merge_params(
        self,
        base_params: Dict[str, Any],
        new_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two parameter dictionaries with conflict resolution.
        
        Strategy:
        - New values overwrite base values
        - Nested dicts are merged recursively
        - Lists are replaced (not merged)
        
        Args:
            base_params: Base parameters
            new_params: New parameters to merge
        
        Returns:
            Merged parameters
        """
        result = base_params.copy()
        
        for key, value in new_params.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursive merge for nested dicts
                result[key] = self._merge_params(result[key], value)
            else:
                # Overwrite for all other cases
                result[key] = value
        
        return result
    
    async def intercept_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Run all event interceptors with optimized parallel execution.
        
        Same optimization strategy as intercept_message but for events.
        
        Args:
            event_name: Event name
            event_data: Event data
            source: Event source
        
        Returns:
            Tuple of (allow, modified_event_data)
        """
        if not self._event_interceptors:
            return (True, event_data.copy())
        
        start_time = time.time()
        current_data = event_data.copy()
        
        # Group interceptors by priority for parallel execution
        priority_groups = self._group_by_priority(self._event_interceptors)
        
        logger.debug(
            f"Processing {len(self._event_interceptors)} event interceptors "
            f"in {len(priority_groups)} priority groups (mode: {self._execution_mode})"
        )
        
        # Process each priority group
        for priority, interceptors in priority_groups:
            # Check if we should execute in parallel
            if self._execution_mode == ExecutionMode.PARALLEL or \
               (self._execution_mode == ExecutionMode.HYBRID and len(interceptors) > 1):
                # Parallel execution for this priority group
                allow, current_data = await self._execute_parallel_event(
                    interceptors, event_name, current_data, source
                )
            else:
                # Serial execution for this priority group
                allow, current_data = await self._execute_serial_event(
                    interceptors, event_name, current_data, source
                )
            
            # If any interceptor blocks, stop processing
            if not allow:
                logger.debug(f"Event blocked by priority group {priority}")
                return (False, current_data)
        
        total_time = time.time() - start_time
        logger.debug(
            f"Event interception completed in {total_time:.3f}s "
            f"({len(self._event_interceptors)} interceptors)"
        )
        
        return (True, current_data)
    
    async def _execute_parallel_event(
        self,
        interceptors: List[EventInterceptor],
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute event interceptors in parallel (same priority group only)."""
        # Filter out interceptors with open circuits
        active_interceptors = []
        for interceptor in interceptors:
            stats = self._get_stats(interceptor.plugin_id)
            stats.try_close_circuit()
            
            if stats.is_circuit_open:
                logger.debug(
                    f"Skipping event interceptor {interceptor.plugin_id} (circuit breaker open)"
                )
                continue
            
            active_interceptors.append(interceptor)
        
        if not active_interceptors:
            return (True, event_data)
        
        # All interceptors in same priority group receive same input
        input_data = event_data.copy()
        
        # Create tasks for all interceptors
        tasks = []
        for interceptor in active_interceptors:
            stats = self._get_stats(interceptor.plugin_id)
            timeout = stats.get_adaptive_timeout(self._base_timeout, self._max_timeout)
            
            task = asyncio.create_task(
                self._execute_single_interceptor_event(
                    interceptor, event_name, input_data, source, timeout
                )
            )
            tasks.append((interceptor, task, timeout))
        
        # Wait for all tasks concurrently
        results = await asyncio.gather(
            *[task for _, task, _ in tasks],
            return_exceptions=True
        )
        
        # Process results
        all_allow = True
        modified_data_list = []
        
        for (interceptor, _, timeout), result in zip(tasks, results):
            stats = self._get_stats(interceptor.plugin_id)
            
            if isinstance(result, Exception):
                # Handle exception
                logger.error(
                    f"Error in event interceptor {interceptor.plugin_id}: {result}",
                    exc_info=result
                )
                stats.update_failure(is_timeout=isinstance(result, asyncio.TimeoutError))
                
                # Open circuit breaker if threshold reached
                if stats.should_open_circuit(self._circuit_breaker_threshold):
                    stats.open_circuit(self._circuit_breaker_duration)
            
            elif isinstance(result, InterceptorResult):
                # Successful execution
                stats.update_success(result.execution_time)
                
                # Check if blocked
                if result.is_blocked():
                    logger.debug(f"Event blocked by interceptor {interceptor.plugin_id}")
                    return (False, input_data)
                
                # Collect modifications
                if result.is_modified():
                    modified_data_list.append(result.modified_data)
        
        # Merge all modifications from same priority group
        merged_data = input_data
        for modified_data in modified_data_list:
            merged_data = self._merge_params(merged_data, modified_data)
        
        return (all_allow, merged_data)
    
    async def _execute_single_interceptor_event(
        self,
        interceptor: EventInterceptor,
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str],
        timeout: float
    ) -> InterceptorResult:
        """Execute a single event interceptor with timeout."""
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                interceptor.intercept_event(event_name, event_data, source),
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(
                f"Event interceptor {interceptor.plugin_id} timed out after {timeout:.2f}s"
            )
            raise
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Error in event interceptor {interceptor.plugin_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _execute_serial_event(
        self,
        interceptors: List[EventInterceptor],
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute event interceptors serially (one after another)."""
        current_data = event_data.copy()
        
        for interceptor in interceptors:
            stats = self._get_stats(interceptor.plugin_id)
            stats.try_close_circuit()
            
            # Skip if circuit breaker is open
            if stats.is_circuit_open:
                logger.debug(
                    f"Skipping event interceptor {interceptor.plugin_id} (circuit breaker open)"
                )
                continue
            
            timeout = stats.get_adaptive_timeout(self._base_timeout, self._max_timeout)
            
            try:
                result = await self._execute_single_interceptor_event(
                    interceptor, event_name, current_data, source, timeout
                )
                
                stats.update_success(result.execution_time)
                
                # Check if blocked
                if result.is_blocked():
                    logger.debug(f"Event blocked by interceptor {interceptor.plugin_id}")
                    return (False, current_data)
                
                # Apply modification
                if result.is_modified():
                    current_data = result.modified_data
                    logger.debug(
                        f"Event interceptor {interceptor.plugin_id} modified data "
                        f"(execution time: {result.execution_time:.3f}s)"
                    )
            
            except Exception as e:
                stats.update_failure(is_timeout=isinstance(e, asyncio.TimeoutError))
                
                # Open circuit breaker if threshold reached
                if stats.should_open_circuit(self._circuit_breaker_threshold):
                    stats.open_circuit(self._circuit_breaker_duration)
                
                # Continue with current data
                continue
        
        return (True, current_data)
    
    def get_message_interceptors(self) -> list[MessageInterceptor]:
        """Get all message interceptors."""
        return self._message_interceptors.copy()
    
    def get_event_interceptors(self) -> list[EventInterceptor]:
        """Get all event interceptors."""
        return self._event_interceptors.copy()
    
    def get_stats(self) -> Dict[str, InterceptorStats]:
        """Get statistics for all interceptors.
        
        Returns:
            Dictionary mapping plugin_id to InterceptorStats
        """
        return self._stats.copy()
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get a summary of interceptor statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        summary = {
            'total_interceptors': len(self._message_interceptors) + len(self._event_interceptors),
            'message_interceptors': len(self._message_interceptors),
            'event_interceptors': len(self._event_interceptors),
            'execution_mode': self._execution_mode.value,
            'interceptor_stats': []
        }
        
        for plugin_id, stats in self._stats.items():
            summary['interceptor_stats'].append({
                'plugin_id': plugin_id,
                'total_calls': stats.total_calls,
                'total_failures': stats.total_failures,
                'total_timeouts': stats.total_timeouts,
                'success_rate': (
                    (stats.total_calls - stats.total_failures) / stats.total_calls * 100
                    if stats.total_calls > 0 else 0.0
                ),
                'avg_execution_time': stats.avg_execution_time,
                'last_execution_time': stats.last_execution_time,
                'circuit_breaker_open': stats.is_circuit_open,
                'consecutive_failures': stats.consecutive_failures
            })
        
        # Sort by success rate (descending)
        summary['interceptor_stats'].sort(
            key=lambda x: x['success_rate'],
            reverse=True
        )
        
        return summary
    
    def reset_stats(self, plugin_id: Optional[str] = None):
        """Reset statistics for a specific plugin or all plugins.
        
        Args:
            plugin_id: Plugin ID to reset stats for, or None to reset all
        """
        if plugin_id:
            if plugin_id in self._stats:
                self._stats[plugin_id] = InterceptorStats(plugin_id=plugin_id)
                logger.info(f"Reset stats for interceptor: {plugin_id}")
        else:
            self._stats.clear()
            logger.info("Reset all interceptor stats")
    
    def set_execution_mode(self, mode: ExecutionMode):
        """Set the execution mode for interceptors.
        
        Args:
            mode: Execution mode (SERIAL, PARALLEL, or HYBRID)
        """
        self._execution_mode = mode
        logger.info(f"Set interceptor execution mode to: {mode.value}")
    
    def configure_circuit_breaker(
        self,
        threshold: int = 3,
        duration: float = 30.0
    ):
        """Configure circuit breaker parameters.
        
        Args:
            threshold: Number of consecutive failures before opening circuit
            duration: How long to keep circuit open (seconds)
        """
        self._circuit_breaker_threshold = threshold
        self._circuit_breaker_duration = duration
        logger.info(
            f"Configured circuit breaker: threshold={threshold}, duration={duration}s"
        )
    
    def configure_timeouts(
        self,
        base_timeout: float = 3.0,
        max_timeout: float = 10.0
    ):
        """Configure timeout parameters.
        
        Args:
            base_timeout: Base timeout for interceptors (seconds)
            max_timeout: Maximum adaptive timeout (seconds)
        """
        self._base_timeout = base_timeout
        self._max_timeout = max_timeout
        logger.info(
            f"Configured timeouts: base={base_timeout}s, max={max_timeout}s"
        )


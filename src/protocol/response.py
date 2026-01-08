"""Response waiter for OneBot API calls."""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..core.logger import get_logger

logger = get_logger(__name__)


class ResponseWaiter:
    """Wait for API response by echo."""
    
    def __init__(self):
        self._pending: Dict[str, asyncio.Future] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def start_cleanup_task(self):
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired())
    
    async def _cleanup_expired(self):
        """Cleanup expired pending responses."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                expired = []
                for echo, future in self._pending.items():
                    if future.done() or future.cancelled():
                        expired.append(echo)
                
                for echo in expired:
                    del self._pending[echo]
                    logger.debug(f"Cleaned up expired echo: {echo}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def wait_for_response(
        self,
        echo: str,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for API response.
        
        Args:
            echo: Echo identifier
            timeout: Timeout in seconds
        
        Returns:
            Response data or None if timeout
        """
        # Create future for this echo
        future = asyncio.Future()
        self._pending[echo] = future
        
        try:
            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        
        except asyncio.TimeoutError:
            logger.warning(f"Response timeout for echo: {echo}")
            return None
        
        finally:
            # Clean up
            if echo in self._pending:
                del self._pending[echo]
    
    def register_response(self, echo: str, data: Dict[str, Any]):
        """
        Register a response.
        
        Args:
            echo: Echo identifier
            data: Response data
        """
        if echo in self._pending:
            future = self._pending[echo]
            if not future.done():
                future.set_result(data)
                logger.debug(f"Registered response for echo: {echo}")
        else:
            logger.warning(f"No pending request for echo: {echo}")
    
    def cancel_all(self):
        """Cancel all pending requests."""
        for echo, future in self._pending.items():
            if not future.done():
                future.cancel()
        self._pending.clear()
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()


# Global instance
_response_waiter: Optional[ResponseWaiter] = None


def get_response_waiter() -> ResponseWaiter:
    """Get global response waiter instance."""
    global _response_waiter
    if _response_waiter is None:
        _response_waiter = ResponseWaiter()
        _response_waiter.start_cleanup_task()
    return _response_waiter


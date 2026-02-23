"""Example: How to use interceptors in plugins.

This example demonstrates:
1. Creating custom interceptors
2. Registering interceptors with different priorities
3. Intercepting and modifying messages
4. Best practices for interceptor implementation
"""

from src.plugins.interceptor import MessageInterceptor, InterceptorResult
from typing import Dict, Any, Optional
import re


# Example 1: Simple message filter
class BadWordFilterInterceptor(MessageInterceptor):
    """Filter bad words from all outgoing messages."""
    
    def __init__(self, plugin_id: str):
        # Use priority 50 (medium priority)
        super().__init__(plugin_id, priority=50)
        self.bad_words = ['bad', 'evil', 'spam']
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        # Only process group messages
        if action != 'send_group_msg':
            return InterceptorResult(allow=True)
        
        message = params.get('message', '')
        
        # Check for bad words
        for bad_word in self.bad_words:
            if bad_word in message.lower():
                # Option 1: Block the message
                return InterceptorResult(
                    allow=False,
                    block_reason=f"Message contains prohibited word: {bad_word}"
                )
                
                # Option 2: Replace bad words (uncomment to use)
                # message = message.replace(bad_word, '***')
                # params_copy = params.copy()
                # params_copy['message'] = message
                # return InterceptorResult(allow=True, modified_data=params_copy)
        
        # Allow message if no bad words
        return InterceptorResult(allow=True)


# Example 2: Rate limiter
class RateLimitInterceptor(MessageInterceptor):
    """Prevent message spam by rate limiting."""
    
    def __init__(self, plugin_id: str, max_messages_per_minute: int = 10):
        # Use priority 10 (high priority - check early)
        super().__init__(plugin_id, priority=10)
        self.max_messages_per_minute = max_messages_per_minute
        self.message_timestamps = {}
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        import time
        
        # Get group/user ID
        group_id = params.get('group_id')
        user_id = params.get('user_id')
        target_id = f"group_{group_id}" if group_id else f"user_{user_id}"
        
        if not target_id:
            return InterceptorResult(allow=True)
        
        # Clean old timestamps
        current_time = time.time()
        if target_id in self.message_timestamps:
            self.message_timestamps[target_id] = [
                ts for ts in self.message_timestamps[target_id]
                if current_time - ts < 60  # Keep last 60 seconds
            ]
        else:
            self.message_timestamps[target_id] = []
        
        # Check rate limit
        if len(self.message_timestamps[target_id]) >= self.max_messages_per_minute:
            return InterceptorResult(
                allow=False,
                block_reason=f"Rate limit exceeded: {self.max_messages_per_minute} messages/minute"
            )
        
        # Record timestamp
        self.message_timestamps[target_id].append(current_time)
        
        return InterceptorResult(allow=True)


# Example 3: Message logger with async operation
class MessageLoggerInterceptor(MessageInterceptor):
    """Log all outgoing messages to external service."""
    
    def __init__(self, plugin_id: str):
        # Use priority 100 (low priority - log after all modifications)
        super().__init__(plugin_id, priority=100)
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        # Simulate async logging to external service
        # In real implementation, use aiohttp or similar
        try:
            # Example: await self._send_to_logging_service(action, params)
            
            # For demo, just print
            print(f"[LOG] Action: {action}, Source: {source_plugin or 'framework'}")
            print(f"[LOG] Message: {params.get('message', 'N/A')}")
            
        except Exception as e:
            # Don't block message if logging fails
            print(f"[LOG] Error logging message: {e}")
        
        # Always allow (logging should not block messages)
        return InterceptorResult(allow=True)


# Example 4: Smart message enhancer
class MessageEnhancerInterceptor(MessageInterceptor):
    """Add helpful metadata to messages."""
    
    def __init__(self, plugin_id: str):
        super().__init__(plugin_id, priority=50)
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        # Add source plugin info if not present
        if source_plugin and 'message' in params:
            message = params['message']
            
            # Only add prefix if not already added
            if not message.startswith('['):
                params_copy = params.copy()
                params_copy['message'] = f"[From {source_plugin}] {message}"
                
                return InterceptorResult(allow=True, modified_data=params_copy)
        
        return InterceptorResult(allow=True)


# Example 5: Permission checker (with external API call)
class PermissionCheckerInterceptor(MessageInterceptor):
    """Check permissions before sending messages."""
    
    def __init__(self, plugin_id: str):
        # Use priority 5 (very high priority - security check)
        super().__init__(plugin_id, priority=5)
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        # Simulate async permission check
        # In real implementation, call your permission service
        
        # Example: Check if plugin has permission to send to this group
        group_id = params.get('group_id')
        if group_id and source_plugin:
            # Simulate API call with timeout
            import asyncio
            try:
                # await self._check_permission_api(source_plugin, group_id)
                await asyncio.sleep(0.1)  # Simulate fast API call
                
                # For demo, allow all
                has_permission = True
                
                if not has_permission:
                    return InterceptorResult(
                        allow=False,
                        block_reason=f"Plugin {source_plugin} has no permission for group {group_id}"
                    )
            except Exception as e:
                # On error, allow by default (fail-open for availability)
                # Or use fail-closed for security: return InterceptorResult(allow=False)
                print(f"[PERM] Error checking permission: {e}")
        
        return InterceptorResult(allow=True)


# How to use in a plugin:
"""
In your plugin's on_load() method:

def on_load(self):
    '''Called when plugin is loaded.'''
    
    # Create interceptor(s)
    bad_word_filter = BadWordFilterInterceptor(self.plugin_name)
    rate_limiter = RateLimitInterceptor(self.plugin_name, max_messages_per_minute=10)
    
    # Register interceptors
    self.api.register_message_interceptor(bad_word_filter)
    self.api.register_message_interceptor(rate_limiter)
    
    self.logger.info("Interceptors registered successfully")

def on_unload(self):
    '''Called when plugin is unloaded.'''
    
    # Unregister interceptors
    self.api.unregister_message_interceptor()
    
    self.logger.info("Interceptors unregistered")
"""


# Best practices:
"""
1. PRIORITY ASSIGNMENT:
   - 1-10: Security checks (permissions, authentication)
   - 10-50: Rate limiting, spam detection
   - 50-80: Content modification (filters, enhancers)
   - 80-100: Logging, monitoring (should not block)

2. PERFORMANCE:
   - Keep interceptors fast (< 100ms if possible)
   - Use async I/O for external calls
   - Cache frequently used data
   - Avoid blocking operations

3. ERROR HANDLING:
   - Always catch exceptions
   - Decide: fail-open (allow) or fail-closed (block)
   - Log errors for debugging
   - Don't let errors crash the framework

4. PRIORITY GROUPING:
   - Same priority = can run in parallel
   - Different priority = run in sequence
   - Use HYBRID mode for best performance

5. TESTING:
   - Test with timeouts (should not block forever)
   - Test with failures (should handle gracefully)
   - Test with high load (circuit breaker should work)
   - Monitor performance metrics

6. CONFIGURATION:
   - Make parameters configurable
   - Use plugin config storage
   - Allow runtime updates
"""


# Example plugin that uses interceptors:
class ExamplePlugin:
    """Example plugin with interceptors."""
    
    def __init__(self, api):
        self.api = api
        self.plugin_name = "author/example-plugin"
        self.logger = api.logger
        
        # Store interceptor references for cleanup
        self.interceptors = []
    
    def on_load(self):
        """Initialize plugin and register interceptors."""
        
        # Create multiple interceptors with different priorities
        perm_checker = PermissionCheckerInterceptor(self.plugin_name)
        rate_limiter = RateLimitInterceptor(self.plugin_name, max_messages_per_minute=10)
        bad_word_filter = BadWordFilterInterceptor(self.plugin_name)
        message_logger = MessageLoggerInterceptor(self.plugin_name)
        
        # Register in any order (they will be sorted by priority automatically)
        self.api.register_message_interceptor(perm_checker)
        self.api.register_message_interceptor(rate_limiter)
        self.api.register_message_interceptor(bad_word_filter)
        self.api.register_message_interceptor(message_logger)
        
        self.logger.info("All interceptors registered successfully")
        self.logger.info("Execution order by priority: perm_checker(5) -> rate_limiter(10) -> "
                        "bad_word_filter(50) -> message_logger(100)")
    
    def on_unload(self):
        """Clean up plugin and unregister interceptors."""
        self.api.unregister_message_interceptor()
        self.logger.info("All interceptors unregistered")


if __name__ == '__main__':
    print("This is an example file. See the code for usage instructions.")
    print("\nExample interceptors:")
    print("1. BadWordFilterInterceptor - Filter prohibited words")
    print("2. RateLimitInterceptor - Prevent message spam")
    print("3. MessageLoggerInterceptor - Log all messages")
    print("4. MessageEnhancerInterceptor - Add metadata to messages")
    print("5. PermissionCheckerInterceptor - Check permissions")
    print("\nSee code comments for how to use in your plugin.")


"""Enhanced sandbox manager with code execution capabilities."""
import asyncio
import json
import uuid as uuid_module
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path
from ..logger import get_logger
from ..database import get_database_manager
from ..models.sandbox import Sandbox
from ..event_bus import get_event_bus
from .booters.base import ComputerBooter
from .booters.local import LocalBooter
logger = get_logger(__name__)
class SandboxManager:
    """Enhanced sandbox manager with code execution capabilities.
    
    Features:
    - Create multiple sandboxes with different configurations
    - Simulate message sending/receiving
    - Execute shell commands, Python code, file operations
    - Route messages through plugin systems
    - Record message and execution history
    - Session-based isolated execution environments
    """
    def __init__(self):
        self.db_manager = get_database_manager()
        self.event_bus = get_event_bus()
        self._plugin_connector = None
        self._message_callbacks: Dict[str, List[Callable]] = {}
        self._booters: Dict[str, ComputerBooter] = {}
        self._base_work_dir = Path("data/sandbox_work")
        self._base_work_dir.mkdir(parents=True, exist_ok=True)
        self._current_sandbox_uuid: Optional[str] = None
    def set_plugin_connector(self, plugin_connector):
        """Set plugin connector for routing messages to plugins."""
        self._plugin_connector = plugin_connector
        logger.info("Plugin connector set for sandbox manager")
    def register_message_callback(self, sandbox_uuid: str, callback: Callable):
        """Register callback for receiving sandbox messages (e.g., WebSocket)."""
        if sandbox_uuid not in self._message_callbacks:
            self._message_callbacks[sandbox_uuid] = []
        self._message_callbacks[sandbox_uuid].append(callback)
        logger.debug(f"Registered message callback for sandbox {sandbox_uuid}")
    def unregister_message_callback(self, sandbox_uuid: str, callback: Callable):
        """Unregister message callback."""
        if sandbox_uuid in self._message_callbacks:
            try:
                self._message_callbacks[sandbox_uuid].remove(callback)
                logger.debug(f"Unregistered message callback for sandbox {sandbox_uuid}")
            except ValueError:
                pass
    async def _notify_callbacks(self, sandbox_uuid: str, message: Dict[str, Any]):
        """Notify all registered callbacks about new message."""
        if sandbox_uuid in self._message_callbacks:
            for callback in self._message_callbacks[sandbox_uuid]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Error in sandbox message callback: {e}", exc_info=True)
    async def get_booter(self, sandbox_uuid: str) -> ComputerBooter:
        """Get or create booter for sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            
        Returns:
            ComputerBooter instance
        """
        if sandbox_uuid in self._booters:
            booter = self._booters[sandbox_uuid]
            if await booter.available():
                return booter
            else:
                logger.warning(f"Sandbox booter unhealthy, recreating: {sandbox_uuid}")
                await booter.shutdown()
                del self._booters[sandbox_uuid]
        logger.info(f"Creating new booter for sandbox: {sandbox_uuid}")
        booter = LocalBooter(base_work_dir=self._base_work_dir)
        await booter.boot(sandbox_uuid)
        self._booters[sandbox_uuid] = booter
        return booter
    async def record_plugin_response(
        self,
        source_plugin: str,
        message_content: str,
        action: str,
        params: Dict[str, Any]
    ):
        """Record plugin response message in sandbox.
        
        This is called when a plugin tries to send a message in sandbox mode.
        """
        if not self._current_sandbox_uuid:
            return
        try:
            sandbox = await self.db_manager.get_sandbox(self._current_sandbox_uuid)
            if not sandbox:
                return
            message_type = "private"
            if action == "send_group_msg":
                message_type = "group"
            outbound_msg = await self.db_manager.create_sandbox_message(
                sandbox_uuid=self._current_sandbox_uuid,
                message_type=message_type,
                direction="outbound",
                user_id="bot",
                user_nickname=f":{source_plugin}",
                group_id=sandbox.mock_group_id if message_type == "group" else None,
                group_name=sandbox.mock_group_name if message_type == "group" else None,
                content=message_content,
                raw_message=message_content,
                processed_by_plugins=True
            )
            await self._notify_callbacks(self._current_sandbox_uuid, outbound_msg.to_dict())
            logger.debug(f"Recorded plugin response in sandbox: {source_plugin}")
        except Exception as e:
            logger.error(f"Failed to record plugin response: {e}", exc_info=True)

    def _stringify_plugin_message(self, message: Any) -> str:
        if isinstance(message, str):
            return message
        try:
            return json.dumps(message, ensure_ascii=False)
        except Exception:
            return str(message)

    def _sandbox_send_target(self, action: str, params: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        action = str(action or "")
        if action == "send_group_msg":
            return "group", str(params.get("group_id") or "").strip() or None
        if action == "send_private_msg":
            return "private", str(params.get("user_id") or "").strip() or None
        if action == "send_msg":
            message_type = str(params.get("message_type") or params.get("type") or "").strip().lower()
            if message_type == "group" or params.get("group_id"):
                return "group", str(params.get("group_id") or "").strip() or None
            if message_type == "private" or params.get("user_id"):
                return "private", str(params.get("user_id") or "").strip() or None
        return None, None

    async def record_plugin_api_call(
        self,
        source_plugin: str,
        action: str,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Capture plugin message sends whose target belongs to an enabled sandbox."""
        target_type, target_id = self._sandbox_send_target(action, params or {})
        if not target_type or not target_id:
            return None

        sandboxes = await self.db_manager.list_sandboxes()
        if self._current_sandbox_uuid:
            sandboxes.sort(key=lambda item: 0 if item.uuid == self._current_sandbox_uuid else 1)

        matched_sandbox = None
        for sandbox in sandboxes:
            if not sandbox.enabled:
                continue
            if target_type == "private" and str(sandbox.mock_user_id or "") == target_id:
                matched_sandbox = sandbox
                break
            if target_type == "group" and str(sandbox.mock_group_id or "") == target_id:
                matched_sandbox = sandbox
                break

        if not matched_sandbox:
            return None

        message_content = self._stringify_plugin_message((params or {}).get("message", ""))
        outbound_msg = await self.db_manager.create_sandbox_message(
            sandbox_uuid=matched_sandbox.uuid,
            message_type=target_type,
            direction="outbound",
            user_id="bot",
            user_nickname=source_plugin or "Plugin",
            group_id=matched_sandbox.mock_group_id if target_type == "group" else None,
            group_name=matched_sandbox.mock_group_name if target_type == "group" else None,
            content=message_content,
            raw_message=message_content,
            processed_by_plugins=True,
        )
        await self._notify_callbacks(matched_sandbox.uuid, outbound_msg.to_dict())
        logger.info(
            "Captured plugin API call as sandbox message",
            sandbox_uuid=matched_sandbox.uuid,
            action=action,
            source_plugin=source_plugin,
        )
        return {
            "message_id": outbound_msg.id,
            "sandbox": True,
            "sandbox_uuid": matched_sandbox.uuid,
        }
    async def shutdown_booter(self, sandbox_uuid: str):
        """Shutdown booter for sandbox."""
        if sandbox_uuid in self._booters:
            booter = self._booters[sandbox_uuid]
            await booter.shutdown()
            del self._booters[sandbox_uuid]
            logger.info(f"Sandbox booter shutdown: {sandbox_uuid}")
    async def create_sandbox(
        self,
        name: str,
        mock_user_id: str,
        description: Optional[str] = None,
        mock_user_nickname: str = "",
        mock_group_id: Optional[str] = None,
        mock_group_name: Optional[str] = None,
        use_plugins: bool = True,
        **kwargs
    ) -> Sandbox:
        """Create a new sandbox."""
        sandbox_uuid = str(uuid_module.uuid4())
        sandbox = await self.db_manager.create_sandbox(
            uuid=sandbox_uuid,
            name=name,
            description=description,
            mock_user_id=mock_user_id,
            mock_user_nickname=mock_user_nickname,
            mock_group_id=mock_group_id,
            mock_group_name=mock_group_name,
            use_plugins=True,
            **kwargs
        )
        logger.info(f"Created sandbox: {name} ({sandbox_uuid})")
        try:
            await self.get_booter(sandbox_uuid)
        except Exception as e:
            logger.error(f"Failed to initialize sandbox booter: {e}")
        return sandbox
    async def delete_sandbox(self, sandbox_uuid: str):
        """Delete sandbox and cleanup resources."""
        await self.shutdown_booter(sandbox_uuid)
        await self.db_manager.delete_sandbox(sandbox_uuid)
        logger.info(f"Deleted sandbox: {sandbox_uuid}")
    async def execute_shell(
        self,
        sandbox_uuid: str,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute shell command in sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            command: Shell command to execute
            cwd: Working directory
            timeout: Timeout in seconds
            
        Returns:
            Execution result with stdout, stderr, exit_code
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        if not sandbox.enabled:
            raise ValueError(f"Sandbox {sandbox_uuid} is disabled")
        logger.info(f"Executing shell command in sandbox {sandbox.name}: {command[:100]}")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.shell.exec(
            command=command,
            cwd=cwd,
            timeout=timeout,
        )
        return result
    async def execute_python(
        self,
        sandbox_uuid: str,
        code: str,
        kernel_id: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute Python code in sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            code: Python code to execute
            kernel_id: Optional kernel ID for stateful execution
            timeout: Timeout in seconds
            
        Returns:
            Execution result with output, error
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        if not sandbox.enabled:
            raise ValueError(f"Sandbox {sandbox_uuid} is disabled")
        logger.info(f"Executing Python code in sandbox {sandbox.name}")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.python.exec(
            code=code,
            kernel_id=kernel_id,
            timeout=timeout,
        )
        return result
    async def list_files(
        self,
        sandbox_uuid: str,
        path: str = ".",
        show_hidden: bool = False,
    ) -> Dict[str, Any]:
        """List files in sandbox directory.
        
        Args:
            sandbox_uuid: Sandbox UUID
            path: Directory path
            show_hidden: Show hidden files
            
        Returns:
            Directory listing with file info
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.fs.list_dir(path=path, show_hidden=show_hidden)
        return result
    async def read_file(
        self,
        sandbox_uuid: str,
        path: str,
    ) -> Dict[str, Any]:
        """Read file from sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            path: File path
            
        Returns:
            File content
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.fs.read_file(path=path)
        return result
    async def write_file(
        self,
        sandbox_uuid: str,
        path: str,
        content: str,
    ) -> Dict[str, Any]:
        """Write file to sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            path: File path
            content: File content
            
        Returns:
            Write result
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.fs.write_file(path=path, content=content)
        return result
    async def delete_file(
        self,
        sandbox_uuid: str,
        path: str,
    ) -> Dict[str, Any]:
        """Delete file from sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            path: File path
            
        Returns:
            Delete result
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.fs.delete_file(path=path)
        return result
    async def create_directory(
        self,
        sandbox_uuid: str,
        path: str,
    ) -> Dict[str, Any]:
        """Create directory in sandbox.
        
        Args:
            sandbox_uuid: Sandbox UUID
            path: Directory path
            
        Returns:
            Create result
        """
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        booter = await self.get_booter(sandbox_uuid)
        result = await booter.fs.create_dir(path=path)
        return result
    async def send_message_to_sandbox(
        self,
        sandbox_uuid: str,
        message_content: str,
        message_type: str = "private"
    ) -> Dict[str, Any]:
        """Send a message to sandbox (simulate user sending message)."""
        sandbox = await self.db_manager.get_sandbox(sandbox_uuid)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_uuid} not found")
        if not sandbox.enabled:
            raise ValueError(f"Sandbox {sandbox_uuid} is disabled")
        logger.info(f"Processing message in sandbox {sandbox.name}: {message_content[:50]}")
        self._current_sandbox_uuid = sandbox_uuid
        inbound_msg = await self.db_manager.create_sandbox_message(
            sandbox_uuid=sandbox_uuid,
            message_type=message_type,
            direction="inbound",
            user_id=sandbox.mock_user_id,
            user_nickname=sandbox.mock_user_nickname,
            group_id=sandbox.mock_group_id if message_type == "group" else None,
            group_name=sandbox.mock_group_name if message_type == "group" else None,
            content=message_content,
            raw_message=message_content
        )
        await self._notify_callbacks(sandbox_uuid, inbound_msg.to_dict())
        onebot_event = self._build_onebot_event(sandbox, message_content, message_type)
        responses = []
        plugin_responses = []
        has_error = False
        error_message = None
        try:
            if self._plugin_connector:
                logger.debug(f"Processing sandbox message through plugins")
                try:
                    from ..event_context import EventContext
                    ctx = EventContext(
                        event_name='message.received',
                        event_data=onebot_event,
                        source="sandbox",
                        metadata={
                            "sandbox_mode": True,
                            "sandbox_uuid": sandbox_uuid,
                            "sandbox_name": sandbox.name,
                        }
                    )
                    modified_ctx = await self._plugin_connector.emit_event_with_context(
                        ctx,
                        bound_plugins=None
                    )
                    if modified_ctx is None or modified_ctx.is_prevented_default():
                        logger.info("Message blocked by plugin in sandbox")
                        plugin_responses.append({
                            "blocked": True,
                            "message": "Message blocked by plugin"
                        })
                    else:
                        if modified_ctx.is_modified():
                            onebot_event = modified_ctx.event_data
                        if hasattr(modified_ctx, 'metadata') and 'plugin_responses' in modified_ctx.metadata:
                            plugin_responses.extend(modified_ctx.metadata['plugin_responses'])
                except Exception as e:
                    logger.error(f"Error processing through plugins in sandbox: {e}", exc_info=True)
                    has_error = True
                    error_message = f"Plugin error: {str(e)}"
        except Exception as e:
            logger.error(f"Error processing sandbox message: {e}", exc_info=True)
            has_error = True
            error_message = str(e)
        finally:
            self._current_sandbox_uuid = None
        await self.db_manager.update_sandbox_message(
            inbound_msg.id,
            processed_by_plugins=True,
            plugin_responses=plugin_responses,
            has_error=has_error,
            error_message=error_message
        )
        return {
            "sandbox_uuid": sandbox_uuid,
            "inbound_message_id": inbound_msg.id,
            "responses": responses,
            "plugin_responses": plugin_responses,
            "has_error": has_error,
            "error_message": error_message
        }
    def _build_onebot_event(
        self,
        sandbox: Sandbox,
        message_content: str,
        message_type: str
    ) -> Dict[str, Any]:
        """Build OneBot-like event for plugin processing."""
        event = {
            "time": int(datetime.now().timestamp()),
            "self_id": "sandbox_bot",
            "post_type": "message",
            "message_type": message_type,
            "sub_type": "normal",
            "message_id": int(datetime.now().timestamp() * 1000),
            "user_id": sandbox.mock_user_id,
            "message": message_content,
            "raw_message": message_content,
            "font": 0,
            "sender": {
                "user_id": sandbox.mock_user_id,
                "nickname": sandbox.mock_user_nickname,
                "card": "",
                "role": "member"
            }
        }
        if message_type == "group" and sandbox.mock_group_id:
            event["group_id"] = sandbox.mock_group_id
            event["sender"]["role"] = "member"
        return event
_sandbox_manager: Optional[SandboxManager] = None
def get_sandbox_manager() -> SandboxManager:
    """Get global sandbox manager instance."""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager

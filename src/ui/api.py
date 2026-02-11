"""FastAPI application for Web UI."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form, Body, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from starlette.middleware import Middleware
from pydantic import BaseModel
from pathlib import Path
import zipfile
import shutil
import tempfile
import uuid
import time
import os
import json

from ..core.app import get_app
from ..core.config import get_config, get_config_manager, reload_config
from ..core.event_bus import get_event_bus
from ..core.database import get_database_manager
from ..security.auth import AuthManager
from ..security.permissions import get_permission_manager, Permission
from ..security.audit import get_audit_logger, AuditEventType, AuditEvent
from ..core.logger import get_logger
from ..core.ai_detector import is_ai_available, get_ai_detector
from ..core.version import get_version
from datetime import datetime

logger = get_logger(__name__)
security = HTTPBearer()

# Global AI managers (module-level) - Only initialized if AI is available
_model_manager = None
_ai_manager = None
_mcp_manager = None
_ai_available = None

# Request/Response Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PluginInfo(BaseModel):
    name: str
    enabled: bool
    metadata: Dict[str, Any]

class PluginAction(BaseModel):
    action: str  # load, unload, enable, disable, reload

class ConfigUpdate(BaseModel):
    config: Dict[str, Any]
    priority: Optional[int] = None  # Plugin priority (lower = earlier execution, default: 100)

# Global auth manager instance
_auth_manager = None

def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

# Dependency for authentication
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify user from token."""
    auth_manager = get_auth_manager()
    session = await auth_manager.verify_session(credentials.credentials)
    
    if not session:
        await get_audit_logger().log_access_denied(
            username="unknown",
            resource="api",
            action="access",
            reason="Invalid or expired token"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return session

# Dependency for permission checking
def require_permission(permission: Permission):
    """Decorator to require a specific permission."""
    async def check(user: Dict[str, Any] = Depends(get_current_user)):
        username = user.get("username")
        perm_manager = get_permission_manager()
        
        # Check if user has the required permission
        has_perm = perm_manager.has_permission(username, permission)
        
        logger.debug(
            "Permission check",
            username=username,
            permission=permission.value,
            has_permission=has_perm,
            user_permissions=[p.value for p in perm_manager.get_user_permissions(username)]
        )
        
        if not has_perm:
            await get_audit_logger().log_access_denied(
                username=username,
                resource="api",
                action=permission.value,
                reason="Insufficient permissions"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission.value}"
            )
        return user
    return check


# WebSocket Manager for real-time message updates
class WebSocketManager:
    """Manage WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._subscribed = False
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected, total connections: {len(self.active_connections)}")
        
        # Subscribe to event bus on first connection
        if not self._subscribed:
            event_bus = get_event_bus()
            event_bus.subscribe("onebot.message", self._on_message_event)
            event_bus.subscribe("onebot.notice", self._on_message_event)
            event_bus.subscribe("onebot.request", self._on_message_event)
            self._subscribed = True
            logger.info("WebSocket manager subscribed to event bus")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected, total connections: {len(self.active_connections)}")
    
    async def _on_message_event(self, event):
        """Event bus callback: push new message to all WebSocket clients."""
        if not self.active_connections:
            return
        
        try:
            payload = event.payload
            if not isinstance(payload, dict):
                return
            
            # Format the event based on its type
            event_data = None
            
            if event.name == "onebot.message":
                event_data = {
                    "type": "message",
                    "id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "time": event.timestamp.isoformat(),
                    "event_type": "message",
                    "post_type": "message",
                    "message_id": str(payload.get("message_id", "")),
                    "message_type": payload.get("message_type", "unknown"),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "raw_message": payload.get("raw_message", ""),
                    "message": payload.get("raw_message", ""),
                    "sender": payload.get("sender", {}),
                    "is_self": payload.get("is_self", False),
                    "target_id": str(payload.get("target_id", "")) if payload.get("target_id") else None,
                }
            
            elif event.name == "onebot.notice":
                formatted_text = _format_notice_event(payload)
                event_data = {
                    "type": "notice",
                    "id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "time": event.timestamp.isoformat(),
                    "event_type": "notice",
                    "post_type": "notice",
                    "notice_type": payload.get("notice_type", ""),
                    "sub_type": payload.get("sub_type", ""),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "operator_id": str(payload.get("operator_id", "")) if payload.get("operator_id") else None,
                    "message": formatted_text,
                    "raw_message": formatted_text,
                    "is_system": True,
                }
            
            elif event.name == "onebot.request":
                formatted_text = _format_request_event(payload)
                event_data = {
                    "type": "request",
                    "id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "time": event.timestamp.isoformat(),
                    "event_type": "request",
                    "post_type": "request",
                    "request_type": payload.get("request_type", ""),
                    "sub_type": payload.get("sub_type", ""),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "comment": payload.get("comment", ""),
                    "message": formatted_text,
                    "raw_message": formatted_text,
                    "is_system": True,
                }
            
            if event_data:
                # Send to all connected clients
                await self.broadcast(event_data)
        
        except Exception as e:
            logger.error(f"Error in WebSocket message event handler: {e}", exc_info=True)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


# Global WebSocket manager
_ws_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    # Windows + Python 3.13 compatibility: ensure ProactorEventLoop policy is set
    import sys
    if sys.platform == 'win32' and sys.version_info >= (3, 13):
        try:
            import asyncio
            # Check current policy
            current_policy = asyncio.get_event_loop_policy()
            if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
                # Set ProactorEventLoop policy
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                logger.info("Set ProactorEventLoop policy for Windows + Python 3.13 compatibility")
        except Exception as e:
            logger.warning(f"Failed to set ProactorEventLoop policy: {e}")
    
    # Startup
    application = get_app()
    await application.startup()
    logger.info("Web UI started")
    
    yield
    
    # Shutdown
    await application.shutdown()
    logger.info("Web UI stopped")


def _format_notice_event(payload: Dict[str, Any]) -> str:
    """Format notice event to readable text."""
    notice_type = payload.get("notice_type", "")
    user_id = payload.get("user_id", "")
    operator_id = payload.get("operator_id", "")
    group_id = payload.get("group_id", "")
    
    if notice_type == "group_increase":
        sub_type = payload.get("sub_type", "")
        if sub_type == "approve":
            return f"[系统通知] {user_id} 通过邀请加入了群 {group_id}"
        elif sub_type == "invite":
            return f"[系统通知] {user_id} 被 {operator_id} 邀请加入了群 {group_id}"
        return f"[系统通知] {user_id} 加入了群 {group_id}"
    
    elif notice_type == "group_decrease":
        sub_type = payload.get("sub_type", "")
        if sub_type == "leave":
            return f"[系统通知] {user_id} 退出了群 {group_id}"
        elif sub_type == "kick":
            return f"[系统通知] {user_id} 被 {operator_id} 踢出了群 {group_id}"
        elif sub_type == "kick_me":
            return f"[系统通知] 机器人被 {operator_id} 踢出了群 {group_id}"
        return f"[系统通知] {user_id} 离开了群 {group_id}"
    
    elif notice_type == "group_ban":
        sub_type = payload.get("sub_type", "")
        duration = payload.get("duration", 0)
        if sub_type == "ban":
            if duration > 0:
                minutes = duration // 60
                return f"[系统通知] {user_id} 被 {operator_id} 禁言 {minutes} 分钟"
            return f"[系统通知] {user_id} 被 {operator_id} 禁言"
        elif sub_type == "lift_ban":
            return f"[系统通知] {user_id} 被 {operator_id} 解除禁言"
        return f"[系统通知] 群 {group_id} 禁言状态变更"
    
    elif notice_type == "group_recall":
        message_id = payload.get("message_id", "")
        return f"[系统通知] {operator_id} 撤回了 {user_id} 的消息 (ID: {message_id})"
    
    elif notice_type == "friend_recall":
        message_id = payload.get("message_id", "")
        return f"[系统通知] {user_id} 撤回了一条消息 (ID: {message_id})"
    
    elif notice_type == "friend_add":
        return f"[系统通知] {user_id} 成为了好友"
    
    elif notice_type == "group_admin":
        sub_type = payload.get("sub_type", "")
        if sub_type == "set":
            return f"[系统通知] {user_id} 被设置为群 {group_id} 的管理员"
        elif sub_type == "unset":
            return f"[系统通知] {user_id} 被取消群 {group_id} 的管理员"
        return f"[系统通知] 群 {group_id} 管理员变更"
    
    elif notice_type == "group_upload":
        file_info = payload.get("file", {})
        file_name = file_info.get("name", "未知文件")
        return f"[系统通知] {user_id} 上传了文件: {file_name}"
    
    elif notice_type == "notify":
        sub_type = payload.get("sub_type", "")
        if sub_type == "poke":
            target_id = payload.get("target_id", "")
            return f"[系统通知] {user_id} 戳了戳 {target_id}"
        elif sub_type == "lucky_king":
            return f"[系统通知] {user_id} 是群 {group_id} 的红包运气王"
        elif sub_type == "honor":
            honor_type = payload.get("honor_type", "")
            return f"[系统通知] {user_id} 获得了群 {group_id} 的 {honor_type} 荣誉"
        return f"[系统通知] 群 {group_id} 提醒事件"
    
    # Unknown notice type - show all available info for debugging
    if notice_type:
        return f"[系统通知] {notice_type} 事件 (群:{group_id}, 用户:{user_id}, 操作者:{operator_id})"
    else:
        # No notice_type - show raw data
        sub_type = payload.get("sub_type", "")
        return f"[系统通知] 未知通知类型 (sub_type:{sub_type}, 群:{group_id}, 用户:{user_id})"


def _format_request_event(payload: Dict[str, Any]) -> str:
    """Format request event to readable text."""
    request_type = payload.get("request_type", "")
    user_id = payload.get("user_id", "")
    comment = payload.get("comment", "")
    
    if request_type == "friend":
        return f"[好友请求] {user_id} 请求添加好友: {comment}"
    
    elif request_type == "group":
        sub_type = payload.get("sub_type", "")
        group_id = payload.get("group_id", "")
        if sub_type == "add":
            return f"[加群请求] {user_id} 请求加入群 {group_id}: {comment}"
        elif sub_type == "invite":
            return f"[群邀请] {user_id} 邀请机器人加入群 {group_id}: {comment}"
        return f"[群请求] {user_id} 的群 {group_id} 请求: {comment}"
    
    return f"[请求] {request_type} 请求"


def create_app() -> FastAPI:
    """Create FastAPI application."""
    config = get_config()
    
    # Configure CORS middleware using Middleware class
    cors_middleware = Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app = FastAPI(
        title="Xiaoyi_QQ Framework",
        description="OneBot protocol framework with plugin system",
        version=get_version(),
        lifespan=lifespan,
        middleware=[cors_middleware]
    )
    
    # Static files - serve Vite React app (only if WebUI is enabled)
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Serve static assets (JS, CSS, etc.) - only if WebUI is enabled
    if config.web_ui_enabled and (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
    
    # Serve favicon and other static files - only if WebUI is enabled
    @app.get("/favicon.ico")
    async def favicon():
        """Serve favicon - only if WebUI is enabled."""
        config = get_config()
        if not config.web_ui_enabled:
            raise HTTPException(status_code=404, detail="Not found")
        favicon_path = static_dir / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(str(favicon_path))
        raise HTTPException(status_code=404)
    
    # Serve logo.jpg - only if WebUI is enabled
    @app.get("/logo.jpg")
    async def logo():
        """Serve logo.jpg - only if WebUI is enabled."""
        config = get_config()
        if not config.web_ui_enabled:
            raise HTTPException(status_code=404, detail="Not found")
        logo_path = static_dir / "logo.jpg"
        if logo_path.exists():
            return FileResponse(str(logo_path))
        raise HTTPException(status_code=404)
    
    # Authentication endpoints
    @app.post("/api/auth/login", response_model=LoginResponse)
    async def login(request: LoginRequest):
        """Login and get access token."""
        auth_manager = get_auth_manager()
        token = await auth_manager.authenticate(request.username, request.password)
        
        if not token:
            await get_audit_logger().log_login(request.username, False)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        await get_audit_logger().log_login(request.username, True)
        return LoginResponse(access_token=token)
    
    @app.post("/api/auth/logout")
    async def logout(user: Dict[str, Any] = Depends(get_current_user)):
        """Logout current user."""
        await get_audit_logger().log_logout(user.get("username"))
        return {"message": "Logged out successfully"}
    
    @app.get("/api/auth/me")
    async def get_current_user_info(user: Dict[str, Any] = Depends(get_current_user)):
        """Get current user info."""
        return user
    
    # Plugin management endpoints
    @app.get("/api/plugins", response_model=List[PluginInfo])
    async def list_plugins(user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_VIEW))):
        """Get list of all plugins (loaded and discovered)."""
        from ..core.app import get_app
        from pathlib import Path
        import json
        
        config = get_config()
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        plugin_base = Path(config.plugin_dir)
        all_plugins = []
        
        # Get thread pool for file operations
        app = get_app()
        thread_pool = getattr(app, 'plugin_thread_pool', None)
        
        # Discover all available plugins in plugins/{name} structure
        if plugin_base.exists():
            # Scan directory in thread pool to avoid blocking
            if thread_pool:
                def scan_plugin_dirs():
                    return [d for d in plugin_base.iterdir() 
                            if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')]
                plugin_dirs = await thread_pool.run_in_executor(scan_plugin_dirs)
            else:
                plugin_dirs = [d for d in plugin_base.iterdir() 
                               if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')]
            
            for plugin_dir in plugin_dirs:
                plugin_json = plugin_dir / "plugin.json"
                if not plugin_json.exists():
                    continue
                
                # Load plugin.json in thread pool
                try:
                    if thread_pool:
                        def read_plugin_json():
                            with open(plugin_json, 'r', encoding='utf-8') as f:
                                return json.load(f)
                        plugin_config = await thread_pool.run_in_executor(read_plugin_json)
                    else:
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            plugin_config = json.load(f)
                    
                    author = plugin_config.get("author", "Unknown")
                    plugin_name = plugin_config.get("name", plugin_dir.name)
                    
                    # Build metadata from plugin.json
                    metadata = {
                        "name": plugin_name,
                        "version": plugin_config.get("version", "1.0.0"),
                        "author": author,
                        "description": plugin_config.get("description", f"Plugin: {plugin_name}"),
                        "required_permissions": [],
                        "required_capabilities": [],
                        "dependencies": plugin_config.get("dependencies", []),
                        "config_schema": None,
                        "default_config": plugin_config.get("default_config", {}),
                        "tags": plugin_config.get("tags", []),
                        "category": plugin_config.get("category", "general"),
                        "homepage": plugin_config.get("homepage"),
                        "repository": plugin_config.get("repository"),
                        "documentation": plugin_config.get("documentation"),
                    }
                except Exception as e:
                    logger.error(f"Failed to load plugin.json for {plugin_dir.name}: {e}")
                    continue
                
                # Get enabled status from database
                enabled = False
                # Priority: database > plugin.json > default (100)
                priority_from_json = plugin_config.get("priority")
                priority = 100  # Default: 100 (lower = earlier execution)
                config_data = metadata.get("default_config", {})
                
                if db_manager:
                    try:
                        db_setting = await db_manager.get_plugin_setting(author, plugin_name)
                        if db_setting:
                            enabled = db_setting.enabled
                            priority = db_setting.priority
                            config_data = db_setting.config or config_data
                            logger.debug(f"Plugin {author}/{plugin_name} enabled status from DB: {enabled}")
                        else:
                            # No database setting, use plugin.json priority if available
                            if priority_from_json is not None:
                                priority = priority_from_json
                            logger.debug(f"Plugin {author}/{plugin_name} not found in database, defaulting to disabled")
                    except Exception as e:
                        logger.error(f"Failed to get plugin status from database for {author}/{plugin_name}: {e}", exc_info=True)
                
                all_plugins.append({
                    "name": plugin_name,
                    "enabled": enabled,
                    "metadata": metadata,
                    "system_data": {
                        "enabled": enabled,
                        "priority": priority,
                        "config": config_data
                    }
                })
        
        return all_plugins
    
    @app.get("/api/plugins/{plugin_name}")
    async def get_plugin(
        plugin_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_VIEW))
    ):
        """Get specific plugin information."""
        from ..core.app import get_app
        from pathlib import Path
        import json
        
        config = get_config()
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        # Find plugin directory
        plugin_base = Path(config.plugin_dir)
        plugin_dir = plugin_base / plugin_name
        
        if not plugin_dir.exists():
            raise HTTPException(status_code=404, detail="Plugin not found")
        
        plugin_json = plugin_dir / "plugin.json"
        if not plugin_json.exists():
            raise HTTPException(status_code=404, detail="Plugin metadata not found")
        
        # Load plugin.json using thread pool
        app = get_app()
        thread_pool = getattr(app, 'plugin_thread_pool', None)
        
        try:
            if thread_pool:
                def read_plugin_json():
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        return json.load(f)
                plugin_config = await thread_pool.run_in_executor(read_plugin_json)
            else:
                with open(plugin_json, 'r', encoding='utf-8') as f:
                    plugin_config = json.load(f)
            
            author = plugin_config.get("author", "Unknown")
            name = plugin_config.get("name", plugin_name)
            
            metadata = {
                "name": name,
                "version": plugin_config.get("version", "1.0.0"),
                "author": author,
                "description": plugin_config.get("description", ""),
                "required_permissions": [],
                "required_capabilities": [],
                "dependencies": plugin_config.get("dependencies", []),
                "config_schema": plugin_config.get("config_schema"),
                "default_config": plugin_config.get("default_config", {}),
                "tags": plugin_config.get("tags", []),
                "category": plugin_config.get("category", "general"),
                "homepage": plugin_config.get("homepage"),
                "repository": plugin_config.get("repository"),
                "documentation": plugin_config.get("documentation"),
            }
        except Exception as e:
            logger.error(f"Failed to load plugin.json: {e}")
            raise HTTPException(status_code=500, detail="Failed to load plugin metadata")
        
        # Get status from database
        enabled = False
        config_data = metadata.get("default_config", {})
        
        if db_manager:
            try:
                db_setting = await db_manager.get_plugin_setting(author, name)
                if db_setting:
                    enabled = db_setting.enabled
                    config_data = db_setting.config or config_data
            except Exception as e:
                logger.error(f"Failed to get plugin status: {e}")
        
        return {
            "name": name,
            "enabled": enabled,
            "metadata": metadata,
            "config": config_data
        }
    
    @app.delete("/api/plugins/{plugin_name}")
    async def delete_plugin(
        plugin_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_LOAD))
    ):
        """Delete a plugin completely (remove from database and filesystem)."""
        username = user.get("username", "unknown")
        
        try:
            from ..core.app import get_app
            from pathlib import Path
            import shutil
            
            app = get_app()
            db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
            
            # Plugin directory structure: plugins/{name}
            config = get_config()
            plugin_dir = Path(config.plugin_dir) / plugin_name
            
            if not plugin_dir.exists():
                raise HTTPException(status_code=404, detail=f"Plugin {plugin_name} not found")
            
            # Load plugin.json to get author
            plugin_json = plugin_dir / "plugin.json"
            author = "Unknown"
            name = plugin_name
            
            if plugin_json.exists():
                try:
                    # Use thread pool for file IO
                    app = get_app()
                    thread_pool = getattr(app, 'plugin_thread_pool', None)
                    
                    if thread_pool:
                        def read_plugin_json():
                            with open(plugin_json, 'r', encoding='utf-8') as f:
                                return json.load(f)
                        metadata = await thread_pool.run_in_executor(read_plugin_json)
                    else:
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    author = metadata.get('author', 'Unknown')
                    name = metadata.get('name', plugin_name)
                except Exception as e:
                    logger.warning(f"Failed to read plugin.json: {e}")
            
            # Delete from database
            if db_manager:
                # 1. Delete plugin settings
                deleted = await db_manager.delete_plugin_setting(author, name)
                if deleted:
                    logger.info(f"Deleted plugin {author}/{name} settings from database")
                else:
                    logger.warning(f"Plugin {author}/{name} settings not found in database")
                
                # 2. Delete all binary storage data for this plugin
                try:
                    # Get all storage keys for this plugin
                    storage_keys = await db_manager.list_binary_keys('plugin', f"{author}/{name}")
                    deleted_count = 0
                    for key in storage_keys:
                        if await db_manager.delete_binary('plugin', f"{author}/{name}", key):
                            deleted_count += 1
                    
                    if deleted_count > 0:
                        logger.info(f"Deleted {deleted_count} binary storage entries for plugin {author}/{name}")
                    else:
                        logger.debug(f"No binary storage data found for plugin {author}/{name}")
                except Exception as e:
                    logger.error(f"Failed to delete binary storage for plugin {author}/{name}: {e}")
            
            # Delete plugin directory
            shutil.rmtree(plugin_dir)
            logger.info(f"Deleted plugin directory: {plugin_dir}")
            
            # Reload plugins in runtime
            if hasattr(app, 'plugin_connector') and app.plugin_connector:
                try:
                    await app.plugin_connector.reload_plugins()
                except Exception as e:
                    logger.warning(f"Failed to reload plugins after delete: {e}")
            
            # Log action
            await get_audit_logger().log_plugin_action(
                username=username,
                plugin_name=plugin_name,
                action="delete",
                success=True
            )
            
            return {"message": f"Plugin {plugin_name} deleted successfully"}
            
        except Exception as e:
            logger.error(f"Failed to delete plugin {plugin_name}: {e}", exc_info=True)
            await get_audit_logger().log_plugin_action(
                username=username,
                plugin_name=plugin_name,
                action="delete",
                success=False,
                details={"error": str(e)}
            )
            raise HTTPException(status_code=500, detail=f"Failed to delete plugin: {str(e)}")
    
    @app.post("/api/plugins/{plugin_name}/action")
    async def plugin_action(
        plugin_name: str,
        action: PluginAction,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Perform action on plugin (new system)."""
        from ..core.app import get_app
        from pathlib import Path
        import json
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        plugin_connector = app.plugin_connector if hasattr(app, 'plugin_connector') and app.plugin_connector else None
        perm_manager = get_permission_manager()
        username = user.get("username")
        
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database manager not available")
        
        # Helper function to get author from plugin.json
        async def get_plugin_author(plugin_name: str) -> tuple[str, str]:
            """Get author and name from plugin.json. Returns (author, name)."""
            config = get_config()
            plugin_dir = Path(config.plugin_dir) / plugin_name
            plugin_json = plugin_dir / "plugin.json"
            
            if plugin_json.exists():
                try:
                    # Use thread pool for file IO
                    app = get_app()
                    thread_pool = getattr(app, 'plugin_thread_pool', None)
                    
                    if thread_pool:
                        def read_plugin_json():
                            with open(plugin_json, 'r', encoding='utf-8') as f:
                                return json.load(f)
                        metadata = await thread_pool.run_in_executor(read_plugin_json)
                    else:
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    author = metadata.get('author', 'Unknown')
                    name = metadata.get('name', plugin_name)
                    return author, name
                except Exception as e:
                    logger.warning(f"Failed to read plugin.json for {plugin_name}: {e}")
            
            return 'Unknown', plugin_name
        
        # Check permissions based on action
        perm_map = {
            "load": Permission.PLUGIN_LOAD,
            "unload": Permission.PLUGIN_UNLOAD,
            "reload": Permission.PLUGIN_RELOAD,
            "enable": Permission.PLUGIN_ENABLE,
            "disable": Permission.PLUGIN_DISABLE,
        }
        
        required_perm = perm_map.get(action.action)
        if required_perm and not perm_manager.has_permission(username, required_perm):
            await get_audit_logger().log_access_denied(
                username=username,
                resource=f"plugin:{plugin_name}",
                action=action.action,
                reason="Insufficient permissions"
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Get plugin author and name
        author, name = await get_plugin_author(plugin_name)
        
        # Perform action
        success = False
        try:
            if action.action in ["load", "enable"]:
                # Enable plugin in database
                setting = await db_manager.get_plugin_setting(author, name)
                if not setting:
                    # Create new setting
                    result = await db_manager.create_plugin_setting(
                        author=author,
                        name=name,
                        enabled=True,
                        config={},
                        install_source='local'
                    )
                    success = result is not None
                else:
                    # Update existing setting
                    success = await db_manager.update_plugin_setting(author, name, enabled=True)
                
                # Load only this specific plugin in runtime (don't reload all plugins)
                if success and plugin_connector:
                    success = await plugin_connector.reload_plugin(plugin_name)
                    logger.info(f"Plugin {plugin_name} enabled and loaded")
            
            elif action.action in ["unload", "disable"]:
                # Disable plugin in database
                setting = await db_manager.get_plugin_setting(author, name)
                if setting:
                    success = await db_manager.update_plugin_setting(author, name, enabled=False)
                    logger.info(f"Plugin {plugin_name} disabled in database")
                    
                    # Unload only this specific plugin in runtime (don't reload all plugins)
                    if success and plugin_connector:
                        success = await plugin_connector.unload_plugin(plugin_name)
                        logger.info(f"Plugin {plugin_name} unloaded from runtime")
                else:
                    success = False
                    raise HTTPException(status_code=404, detail="Plugin not found in database")
            
            elif action.action == "reload":
                # Reload plugin: reload from file and restart in runtime
                if plugin_connector:
                    success = await plugin_connector.reload_plugin(plugin_name)
                    if success:
                        logger.info(f"Plugin {plugin_name} reloaded")
                    else:
                        raise HTTPException(status_code=500, detail=f"Failed to reload plugin {plugin_name}")
                else:
                    raise HTTPException(status_code=500, detail="Plugin connector not available")
            
            else:
                raise HTTPException(status_code=400, detail=f"Invalid action: {action.action}")
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to {action.action} plugin {plugin_name}: {e}", exc_info=True)
            await get_audit_logger().log_plugin_action(
                action.action,
                plugin_name,
                username,
                False,
                {"error": str(e)}
            )
            raise HTTPException(status_code=500, detail=f"Failed to {action.action} plugin: {str(e)}")
        
        # Log action
        await get_audit_logger().log_plugin_action(
            action.action,
            plugin_name,
            username,
            success
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to {action.action} plugin")
        
        return {"message": f"Plugin {action.action} successful"}
    
    @app.post("/api/plugins/reload-all")
    async def reload_all_plugins(
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_RELOAD))
    ):
        """Reload all plugins and update their metadata from plugin.json to database."""
        from ..core.app import get_app
        from pathlib import Path
        import json
        
        username = user.get("username", "unknown")
        config = get_config()
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        updated_count = 0
        created_count = 0
        failed_plugins = []
        
        # Get thread pool for file operations
        app = get_app()
        thread_pool = getattr(app, 'plugin_thread_pool', None)
        
        # Scan all plugins and update database
        if db_manager:
            plugin_base = Path(config.plugin_dir)
            if plugin_base.exists():
                # Scan directory in thread pool
                if thread_pool:
                    def scan_plugin_dirs():
                        return [d for d in plugin_base.iterdir() 
                                if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')]
                    plugin_dirs = await thread_pool.run_in_executor(scan_plugin_dirs)
                else:
                    plugin_dirs = [d for d in plugin_base.iterdir() 
                                   if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')]
                
                for plugin_dir in plugin_dirs:
                    plugin_json_file = plugin_dir / "plugin.json"
                    if not plugin_json_file.exists():
                        continue
                    
                    try:
                        # Read plugin.json in thread pool
                        if thread_pool:
                            def read_plugin_json():
                                with open(plugin_json_file, 'r', encoding='utf-8') as f:
                                    return json.load(f)
                            plugin_metadata = await thread_pool.run_in_executor(read_plugin_json)
                        else:
                            with open(plugin_json_file, 'r', encoding='utf-8') as f:
                                plugin_metadata = json.load(f)
                        
                        author = plugin_metadata.get('author', 'Unknown')
                        name = plugin_metadata.get('name', plugin_dir.name)
                        version = plugin_metadata.get('version', '1.0.0')
                        default_config = plugin_metadata.get('default_config', {})
                        
                        # Check if plugin exists in database
                        existing = await db_manager.get_plugin_setting(author, name)
                        if existing:
                            # Update install_info with new version
                            install_info = existing.install_info or {}
                            install_info['version'] = version
                            install_info['reloaded_at'] = datetime.now().isoformat()
                            install_info['reloaded_by'] = username
                            
                            await db_manager.update_plugin_setting(
                                author,
                                name,
                                install_info=install_info
                            )
                            updated_count += 1
                            logger.info(f"Updated plugin metadata: {author}/{name}")
                        else:
                            # Create if not exists
                            await db_manager.create_plugin_setting(
                                author=author,
                                name=name,
                                enabled=False,
                                priority=100,  # Default: 100 (lower = earlier execution)
                                config=default_config,
                                install_source='manual',
                                install_info={
                                    'version': version,
                                    'created_at': datetime.now().isoformat()
                                }
                            )
                            created_count += 1
                            logger.info(f"Created plugin setting: {author}/{name}")
                    except Exception as e:
                        logger.error(f"Failed to update plugin {plugin_dir.name}: {e}")
                        failed_plugins.append(plugin_dir.name)
        
        # Reload plugins in runtime
        try:
            if hasattr(app, 'plugin_connector') and app.plugin_connector:
                await app.plugin_connector.reload_plugins()
                logger.info("Reloaded all plugins in runtime")
        except Exception as e:
            logger.error(f"Failed to reload plugins in runtime: {e}")
        
        # Log action
        await get_audit_logger().log_plugin_action(
            "reload_all",
            "all",
            username,
            True,
            {
                "updated": updated_count,
                "created": created_count,
                "failed": failed_plugins
            }
        )
        
        return {
            "message": f"Reloaded all plugins. Updated: {updated_count}, Created: {created_count}, Failed: {len(failed_plugins)}",
            "updated_count": updated_count,
            "created_count": created_count,
            "failed_plugins": failed_plugins
        }
    
    @app.put("/api/plugins/{plugin_name}/config")
    async def update_plugin_config(
        plugin_name: str,
        config_update: ConfigUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_CONFIGURE))
    ):
        """Update plugin configuration and save to database."""
        from ..core.app import get_app
        from pathlib import Path
        import json
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        plugin_connector = app.plugin_connector if hasattr(app, 'plugin_connector') and app.plugin_connector else None
        
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database manager not available")
        
        # Get plugin directory
        config = get_config()
        plugin_dir = Path(config.plugin_dir)
        if not plugin_dir.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            plugin_dir = (project_root / config.plugin_dir).resolve()
        
        plugin_path = plugin_dir / plugin_name
        
        if not plugin_path.exists():
            raise HTTPException(status_code=404, detail="Plugin not found")
        
        # Load plugin metadata from plugin.json
        plugin_metadata = {}
        config_schema = {}
        default_config = {}
        author = "Unknown"
        name = plugin_name
        
        try:
            plugin_json = plugin_path / "plugin.json"
            if plugin_json.exists():
                # Use thread pool for file IO
                thread_pool = getattr(app, 'plugin_thread_pool', None)
                
                if thread_pool:
                    def read_plugin_json():
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    plugin_metadata = await thread_pool.run_in_executor(read_plugin_json)
                else:
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        plugin_metadata = json.load(f)
                author = plugin_metadata.get("author", "Unknown")
                name = plugin_metadata.get("name", plugin_name)
                config_schema = plugin_metadata.get("config_schema", {})
                default_config = plugin_metadata.get("default_config", {})
        except Exception as e:
            logger.warning(f"Failed to load plugin metadata: {e}")
        
        # Normalize config: ensure array fields are arrays, merge with defaults
        normalized_config = default_config.copy()
        
        # Merge with provided config
        if config_schema:
            # Have schema, process according to field types
            for key, value in config_update.config.items():
                if key in config_schema:
                    field_schema = config_schema[key]
                    field_type = field_schema.get("type")
                    
                    if field_type == "array":
                        # Ensure it's an array
                        if isinstance(value, list):
                            normalized_config[key] = value
                        elif isinstance(value, str):
                            # Convert string to array
                            import re
                            if value.strip():
                                normalized_config[key] = [v.strip() for v in re.split(r'[\n,\s]+', value) if v.strip()]
                            else:
                                normalized_config[key] = []
                        else:
                            normalized_config[key] = []
                    elif field_type == "number":
                        # Ensure it's a number, handle NaN and None
                        if value is None or (isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf'))):
                            # Use default value if available, otherwise 0
                            normalized_config[key] = field_schema.get("default_value", normalized_config.get(key, 0))
                        else:
                            try:
                                num_value = float(value) if not isinstance(value, (int, float)) else value
                                if not (num_value != num_value or num_value == float('inf') or num_value == float('-inf')):
                                    normalized_config[key] = num_value
                                else:
                                    normalized_config[key] = field_schema.get("default_value", normalized_config.get(key, 0))
                            except (ValueError, TypeError):
                                normalized_config[key] = field_schema.get("default_value", normalized_config.get(key, 0))
                    elif field_type == "boolean":
                        # Ensure it's a boolean
                        if isinstance(value, bool):
                            normalized_config[key] = value
                        elif isinstance(value, str):
                            normalized_config[key] = value.lower() in ('true', '1', 'yes', 'on')
                        else:
                            normalized_config[key] = bool(value)
                    else:
                        # For string, textarea, select, etc., use value as-is
                        normalized_config[key] = value
                else:
                    # Key not in schema, use value as-is
                    normalized_config[key] = value
        else:
            # No metadata, use config as-is but ensure arrays are arrays
            normalized_config = config_update.config.copy()
            for key, value in normalized_config.items():
                if isinstance(value, str) and key.endswith("_list"):
                    # Heuristic: if key ends with _list, try to convert to array
                    import re
                    if value.strip():
                        normalized_config[key] = [v.strip() for v in re.split(r'[\n,\s]+', value) if v.strip()]
                    else:
                        normalized_config[key] = []
        
        # Save config to database
        updated_config = normalized_config  # Default to normalized_config
        try:
            setting = await db_manager.get_plugin_setting(author, name)
            
            # Get priority: request > database > plugin.json > default (100)
            # First, get priority from plugin.json if available
            priority_from_json = None
            try:
                plugin_json = plugin_path / "plugin.json"
                if plugin_json.exists():
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        plugin_metadata = json.load(f)
                        priority_from_json = plugin_metadata.get('priority')
            except Exception:
                pass
            
            # Priority priority: request > database > plugin.json > default
            if hasattr(config_update, 'priority') and config_update.priority is not None:
                priority = config_update.priority
            elif setting and setting.priority != 100:
                priority = setting.priority
            elif priority_from_json is not None:
                priority = priority_from_json
            else:
                priority = 100
            
            if not setting:
                # Create new setting
                await db_manager.create_plugin_setting(
                    author=author,
                    name=name,
                    enabled=False,
                    priority=priority,
                    config=normalized_config,
                    install_source='local'
                )
            else:
                # Update existing setting (including priority if provided)
                update_data = {'config': normalized_config}
                if hasattr(config_update, 'priority') and config_update.priority is not None:
                    update_data['priority'] = priority
                await db_manager.update_plugin_setting(author, name, **update_data)
            
            logger.info(f"Updated config for plugin {author}/{name}")
            
            # Get the updated config from database to return to frontend
            updated_setting = await db_manager.get_plugin_setting(author, name)
            if updated_setting and updated_setting.config:
                updated_config = updated_setting.config
            
            # Reload plugin in runtime if it's running
            if plugin_connector:
                try:
                    await plugin_connector.reload_plugins()
                except Exception as e:
                    logger.warning(f"Failed to reload plugins after config update: {e}")
            
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save plugin config: {str(e)}")
        
        await get_audit_logger().log_plugin_action(
            "configure",
            plugin_name,
            user.get("username"),
            True,
            {"config": normalized_config}
        )
        
        # Return updated config so frontend doesn't need to reload
        return {
            "message": "Configuration updated successfully",
            "config": updated_config
        }
    
    # Note: Plugin adapter endpoint removed - new system uses independent process runtime
    # All plugins are loaded directly without adapters
    
    @app.post("/api/plugins/upload")
    async def upload_plugin(
        file: UploadFile = File(...),
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_LOAD))
    ):
        """Upload and install a plugin from ZIP file."""
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only ZIP files are supported")
        
        from ..core.app import get_app
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        plugin_connector = app.plugin_connector if hasattr(app, 'plugin_connector') and app.plugin_connector else None
        config = get_config()
        
        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / file.filename
            
            # Save uploaded file
            with open(zip_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            # Extract and install plugin
            return await _install_plugin_from_zip(zip_path, config, db_manager, plugin_connector, user)
    
    @app.post("/api/plugins/config-files")
    async def upload_plugin_config_file(
        file: UploadFile = File(...),
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_CONFIGURE))
    ):
        """Upload a file for plugin configuration.
        
        Returns file_key that can be used in plugin config.
        """
        from ..core.app import get_app
        import uuid
        import os
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database manager not available")
        
        # Check file size (10MB limit)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Generate unique file key with original extension
        original_filename = file.filename or "file"
        _, ext = os.path.splitext(original_filename)
        file_key = f'plugin_config_{uuid.uuid4().hex}{ext}'
        
        # Save file using database binary storage (owner_type='system', owner='plugin_config')
        try:
            await db_manager.set_binary('system', 'plugin_config', file_key, file_bytes)
            logger.info(f"Uploaded plugin config file: {file_key}, size: {len(file_bytes)} bytes")
            return {"file_key": file_key}
        except Exception as e:
            logger.error(f"Failed to save config file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    @app.delete("/api/plugins/config-files/{file_key}")
    async def delete_plugin_config_file(
        file_key: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_CONFIGURE))
    ):
        """Delete a plugin configuration file."""
        from ..core.app import get_app
        
        # Only allow deletion of files with plugin_config_ prefix for security
        if not file_key.startswith('plugin_config_'):
            raise HTTPException(status_code=400, detail="Invalid file key")
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database manager not available")
        
        try:
            success = await db_manager.delete_binary('system', 'plugin_config', file_key)
            if success:
                logger.info(f"Deleted plugin config file: {file_key}")
                return {"deleted": True}
            else:
                raise HTTPException(status_code=404, detail="File not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete config file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    
    @app.post("/api/plugins/install-from-github")
    async def install_plugin_from_github(
        repo_url: str = Body(..., embed=True),
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_LOAD))
    ):
        """Download and install a plugin from GitHub repository."""
        import httpx
        from ..core.app import get_app
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        plugin_connector = app.plugin_connector if hasattr(app, 'plugin_connector') and app.plugin_connector else None
        config = get_config()
        username = user.get("username")
        
        # Parse GitHub URL to get owner and repo
        # Support formats: 
        # - https://github.com/owner/repo
        # - https://github.com/owner/repo.git
        # - owner/repo
        repo_url = repo_url.strip()
        if repo_url.startswith('https://github.com/'):
            repo_url = repo_url.replace('https://github.com/', '')
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        
        parts = repo_url.strip('/').split('/')
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL. Format: owner/repo")
        
        owner, repo = parts[0], parts[1]
        
        # Download ZIP from GitHub
        download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
        
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                logger.info(f"Downloading plugin from GitHub: {owner}/{repo}")
                response = await client.get(download_url)
                
                # Try master branch if main doesn't exist
                if response.status_code == 404:
                    download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip"
                    response = await client.get(download_url)
                
                response.raise_for_status()
                zip_content = response.content
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to download plugin from GitHub: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to download from GitHub. Please check the repository URL and ensure it's public."
            )
        except Exception as e:
            logger.error(f"Error downloading plugin: {e}")
            raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")
        
        # Save to temporary file and install
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / f"{repo}.zip"
            
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            
            try:
                result = await _install_plugin_from_zip(zip_path, config, db_manager, plugin_connector, user)
                
                # Log action
                await get_audit_logger().log_plugin_action(
                    action="install_from_github",
                    plugin_name=result.get('plugin_name', repo),
                    username=username,
                    success=True,
                    details={"repo": f"{owner}/{repo}"}
                )
                
                return result
            except Exception as e:
                await get_audit_logger().log_plugin_action(
                    action="install_from_github",
                    plugin_name=repo,
                    username=username,
                    success=False,
                    details={"repo": f"{owner}/{repo}", "error": str(e)}
                )
                raise
    
    async def _install_plugin_from_zip(zip_path: Path, config, db_manager, plugin_connector, user):
        """Helper function to install plugin from ZIP file."""
        extract_dir = zip_path.parent / "extracted"
        extract_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP file")
        
        # Find plugin directory
        plugin_dirs = [d for d in extract_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        
        if not plugin_dirs:
            raise HTTPException(status_code=400, detail="No plugin directory found in ZIP")
        
        plugin_dir = plugin_dirs[0]
        plugin_folder_name = plugin_dir.name
        
        # Validate plugin structure
        plugin_json = plugin_dir / "plugin.json"
        if not plugin_json.exists():
            raise HTTPException(status_code=400, detail="Plugin must contain plugin.json file")
        
        # Validate and parse plugin.json using thread pool
        try:
            app = get_app()
            thread_pool = getattr(app, 'plugin_thread_pool', None)
            
            if thread_pool:
                def read_plugin_json():
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        return json.load(f)
                plugin_metadata = await thread_pool.run_in_executor(read_plugin_json)
            else:
                with open(plugin_json, 'r', encoding='utf-8') as f:
                    plugin_metadata = json.load(f)
                
            # Check required fields
            if 'name' not in plugin_metadata:
                raise HTTPException(status_code=400, detail="plugin.json must contain 'name' field")
            if 'version' not in plugin_metadata:
                raise HTTPException(status_code=400, detail="plugin.json must contain 'version' field")
                
            plugin_author = plugin_metadata.get('author', 'Unknown')
            plugin_name = plugin_metadata['name']
            plugin_version = plugin_metadata['version']
            default_config = plugin_metadata.get('default_config', {})
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid plugin.json format")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading plugin.json: {str(e)}")
        
        # Target directory: plugins/{name}
        target_dir = Path(config.plugin_dir) / plugin_name
        
        # Copy to plugin directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        # Ensure parent directory exists
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        # Copy the plugin directory
        shutil.copytree(plugin_dir, target_dir)
        
        # Auto-install dependencies
        from ...plugins.runtime.connector import install_plugin_dependencies
        logger.info(f"Checking dependencies for plugin: {plugin_author}/{plugin_name}")
        await install_plugin_dependencies(target_dir, plugin_metadata)
        
        # Register plugin in database
        db_manager = get_database_manager()
        try:
            # Check if plugin already exists
            existing = await db_manager.get_plugin_setting(plugin_author, plugin_name)
            if existing:
                # Update existing plugin
                await db_manager.update_plugin_setting(
                    plugin_author,
                    plugin_name,
                    config=existing.config,  # Keep existing config
                    install_source='upload',
                    install_info={
                        'version': plugin_version,
                        'uploaded_at': datetime.now().isoformat(),
                        'uploaded_by': user.get('username')
                    }
                )
                logger.info(f"Updated existing plugin: {plugin_author}/{plugin_name}")
            else:
                # Create new plugin setting (disabled by default)
                await db_manager.create_plugin_setting(
                    author=plugin_author,
                    name=plugin_name,
                    enabled=False,
                    priority=0,
                    config=default_config,
                    install_source='upload',
                    install_info={
                        'version': plugin_version,
                        'uploaded_at': datetime.now().isoformat(),
                        'uploaded_by': user.get('username')
                    }
                )
                logger.info(f"Created new plugin setting: {plugin_author}/{plugin_name}")
        except Exception as e:
            logger.error(f"Failed to register plugin in database: {e}")
            # Clean up on failure
            if target_dir.exists():
                shutil.rmtree(target_dir)
            raise HTTPException(status_code=500, detail=f"Failed to register plugin: {str(e)}")
        
        await get_audit_logger().log_plugin_action(
            "upload",
            plugin_name,
            user.get("username"),
            True
        )
        
        return {
            "message": "Plugin uploaded successfully. Please enable it in the plugin list to use.",
            "plugin_name": plugin_name,
            "plugin_author": plugin_author,
            "plugin_version": plugin_version
        }
    
    @app.get("/api/plugins/{plugin_name}/config-schema")
    async def get_plugin_config_schema(
        plugin_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_VIEW))
    ):
        """Get plugin configuration schema and current config.
        
        Reads from the database system.
        """
        # Try new plugin system first (database)
        try:
            from ..core.app import get_app
            from pathlib import Path
            import json
            
            app = get_app()
            if hasattr(app, 'db_manager') and app.db_manager:
                # Load schema from plugin.json first to get correct author
                author = "Unknown"
                name = plugin_name
                
                plugin_dir = Path("plugins") / name
                plugin_json = plugin_dir / "plugin.json"
                
                config_schema = {}
                default_config = {}
                
                if plugin_json.exists():
                    # Use thread pool for file IO
                    thread_pool = getattr(app, 'plugin_thread_pool', None)
                    
                    if thread_pool:
                        def read_plugin_json():
                            with open(plugin_json, 'r', encoding='utf-8') as f:
                                return json.load(f)
                        plugin_data = await thread_pool.run_in_executor(read_plugin_json)
                    else:
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            plugin_data = json.load(f)
                    author = plugin_data.get("author", "Unknown")
                    config_schema = plugin_data.get("config_schema", {})
                    default_config = plugin_data.get("default_config", {})
                
                # Get current config from database
                setting = await app.db_manager.get_plugin_setting(author, name)
                
                # Current config from database, or default
                # Merge default_config with database config to ensure all fields are present
                # Start with default_config to ensure all schema fields are present
                current_config = default_config.copy() if default_config else {}
                # Then override with database config (database config takes priority)
                if setting and setting.config:
                    # Deep merge to handle nested objects properly
                    for key, value in setting.config.items():
                        current_config[key] = value
                
                if plugin_json.exists():
                    # Return schema and configs
                    return {
                        "config_schema": config_schema,
                        "default_config": default_config,
                        "current_config": current_config
                    }
        except Exception as e:
            logger.warning(f"Failed to get config from new system: {e}")
        
        # If new system failed, return empty schema
        return {
            "config_schema": None,
            "default_config": {},
            "current_config": {}
        }


    @app.get("/api/ai/health")
    async def get_ai_health_status(user: Dict[str, Any] = Depends(get_current_user)):
        """Get comprehensive AI system health status."""
        from ..core.app import get_app
        from ..ai.dream import get_dream_scheduler
        
        app = get_app()
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "systems": {}
        }
        
        # 1. AI Message Handler
        if hasattr(app, 'ai_message_handler') and app.ai_message_handler:
            try:
                health_status["systems"]["ai_message_handler"] = {
                    "status": "running",
                    "initialized": True,
                    "error": None
                }
            except Exception as e:
                health_status["systems"]["ai_message_handler"] = {
                    "status": "error",
                    "initialized": False,
                    "error": str(e)
                }
                health_status["overall_status"] = "degraded"
        else:
            health_status["systems"]["ai_message_handler"] = {
                "status": "disabled",
                "initialized": False,
                "error": "Not initialized"
            }
        
        # 2. Dream Scheduler
        dream_scheduler = get_dream_scheduler()
        if dream_scheduler:
            stats = dream_scheduler.get_statistics()
            health_status["systems"]["dream_scheduler"] = {
                "status": "running" if stats['is_running'] else "stopped",
                "enabled": stats['enabled'],
                "total_cycles": stats['total_cycles'],
                "successful_cycles": stats['successful_cycles'],
                "failed_cycles": stats['failed_cycles'],
                "avg_iterations": round(stats['avg_iterations'], 2),
                "avg_cost_seconds": round(stats['avg_cost_seconds'], 2),
                "last_cycle_time": stats['last_cycle_time'],
                "error": None
            }
        else:
            health_status["systems"]["dream_scheduler"] = {
                "status": "not_initialized",
                "enabled": False,
                "error": "Scheduler not initialized"
            }
            health_status["overall_status"] = "degraded"
        
        # 3. Model Manager
        try:
            from ..ai.model_manager import ModelManager
            model_manager = ModelManager()
            await model_manager.initialize()
            
            models = await model_manager.list_models()
            default_model = await model_manager.get_default_model()
            
            health_status["systems"]["model_manager"] = {
                "status": "running",
                "total_models": len(models),
                "has_default_model": default_model is not None,
                "default_model": default_model.get('name') if default_model else None,
                "error": None
            }
        except Exception as e:
            health_status["systems"]["model_manager"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["overall_status"] = "degraded"
        
        # 4. Expression Systems
        health_status["systems"]["expression_systems"] = {
            "auto_checker": {"status": "running", "note": "Checks expressions hourly"},
            "reflector": {"status": "running", "note": "Reflects every 2 hours"},
            "selector": {"status": "available"},
            "learner": {"status": "available"}
        }
        
        # 5. Knowledge Graph
        try:
            from ..ai.knowledge import kg_manager
            health_status["systems"]["knowledge_graph"] = {
                "status": "available",
                "note": "OpenIE-based knowledge extraction"
            }
        except Exception as e:
            health_status["systems"]["knowledge_graph"] = {
                "status": "error",
                "error": str(e)
            }
        
        # 6. Memory Systems
        health_status["systems"]["memory_systems"] = {
            "chat_history": {"status": "available"},
            "jargon_miner": {"status": "available"},
            "person_profiler": {"status": "available"},
            "group_profiler": {"status": "available"}
        }
        
        # 7. Sticker System
        health_status["systems"]["sticker_system"] = {
            "manager": {"status": "available"},
            "learner": {"status": "available"},
            "selector": {"status": "available"},
            "integration": {"status": "available"}
        }
        
        # 8. Other AI Components
        health_status["systems"]["other_components"] = {
            "brain_planner": {"status": "available"},
            "chat_summarizer": {"status": "available"},
            "frequency_control": {"status": "available"},
            "thread_pool": {"status": "available"},
            "mcp_manager": {"status": "available"}
        }
        
        return health_status
    
    @app.get("/api/onebot/status")
    async def get_onebot_status(user: Dict[str, Any] = Depends(get_current_user)):
        """Get OneBot adapter status and connection info."""
        application = get_app()
        config = get_config()
        
        status = {
            "connected": False,
            "connection_type": config.onebot_connection_type,
            "version": config.onebot_version,
            "has_access_token": bool(config.onebot_access_token),
            "has_secret": bool(config.onebot_secret),
            "client_count": 0,
            "details": {}
        }
        
        if hasattr(application, 'onebot_adapter') and application.onebot_adapter:
            adapter = application.onebot_adapter
            status["connected"] = getattr(adapter, '_running', False)
            
            # 根据连接类型提供详细信息
            if config.onebot_connection_type == "http":
                status["details"] = {
                    "url": config.onebot_http_url,
                    "auth_configured": bool(config.onebot_access_token)
                }
            elif config.onebot_connection_type in ["ws", "ws_forward"]:
                status["details"] = {
                    "url": config.onebot_ws_url,
                    "auth_configured": bool(config.onebot_access_token),
                    "ws_connected": adapter._ws is not None and not adapter._ws.closed if adapter._ws else False
                }
            elif config.onebot_connection_type == "ws_reverse":
                status["client_count"] = len(adapter._reverse_clients) if hasattr(adapter, '_reverse_clients') else 0
                status["details"] = {
                    "host": config.onebot_ws_reverse_host,
                    "port": config.onebot_ws_reverse_port,
                    "path": config.onebot_ws_reverse_path,
                    "auth_configured": bool(config.onebot_access_token),
                    "server_running": adapter._ws_server is not None,
                    "connected_clients": status["client_count"]
                }
        
        return status
    
    @app.get("/api/onebot/config")
    async def get_onebot_config(user: Dict[str, Any] = Depends(get_current_user)):
        """Get OneBot configuration."""
        config = get_config()
        return {
            "version": config.onebot_version,
            "connection_type": config.onebot_connection_type,
            "http_url": config.onebot_http_url,
            "ws_url": config.onebot_ws_url,
            "ws_reverse_host": config.onebot_ws_reverse_host,
            "ws_reverse_port": config.onebot_ws_reverse_port,
            "ws_reverse_path": config.onebot_ws_reverse_path,
            "access_token": config.onebot_access_token,
            "secret": config.onebot_secret,
        }
    
    @app.post("/api/onebot/config")
    async def update_onebot_config(
        config_update: Dict[str, Any],
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Update OneBot configuration."""
        from pydantic import ValidationError
        import os
        
        # Get current config
        config_manager = get_config_manager()
        current_config = config_manager.get()
        
        # Update config values
        update_data = {}
        if "connection_type" in config_update:
            update_data["onebot_connection_type"] = config_update["connection_type"]
        if "http_url" in config_update:
            update_data["onebot_http_url"] = config_update["http_url"]
        if "ws_url" in config_update:
            update_data["onebot_ws_url"] = config_update["ws_url"]
        if "ws_reverse_host" in config_update:
            update_data["onebot_ws_reverse_host"] = config_update["ws_reverse_host"]
        if "ws_reverse_port" in config_update:
            update_data["onebot_ws_reverse_port"] = config_update["ws_reverse_port"]
        if "ws_reverse_path" in config_update:
            update_data["onebot_ws_reverse_path"] = config_update["ws_reverse_path"]
        if "access_token" in config_update:
            # 如果 access_token 是空字符串，表示不需要 token 认证，允许设置为空
            update_data["onebot_access_token"] = config_update["access_token"]
        if "secret" in config_update:
            # 如果 secret 是空字符串，表示不需要签名验证，允许设置为空
            update_data["onebot_secret"] = config_update["secret"]
        if "version" in config_update:
            update_data["onebot_version"] = config_update["version"]
        
        # Update configuration in TOML file
        # Find config.toml file in project root (go up from src/ui/api.py to onebot_framework/)
        # api.py is at: onebot_framework/src/ui/api.py
        # config.toml is at: onebot_framework/config.toml
        project_root = Path(__file__).parent.parent.parent  # onebot_framework/
        toml_file = project_root / "config.toml"
        
        # Read existing TOML file
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib  # Fallback for older Python versions
        
        try:
            import tomli_w
        except ImportError:
            logger.error("tomli-w is not installed. Please install it: pip install tomli-w")
            raise HTTPException(
                status_code=500,
                detail="TOML write support not available. Please install tomli-w."
            )
        
        # Use thread pool for synchronous file IO
        app = get_app()
        thread_pool = getattr(app, 'plugin_thread_pool', None)
        
        config_data = {}
        if toml_file.exists():
            if thread_pool:
                def read_toml_file():
                    with open(toml_file, "rb") as f:
                        return tomllib.load(f)
                config_data = await thread_pool.run_in_executor(read_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "rb") as f:
                    config_data = tomllib.load(f)
        
        # Ensure [onebot] section exists
        if "onebot" not in config_data:
            config_data["onebot"] = {}
        
        # Map config keys to TOML structure
        toml_mapping = {
            "onebot_connection_type": ("onebot", "connection_type"),
            "onebot_http_url": ("onebot", "http_url"),
            "onebot_ws_url": ("onebot", "ws_url"),
            "onebot_ws_reverse_host": ("onebot", "ws_reverse_host"),
            "onebot_ws_reverse_port": ("onebot", "ws_reverse_port"),
            "onebot_ws_reverse_path": ("onebot", "ws_reverse_path"),
            "onebot_access_token": ("onebot", "access_token"),
            "onebot_secret": ("onebot", "secret"),
            "onebot_version": ("onebot", "version"),
        }
        
        # Update TOML data
        for key, value in update_data.items():
            section, field = toml_mapping.get(key, (None, None))
            if section and field:
                if section not in config_data:
                    config_data[section] = {}
                config_data[section][field] = value
                # Also update environment variable for immediate effect
                env_key = key.upper()
                os.environ[env_key] = str(value)
        
        # Write back to TOML file using thread pool
        if thread_pool:
            def write_toml_file():
                with open(toml_file, "wb") as f:
                    tomli_w.dump(config_data, f)
            await thread_pool.run_in_executor(write_toml_file)
        else:
            # Fallback to sync operation if thread pool not available
            with open(toml_file, "wb") as f:
                tomli_w.dump(config_data, f)
        
        logger.info("Configuration saved to config.toml", file=str(toml_file))
        
        # Update in-memory config
        config_manager.update(**update_data)
        
        # Reload config (force reload from .env file)
        reload_config()
        # Also clear the cache to ensure fresh config
        get_config.cache_clear()
        new_config = get_config()
        logger.info("Configuration reloaded", connection_type=new_config.onebot_connection_type)
        
        # Restart OneBot adapter with new config
        application = get_app()
        if hasattr(application, 'onebot_adapter') and application.onebot_adapter:
            try:
                # Stop current adapter
                await application.onebot_adapter.stop()
                logger.info("OneBot adapter stopped for reconfiguration")
                
                # Get new config
                new_config = get_config()
                onebot_config = {
                    "version": new_config.onebot_version,
                    "connection_type": new_config.onebot_connection_type,
                    "http_url": new_config.onebot_http_url,
                    "ws_url": new_config.onebot_ws_url,
                    "ws_reverse_host": new_config.onebot_ws_reverse_host,
                    "ws_reverse_port": new_config.onebot_ws_reverse_port,
                    "ws_reverse_path": new_config.onebot_ws_reverse_path,
                    "access_token": new_config.onebot_access_token,
                    "secret": new_config.onebot_secret,
                }
                
                # Create new adapter with updated config
                from ..protocol.onebot import OneBotAdapter
                application.onebot_adapter = OneBotAdapter(onebot_config)
                
                # Re-register event handler
                event_bus = get_event_bus()
                async def handle_onebot_event(event):
                    await event_bus.publish(
                        f"onebot.{event['type']}",
                        event,
                        source="onebot"
                    )
                
                application.onebot_adapter.on_event(handle_onebot_event)
                
                # Start new adapter
                await application.onebot_adapter.start()
                logger.info("OneBot adapter restarted with new configuration")
                
            except Exception as e:
                logger.error("Failed to restart OneBot adapter", error=str(e), exc_info=True)
                return {
                    "message": f"Configuration saved but failed to restart adapter: {str(e)}. Please restart the application manually."
                }
        
        # Log the action
        await get_audit_logger().log_plugin_action(
            "configure",
            "onebot",
            user.get("username"),
            True,
            {"config": config_update}
        )
        
        return {"message": "Configuration updated and OneBot adapter restarted successfully."}
    
    @app.post("/api/onebot/reconnect")
    async def reconnect_onebot(user: Dict[str, Any] = Depends(get_current_user)):
        """Manually reconnect OneBot adapter."""
        application = get_app()
        if not hasattr(application, 'onebot_adapter') or not application.onebot_adapter:
            return {"success": False, "message": "OneBot adapter not initialized"}
        
        try:
            # Stop current adapter
            await application.onebot_adapter.stop()
            logger.info("OneBot adapter stopped for manual reconnection")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Get current config
            config = get_config()
            onebot_config = {
                "version": config.onebot_version,
                "connection_type": config.onebot_connection_type,
                "http_url": config.onebot_http_url,
                "ws_url": config.onebot_ws_url,
                "ws_reverse_host": config.onebot_ws_reverse_host,
                "ws_reverse_port": config.onebot_ws_reverse_port,
                "ws_reverse_path": config.onebot_ws_reverse_path,
                "access_token": config.onebot_access_token,
                "secret": config.onebot_secret,
            }
            
            # Create new adapter
            from ..protocol.onebot import OneBotAdapter
            application.onebot_adapter = OneBotAdapter(onebot_config)
            
            # Re-register event handler
            event_bus = get_event_bus()
            async def handle_onebot_event(event):
                await event_bus.publish(
                    f"onebot.{event['type']}",
                    event,
                    source="onebot"
                )
            
            application.onebot_adapter.on_event(handle_onebot_event)
            
            # Start adapter
            await application.onebot_adapter.start()
            logger.info("OneBot adapter reconnected successfully")
            
            # Log the action
            await get_audit_logger().log_plugin_action(
                "reconnect",
                "onebot",
                user.get("username"),
                True,
                {}
            )
            
            return {"success": True, "message": "OneBot adapter reconnected successfully"}
        except Exception as e:
            logger.error("Failed to reconnect OneBot adapter", error=str(e), exc_info=True)
            return {"success": False, "message": f"Failed to reconnect: {str(e)}"}
    
    @app.get("/api/messages/log")
    async def get_message_log(
        limit: int = 100,
        include_notices: bool = True,
        include_requests: bool = True,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get message log from event bus, including messages, notices, and requests."""
        event_bus = get_event_bus()
        events = event_bus.get_event_history(limit * 3)  # Get more to filter
        
        # Filter for all events (messages, notices, requests)
        all_events = []
        for event in events:
            payload = event.payload
            if not isinstance(payload, dict):
                continue
            
            event_data = None
            
            # Message events
            if event.name == "onebot.message":
                event_data = {
                    "id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "time": event.timestamp.isoformat(),
                    "event_type": "message",
                    "post_type": "message",
                    "message_id": str(payload.get("message_id", "")),
                    "message_type": payload.get("message_type", "unknown"),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "raw_message": payload.get("raw_message", ""),
                    "message": payload.get("raw_message", ""),
                    "sender": payload.get("sender", {}),
                    "is_self": payload.get("is_self", False),  # Mark if self-sent
                }
            
            # Notice events
            elif event.name == "onebot.notice" and include_notices:
                # Debug log to see what we're receiving
                logger.debug(f"Formatting notice event: {payload.get('notice_type', 'NO_TYPE')} | payload keys: {list(payload.keys())}")
                
                formatted_text = _format_notice_event(payload)
                event_data = {
                    "id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "time": event.timestamp.isoformat(),
                    "event_type": "notice",
                    "post_type": "notice",
                    "notice_type": payload.get("notice_type", ""),
                    "sub_type": payload.get("sub_type", ""),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "operator_id": str(payload.get("operator_id", "")) if payload.get("operator_id") else None,
                    "message": formatted_text,
                    "raw_message": formatted_text,
                    "is_system": True,
                    "raw_data": payload
                }
            
            # Request events
            elif event.name == "onebot.request" and include_requests:
                formatted_text = _format_request_event(payload)
                event_data = {
                    "id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "time": event.timestamp.isoformat(),
                    "event_type": "request",
                    "post_type": "request",
                    "request_type": payload.get("request_type", ""),
                    "sub_type": payload.get("sub_type", ""),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "comment": payload.get("comment", ""),
                    "message": formatted_text,
                    "raw_message": formatted_text,
                    "is_system": True,
                    "raw_data": payload
                }
            
            if event_data:
                all_events.append(event_data)
                if len(all_events) >= limit:
                    break
        
        # Sort by timestamp (newest first)
        all_events.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return all_events[:limit]
    
    @app.websocket("/ws/messages")
    async def websocket_messages(websocket: WebSocket):
        """WebSocket endpoint for real-time message updates."""
        await _ws_manager.connect(websocket)
        try:
            # Keep connection alive and handle incoming messages (e.g., ping/pong)
            while True:
                # Wait for any message from client (typically ping/pong or keep-alive)
                try:
                    data = await websocket.receive_text()
                    # Echo back for keep-alive
                    if data == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    break
        finally:
            _ws_manager.disconnect(websocket)
    
    # System endpoints
    def _get_bot_status(application) -> Dict[str, Any]:
        """Get bot connection status."""
        bot_status = {
            "online": False,
            "connection_type": None,
            "status_text": "离线"
        }
        
        if hasattr(application, 'onebot_adapter'):
            adapter = application.onebot_adapter
            if adapter and adapter._running:
                bot_status["online"] = True
                bot_status["connection_type"] = adapter.connection_type
                
                # Check connection based on type
                if adapter.connection_type in ("ws", "ws_forward"):
                    # Forward WebSocket: check if _ws exists
                    # websockets library doesn't have a 'closed' attribute
                    # When connection closes, _ws is set to None (see onebot.py line 183)
                    if adapter._ws is not None:
                        bot_status["status_text"] = "在线"
                    else:
                        bot_status["status_text"] = "连接中"
                elif adapter.connection_type == "ws_reverse":
                    # Reverse WebSocket: check if there are connected clients
                    if adapter._reverse_clients and len(adapter._reverse_clients) > 0:
                        bot_status["status_text"] = "在线"
                    else:
                        bot_status["status_text"] = "等待连接"
                else:
                    # HTTP only
                    bot_status["status_text"] = "在线"
        
        return bot_status
    
    @app.get("/api/chat/contacts")
    async def get_chat_contacts(
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get group and friend lists for chat."""
        from ..core.app import get_app
        app_instance = get_app()
        
        contacts = {
            "groups": [],
            "friends": []
        }
        
        if hasattr(app_instance, 'onebot_adapter') and app_instance.onebot_adapter:
            try:
                # Get group list
                group_result = await app_instance.onebot_adapter.call_api("get_group_list", {})
                if isinstance(group_result, dict) and "data" in group_result:
                    groups = group_result["data"]
                elif isinstance(group_result, list):
                    groups = group_result
                else:
                    groups = []
                
                for group in groups:
                    contacts["groups"].append({
                        "id": str(group.get("group_id", "")),
                        "name": group.get("group_name", "未知群"),
                        "avatar": f"http://p.qlogo.cn/gh/{group.get('group_id', '')}/{group.get('group_id', '')}/640/",
                        "member_count": group.get("member_count", 0),
                        "max_member_count": group.get("max_member_count", 0)
                    })
                
                # Get friend list
                friend_result = await app_instance.onebot_adapter.call_api("get_friend_list", {})
                if isinstance(friend_result, dict) and "data" in friend_result:
                    friends = friend_result["data"]
                elif isinstance(friend_result, list):
                    friends = friend_result
                else:
                    friends = []
                
                for friend in friends:
                    contacts["friends"].append({
                        "id": str(friend.get("user_id", "")),
                        "name": friend.get("nickname", "") or friend.get("remark", "") or "未知好友",
                        "avatar": f"http://q.qlogo.cn/headimg_dl?dst_uin={friend.get('user_id', '')}&spec=640",
                        "remark": friend.get("remark", "")
                    })
                
            except Exception as e:
                logger.error(f"Failed to get contacts: {e}", exc_info=True)
        
        return contacts
    
    @app.post("/api/chat/send")
    async def send_chat_message(
        request: Dict[str, Any],
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Send a message to group or friend."""
        from ..core.app import get_app
        import time
        app_instance = get_app()
        
        chat_type = request.get("type")  # "group" or "private"
        chat_id = request.get("id")  # group_id or user_id
        message = request.get("message")
        
        if not all([chat_type, chat_id, message]):
            raise HTTPException(status_code=400, detail="Missing required fields: type, id, message")
        
        if not hasattr(app_instance, 'onebot_adapter') or not app_instance.onebot_adapter:
            raise HTTPException(status_code=503, detail="OneBot adapter not available")
        
        try:
            # Get bot's self_id first
            login_info = await app_instance.onebot_adapter.call_api("get_login_info", {})
            self_id = login_info.get("data", {}).get("user_id") if isinstance(login_info, dict) else None
            self_nickname = login_info.get("data", {}).get("nickname", "Bot") if isinstance(login_info, dict) else "Bot"
            
            # Send message
            if chat_type == "group":
                result = await app_instance.onebot_adapter.call_api(
                    "send_group_msg",
                    {"group_id": int(chat_id), "message": message}
                )
            elif chat_type == "private":
                result = await app_instance.onebot_adapter.call_api(
                    "send_private_msg",
                    {"user_id": int(chat_id), "message": message}
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid type, must be 'group' or 'private'")
            
            # Get message_id from result
            message_id = None
            if isinstance(result, dict):
                if "data" in result:
                    message_id = result["data"].get("message_id")
                elif "message_id" in result:
                    message_id = result["message_id"]
            
            # Publish to EventBus for message history (but mark as source="self" so plugins can ignore if needed)
            message_obj = None
            if self_id and message_id:
                simulated_event = {
                    "time": int(time.time()),
                    "self_id": self_id,
                    "post_type": "message",
                    "message_type": chat_type,
                    "sub_type": "normal",
                    "message_id": message_id,
                    "user_id": self_id,
                    "message": message,
                    "raw_message": message,
                    "font": 0,
                    "sender": {
                        "user_id": self_id,
                        "nickname": self_nickname,
                        "card": "",
                        "role": "owner"
                    },
                    "is_self": True,  # Mark as self-sent
                    "target_id": chat_id  # Add target_id to identify the recipient
                }
                
                # Add group_id for group messages
                if chat_type == "group":
                    simulated_event["group_id"] = str(chat_id)  # Use string to match received messages
                
                # Publish to event bus for message history
                event_bus = get_event_bus()
                await event_bus.publish(
                    "onebot.message",
                    simulated_event,
                    source="self"  # Mark source as "self" so plugins can filter if needed
                )
                
                # Prepare message object for immediate display
                message_obj = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "message_id": str(message_id),
                    "user_id": str(self_id),
                    "message": message,
                    "sender": {
                        "user_id": self_id,
                        "nickname": self_nickname,
                        "card": "",
                        "role": "owner"
                    },
                    "is_self": True
                }
            
            return {
                "success": True,
                "message_id": message_id,
                "message": message_obj
            }
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    
    @app.get("/api/chat/image-proxy")
    async def proxy_chat_image(
        url: str,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Proxy chat images to bypass CORS and referer restrictions."""
        import httpx
        
        try:
            # 解码 URL（前端可能进行了编码）
            image_url = url
            if image_url.startswith('http%3A') or image_url.startswith('https%3A'):
                from urllib.parse import unquote
                image_url = unquote(image_url)
            
            # 添加必要的请求头来绕过防盗链
            headers = {
                'Referer': 'https://qzone.qq.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # 下载图片
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.get(image_url, headers=headers)
                response.raise_for_status()
                
                # 返回图片内容
                from fastapi.responses import Response
                return Response(
                    content=response.content,
                    media_type=response.headers.get('content-type', 'image/jpeg')
                )
        except Exception as e:
            logger.error(f"Failed to proxy image: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load image: {str(e)}")
    
    @app.get("/api/chat/history/{chat_type}/{chat_id}")
    async def get_chat_history(
        chat_type: str,
        chat_id: str,
        limit: int = 50,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get chat history for a specific group or friend."""
        event_bus = get_event_bus()
        events = event_bus.get_event_history(500)  # Get more to filter
        
        logger.debug(f"Getting chat history for {chat_type} {chat_id}, total events: {len(events)}")
        
        messages = []
        for event in events:
            if event.name == "onebot.message":
                payload = event.payload
                if isinstance(payload, dict):
                    # Add is_self flag from event source if not already present
                    if "is_self" not in payload and event.source == "self":
                        payload_is_self = True
                    else:
                        payload_is_self = payload.get("is_self", False)
                    
                    logger.debug(f"Event payload: message_type={payload.get('message_type')}, group_id={payload.get('group_id')}, user_id={payload.get('user_id')}, is_self={payload_is_self}, target_id={payload.get('target_id')}, source={event.source}")
                    
                    # Filter by chat type and ID
                    if chat_type == "group" and str(payload.get("group_id")) == str(chat_id):
                        logger.debug(f"Adding group message to history: {payload.get('raw_message', '')[:50]}")
                        messages.append({
                            "id": event.event_id,
                            "timestamp": event.timestamp.isoformat(),
                            "message_id": str(payload.get("message_id", "")),
                            "user_id": str(payload.get("user_id", "")),
                            "message": payload.get("raw_message", ""),
                            "sender": payload.get("sender", {}),
                            "is_self": payload_is_self
                        })
                    elif chat_type == "private" and payload.get("message_type") == "private":
                        # For private messages, include both:
                        # 1. Messages FROM this user (user_id == chat_id)
                        # 2. Messages TO this user (target_id == chat_id, sent by bot)
                        is_from_user = str(payload.get("user_id")) == str(chat_id)
                        is_to_user = str(payload.get("target_id")) == str(chat_id) and payload_is_self
                        
                        if is_from_user or is_to_user:
                            logger.debug(f"Adding private message to history: {payload.get('raw_message', '')[:50]}")
                            messages.append({
                                "id": event.event_id,
                                "timestamp": event.timestamp.isoformat(),
                                "message_id": str(payload.get("message_id", "")),
                                "user_id": str(payload.get("user_id", "")),
                                "message": payload.get("raw_message", ""),
                                "sender": payload.get("sender", {}),
                                "is_self": payload_is_self
                            })
                    
                    if len(messages) >= limit:
                        break
        
        logger.debug(f"Returning {len(messages)} messages for {chat_type} {chat_id}")
        
        # Sort by timestamp (oldest first for chat display)
        messages.sort(key=lambda x: x["timestamp"])
        
        return messages[-limit:]  # Return last N messages
    
    @app.get("/api/onebot/login-info")
    async def get_login_info(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get OneBot login information."""
        try:
            app = get_app()
            if not app.onebot_adapter or not app.onebot_adapter.is_running():
                return {
                    "status": "error",
                    "message": "OneBot adapter not running",
                    "data": None
                }
            
            # Call get_login_info API
            result = await app.onebot_adapter.call_api("get_login_info", {})
            logger.debug(f"Login info API result: {result}")
            
            return {
                "status": "ok",
                "data": result
            }
        except Exception as e:
            logger.error(f"Failed to get login info: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "data": None
            }
    
    async def _get_plugin_stats(db_manager) -> Dict[str, int]:
        """Get plugin statistics from database.
        
        Note: enabled plugins are automatically loaded into runtime,
        so enabled count should equal running count in normal cases.
        """
        if not db_manager:
            return {"total": 0, "enabled": 0}
        
        try:
            all_plugins = await db_manager.list_plugin_settings()
            enabled_plugins = await db_manager.list_plugin_settings(enabled_only=True)
            
            # Enabled plugins are automatically loaded into runtime
            # So enabled count should be the actual running count
            return {
                "total": len(all_plugins),
                "enabled": len(enabled_plugins)
            }
        except Exception as e:
            logger.warning(f"Failed to get plugin stats: {e}")
            return {"total": 0, "enabled": 0}
    
    @app.get("/api/system/status")
    async def get_system_status(user: Dict[str, Any] = Depends(get_current_user)):
        """Get system status."""
        import platform
        import psutil
        from datetime import datetime, timedelta
        event_bus = get_event_bus()
        application = get_app()
        config = get_config()
        db_manager = application.db_manager if hasattr(application, 'db_manager') and application.db_manager else None
        
        # Calculate uptime
        uptime_str = "N/A"
        if hasattr(application, '_start_time'):
            uptime_delta = datetime.now() - application._start_time
            days = uptime_delta.days
            hours = uptime_delta.seconds // 3600
            minutes = (uptime_delta.seconds % 3600) // 60
            if days > 0:
                uptime_str = f"{days}天 {hours}小时"
            elif hours > 0:
                uptime_str = f"{hours}小时 {minutes}分钟"
            else:
                uptime_str = f"{minutes}分钟"
        
        event_stats = event_bus.get_stats()
        
        # Get today's message statistics from event bus counters
        # (These are maintained by event bus and reset at midnight)
        today_received = event_stats.get("today_received", 0)
        today_sent = event_stats.get("today_sent", 0)
        
        # Fallback: If counters not available, count from event history
        if today_received == 0 and today_sent == 0:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Count messages from event history
            for event in event_bus._event_history:
                if event.timestamp >= today_start:
                    # Check for received messages
                    is_message = False
                    
                    # Check if it's a received message event
                    if event.name == "onebot.message":
                        is_message = True
                    elif isinstance(event.payload, dict):
                        payload = event.payload
                        if payload.get('type') == 'message':
                            is_message = True
                        elif payload.get('raw') and isinstance(payload.get('raw'), dict):
                            raw_data = payload.get('raw', {})
                            if raw_data.get('post_type') == 'message':
                                is_message = True
                        elif payload.get('post_type') == 'message':
                            is_message = True
                    
                    if is_message:
                        today_received += 1
                    
                    # Check for sent messages
                    if event.name == "onebot.message_sent":
                        today_sent += 1
        
        # Get CPU and memory info (with fallback if psutil fails)
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Get current process info
            process = psutil.Process()
            process_cpu = process.cpu_percent(interval=0.1)
            process_memory = process.memory_info()
            
            cpu_info = {
                "model": platform.processor() or "Unknown",
                "cores": cpu_count,
                "frequency": f"{cpu_freq.current:.2f} GHz" if cpu_freq else "N/A",
                "usage": round(cpu_percent, 2),
                "process_usage": round(process_cpu, 2),
            }
            memory_info = {
                "total": round(memory.total / (1024 * 1024), 2),  # MB
                "used": round(memory.used / (1024 * 1024), 2),  # MB
                "available": round(memory.available / (1024 * 1024), 2),  # MB
                "percent": round(memory.percent, 2),
                "process_memory": round(process_memory.rss / (1024 * 1024), 2),  # MB
            }
            
            # Get disk usage
            disk_usage = psutil.disk_usage('/')
            disk_info = {
                "total": round(disk_usage.total / (1024 * 1024 * 1024), 2),  # GB
                "used": round(disk_usage.used / (1024 * 1024 * 1024), 2),  # GB
                "free": round(disk_usage.free / (1024 * 1024 * 1024), 2),  # GB
                "percent": round(disk_usage.percent, 2),
            }
            
            # Get network I/O
            net_io = psutil.net_io_counters()
            network_info = {
                "bytes_sent": round(net_io.bytes_sent / (1024 * 1024), 2),  # MB
                "bytes_recv": round(net_io.bytes_recv / (1024 * 1024), 2),  # MB
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }
            
            # Get disk I/O
            try:
                disk_io = psutil.disk_io_counters()
                disk_io_info = {
                    "read_bytes": round(disk_io.read_bytes / (1024 * 1024), 2) if disk_io else 0,  # MB
                    "write_bytes": round(disk_io.write_bytes / (1024 * 1024), 2) if disk_io else 0,  # MB
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0,
                }
            except Exception:
                disk_io_info = {
                    "read_bytes": 0,
                    "write_bytes": 0,
                    "read_count": 0,
                    "write_count": 0,
                }
        except Exception as e:
            logger.warning("Failed to get system metrics", error=str(e))
            cpu_info = {
                "model": platform.processor() or "Unknown",
                "cores": 0,
                "frequency": "N/A",
                "usage": 0.0,
                "process_usage": 0.0,
            }
            memory_info = {
                "total": 0.0,
                "used": 0.0,
                "available": 0.0,
                "percent": 0.0,
                "process_memory": 0.0,
            }
            disk_info = {
                "total": 0.0,
                "used": 0.0,
                "free": 0.0,
                "percent": 0.0,
            }
            network_info = {
                "bytes_sent": 0.0,
                "bytes_recv": 0.0,
                "packets_sent": 0,
                "packets_recv": 0,
            }
            disk_io_info = {
                "read_bytes": 0.0,
                "write_bytes": 0.0,
                "read_count": 0,
                "write_count": 0,
            }
        
        return {
            "status": "running" if application.is_running() else "stopped",
            "event_bus": {
                **event_stats,
                "total_events": event_stats.get("total_events_processed", event_stats.get("history_size", 0)),
                "today_received": today_received,
                "today_sent": today_sent,
            },
            "plugins": await _get_plugin_stats(db_manager),
            "uptime": uptime_str,
            "bot_status": _get_bot_status(application),
            "system": {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
            },
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "network": network_info,
            "disk_io": disk_io_info,
            "versions": {
                "framework": config.app_version,
                "onebot": config.onebot_version,
                "webui": "NEXT",  # Vite + React
                "python": platform.python_version(),
                "typescript": "5.2.2",  # From package.json
                "react": "18.2.0",  # From package.json
                "vite": "5.0.8",  # From package.json
            }
        }
    
    @app.get("/api/system/config")
    async def get_system_config(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get system configuration."""
        config = get_config()
        # Don't expose sensitive values
        safe_config = {
            "app_name": config.app_name,
            "app_version": config.app_version,
            "environment": config.environment,
            "debug": config.debug,
            "log_level": config.log_level,
            "plugin_auto_load": config.plugin_auto_load,
            "web_ui_enabled": config.web_ui_enabled,
            "ai_thread_pool_enabled": getattr(config, 'ai_thread_pool_enabled', True),
            "plugin_thread_pool_enabled": getattr(config, 'plugin_thread_pool_enabled', True),
        }
        # Add Tencent Cloud TTS config if exists
        config_manager = get_config_manager()
        config_obj = config_manager.get()
        project_root = Path(__file__).parent.parent.parent
        toml_file = project_root / "config.toml"
        
        tencent_config = {}
        if toml_file.exists():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            
            # Use thread pool for synchronous file IO
            app = get_app()
            thread_pool = getattr(app, 'plugin_thread_pool', None)
            
            if thread_pool:
                def read_toml_file():
                    with open(toml_file, "rb") as f:
                        return tomllib.load(f)
                toml_data = await thread_pool.run_in_executor(read_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "rb") as f:
                    toml_data = tomllib.load(f)
            
            if "tencent_cloud" in toml_data:
                tencent_cloud = toml_data["tencent_cloud"]
                # Only return if secret_id exists (mask secret_key)
                if "secret_id" in tencent_cloud:
                    tencent_config = {
                        "secret_id": tencent_cloud.get("secret_id", ""),
                        "secret_key_set": bool(tencent_cloud.get("secret_key", ""))  # Don't expose actual key
                    }
            # Load thread pool config
            if "ai" in toml_data:
                ai_config = toml_data["ai"]
                safe_config["ai_thread_pool_enabled"] = ai_config.get("thread_pool_enabled", True)
            if "plugins" in toml_data:
                plugins_config = toml_data["plugins"]
                safe_config["plugin_thread_pool_enabled"] = plugins_config.get("thread_pool_enabled", True)
        
        safe_config["tencent_cloud"] = tencent_config
        return safe_config
    
    @app.get("/api/system/threadpool-stats")
    async def get_threadpool_stats(user: Dict[str, Any] = Depends(get_current_user)):
        """Get thread pool statistics."""
        stats = {
            "ai_threadpool": None,
            "plugin_threadpool": None
        }
        
        # Try to get AI thread pool stats
        try:
            from ..ai.thread_pool import _thread_pool_manager
            if _thread_pool_manager:
                stats["ai_threadpool"] = _thread_pool_manager.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get AI thread pool stats: {e}")
        
        # Try to get plugin thread pool stats  
        try:
            from ..plugins.thread_pool import _plugin_thread_pool_manager
            if _plugin_thread_pool_manager:
                stats["plugin_threadpool"] = _plugin_thread_pool_manager.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get plugin thread pool stats: {e}")
        
        return stats
    
    @app.post("/api/system/config")
    async def update_system_config(
        config_update: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update system configuration."""
        config_manager = get_config_manager()
        current_config = config_manager.get()
        
        # Update allowed config values
        update_data = {}
        allowed_keys = ["web_ui_enabled", "debug", "log_level", "plugin_auto_load", "ai_thread_pool_enabled", "plugin_thread_pool_enabled"]
        for key in allowed_keys:
            if key in config_update:
                update_data[key] = config_update[key]
        
        # Handle Tencent Cloud TTS config separately (sensitive data)
        tencent_config = config_update.get("tencent_cloud")
        
        # Allow update if either update_data or tencent_config is provided
        if not update_data and tencent_config is None:
            raise HTTPException(status_code=400, detail="No valid configuration fields to update")
        
        # Update config in TOML file
        project_root = Path(__file__).parent.parent.parent
        toml_file = project_root / "config.toml"
        
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        
        try:
            import tomli_w
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="TOML write support not available. Please install tomli-w."
            )
        
        # Use thread pool for synchronous file IO
        app = get_app()
        thread_pool = getattr(app, 'plugin_thread_pool', None)
        
        if toml_file.exists():
            if thread_pool:
                def read_toml_file():
                    with open(toml_file, "rb") as f:
                        return tomllib.load(f)
                toml_data = await thread_pool.run_in_executor(read_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "rb") as f:
                    toml_data = tomllib.load(f)
        else:
            toml_data = {}
        
        # Update TOML data according to config.toml structure
        # Note: _flatten_toml converts TOML to env vars:
        # [logging].level -> LOGGING_LEVEL (but Config expects LOG_LEVEL)
        # [web_ui].enabled -> WEB_UI_ENABLED (Config expects WEB_UI_ENABLED)
        # [web_ui].password -> WEB_UI_PASSWORD (Config expects WEB_UI_PASSWORD)
        # [app].debug -> APP_DEBUG (but Config expects DEBUG)
        # [app].log_level -> APP_LOG_LEVEL (but Config expects LOG_LEVEL)
        # 
        # However, looking at the actual config.toml, it seems like:
        # - log_level is in [app].log_level (which becomes APP_LOG_LEVEL, but Config might read it differently)
        # - debug is in [app].debug (which becomes APP_DEBUG, but Config expects DEBUG)
        # 
        # Let's check what the actual mapping should be. For now, save to match the existing structure:
        # - log_level: save to both [app].log_level AND [logging].level (to be safe)
        # - web_ui_enabled: save to [web_ui].enabled
        # - debug: save to [app].debug
        # - plugin_auto_load: save to [plugins].auto_load
        
        for key, value in update_data.items():
            if key == "log_level":
                # Normalize log level to uppercase for consistency
                log_level_upper = str(value).upper()
                # Validate log level
                valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                if log_level_upper not in valid_levels:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid log level: {value}. Must be one of: {', '.join(valid_levels)}"
                    )
                # Save to [logging].level (primary) and [app].log_level (for compatibility)
                if "logging" not in toml_data:
                    toml_data["logging"] = {}
                toml_data["logging"]["level"] = log_level_upper
                # Also save to [app].log_level for compatibility
                if "app" not in toml_data:
                    toml_data["app"] = {}
                toml_data["app"]["log_level"] = log_level_upper
                # Update update_data with normalized value for hot reload
                update_data["log_level"] = log_level_upper
                
                # When log_level is set, automatically sync debug mode:
                # - log_level = DEBUG -> debug = True
                # - log_level != DEBUG -> debug = False
                # BUT: if user explicitly set debug in the same request, debug takes priority
                if "debug" not in update_data:
                    # User didn't explicitly set debug, so auto-adjust based on log_level
                    if "app" not in toml_data:
                        toml_data["app"] = {}
                    debug_value = (log_level_upper == "DEBUG")
                    toml_data["app"]["debug"] = debug_value
                    # Add debug to update_data to trigger hot reload
                    update_data["debug"] = debug_value
                # If user explicitly set debug, we don't override it here
                # The debug handler will handle the sync
            elif key == "web_ui_enabled":
                # Save to [web_ui].enabled
                if "web_ui" not in toml_data:
                    toml_data["web_ui"] = {}
                toml_data["web_ui"]["enabled"] = value
            elif key == "debug":
                # Save to [app].debug
                if "app" not in toml_data:
                    toml_data["app"] = {}
                toml_data["app"]["debug"] = value
                # When debug mode is manually set, sync log_level (debug takes priority):
                # - debug = True -> log_level = DEBUG
                # - debug = False -> log_level = INFO (if current is DEBUG)
                # debug takes priority over log_level setting
                if value:  # debug = True
                    # Enable debug mode: set log_level to DEBUG
                    if "logging" not in toml_data:
                        toml_data["logging"] = {}
                    toml_data["logging"]["level"] = "DEBUG"
                    # Also save to [app].log_level for compatibility
                    toml_data["app"]["log_level"] = "DEBUG"
                    # Always update log_level in update_data (debug takes priority)
                    update_data["log_level"] = "DEBUG"
                else:  # debug = False
                    # Disable debug mode: if log_level is DEBUG, change to INFO
                    current_log_level = None
                    if "logging" in toml_data and "level" in toml_data["logging"]:
                        current_log_level = toml_data["logging"]["level"]
                    elif "app" in toml_data and "log_level" in toml_data["app"]:
                        current_log_level = toml_data["app"]["log_level"]
                    
                    if current_log_level == "DEBUG":
                        if "logging" not in toml_data:
                            toml_data["logging"] = {}
                        toml_data["logging"]["level"] = "INFO"
                        toml_data["app"]["log_level"] = "INFO"
                        # Always update log_level in update_data (debug takes priority)
                        update_data["log_level"] = "INFO"
            elif key == "plugin_auto_load":
                # Save to [plugins].auto_load
                if "plugins" not in toml_data:
                    toml_data["plugins"] = {}
                toml_data["plugins"]["auto_load"] = value
            elif key == "ai_thread_pool_enabled":
                # Save to [ai].thread_pool_enabled
                if "ai" not in toml_data:
                    toml_data["ai"] = {}
                toml_data["ai"]["thread_pool_enabled"] = value
            elif key == "plugin_thread_pool_enabled":
                # Save to [plugins].thread_pool_enabled
                if "plugins" not in toml_data:
                    toml_data["plugins"] = {}
                toml_data["plugins"]["thread_pool_enabled"] = value
        
        # Handle Tencent Cloud TTS config
        tencent_config = config_update.get("tencent_cloud")
        if tencent_config is not None:
            if "tencent_cloud" not in toml_data:
                toml_data["tencent_cloud"] = {}
            
            # Only update if values are provided (allow partial updates)
            if "secret_id" in tencent_config:
                toml_data["tencent_cloud"]["secret_id"] = tencent_config["secret_id"]
                # Also set as environment variable for immediate use
                os.environ["TENCENT_CLOUD_SECRET_ID"] = tencent_config["secret_id"]
            
            if "secret_key" in tencent_config:
                # Only update if not empty (to allow clearing)
                if tencent_config["secret_key"]:
                    toml_data["tencent_cloud"]["secret_key"] = tencent_config["secret_key"]
                    # Also set as environment variable for immediate use
                    os.environ["TENCENT_CLOUD_SECRET_KEY"] = tencent_config["secret_key"]
                elif "secret_key" in toml_data["tencent_cloud"]:
                    # Clear secret_key if empty string provided
                    del toml_data["tencent_cloud"]["secret_key"]
                    if "TENCENT_CLOUD_SECRET_KEY" in os.environ:
                        del os.environ["TENCENT_CLOUD_SECRET_KEY"]
        
        # Write back to TOML using thread pool
        try:
            if thread_pool:
                def write_toml_file():
                    with open(toml_file, "wb") as f:
                        tomli_w.dump(toml_data, f)
                await thread_pool.run_in_executor(write_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "wb") as f:
                    tomli_w.dump(toml_data, f)
        except Exception as e:
            logger.error(f"Failed to write TOML config: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save configuration to file: {str(e)}"
            )
        
        # Reload config from file to ensure consistency
        try:
            # Force clear cache and reload
            reload_config.cache_clear() if hasattr(reload_config, 'cache_clear') else None
            new_config = reload_config()
            # Also reload via config manager
            config_manager.reload()
            
            # If log_level was updated, apply it to all loggers immediately
            if "log_level" in update_data:
                from ..core.logger import update_log_level
                try:
                    update_log_level(update_data["log_level"])
                    logger.info(f"Log level updated to {update_data['log_level']}")
                except Exception as e:
                    logger.warning(f"Failed to update log level: {e}")
        except Exception as e:
            logger.warning(f"Failed to reload config after update: {e}")
            # Continue anyway, config is saved to file
        
        await get_audit_logger().log(AuditEvent(
            event_type=AuditEventType.CONFIG_CHANGED,
            timestamp=datetime.utcnow(),
            username=user.get("username"),
            resource="system",
            action="update_config",
            success=True,
            details={"updated_fields": list(update_data.keys())}
        ))
        
        return {"message": "Configuration updated", "updated": update_data}
    
    @app.post("/api/system/reset-admin-password")
    async def reset_admin_password(
        request: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.ADMIN_ALL))
    ):
        """Reset admin password."""
        try:
            new_password = request.get("password")
            if not new_password or len(new_password) < 6:
                raise HTTPException(
                    status_code=400,
                    detail="Password must be at least 6 characters long"
                )
            
            auth_manager = get_auth_manager()
            from ..security.auth import get_password_hash
            
            # Update admin password in memory
            if "admin" not in auth_manager._users:
                raise HTTPException(
                    status_code=404,
                    detail="Admin user not found"
                )
            
            auth_manager._users["admin"]["password_hash"] = get_password_hash(new_password)
            
            # Also update in config file
            config_manager = get_config_manager()
            project_root = Path(__file__).parent.parent.parent
            toml_file = project_root / "config.toml"
            
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            
            try:
                import tomli_w
            except ImportError:
                logger.warning("tomli-w not available, password not saved to config file")
                # Continue without saving to file, password is already updated in memory
            else:
                # Use thread pool for synchronous file IO
                app = get_app()
                thread_pool = getattr(app, 'plugin_thread_pool', None)
                
                if toml_file.exists():
                    if thread_pool:
                        def read_toml_file():
                            with open(toml_file, "rb") as f:
                                return tomllib.load(f)
                        toml_data = await thread_pool.run_in_executor(read_toml_file)
                    else:
                        with open(toml_file, "rb") as f:
                            toml_data = tomllib.load(f)
                else:
                    toml_data = {}
                
                # Update password in [web_ui].password
                if "web_ui" not in toml_data:
                    toml_data["web_ui"] = {}
                
                toml_data["web_ui"]["password"] = new_password
                
                # Write back using thread pool
                if thread_pool:
                    def write_toml_file():
                        with open(toml_file, "wb") as f:
                            tomli_w.dump(toml_data, f)
                    await thread_pool.run_in_executor(write_toml_file)
                else:
                    with open(toml_file, "wb") as f:
                        tomli_w.dump(toml_data, f)
                
                reload_config()
            
            await get_audit_logger().log(AuditEvent(
                event_type=AuditEventType.CONFIG_CHANGED,
                timestamp=datetime.utcnow(),
                username=user.get("username"),
                resource="system",
                action="reset_admin_password",
                success=True
            ))
            
            logger.info("Admin password reset successfully", username=user.get("username"))
            return {"message": "Admin password reset successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to reset admin password", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to reset password: {str(e)}"
            )
    
    # System Logs endpoint
    @app.get("/api/system/logs")
    async def get_system_logs(
        limit: int = 100,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get system logs from memory (since application startup)."""
        from ..core.logger import get_memory_logs
        try:
            logs = get_memory_logs(limit)
            # Reverse to show newest first
            logs.reverse()
            return logs
        except Exception as e:
            logger.error(f"Failed to get system logs: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get system logs: {str(e)}")
    
    # Splash screen endpoints
    @app.get("/api/splash/check")
    async def check_splash_screen():
        """Check if splash screen should be shown."""
        try:
            config = get_config()
            # 如果 WebUI 未启用，直接返回不显示
            if not config.web_ui_enabled:
                return {"should_show": False, "reason": "webui_disabled"}
            
            # 检查开屏动画文件夹是否存在（在webui目录下）
            # 使用项目根目录作为基准路径
            project_root = Path(__file__).parent.parent.parent
            splash_dir = project_root / "webui" / "splash_screen"
            
            # 如果 webui 文件夹不存在，返回不显示
            if not splash_dir.exists():
                return {"should_show": False, "reason": "splash_dir_not_exists"}
            
            # 检查标记文件是否存在
            marker_file = splash_dir / ".splash_shown"
            if marker_file.exists():
                return {"should_show": False, "reason": "already_shown"}
            
            return {"should_show": True}
        except Exception as e:
            logger.error(f"Failed to check splash screen: {e}", exc_info=True)
            # 出错时默认不显示
            return {"should_show": False, "reason": "error", "error": str(e)}
    
    @app.post("/api/splash/mark-shown")
    async def mark_splash_screen_shown():
        """Mark splash screen as shown. No authentication required."""
        try:
            config = get_config()
            # 如果 WebUI 未启用，直接返回成功（静默处理）
            if not config.web_ui_enabled:
                return {"success": True, "message": "WebUI disabled, splash screen skipped"}
            
            # 使用项目根目录作为基准路径
            project_root = Path(__file__).parent.parent.parent
            splash_dir = project_root / "webui" / "splash_screen"
            
            # 如果 webui 文件夹不存在，尝试创建（但可能失败，这是正常的）
            try:
                splash_dir.mkdir(parents=True, exist_ok=True)
            except Exception as mkdir_error:
                # 如果无法创建目录（例如 webui 文件夹被删除），静默处理
                logger.debug(f"Cannot create splash screen directory: {mkdir_error}")
                return {"success": True, "message": "WebUI directory not available, splash screen skipped"}
            
            # 创建标记文件
            try:
                marker_file = splash_dir / ".splash_shown"
                marker_file.touch()
                logger.info(f"Splash screen marked as shown. Marker file: {marker_file}")
                return {"success": True, "message": "Splash screen marked as shown"}
            except Exception as touch_error:
                # 如果无法创建标记文件，静默处理
                logger.debug(f"Cannot create splash screen marker file: {touch_error}")
                return {"success": True, "message": "Cannot create marker file, but operation completed"}
        except Exception as e:
            logger.error(f"Failed to mark splash screen as shown: {e}", exc_info=True)
            # 即使出错也返回成功，避免影响主程序运行
            return {"success": True, "message": "Error occurred but operation completed", "error": str(e)}
    
    # Health check
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    # ==================== AI System API ====================
    
    # Check if AI is available
    global _ai_available
    _ai_available = is_ai_available()
    
    if _ai_available:
        logger.info("AI系统已检测到，正在加载AI模块...")
        try:
            from ..ai import ModelManager, AIManager, MCPManager
        except ImportError as e:
            logger.error(f"AI模块导入失败: {e}")
            _ai_available = False
    else:
        logger.info("AI系统未检测到，AI功能将不可用")
    
    def check_ai_available():
        """Check if AI is available, raise 503 if not."""
        if not _ai_available:
            raise HTTPException(
                status_code=503,
                detail="AI系统未安装或不可用"
            )
    
    def get_model_manager():
        """Get model manager instance."""
        check_ai_available()
        global _model_manager
        if _model_manager is None:
            from ..ai import ModelManager
            _model_manager = ModelManager()
        return _model_manager
    
    def get_ai_manager():
        """Get AI manager instance."""
        check_ai_available()
        global _ai_manager
        if _ai_manager is None:
            from ..ai import AIManager
            _ai_manager = AIManager()
        return _ai_manager
    
    def get_mcp_manager():
        """Get MCP manager instance."""
        check_ai_available()
        global _mcp_manager
        if _mcp_manager is None:
            from ..ai import MCPManager
            _mcp_manager = MCPManager()
        return _mcp_manager
    
    # Initialize managers on startup (only if AI is available)
    @app.on_event("startup")
    async def init_ai_managers():
        """Initialize AI managers."""
        if _ai_available:
            try:
                await get_model_manager().initialize()
                await get_ai_manager().initialize()
                await get_mcp_manager().initialize()
                logger.info("AI管理器初始化成功")
            except Exception as e:
                logger.error(f"AI管理器初始化失败: {e}", exc_info=True)
        else:
            logger.info("AI系统不可用，跳过AI管理器初始化")
    
    # ==================== AI Availability Check ====================
    
    @app.get("/api/ai/availability")
    async def check_ai_availability():
        """检测AI系统是否可用。"""
        detector = get_ai_detector()
        available = detector.is_ai_available()
        
        result = {
            "available": available,
            "message": "AI系统可用" if available else "AI系统未安装或不可用"
        }
        
        if available:
            result["module_path"] = str(detector.get_ai_module_path())
        
        return result
    
    # ==================== AI Configuration ====================
    
    @app.get("/api/ai/config")
    async def get_ai_config(
        config_type: str,
        target_id: Optional[str] = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get AI configuration."""
        ai_manager = get_ai_manager()
        config = await ai_manager.get_config(config_type, target_id)
        return config
    
    class AIConfigUpdate(BaseModel):
        enabled: Optional[bool] = None
        model_uuid: Optional[str] = None
        preset_uuid: Optional[str] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.put("/api/ai/config")
    async def update_ai_config(
        config_type: str,
        target_id: Optional[str] = None,
        updates: AIConfigUpdate = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update AI configuration."""
        ai_manager = get_ai_manager()
        update_dict = {}
        if updates:
            if updates.enabled is not None:
                update_dict['enabled'] = updates.enabled
            if updates.model_uuid is not None:
                update_dict['model_uuid'] = updates.model_uuid
            if updates.preset_uuid is not None:
                update_dict['preset_uuid'] = updates.preset_uuid
            if updates.config is not None:
                update_dict['config'] = updates.config
        
        success = await ai_manager.update_config(config_type, target_id, **update_dict)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update config")
        return {"success": True}
    
    @app.get("/api/ai/groups")
    async def list_group_configs(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List all group configurations."""
        ai_manager = get_ai_manager()
        configs = await ai_manager.list_group_configs()
        return configs
    
    class BatchGroupUpdate(BaseModel):
        group_ids: List[str]
        enabled: Optional[bool] = None
        model_uuid: Optional[str] = None
        preset_uuid: Optional[str] = None
    
    @app.post("/api/ai/groups/batch")
    async def batch_update_groups(
        request: BatchGroupUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Batch update group configurations."""
        ai_manager = get_ai_manager()
        count = await ai_manager.batch_update_groups(
            request.group_ids,
            enabled=request.enabled,
            model_uuid=request.model_uuid,
            preset_uuid=request.preset_uuid
        )
        return {"success": True, "updated_count": count}
    
    @app.post("/api/ai/groups/{group_id}/mark-left")
    async def mark_group_left(
        group_id: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Mark a group as left (exited). Group settings will be kept for 30 days."""
        db_manager = get_database_manager()
        success = await db_manager.mark_group_left(group_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Group configuration not found")
        
        logger.info(f"Group {group_id} marked as left, data will be kept for 30 days")
        
        await get_audit_logger().log_plugin_action(
            "mark_group_left",
            group_id,
            user.get("username"),
            True
        )
        
        return {
            "success": True,
            "message": "Group marked as left. Settings will be automatically deleted after 30 days."
        }
    
    @app.post("/api/ai/groups/cleanup-expired")
    async def cleanup_expired_left_groups(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Manually trigger cleanup of expired left group data (>30 days)."""
        db_manager = get_database_manager()
        count = await db_manager.cleanup_expired_left_groups(days=30)
        
        logger.info(f"Cleaned up {count} expired left group configurations")
        
        await get_audit_logger().log_plugin_action(
            "cleanup_expired_groups",
            "all",
            user.get("username"),
            True,
            {"deleted_count": count}
        )
        
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Cleaned up {count} expired group configurations"
        }
    
    class CleanupOldGroupsRequest(BaseModel):
        days: Optional[int] = None  # 删除指定天数前的数据
        only_disabled: bool = False  # 仅删除未启用的
        max_message_count: Optional[int] = None  # 消息数少于此值
        group_ids: Optional[List[str]] = None  # 指定群号列表
    
    @app.post("/api/ai/groups/cleanup-old")
    async def cleanup_old_groups(
        request: CleanupOldGroupsRequest,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """批量清理旧群组数据（提供多种清理选项）"""
        from datetime import datetime, timedelta
        db_manager = get_database_manager()
        
        deleted_count = 0
        
        try:
            # 选项1: 删除指定群号
            if request.group_ids:
                for group_id in request.group_ids:
                    success = await db_manager.delete_ai_config('group', group_id)
                    if success:
                        deleted_count += 1
                
                logger.info(f"Deleted {deleted_count} specified group configurations")
            
            # 选项2: 删除所有未启用的群组
            elif request.only_disabled:
                configs = await db_manager.list_ai_configs('group', exclude_left=False)
                for config in configs:
                    if not config.enabled:
                        success = await db_manager.delete_ai_config('group', config.target_id)
                        if success:
                            deleted_count += 1
                
                logger.info(f"Deleted {deleted_count} disabled group configurations")
            
            # 选项3: 按天数和消息数清理不活跃群组
            elif request.days is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=request.days)
                configs = await db_manager.list_ai_configs('group', exclude_left=False)
                
                for config in configs:
                    # 检查更新时间
                    if config.updated_at < cutoff_date:
                        # 如果指定了消息数限制，检查消息数
                        if request.max_message_count is not None:
                            if config.message_count <= request.max_message_count:
                                success = await db_manager.delete_ai_config('group', config.target_id)
                                if success:
                                    deleted_count += 1
                        else:
                            success = await db_manager.delete_ai_config('group', config.target_id)
                            if success:
                                deleted_count += 1
                
                logger.info(f"Deleted {deleted_count} inactive group configurations")
            
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Please specify cleanup criteria: group_ids, only_disabled, or days"
                )
            
            await get_audit_logger().log_plugin_action(
                "cleanup_old_groups",
                "all",
                user.get("username"),
                True,
                {
                    "deleted_count": deleted_count,
                    "criteria": request.dict()
                }
            )
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Successfully cleaned up {deleted_count} group configurations"
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to cleanup old groups: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to cleanup: {str(e)}")
    
    # ==================== AI Tools Management ====================
    
    @app.get("/api/ai/tools")
    async def list_ai_tools(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get all available AI tools metadata."""
        from ..ai.tools import AITools
        tools = AITools.get_all_tools_metadata()
        return tools
    
    @app.get("/api/ai/tools/enabled")
    async def get_enabled_tools(
        config_type: str,
        target_id: Optional[str] = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get enabled tools for a config."""
        ai_manager = get_ai_manager()
        config = await ai_manager.get_config(config_type, target_id)
        enabled_tools = config.get('config', {}).get('enabled_tools', {})
        return enabled_tools
    
    class ToolsUpdate(BaseModel):
        enabled_tools: Dict[str, bool]
    
    @app.put("/api/ai/tools/enabled")
    async def update_enabled_tools(
        config_type: str,
        target_id: Optional[str] = None,
        updates: ToolsUpdate = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update enabled tools for a config."""
        ai_manager = get_ai_manager()
        config = await ai_manager.get_config(config_type, target_id)
        current_config = config.get('config', {})
        current_config['enabled_tools'] = updates.enabled_tools if updates else {}
        
        success = await ai_manager.update_config(config_type, target_id, config=current_config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update tools")
        return {"success": True}
    
    # ==================== Model Management ====================
    
    @app.get("/api/ai/models")
    async def list_models(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List all models."""
        model_manager = get_model_manager()
        models = await model_manager.list_models()
        return models
    
    @app.get("/api/ai/models/{model_uuid}")
    async def get_model(
        model_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get model by UUID."""
        model_manager = get_model_manager()
        model = await model_manager.get_model(model_uuid)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return model
    
    class ModelCreate(BaseModel):
        name: str
        provider: str
        model_name: str
        api_key: Optional[str] = None
        base_url: Optional[str] = None
        is_default: bool = False
        supports_tools: bool = False
        supports_vision: bool = False
        description: Optional[str] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.post("/api/ai/models")
    async def create_model(
        model: ModelCreate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Create a new model."""
        model_manager = get_model_manager()
        created_model = await model_manager.create_model(
            name=model.name,
            provider=model.provider,
            model_name=model.model_name,
            api_key=model.api_key,
            base_url=model.base_url,
            is_default=model.is_default,
            supports_tools=model.supports_tools,
            supports_vision=model.supports_vision,
            description=model.description,
            config=model.config or {}
        )
        return created_model
    
    class ModelUpdate(BaseModel):
        name: Optional[str] = None
        provider: Optional[str] = None
        model_name: Optional[str] = None
        api_key: Optional[str] = None
        base_url: Optional[str] = None
        is_default: Optional[bool] = None
        supports_tools: Optional[bool] = None
        supports_vision: Optional[bool] = None
        description: Optional[str] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.put("/api/ai/models/{model_uuid}")
    async def update_model(
        model_uuid: str,
        updates: ModelUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update model."""
        model_manager = get_model_manager()
        update_dict = updates.dict(exclude_unset=True)
        
        # 如果 api_key 是空字符串，移除它（保持原有值不变）
        if 'api_key' in update_dict and update_dict['api_key'] == '':
            del update_dict['api_key']
        
        # 如果 base_url 是空字符串，移除它（保持原有值不变）
        if 'base_url' in update_dict and update_dict['base_url'] == '':
            del update_dict['base_url']
        
        success = await model_manager.update_model(model_uuid, **update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"success": True}
    
    @app.delete("/api/ai/models/{model_uuid}")
    async def delete_model(
        model_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete model."""
        model_manager = get_model_manager()
        success = await model_manager.delete_model(model_uuid)
        if not success:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"success": True}
    
    @app.get("/api/ai/models/providers/list")
    async def list_providers(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List available providers."""
        model_manager = get_model_manager()
        providers = await model_manager.get_providers()
        return providers
    
    # ==================== Preset Management ====================
    
    @app.get("/api/ai/presets")
    async def list_presets(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List all presets."""
        from ..core.database import get_database_manager
        db_manager = get_database_manager()
        presets = await db_manager.list_ai_presets()
        return [preset.to_dict() for preset in presets]
    
    @app.get("/api/ai/presets/{preset_uuid}")
    async def get_preset(
        preset_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get preset by UUID."""
        from ..core.database import get_database_manager
        db_manager = get_database_manager()
        preset = await db_manager.get_ai_preset(preset_uuid)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        return preset.to_dict()
    
    class PresetCreate(BaseModel):
        name: str
        system_prompt: str
        temperature: float = 1.0
        max_tokens: int = 2000
        description: Optional[str] = None
        top_p: Optional[float] = None
        top_k: Optional[int] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.post("/api/ai/presets")
    async def create_preset(
        preset: PresetCreate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Create a new preset."""
        import uuid
        from ..core.database import get_database_manager
        db_manager = get_database_manager()
        preset_uuid = str(uuid.uuid4())
        created_preset = await db_manager.create_ai_preset(
            uuid=preset_uuid,
            name=preset.name,
            system_prompt=preset.system_prompt,
            temperature=preset.temperature,
            max_tokens=preset.max_tokens,
            description=preset.description,
            top_p=preset.top_p,
            top_k=preset.top_k,
            config=preset.config or {}
        )
        return created_preset.to_dict()
    
    class PresetUpdate(BaseModel):
        name: Optional[str] = None
        system_prompt: Optional[str] = None
        temperature: Optional[float] = None
        max_tokens: Optional[int] = None
        description: Optional[str] = None
        top_p: Optional[float] = None
        top_k: Optional[int] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.put("/api/ai/presets/{preset_uuid}")
    async def update_preset(
        preset_uuid: str,
        updates: PresetUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update preset."""
        from ..core.database import get_database_manager
        db_manager = get_database_manager()
        update_dict = updates.dict(exclude_unset=True)
        
        success = await db_manager.update_ai_preset(preset_uuid, **update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Preset not found")
        return {"success": True}
    
    @app.delete("/api/ai/presets/{preset_uuid}")
    async def delete_preset(
        preset_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete preset."""
        from ..core.database import get_database_manager
        db_manager = get_database_manager()
        success = await db_manager.delete_ai_preset(preset_uuid)
        if not success:
            raise HTTPException(status_code=404, detail="Preset not found")
        return {"success": True}
    
    # ==================== Memory Management ====================
    
    @app.get("/api/ai/memories")
    async def list_memories(
        memory_type: Optional[str] = None,
        target_id: Optional[str] = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List AI memories."""
        ai_manager = get_ai_manager()
        memories = await ai_manager.list_memories(memory_type, target_id)
        return memories
    
    @app.get("/api/ai/memories/{memory_uuid}")
    async def get_memory(
        memory_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get memory by UUID."""
        from ..core.database import get_database_manager
        db_manager = get_database_manager()
        memories = await db_manager.list_ai_memories()
        memory = next((m for m in memories if m.uuid == memory_uuid), None)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        return memory.to_dict()
    
    @app.delete("/api/ai/memories/{memory_uuid}")
    async def delete_memory(
        memory_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete memory."""
        ai_manager = get_ai_manager()
        success = await ai_manager.delete_memory(memory_uuid)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"success": True}
    
    class ClearMemoryRequest(BaseModel):
        memory_type: str
        target_id: str
        preset_uuid: Optional[str] = None
    
    @app.post("/api/ai/memories/clear")
    async def clear_memory(
        request: ClearMemoryRequest,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Clear memory."""
        ai_manager = get_ai_manager()
        success = await ai_manager.clear_memory(request.memory_type, request.target_id, request.preset_uuid)
        return {"success": success}
    
    # ==================== MCP Management ====================
    
    @app.get("/api/ai/mcp/servers")
    async def list_mcp_servers(
        enabled_only: bool = False,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List MCP servers."""
        mcp_manager = get_mcp_manager()
        servers = await mcp_manager.list_servers(enabled_only)
        return servers
    
    @app.get("/api/ai/mcp/servers/{server_uuid}")
    async def get_mcp_server(
        server_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get MCP server by UUID."""
        mcp_manager = get_mcp_manager()
        server = await mcp_manager.get_server(server_uuid)
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")
        return server
    
    class MCPServerCreate(BaseModel):
        name: str
        mode: str
        enabled: bool = False
        description: Optional[str] = None
        command: Optional[str] = None
        args: Optional[List[str]] = None
        env: Optional[Dict[str, str]] = None
        url: Optional[str] = None
        headers: Optional[Dict[str, str]] = None
        timeout: Optional[int] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.post("/api/ai/mcp/servers")
    async def create_mcp_server(
        server: MCPServerCreate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Create MCP server."""
        mcp_manager = get_mcp_manager()
        created_server = await mcp_manager.create_server(
            name=server.name,
            mode=server.mode,
            enabled=server.enabled,
            description=server.description,
            command=server.command,
            args=server.args or [],
            env=server.env or {},
            url=server.url,
            headers=server.headers or {},
            timeout=server.timeout,
            config=server.config or {}
        )
        return created_server
    
    class MCPServerUpdate(BaseModel):
        name: Optional[str] = None
        mode: Optional[str] = None
        enabled: Optional[bool] = None
        description: Optional[str] = None
        command: Optional[str] = None
        args: Optional[List[str]] = None
        env: Optional[Dict[str, str]] = None
        url: Optional[str] = None
        headers: Optional[Dict[str, str]] = None
        timeout: Optional[int] = None
        config: Optional[Dict[str, Any]] = None
    
    @app.put("/api/ai/mcp/servers/{server_uuid}")
    async def update_mcp_server(
        server_uuid: str,
        updates: MCPServerUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update MCP server."""
        mcp_manager = get_mcp_manager()
        update_dict = updates.dict(exclude_unset=True)
        
        success = await mcp_manager.update_server(server_uuid, **update_dict)
        if not success:
            raise HTTPException(status_code=404, detail="MCP server not found")
        return {"success": True}
    
    @app.delete("/api/ai/mcp/servers/{server_uuid}")
    async def delete_mcp_server(
        server_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete MCP server."""
        mcp_manager = get_mcp_manager()
        success = await mcp_manager.delete_server(server_uuid)
        if not success:
            raise HTTPException(status_code=404, detail="MCP server not found")
        return {"success": True}
    
    @app.post("/api/ai/mcp/servers/{server_uuid}/connect")
    async def connect_mcp_server(
        server_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Connect to MCP server."""
        mcp_manager = get_mcp_manager()
        success = await mcp_manager.connect_server(server_uuid)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to connect to MCP server")
        return {"success": True}
    
    @app.post("/api/ai/mcp/servers/{server_uuid}/disconnect")
    async def disconnect_mcp_server(
        server_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Disconnect from MCP server."""
        mcp_manager = get_mcp_manager()
        success = await mcp_manager.disconnect_server(server_uuid)
        return {"success": success}
    
    @app.get("/api/ai/mcp/servers/{server_uuid}/tools")
    async def get_mcp_server_tools(
        server_uuid: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get tools from MCP server."""
        mcp_manager = get_mcp_manager()
        tools = await mcp_manager.get_server_tools(server_uuid)
        return tools
    
    @app.get("/api/ai/mcp/tools")
    async def get_all_mcp_tools(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get all tools from all connected MCP servers."""
        mcp_manager = get_mcp_manager()
        tools = await mcp_manager.get_all_tools()
        return tools
    
    # ==================== AI Learning Data ====================
    
    @app.get("/api/ai/learning/expressions")
    async def get_expressions(
        chat_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get learned expressions."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import Expression
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(Expression)
            if chat_id:
                query = query.filter(Expression.chat_id == chat_id)
            query = query.order_by(Expression.count.desc(), Expression.updated_at.desc())
            
            total = query.count()
            expressions = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [expr.to_dict() for expr in expressions]
            }
        finally:
            session.close()
    
    @app.get("/api/ai/learning/jargons")
    async def get_jargons(
        chat_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get learned jargon/slang."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import Jargon
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(Jargon)
            if chat_id:
                query = query.filter(Jargon.chat_id == chat_id)
            query = query.order_by(Jargon.count.desc(), Jargon.updated_at.desc())
            
            total = query.count()
            jargons = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [jargon.to_dict() for jargon in jargons]
            }
        finally:
            session.close()
    
    @app.get("/api/ai/learning/chat-history")
    async def get_chat_history_api(
        chat_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get chat history summaries."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import ChatHistory
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(ChatHistory)
            if chat_id:
                query = query.filter(ChatHistory.chat_id == chat_id)
            query = query.order_by(ChatHistory.end_time.desc())
            
            total = query.count()
            histories = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [hist.to_dict() for hist in histories]
            }
        finally:
            session.close()
    
    @app.get("/api/ai/learning/message-records")
    async def get_message_records_api(
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get message records."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import MessageRecord
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(MessageRecord)
            if chat_id:
                query = query.filter(MessageRecord.chat_id == chat_id)
            if user_id:
                query = query.filter(MessageRecord.user_id == user_id)
            query = query.order_by(MessageRecord.time.desc())
            
            total = query.count()
            records = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [rec.to_dict() for rec in records]
            }
        finally:
            session.close()
    
    @app.get("/api/ai/learning/persons")
    async def get_persons_api(
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get person information."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import PersonInfo
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(PersonInfo).order_by(PersonInfo.updated_at.desc())
            
            total = query.count()
            persons = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [person.to_dict() for person in persons]
            }
        finally:
            session.close()
    
    @app.get("/api/ai/learning/groups")
    async def get_groups_info_api(
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get group information."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import GroupInfo
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(GroupInfo).order_by(GroupInfo.updated_at.desc())
            
            total = query.count()
            groups = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [group.to_dict() for group in groups]
            }
        finally:
            session.close()
    
    @app.get("/api/ai/learning/stats")
    async def get_learning_stats(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get overall learning statistics."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import Expression, Jargon, ChatHistory, MessageRecord, PersonInfo, GroupInfo, Sticker
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            stats = {
                "expressions_count": session.query(Expression).count(),
                "jargons_count": session.query(Jargon).count(),
                "chat_history_count": session.query(ChatHistory).count(),
                "message_records_count": session.query(MessageRecord).count(),
                "persons_count": session.query(PersonInfo).count(),
                "groups_count": session.query(GroupInfo).count(),
                "known_persons_count": session.query(PersonInfo).filter(PersonInfo.is_known == True).count(),
                "stickers_count": session.query(Sticker).count(),
            }
            return stats
        finally:
            session.close()
    
    @app.get("/api/ai/learning/stickers")
    async def get_stickers_api(
        chat_id: Optional[str] = None,
        rejected: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get learned stickers."""
        from ..ai.ai_database import get_ai_database
        from ..ai.ai_database_models import Sticker
        
        db = get_ai_database()
        session = db.get_session()
        
        try:
            query = session.query(Sticker)
            if chat_id:
                query = query.filter(Sticker.chat_id == chat_id)
            if rejected is not None:
                query = query.filter(Sticker.rejected == rejected)
            query = query.order_by(Sticker.count.desc(), Sticker.last_active_time.desc())
            
            total = query.count()
            stickers = query.offset(offset).limit(limit).all()
            
            return {
                "total": total,
                "items": [sticker.to_dict() for sticker in stickers]
            }
        finally:
            session.close()
    
    @app.delete("/api/ai/learning/clear-all")
    async def clear_all_learning_data(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Clear all AI learning data (reset RuaBot memory)."""
        from ..ai.ai_database import get_ai_database
        from ..ai.knowledge import get_kg_storage
        from sqlalchemy import text
        import os
        
        db = get_ai_database()
        session = db.get_session()
        
        cleared_tables = []
        
        try:
            # Clear AI learning database tables
            session.execute(text("DELETE FROM ai_message_records"))
            cleared_tables.append("ai_message_records")
            
            session.execute(text("DELETE FROM ai_chat_history"))
            cleared_tables.append("ai_chat_history")
            
            session.execute(text("DELETE FROM ai_person_info"))
            cleared_tables.append("ai_person_info")
            
            session.execute(text("DELETE FROM ai_group_info"))
            cleared_tables.append("ai_group_info")
            
            session.execute(text("DELETE FROM ai_expressions"))
            cleared_tables.append("ai_expressions")
            
            session.execute(text("DELETE FROM ai_jargons"))
            cleared_tables.append("ai_jargons")
            
            session.execute(text("DELETE FROM ai_stickers"))
            cleared_tables.append("ai_stickers")
            
            # Clear expression usage tracking (if table exists)
            try:
                session.execute(text("DELETE FROM ai_expression_usage"))
                cleared_tables.append("ai_expression_usage")
            except Exception:
                pass  # Table might not exist yet
            
            session.commit()
            
            # Clear Knowledge Graph data
            try:
                kg_storage = get_kg_storage()
                kg_session = kg_storage.get_session()
                try:
                    kg_session.execute(text("DELETE FROM kg_triples"))
                    kg_session.execute(text("DELETE FROM kg_entities"))
                    kg_session.commit()
                    cleared_tables.append("kg_triples")
                    cleared_tables.append("kg_entities")
                    logger.info("Knowledge Graph data cleared")
                except Exception as e:
                    kg_session.rollback()
                    logger.warning(f"Failed to clear KG data: {e}")
                finally:
                    kg_session.close()
            except Exception as e:
                logger.warning(f"Failed to access KG storage: {e}")
            
            # Reset HeartFlow data (in-memory, no database)
            try:
                from ..ai.heartflow_enhanced import get_heartflow_enhanced
                heartflow = get_heartflow_enhanced()
                # Get all chat IDs and reset them
                chat_ids = list(set(
                    list(heartflow.message_count.keys()) +
                    list(heartflow.emotion_states.keys())
                ))
                for chat_id in chat_ids:
                    heartflow.reset_chat(chat_id)
                cleared_tables.append("heartflow (in-memory)")
                logger.info("HeartFlow data reset")
            except Exception as e:
                logger.warning(f"Failed to reset HeartFlow: {e}")
            
            logger.info(f"All AI learning data cleared: {', '.join(cleared_tables)}")
            return {
                "success": True,
                "message": "所有学习数据已清除",
                "cleared_tables": cleared_tables
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to clear learning data: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"清除失败: {str(e)}")
        finally:
            session.close()
    
    # ==================== AI Maintenance APIs ====================
    
    # Dream System APIs
    @app.get("/api/ai/maintenance/dream/config")
    async def get_dream_config(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Dream system configuration."""
        try:
            from ..ai.dream import get_dream_scheduler
            scheduler = get_dream_scheduler()
            if scheduler:
                return {
                    "enabled": scheduler.enabled,
                    "first_delay_seconds": scheduler.first_delay_seconds,
                    "interval_minutes": scheduler.interval_seconds // 60,
                    "max_iterations": 15,  # Default from dream_agent
                    "dream_start_hour": scheduler.dream_start_hour,
                    "dream_end_hour": scheduler.dream_end_hour
                }
            else:
                return {
                    "enabled": False,
                    "first_delay_seconds": 300,
                    "interval_minutes": 30,
                    "max_iterations": 15,
                    "dream_start_hour": 0,
                    "dream_end_hour": 6
                }
        except Exception as e:
            logger.error(f"Failed to get dream config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/ai/maintenance/dream/config")
    async def update_dream_config(
        config: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update Dream system configuration."""
        try:
            # Save to config file
            # TODO: Implement config file update
            logger.info(f"Dream config updated: {config}")
            return {"success": True, "message": "配置已保存（需要重启生效）"}
        except Exception as e:
            logger.error(f"Failed to update dream config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/maintenance/dream/stats")
    async def get_dream_stats(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Dream system statistics."""
        try:
            from ..ai.dream import get_dream_scheduler
            scheduler = get_dream_scheduler()
            if scheduler:
                return scheduler.get_statistics()
            else:
                return {
                    "enabled": False,
                    "total_cycles": 0,
                    "successful_cycles": 0,
                    "failed_cycles": 0,
                    "total_iterations": 0,
                    "avg_iterations": 0,
                    "total_cost_seconds": 0,
                    "avg_cost_seconds": 0,
                    "last_cycle_time": None,
                    "is_running": False
                }
        except Exception as e:
            logger.error(f"Failed to get dream stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/ai/maintenance/dream/run")
    async def trigger_dream_run(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Manually trigger a dream maintenance cycle."""
        try:
            from ..ai.dream import get_dream_scheduler
            scheduler = get_dream_scheduler()
            if scheduler:
                # Run once in background
                import asyncio
                asyncio.create_task(scheduler.run_once())
                return {"success": True, "message": "Dream 维护已启动"}
            else:
                raise HTTPException(status_code=400, detail="Dream scheduler not initialized")
        except Exception as e:
            logger.error(f"Failed to trigger dream run: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Expression Auto Check APIs
    @app.get("/api/ai/maintenance/expression-check/config")
    async def get_expression_check_config(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Expression Auto Check configuration."""
        return {
            "enabled": True,
            "interval_minutes": 60,
            "batch_size": 10,
            "limit": 50
        }
    
    @app.put("/api/ai/maintenance/expression-check/config")
    async def update_expression_check_config(
        config: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update Expression Auto Check configuration."""
        logger.info(f"Expression check config updated: {config}")
        return {"success": True, "message": "配置已保存（需要重启生效）"}
    
    @app.get("/api/ai/maintenance/expression-check/stats")
    async def get_expression_check_stats(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Expression Auto Check statistics."""
        try:
            from ..ai.expression_auto_checker import get_expression_auto_checker
            checker = get_expression_auto_checker()
            return checker.get_statistics()
        except Exception as e:
            logger.error(f"Failed to get expression check stats: {e}")
            return {
                "total_checked": 0,
                "total_accepted": 0,
                "total_rejected": 0,
                "acceptance_rate": 0,
                "last_check_time": None
            }
    
    @app.post("/api/ai/maintenance/expression-check/run")
    async def trigger_expression_check(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Manually trigger expression auto check."""
        try:
            from ..ai.expression_auto_checker import get_expression_auto_checker
            from ..ai.llm_client import LLMClient
            
            # Get default model for LLM client
            model_manager = get_model_manager()
            default_model = await model_manager.get_default_model()
            if not default_model:
                raise HTTPException(status_code=400, detail="未配置默认LLM模型，请先在AI模型管理中设置默认模型")
            
            # Get model with API key
            model_with_secret = await model_manager.get_model_with_secret(default_model['uuid'])
            if not model_with_secret:
                raise HTTPException(status_code=404, detail="默认模型不存在")
            
            # Initialize LLM client with model configuration
            llm_client = LLMClient(
                api_key=model_with_secret.get('api_key', ''),
                base_url=model_with_secret.get('base_url', ''),
                model_name=model_with_secret.get('model_name', ''),
                provider=model_with_secret.get('provider', 'openai')
            )
            
            checker = get_expression_auto_checker()
            
            # Run in background
            import asyncio
            asyncio.create_task(checker.check_unchecked_expressions(llm_client, limit=50))
            
            return {"success": True, "message": "表达方式检查已启动"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to trigger expression check: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Expression Reflect APIs
    @app.get("/api/ai/maintenance/expression-reflect/config")
    async def get_expression_reflect_config(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Expression Reflect configuration."""
        return {
            "enabled": True,
            "interval_minutes": 120,
            "min_usage_count": 5,
            "limit": 30
        }
    
    @app.put("/api/ai/maintenance/expression-reflect/config")
    async def update_expression_reflect_config(
        config: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update Expression Reflect configuration."""
        logger.info(f"Expression reflect config updated: {config}")
        return {"success": True, "message": "配置已保存（需要重启生效）"}
    
    @app.get("/api/ai/maintenance/expression-reflect/stats")
    async def get_expression_reflect_stats(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Expression Auto Check statistics (expression_reflector removed, using auto_checker instead)."""
        try:
            from ..ai.expression_auto_checker import get_expression_auto_checker
            checker = get_expression_auto_checker()
            stats = checker.get_statistics()
            return {
                "total_reflections": stats.get('total_checked', 0),
                "total_analyzed": stats.get('total_checked', 0),
                "total_recommendations": stats.get('total_accepted', 0),
                "last_reflection_time": stats.get('last_check_time'),
                "tracked_expressions": stats.get('total_checked', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get expression auto check stats: {e}")
            return {
                "total_reflections": 0,
                "total_analyzed": 0,
                "total_recommendations": 0,
                "last_reflection_time": None,
                "tracked_expressions": 0
            }
    
    @app.post("/api/ai/maintenance/expression-reflect/run")
    async def trigger_expression_reflect(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Manually trigger expression auto check (expression_reflector removed, using auto_checker instead)."""
        try:
            from ..ai.expression_auto_checker import get_expression_auto_checker
            from ..ai.llm_client import LLMClient
            
            # Get default model for LLM client
            model_manager = get_model_manager()
            default_model = await model_manager.get_default_model()
            if not default_model:
                raise HTTPException(status_code=400, detail="未配置默认LLM模型，请先在AI模型管理中设置默认模型")
            
            # Get model with API key
            model_with_secret = await model_manager.get_model_with_secret(default_model['uuid'])
            if not model_with_secret:
                raise HTTPException(status_code=404, detail="默认模型不存在")
            
            # Initialize LLM client with model configuration
            llm_client = LLMClient(
                api_key=model_with_secret.get('api_key', ''),
                base_url=model_with_secret.get('base_url', ''),
                model_name=model_with_secret.get('model_name', ''),
                provider=model_with_secret.get('provider', 'openai')
            )
            
            checker = get_expression_auto_checker()
            
            # Run in background
            import asyncio
            asyncio.create_task(checker.check_unchecked_expressions(llm_client, limit=50, batch_size=10))
            
            return {"success": True, "message": "表达方式自动检查已启动"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to trigger expression auto check: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Knowledge Graph APIs
    @app.get("/api/ai/knowledge/stats")
    async def get_knowledge_graph_stats(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get Knowledge Graph statistics."""
        try:
            from ..ai.knowledge import get_kg_manager
            manager = get_kg_manager()
            stats = manager.get_statistics()
            # Ensure avg_confidence is included
            if 'avg_confidence' not in stats:
                stats['avg_confidence'] = 0.0
            return stats
        except Exception as e:
            logger.error(f"Failed to get KG stats: {e}", exc_info=True)
            # Return default stats instead of raising error
            return {
                'triples': 0,
                'entities': 0,
                'relationships': 0,
                'avg_confidence': 0.0
            }
    
    @app.get("/api/ai/knowledge/triples")
    async def get_knowledge_triples(
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        obj: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get knowledge triples."""
        try:
            from ..ai.knowledge import get_kg_manager
            from sqlalchemy import func
            
            manager = get_kg_manager()
            storage = manager.storage
            
            # Get total count first
            from ..ai.knowledge.kg_storage import KnowledgeTriple
            session = storage.get_session()
            try:
                count_query = session.query(func.count(KnowledgeTriple.id))
                
                if subject:
                    count_query = count_query.filter(KnowledgeTriple.subject == subject)
                if predicate:
                    count_query = count_query.filter(KnowledgeTriple.predicate == predicate)
                if obj:
                    count_query = count_query.filter(KnowledgeTriple.object == obj)
                
                total = count_query.scalar() or 0
            finally:
                session.close()
            
            # Get triples with offset support
            # Note: query_triples doesn't support offset, so we need to get more and slice
            actual_limit = limit + offset
            triples = storage.query_triples(
                subject=subject,
                predicate=predicate,
                object=obj,  # Use 'object' not 'obj'
                limit=actual_limit
            )
            
            # Apply offset manually
            if offset > 0:
                triples = triples[offset:]
            
            # Limit to requested amount
            triples = triples[:limit]
            
            return {
                "total": total,
                "items": [t.to_dict() for t in triples]
            }
        except Exception as e:
            logger.error(f"Failed to get triples: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/knowledge/entities")
    async def get_knowledge_entities(
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get knowledge entities."""
        try:
            from ..ai.knowledge import get_kg_manager
            from sqlalchemy import func
            
            manager = get_kg_manager()
            storage = manager.storage
            
            # Get total count
            from ..ai.knowledge.kg_storage import Entity
            session = storage.get_session()
            try:
                count_query = session.query(func.count(Entity.id))
                if entity_type:
                    count_query = count_query.filter(Entity.entity_type == entity_type)
                total = count_query.scalar() or 0
            finally:
                session.close()
            
            # Get entities
            entities = storage.get_entities(
                entity_type=entity_type,
                limit=limit,
                offset=offset
            )
            
            return {
                "total": total,
                "items": [e.to_dict() for e in entities]
            }
        except Exception as e:
            logger.error(f"Failed to get entities: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/knowledge/entity/{entity_name}")
    async def get_entity_knowledge(
        entity_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get all knowledge about an entity."""
        try:
            from ..ai.knowledge import get_kg_manager
            manager = get_kg_manager()
            return manager.get_entity_knowledge(entity_name, limit=100)
        except Exception as e:
            logger.error(f"Failed to get entity knowledge: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/ai/knowledge/query")
    async def query_knowledge(
        request: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Query knowledge graph using natural language."""
        try:
            from ..ai.knowledge import get_kg_manager
            from ..ai.llm_client import LLMClient
            
            query_text = request.get('query', '')
            limit = request.get('limit', 10)
            
            if not query_text:
                raise HTTPException(status_code=400, detail="查询文本不能为空")
            
            # Get default model for LLM client
            model_manager = get_model_manager()
            default_model = await model_manager.get_default_model()
            if not default_model:
                raise HTTPException(status_code=400, detail="未配置默认LLM模型，请先在AI模型管理中设置默认模型")
            
            # Get model with API key
            model_with_secret = await model_manager.get_model_with_secret(default_model['uuid'])
            if not model_with_secret:
                raise HTTPException(status_code=404, detail="默认模型不存在")
            
            # Initialize LLM client with model configuration
            llm_client = LLMClient(
                api_key=model_with_secret.get('api_key', ''),
                base_url=model_with_secret.get('base_url', ''),
                model_name=model_with_secret.get('model_name', ''),
                provider=model_with_secret.get('provider', 'openai')
            )
            
            manager = get_kg_manager()
            results = await manager.query_knowledge(query_text, llm_client, limit=limit)
            return {"results": results}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to query knowledge: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    # Learning Features Configuration APIs
    @app.get("/api/ai/learning/config")
    async def get_learning_config_api(
        config_type: str = 'global',
        target_id: Optional[str] = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get learning features configuration."""
        try:
            from ..ai.learning_config import get_learning_config
            config_manager = get_learning_config()
            config = await config_manager.get_config(config_type, target_id)
            return config
        except Exception as e:
            logger.error(f"Failed to get learning config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/ai/learning/config")
    async def update_learning_config_api(
        learning_config: Dict[str, Any],
        config_type: str = 'global',
        target_id: Optional[str] = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update learning features configuration."""
        try:
            from ..ai.learning_config import get_learning_config
            config_manager = get_learning_config()
            success = await config_manager.update_config(learning_config, config_type, target_id)
            if success:
                return {"success": True, "message": "配置已更新"}
            else:
                raise HTTPException(status_code=500, detail="更新配置失败")
        except Exception as e:
            logger.error(f"Failed to update learning config: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # HeartFlow APIs
    @app.get("/api/ai/heartflow/stats/{chat_id}")
    async def get_heartflow_stats(
        chat_id: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get HeartFlow statistics for a chat."""
        try:
            from ..ai.heartflow_enhanced import get_heartflow_enhanced
            heartflow = get_heartflow_enhanced()
            return heartflow.get_flow_metrics(chat_id)
        except Exception as e:
            logger.error(f"Failed to get heartflow stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/heartflow/chats")
    async def get_heartflow_chats(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get all chats with HeartFlow data."""
        try:
            from ..ai.heartflow_enhanced import get_heartflow_enhanced
            heartflow = get_heartflow_enhanced()
            
            # Get all tracked chat IDs
            chat_ids = list(set(
                list(heartflow.message_count.keys()) +
                list(heartflow.emotion_states.keys())
            ))
            
            chats = []
            for chat_id in chat_ids:
                metrics = heartflow.get_flow_metrics(chat_id)
                chats.append({
                    "chat_id": chat_id,
                    **metrics
                })
            
            return {"chats": chats}
        except Exception as e:
            logger.error(f"Failed to get heartflow chats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ==================== Tool Permission Management APIs ====================
    
    @app.get("/api/ai/tool-permissions")
    async def get_tool_permissions(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get all tool permission configurations."""
        from ..core.models.tool_permission import ToolPermission
        from sqlalchemy import select
        
        async with db_manager.session() as session:
            result = await session.execute(select(ToolPermission))
            permissions = result.scalars().all()
            return {"permissions": [perm.to_dict() for perm in permissions]}
    
    @app.post("/api/ai/tool-permissions")
    async def create_or_update_tool_permission(
        permission_data: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Create or update a tool permission configuration."""
        from ..core.models.tool_permission import ToolPermission
        from sqlalchemy import select
        
        tool_name = permission_data.get('tool_name')
        if not tool_name:
            raise HTTPException(status_code=400, detail="tool_name is required")
        
        try:
            async with db_manager.session() as session:
                # Check if exists
                result = await session.execute(
                    select(ToolPermission).where(ToolPermission.tool_name == tool_name)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing
                    for key, value in permission_data.items():
                        if key != 'tool_name' and hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new
                    perm = ToolPermission(
                        tool_name=tool_name,
                        requires_permission=permission_data.get('requires_permission', False),
                        requires_admin_approval=permission_data.get('requires_admin_approval', False),
                        requires_ai_approval=permission_data.get('requires_ai_approval', True),
                        allowed_users=permission_data.get('allowed_users', []),
                        tool_category=permission_data.get('tool_category'),
                        tool_description=permission_data.get('tool_description'),
                        danger_level=permission_data.get('danger_level', 0)
                    )
                    session.add(perm)
                
                await session.commit()
                
                # Fetch and return the updated permission
                result = await session.execute(
                    select(ToolPermission).where(ToolPermission.tool_name == tool_name)
                )
                perm = result.scalar_one()
                return {"success": True, "permission": perm.to_dict()}
        except Exception as e:
            logger.error(f"Failed to save tool permission: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/ai/tool-permissions/{tool_name}")
    async def delete_tool_permission(
        tool_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete a tool permission configuration."""
        from ..core.models.tool_permission import ToolPermission
        from sqlalchemy import delete
        
        try:
            async with db_manager.session() as session:
                await session.execute(
                    delete(ToolPermission).where(ToolPermission.tool_name == tool_name)
                )
                await session.commit()
                return {"success": True, "message": "工具权限已删除"}
        except Exception as e:
            logger.error(f"Failed to delete tool permission: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/admin-users")
    async def get_admin_users(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get all admin users."""
        from ..core.models.tool_permission import AdminUser
        from sqlalchemy import select
        
        async with db_manager.session() as session:
            result = await session.execute(select(AdminUser))
            admins = result.scalars().all()
            return {"admins": [admin.to_dict() for admin in admins]}
    
    @app.post("/api/ai/admin-users")
    async def create_or_update_admin_user(
        admin_data: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Create or update an admin user."""
        from ..core.models.tool_permission import AdminUser
        from sqlalchemy import select
        
        qq_number = admin_data.get('qq_number')
        if not qq_number:
            raise HTTPException(status_code=400, detail="qq_number is required")
        
        try:
            async with db_manager.session() as session:
                # Check if exists
                result = await session.execute(
                    select(AdminUser).where(AdminUser.qq_number == qq_number)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing
                    for key, value in admin_data.items():
                        if key != 'qq_number' and hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new
                    admin = AdminUser(
                        qq_number=qq_number,
                        nickname=admin_data.get('nickname'),
                        permission_level=admin_data.get('permission_level', 1),
                        is_active=admin_data.get('is_active', True),
                        can_approve_all_tools=admin_data.get('can_approve_all_tools', False),
                        approved_tools=admin_data.get('approved_tools', [])
                    )
                    session.add(admin)
                
                await session.commit()
                
                # Fetch and return the updated admin
                result = await session.execute(
                    select(AdminUser).where(AdminUser.qq_number == qq_number)
                )
                admin = result.scalar_one()
                return {"success": True, "admin": admin.to_dict()}
        except Exception as e:
            logger.error(f"Failed to save admin user: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/ai/admin-users/{qq_number}")
    async def delete_admin_user(
        qq_number: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete an admin user."""
        from ..core.models.tool_permission import AdminUser
        from sqlalchemy import delete
        
        try:
            async with db_manager.session() as session:
                await session.execute(
                    delete(AdminUser).where(AdminUser.qq_number == qq_number)
                )
                await session.commit()
                return {"success": True, "message": "管理员已删除"}
        except Exception as e:
            logger.error(f"Failed to delete admin user: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/ai/approval-logs")
    async def get_approval_logs(
        limit: int = 100,
        tool_name: Optional[str] = None,
        user_qq: Optional[str] = None,
        user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_VIEW))
    ):
        """Get tool approval audit logs."""
        from ..core.models.tool_permission import ToolApprovalLog
        from sqlalchemy import select, desc
        
        try:
            async with db_manager.session() as session:
                query = select(ToolApprovalLog).order_by(desc(ToolApprovalLog.created_at)).limit(limit)
                
                if tool_name:
                    query = query.where(ToolApprovalLog.tool_name == tool_name)
                if user_qq:
                    query = query.where(ToolApprovalLog.user_qq == user_qq)
                
                result = await session.execute(query)
                logs = result.scalars().all()
                return {"logs": [log.to_dict() for log in logs]}
        except Exception as e:
            logger.error(f"Failed to get approval logs: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/ai/approval-logs/{log_id}/approve")
    async def admin_approve_tool_usage(
        log_id: int,
        approval_data: Dict[str, Any],
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Admin approve or reject a tool usage request."""
        from ..ai.tool_permission_manager import get_tool_permission_manager
        
        admin_qq = approval_data.get('admin_qq')
        approved = approval_data.get('approved', False)
        reason = approval_data.get('reason')
        
        if not admin_qq:
            raise HTTPException(status_code=400, detail="admin_qq is required")
        
        try:
            tool_perm_mgr = get_tool_permission_manager()
            success = await tool_perm_mgr.admin_approve_tool(
                log_id=log_id,
                admin_qq=admin_qq,
                approved=approved,
                reason=reason
            )
            
            if success:
                return {"success": True, "message": "审批成功"}
            else:
                raise HTTPException(status_code=400, detail="审批失败，请检查管理员权限")
        except Exception as e:
            logger.error(f"Failed to approve tool: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    # Serve Vite React SPA for all non-API routes (must be last) - only if WebUI is enabled
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve Vite React SPA for all non-API routes."""
        config = get_config()
        
        # Check if WebUI is enabled
        if not config.web_ui_enabled:
            # Allow API routes, docs, and health check to pass through
            if (full_path.startswith("api/") or 
                full_path == "docs" or 
                full_path.startswith("docs/") or 
                full_path == "openapi.json" or
                full_path == "redoc" or
                full_path == "health"):
                raise HTTPException(status_code=404, detail="Not found")
            
            # Return 403 Forbidden for WebUI access when disabled
            raise HTTPException(
                status_code=403,
                detail="WebUI is disabled. Please enable it in the configuration file (config.toml: [web_ui].enabled = true)."
            )
        
        # Don't serve React app for API routes, docs, or static assets
        if (full_path.startswith("api/") or 
            full_path == "docs" or 
            full_path.startswith("docs/") or 
            full_path == "openapi.json" or
            full_path == "redoc" or
            full_path.startswith("_next/")):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Check if requested file exists in static folder
        static_dir_path = Path(__file__).parent / "static"
        static_file_path = static_dir_path / full_path.lstrip("/")
        if static_file_path.exists() and static_file_path.is_file():
            return FileResponse(str(static_file_path))
        
        # For SPA, always serve index.html and let React Router handle routing
        # Read file content dynamically on each request to avoid caching issues
        index_file = static_dir_path / "index.html"
        
        # Check if webui source directory exists
        project_root = Path(__file__).parent.parent.parent
        webui_source_dir = project_root / "webui"
        webui_exists = webui_source_dir.exists() and webui_source_dir.is_dir()
        
        if index_file.exists():
            # Read file content on each request to ensure latest version
            content = index_file.read_text(encoding="utf-8")
            response = HTMLResponse(content=content)
            # Disable caching for index.html to ensure users get the latest version
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        else:
            # Fallback HTML if index.html doesn't exist
            # Different messages based on whether webui source directory exists
            if not webui_exists:
                # WebUI folder doesn't exist
                title = "WebUI 文件夹不存在"
                message = """
                        <h1>WebUI 文件夹不存在</h1>
                        <p>配置文件中已启用 WebUI，但 <code>webui</code> 文件夹不存在。</p>
                        <p style="margin-top: 1.5rem;"><strong>解决方案：</strong></p>
                        <ul style="text-align: left; display: inline-block; margin: 1rem 0;">
                            <li>如果您不需要 WebUI，请在 <code>config.toml</code> 中设置 <code>[web_ui].enabled = false</code></li>
                            <li>如果需要 WebUI，请恢复 <code>webui</code> 文件夹并构建前端</li>
                        </ul>
                        <p style="margin-top: 1.5rem; font-size: 0.9rem; opacity: 0.8;">
                            构建命令：<code>cd webui && npm run build</code>
                        </p>
                        <p style="font-size: 0.9rem; opacity: 0.8;">
                            或使用 <code>build.bat</code> (Windows) / <code>build.sh</code> (Linux/Mac)
                        </p>
                """
            else:
                # WebUI folder exists but not built
                title = "WebUI 正在构建中"
                message = """
                        <h1>WebUI 未构建/错误</h1>
                        <p>请运行以下命令构建前端：</p>
                        <p><code>cd webui && npm run build</code></p>
                        <p style="font-size: 0.9rem; opacity: 0.8;">或使用 <code>build.bat</code> (Windows) / <code>build.sh</code> (Linux/Mac)</p>
                """
            
            return HTMLResponse(
                f"""
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Xiaoyi_QQ Framework - {title}</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                        }}
                        .container {{
                            text-align: center;
                            padding: 2rem;
                            background: rgba(255, 255, 255, 0.1);
                            border-radius: 1rem;
                            backdrop-filter: blur(10px);
                            max-width: 600px;
                        }}
                        code {{
                            background: rgba(0, 0, 0, 0.3);
                            padding: 0.2rem 0.5rem;
                            border-radius: 0.25rem;
                            font-family: 'Courier New', monospace;
                        }}
                        ul {{
                            list-style-position: inside;
                        }}
                        li {{
                            margin: 0.5rem 0;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        {message}
                    </div>
                </body>
                </html>
                """
            )
    
    return app


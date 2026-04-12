"""FastAPI application for Web UI."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple
import ipaddress
import platform
import sys
import uuid
import time
import httpx
import re

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form, Body, WebSocket, WebSocketDisconnect, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
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
from collections import defaultdict

from ..core.app import get_app
from ..core.blocking_task_pool import get_blocking_task_pool_manager, run_in_blocking_pool
from ..core.config import (
    get_config,
    get_config_manager,
    reload_config,
    get_config_file_path,
    get_runtime_base_dir,
)
from ..assistant.security import assistant_config_for_response, assistant_config_for_storage
from ..core.event_bus import get_event_bus
from ..core.database import get_database_manager, collect_plugin_config_upload_keys
from ..plugins.manifest import (
    build_plugin_api_metadata,
    coerce_plugin_priority,
    load_plugin_manifest,
    normalize_plugin_default_config,
    plugin_manifest_exists,
)
from ..security.auth import AuthManager
from ..security.permissions import get_permission_manager, Permission
from ..security.audit import (
    AUDIT_EVENT_RETENTION_LIMIT,
    get_audit_logger,
    AuditEventType,
    AuditEvent,
)
from ..security.device_keys import get_device_key_manager, DeviceKeyStatus
from ..core.logger import get_logger
from ..core.version import get_version
from datetime import datetime, timedelta

logger = get_logger(__name__)
security = HTTPBearer()

# Plugin installation progress tracking
_plugin_install_progress: Dict[str, Dict[str, Any]] = {}
_onebot_login_info_last_connectivity_log_at: float = 0.0
_ONEBOT_LOGIN_INFO_CONNECTIVITY_LOG_INTERVAL_SECONDS = 60.0
_record_proxy_fail_until: Dict[str, float] = {}
_BT_IP_INFO_API_URL = "https://www.bt.cn/api/panel/get_ip_info"
_IP_GEO_CACHE_TTL_SECONDS = 6 * 60 * 60
_ip_geo_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# Request/Response Models
class LoginRequest(BaseModel):
    username: str
    password: str
    client_info: Dict[str, Any] = {}

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DeviceKeyCreateRequest(BaseModel):
    """Request body for creating a new device key."""

    name: Optional[str] = None
    device_fingerprint: Dict[str, Any] = {}


class DeviceKeyResponse(BaseModel):
    """Public information about a device key (without opaque token)."""

    key_id: str
    name: str
    status: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    device_fingerprint: Dict[str, Any] = {}


class DeviceKeyWithTokenResponse(DeviceKeyResponse):
    """Device key plus opaque token (only returned at creation time)."""

    opaque_token: str

class PluginInfo(BaseModel):
    name: str
    enabled: bool
    metadata: Dict[str, Any]

class PluginAction(BaseModel):
    action: str  # load, unload, enable, disable, reload

class ConfigUpdate(BaseModel):
    config: Dict[str, Any]
    priority: Optional[int] = None  # Plugin priority (lower = earlier execution, default: 100)


class AIWorkspaceConfigUpdate(BaseModel):
    mode: str


class AIAssistantConfigUpdate(BaseModel):
    config: Dict[str, Any]


class AIAssistantMemoryClearRequest(BaseModel):
    scope: str
    target_id: str
    memory_type: str

# Global auth manager instance
_auth_manager = None

def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def _resolve_plugin_base_dir() -> Path:
    """Resolve plugin base directory for both source and frozen runs."""
    config = get_config()
    plugin_base = Path(config.plugin_dir)
    if not plugin_base.is_absolute():
        plugin_base = (get_runtime_base_dir() / config.plugin_dir).resolve()
    else:
        plugin_base = plugin_base.resolve()
    return plugin_base


async def _load_plugin_manifest_async(plugin_dir: Path, thread_pool: Any = None) -> Dict[str, Any]:
    """Load split plugin manifest files with optional thread-pool offloading."""
    if thread_pool:
        def read_manifest() -> Dict[str, Any]:
            return load_plugin_manifest(plugin_dir)

        return await thread_pool.run_in_executor(read_manifest)

    return await run_in_blocking_pool(load_plugin_manifest, plugin_dir)


def _get_blocking_task_pool(app: Any = None):
    """Get the shared blocking task pool, preferring the app-bound instance."""
    return getattr(app, "blocking_task_pool", None) or get_blocking_task_pool_manager()


def _get_ai_assistant_config_path() -> Path:
    """Return the persisted Assistant configuration path."""
    data_dir = get_runtime_base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "assistant_config.json"


def _normalize_ai_assistant_preset_references(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Assistant config compatibility and clear invalid preset references."""
    if not isinstance(config, dict):
        return {}

    normalized = dict(config)
    models = normalized.get("models")
    if isinstance(models, list):
        next_models = []
        for item in models:
            if not isinstance(item, dict):
                next_models.append(item)
                continue
            model = dict(item)
            raw_capabilities = model.get("capabilities")
            if isinstance(raw_capabilities, list):
                values = raw_capabilities
            else:
                values = re.split(r"[,，/、\s]+", str(model.get("capability") or ""))
            capabilities = set()
            for value in values:
                text = str(value or "").strip().lower()
                if text in {"text", "文本", "文字"}:
                    capabilities.add("text")
                if text in {"image", "vision", "图片", "图像", "视觉", "多模态"}:
                    capabilities.add("image")
            model["capabilities"] = sorted(capabilities or {"text"})
            fmt = str(model.get("apiFormat") or model.get("format") or model.get("api_format") or "openai").strip().lower()
            model["apiFormat"] = "gemini" if fmt in {"gemini", "genimi", "google"} else "openai"
            model.pop("capability", None)
            next_models.append(model)
        normalized["models"] = next_models

    presets = normalized.get("presets")
    enabled_names = {
        str(item.get("name") or "").strip()
        for item in presets
        if isinstance(item, dict) and item.get("enabled", False) and str(item.get("name") or "").strip()
    } if isinstance(presets, list) else set()

    def normalize_policy(item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        policy = dict(item)
        preset = str(policy.get("preset") or "").strip()
        policy["preset"] = preset if preset and preset in enabled_names else ""
        return policy

    for key in ("groups", "personal"):
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = [normalize_policy(item) for item in value]

    return normalized


async def _resolve_plugin_identity(plugin_name: str, app: Any) -> Dict[str, Any]:
    """Resolve plugin path and storage owner from plugin directory name."""
    plugin_base = _resolve_plugin_base_dir()
    plugin_path = plugin_base / plugin_name

    if not plugin_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")
    if not plugin_manifest_exists(plugin_path):
        raise HTTPException(status_code=400, detail="Plugin manifest not found")

    thread_pool = getattr(app, 'blocking_task_pool', None)
    manifest = await _load_plugin_manifest_async(plugin_path, thread_pool)
    author = str(manifest.get("author", "Unknown")).strip() or "Unknown"
    resolved_name = str(manifest.get("name", plugin_name)).strip() or plugin_name

    return {
        "plugin_path": plugin_path,
        "manifest": manifest,
        "author": author,
        "name": resolved_name,
        "plugin_owner": f"{author}/{resolved_name}",
    }


async def _discover_plugins_on_disk(plugin_base: Path, thread_pool: Any = None) -> List[Dict[str, Any]]:
    """Discover plugin manifests from filesystem and normalize metadata."""
    if not plugin_base.exists() or not plugin_base.is_dir():
        return []

    if thread_pool:
        def scan_plugin_dirs():
            return [
                d for d in plugin_base.iterdir()
                if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')
            ]
        plugin_dirs = await thread_pool.run_in_executor(scan_plugin_dirs)
    else:
        def scan_plugin_dirs_sync():
            return [
                d for d in plugin_base.iterdir()
                if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')
            ]
        plugin_dirs = await run_in_blocking_pool(scan_plugin_dirs_sync)

    discovered_plugins: List[Dict[str, Any]] = []
    for plugin_dir in plugin_dirs:
        if not plugin_manifest_exists(plugin_dir):
            continue

        try:
            plugin_config = await _load_plugin_manifest_async(plugin_dir, thread_pool)
        except Exception as e:
            logger.warning("Skipping invalid plugin manifest %s: %s", plugin_dir, e)
            continue

        author = str(plugin_config.get("author", "Unknown")).strip() or "Unknown"
        plugin_name = str(plugin_config.get("name", plugin_dir.name)).strip() or plugin_dir.name
        default_config = normalize_plugin_default_config(plugin_config.get("default_config", {}))
        priority = coerce_plugin_priority(plugin_config.get("priority"), 100)
        metadata = build_plugin_api_metadata(plugin_config, plugin_dir.name)

        discovered_plugins.append({
            "author": author,
            "name": plugin_name,
            "priority": priority,
            "default_config": default_config,
            "metadata": metadata,
        })

    return discovered_plugins


def _onebot_target_hint(adapter: Any) -> str:
    """Human-friendly OneBot target description for diagnostics."""
    conn_type = str(getattr(adapter, "connection_type", "http")).lower()
    if conn_type in ("ws", "ws_forward"):
        return str(getattr(adapter, "ws_url", ""))
    if conn_type == "ws_reverse":
        host = getattr(adapter, "ws_reverse_host", "0.0.0.0")
        port = getattr(adapter, "ws_reverse_port", 8080)
        path = getattr(adapter, "ws_reverse_path", "/onebot/v11/ws")
        return f"ws://{host}:{port}{path}"
    return str(getattr(adapter, "http_url", ""))


def _is_expected_onebot_connectivity_error(error: Exception) -> bool:
    """Detect common transient connectivity errors to avoid noisy traceback logs."""
    patterns = (
        "all connection attempts failed",
        "connecterror",
        "connection refused",
        "failed to connect",
        "timed out",
        "timeout",
        "http client not initialized",
        "websocket not available",
        "reverse websocket",
    )
    seen = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = f"{type(current).__name__}: {current}".lower()
        if any(pattern in text for pattern in patterns):
            return True
        current = current.__cause__ or current.__context__
    return False


def _normalize_plugin_config_value(
    field_type: Optional[str],
    value: Any,
    field_schema: Dict[str, Any],
    current_value: Any,
) -> Any:
    """Normalize one plugin config value according to schema field type."""
    nested_fields = field_schema.get("fields")
    if not isinstance(nested_fields, dict):
        nested_fields = {}

    if field_type == "group":
        if not isinstance(value, dict):
            value = {}
        base_value = current_value if isinstance(current_value, dict) else {}
        return normalize_plugin_config_by_schema(value, nested_fields, base_value)

    if field_type in {"object_array", "table"}:
        if not isinstance(value, list):
            return []
        normalized_rows = []
        for row in value:
            if not isinstance(row, dict):
                row = {}
            normalized_rows.append(
                normalize_plugin_config_by_schema(row, nested_fields, {})
            )
        return normalized_rows

    if field_type == "array":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            import re

            if value.strip():
                return [v.strip() for v in re.split(r"[\n,\s]+", value) if v.strip()]
            return []
        return []

    if field_type == "number":
        default_number = field_schema.get("default", current_value if current_value is not None else 0)
        if value is None or (
            isinstance(value, float)
            and (value != value or value == float("inf") or value == float("-inf"))
        ):
            return default_number

        try:
            num_value = float(value) if not isinstance(value, (int, float)) else value
            if num_value != num_value or num_value == float("inf") or num_value == float("-inf"):
                return default_number
            return num_value
        except (ValueError, TypeError):
            return default_number

    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    # string / textarea / select / file / file_array / unknown:
    return value


def normalize_plugin_config_by_schema(
    config: Dict[str, Any],
    config_schema: Dict[str, Any],
    default_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize plugin config payload according to schema and defaults."""
    normalized_config = (default_config or {}).copy()

    if config_schema:
        for key, value in config.items():
            if key in config_schema:
                field_schema = config_schema[key] or {}
                field_type = field_schema.get("type")
                normalized_config[key] = _normalize_plugin_config_value(
                    field_type,
                    value,
                    field_schema,
                    normalized_config.get(key),
                )
            else:
                normalized_config[key] = value
        return normalized_config

    normalized_config = config.copy()
    for key, value in list(normalized_config.items()):
        if isinstance(value, str) and key.endswith("_list"):
            import re

            if value.strip():
                normalized_config[key] = [v.strip() for v in re.split(r"[\n,\s]+", value) if v.strip()]
            else:
                normalized_config[key] = []
    return normalized_config


def _should_log_onebot_connectivity_issue(now_ts: Optional[float] = None) -> bool:
    """Rate-limit repetitive OneBot connectivity logs."""
    global _onebot_login_info_last_connectivity_log_at
    now = now_ts if now_ts is not None else time.time()
    if now - _onebot_login_info_last_connectivity_log_at >= _ONEBOT_LOGIN_INFO_CONNECTIVITY_LOG_INTERVAL_SECONDS:
        _onebot_login_info_last_connectivity_log_at = now
        return True
    return False


def _normalize_ip_address(value: str) -> str:
    """Return a clean IP address from proxy header fragments."""
    candidate = str(value or "").strip().strip('"')
    if not candidate:
        return ""
    if candidate.lower().startswith("for="):
        candidate = candidate.split("=", 1)[1].strip().strip('"')
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        host, port = candidate.rsplit(":", 1)
        if port.isdigit():
            candidate = host
    candidate = candidate.strip("[]")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return candidate


def _client_ip_from_request(request: Request) -> str:
    """Resolve client IP, respecting common reverse-proxy headers."""
    header_names = [
        "cf-connecting-ip",
        "x-real-ip",
        "x-forwarded-for",
        "x-client-ip",
        "x-forwarded",
        "forwarded-for",
        "forwarded",
    ]
    for name in header_names:
        value = request.headers.get(name)
        if not value:
            continue
        if name == "x-forwarded-for":
            return _normalize_ip_address(value.split(",", 1)[0])
        if name == "forwarded":
            first_forwarded = value.split(",", 1)[0]
            for part in first_forwarded.split(";"):
                part = part.strip()
                if part.lower().startswith("for="):
                    return _normalize_ip_address(part)
        return _normalize_ip_address(value)
    return _normalize_ip_address(request.client.host if request.client else "")


def _public_ip_for_lookup(ip_address: str) -> str:
    """Only query public IPs; private/local addresses have no useful public geo result."""
    try:
        parsed = ipaddress.ip_address(ip_address)
    except ValueError:
        return ""
    return str(parsed) if parsed.is_global else ""


def _geo_from_bt_payload(ip_address: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    raw_info = payload.get(ip_address)
    if not isinstance(raw_info, dict) and len(payload) == 1:
        only_value = next(iter(payload.values()))
        if isinstance(only_value, dict):
            raw_info = only_value
    if not isinstance(raw_info, dict):
        return {}

    fields = [
        "continent",
        "country",
        "province",
        "city",
        "region",
        "carrier",
        "division",
        "en_country",
        "en_short_code",
        "longitude",
        "latitude",
    ]
    geo = {
        key: str(raw_info.get(key)).strip()
        for key in fields
        if raw_info.get(key) not in ("", None)
    }
    if geo:
        geo["source"] = "bt.cn"
    return geo


async def _geo_from_ip_api(ip_address: str) -> Dict[str, Any]:
    lookup_ip = _public_ip_for_lookup(ip_address)
    if not lookup_ip:
        return {}

    now = time.time()
    cached = _ip_geo_cache.get(lookup_ip)
    if cached and now - cached[0] < _IP_GEO_CACHE_TTL_SECONDS:
        return cached[1].copy()

    try:
        timeout = httpx.Timeout(3.0, connect=1.5)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(_BT_IP_INFO_API_URL, params={"ip": lookup_ip})
            response.raise_for_status()
            geo = _geo_from_bt_payload(lookup_ip, response.json())
            if geo:
                _ip_geo_cache[lookup_ip] = (now, geo.copy())
            return geo
    except Exception as exc:
        logger.debug("Failed to lookup IP geo information", ip_address=lookup_ip, error=str(exc))
        return {}


def _geo_from_headers(request: Request, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect best-effort proxy location metadata as a fallback."""
    client_info = client_info if isinstance(client_info, dict) else {}
    geo = {
        "country": request.headers.get("cf-ipcountry")
        or request.headers.get("x-vercel-ip-country")
        or request.headers.get("x-geo-country")
        or "",
        "region": request.headers.get("x-vercel-ip-country-region")
        or request.headers.get("x-geo-region")
        or "",
        "city": request.headers.get("x-vercel-ip-city")
        or request.headers.get("x-geo-city")
        or "",
        "latitude": request.headers.get("x-vercel-ip-latitude")
        or request.headers.get("x-geo-latitude")
        or "",
        "longitude": request.headers.get("x-vercel-ip-longitude")
        or request.headers.get("x-geo-longitude")
        or "",
        "timezone": client_info.get("timezone") or request.headers.get("x-vercel-ip-timezone") or "",
    }
    return {key: value for key, value in geo.items() if value not in ("", None)}


async def _geo_from_request(
    request: Request,
    ip_address: str,
    client_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    header_geo = _geo_from_headers(request, client_info)
    ip_geo = await _geo_from_ip_api(ip_address)
    return {
        key: value
        for key, value in {**header_geo, **ip_geo}.items()
        if value not in ("", None)
    }


async def _request_audit_details(request: Request, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build request/client metadata for security audit records."""
    client_info = client_info if isinstance(client_info, dict) else {}
    ip_address = _client_ip_from_request(request)
    return {
        "ip": ip_address,
        "geo": await _geo_from_request(request, ip_address, client_info),
        "user_agent": request.headers.get("user-agent", ""),
        "referer": request.headers.get("referer", ""),
        "origin": request.headers.get("origin", ""),
        "host": request.headers.get("host", ""),
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "client": client_info,
    }

# Dependency for authentication
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Verify user from token."""
    auth_manager = get_auth_manager()
    session = await auth_manager.verify_session(credentials.credentials)
    
    if not session:
        details = await _request_audit_details(request)
        await get_audit_logger().log_access_denied(
            username="unknown",
            resource="api",
            action="access",
            reason="Invalid or expired token",
            ip_address=details.get("ip"),
            details=details,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return session

# Dependency for permission checking
def require_permission(permission: Permission):
    """Decorator to require a specific permission."""
    async def check(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
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
            details = await _request_audit_details(request)
            await get_audit_logger().log_access_denied(
                username=username,
                resource="api",
                action=permission.value,
                reason="Insufficient permissions",
                ip_address=details.get("ip"),
                details=details,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission.value}"
            )
        return user
    return check


_SESSION_MESSAGE_LOG_LIMIT = 2000


def _format_live_message_event(
    event_name: str,
    payload: Dict[str, Any],
    event_id: str,
    event_time: datetime,
) -> Optional[Dict[str, Any]]:
    """Normalize live OneBot events for WebSocket and startup-session views."""
    if not isinstance(payload, dict):
        return None

    if event_name == "onebot.message":
        sender = payload.get("sender", {})
        if not isinstance(sender, dict):
            sender = {}
        user_id = str(payload.get("user_id", "") or sender.get("user_id", "") or "")
        return {
            "type": "message",
            "id": event_id,
            "timestamp": event_time.isoformat(),
            "time": event_time.isoformat(),
            "event_type": "message",
            "post_type": "message",
            "message_id": str(payload.get("message_id", "")),
            "message_type": payload.get("message_type", "unknown"),
            "user_id": user_id,
            "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
            "raw_message": payload.get("raw_message", ""),
            "message": payload.get("raw_message", ""),
            "sender": sender,
            "is_self": payload.get("is_self", False),
            "target_id": str(payload.get("target_id", "")) if payload.get("target_id") else None,
            "source_plugin": payload.get("source_plugin"),
            "source": payload.get("source"),
        }

    if event_name == "onebot.message_sent":
        raw_text = payload.get("raw_message") or payload.get("message") or ""
        sender = payload.get("sender", {})
        if not isinstance(sender, dict):
            sender = {}
        if not sender.get("nickname"):
            sender["nickname"] = "Bot"
        user_id = str(payload.get("user_id", "") or sender.get("user_id", "") or "")

        target_id = payload.get("target_id") or payload.get("target")
        group_id = payload.get("group_id")
        message_id = payload.get("message_id")

        return {
            "type": "message",
            "id": event_id,
            "timestamp": event_time.isoformat(),
            "time": event_time.isoformat(),
            "event_type": "message",
            "post_type": "message_sent",
            "message_id": str(message_id) if message_id else "",
            "message_type": payload.get("message_type", "unknown"),
            "user_id": user_id,
            "group_id": str(group_id) if group_id else None,
            "raw_message": raw_text,
            "message": raw_text,
            "sender": sender,
            "is_self": True,
            "target_id": str(target_id) if target_id else None,
            "source_plugin": payload.get("source_plugin"),
            "source": payload.get("source"),
        }

    if event_name == "onebot.notice":
        formatted_text = _format_notice_event(payload)
        return {
            "type": "notice",
            "id": event_id,
            "timestamp": event_time.isoformat(),
            "time": event_time.isoformat(),
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

    if event_name == "onebot.request":
        formatted_text = _format_request_event(payload)
        return {
            "type": "request",
            "id": event_id,
            "timestamp": event_time.isoformat(),
            "time": event_time.isoformat(),
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

    return None


class SessionMessageLogStore:
    """Keep only the current-process message stream for the message log page."""

    def __init__(self, max_events: int = _SESSION_MESSAGE_LOG_LIMIT):
        self.max_events = max(100, int(max_events or _SESSION_MESSAGE_LOG_LIMIT))
        self._events: List[Dict[str, Any]] = []
        self._subscribed = False
        self.started_at = datetime.utcnow().isoformat()

    def subscribe(self):
        """Subscribe once so startup-session logs are collected immediately."""
        if self._subscribed:
            return

        event_bus = get_event_bus()
        event_bus.subscribe("onebot.message", self._on_message_event)
        event_bus.subscribe("onebot.message_sent", self._on_message_event)
        event_bus.subscribe("onebot.notice", self._on_message_event)
        event_bus.subscribe("onebot.request", self._on_message_event)
        self._subscribed = True
        self.started_at = datetime.utcnow().isoformat()
        logger.info("Session message log store subscribed to event bus")

    def _append(self, event_data: Dict[str, Any]):
        event_id = str(event_data.get("id", "")).strip()
        if event_id:
            self._events = [
                existing
                for existing in self._events
                if str(existing.get("id", "")).strip() != event_id
            ]

        self._events.append(event_data)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events :]

    async def _on_message_event(self, event):
        """Collect formatted OneBot events for the current process lifetime."""
        try:
            payload = event.payload
            event_data = _format_live_message_event(
                event.name,
                payload,
                event.event_id,
                event.timestamp,
            )
            if event_data:
                self._append(event_data)
        except Exception as e:
            logger.error(f"Error collecting session message event: {e}", exc_info=True)

    def list_events(
        self,
        limit: int = 100,
        include_notices: bool = True,
        include_requests: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return the newest current-session events first."""
        max_items = max(1, min(int(limit or 100), 500))
        results: List[Dict[str, Any]] = []
        for item in reversed(self._events):
            event_type = str(item.get("event_type", "message"))
            if event_type == "notice" and not include_notices:
                continue
            if event_type == "request" and not include_requests:
                continue

            results.append(item)
            if len(results) >= max_items:
                break

        return results


_session_message_log_store = SessionMessageLogStore()


# WebSocket Manager for real-time message updates
class WebSocketManager:
    """Manage WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._subscribed = False

    def subscribe(self):
        """Subscribe once to the event bus for live push updates."""
        if self._subscribed:
            return

        event_bus = get_event_bus()
        event_bus.subscribe("onebot.message", self._on_message_event)
        event_bus.subscribe("onebot.message_sent", self._on_message_event)
        event_bus.subscribe("onebot.notice", self._on_message_event)
        event_bus.subscribe("onebot.request", self._on_message_event)
        self._subscribed = True
        logger.info("WebSocket manager subscribed to event bus")
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected, total connections: {len(self.active_connections)}")
        self.subscribe()
    
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
            event_data = _format_live_message_event(
                event.name,
                event.payload,
                event.event_id,
                event.timestamp,
            )
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
    _session_message_log_store.subscribe()
    _ws_manager.subscribe()
    
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
        detail_parts: List[str] = []
        if sub_type:
            detail_parts.append(f"sub_type:{sub_type}")
        if group_id:
            detail_parts.append(f"群:{group_id}")
        if user_id:
            detail_parts.append(f"用户:{user_id}")
        if operator_id and str(operator_id) != str(user_id):
            detail_parts.append(f"操作者:{operator_id}")
        detail = " ".join(detail_parts) if detail_parts else "无附加字段"
        return f"[系统通知] notify事件 ({detail})"
    
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
    
    # Add global exception handler to prevent API endpoints from crashing
    # Note: HTTPException is handled by FastAPI by default, so we only catch other exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler to prevent API crashes.
        
        This catches all unhandled exceptions and returns a proper error response
        instead of crashing the entire API server.
        """
        # Don't handle HTTPException (let FastAPI handle it)
        if isinstance(exc, HTTPException):
            raise exc
        
        logger.error(f"Unhandled exception in API endpoint {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc) if logger.level <= 10 else "An error occurred",
                "path": str(request.url.path)
            }
        )

    @app.middleware("http")
    async def webui_operation_audit_middleware(request: Request, call_next):
        """Audit mutating WebUI API operations without interrupting the request path."""
        start_ts = time.perf_counter()
        response = await call_next(request)

        path = request.url.path
        method = request.method.upper()
        excluded_paths = {
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/device-login",
            "/api/splash/mark-shown",
        }

        if path.startswith("/api/") and method in {"POST", "PUT", "PATCH", "DELETE"} and path not in excluded_paths:
            try:
                username = "unknown"
                auth_header = request.headers.get("authorization", "")
                if auth_header.lower().startswith("bearer "):
                    token = auth_header.split(" ", 1)[1].strip()
                    session = await get_auth_manager().verify_session(token)
                    if session:
                        username = str(session.get("username") or "unknown")

                duration_ms = round((time.perf_counter() - start_ts) * 1000, 2)
                details = await _request_audit_details(request)
                details.update({
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "operation": f"{method} {path}",
                })
                await get_audit_logger().log_webui_action(
                    username=username,
                    action=f"{method} {path}",
                    resource="webui",
                    success=response.status_code < 400,
                    ip_address=details.get("ip"),
                    details=details,
                )
            except Exception as audit_error:
                logger.warning(f"Failed to audit WebUI operation {method} {path}: {audit_error}")

        return response
    
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
    async def login(body: LoginRequest, http_request: Request):
        """Login and get access token."""
        auth_manager = get_auth_manager()
        token = await auth_manager.authenticate(body.username, body.password)
        audit_details = await _request_audit_details(http_request, body.client_info)
        ip_address = audit_details.get("ip")
        
        if not token:
            await get_audit_logger().log_login(
                body.username,
                False,
                ip_address=ip_address,
                details=audit_details,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        await get_audit_logger().log_login(
            body.username,
            True,
            ip_address=ip_address,
            details=audit_details,
        )
        return LoginResponse(access_token=token)
    
    @app.post("/api/auth/logout")
    async def logout(http_request: Request, user: Dict[str, Any] = Depends(get_current_user)):
        """Logout current user."""
        details = await _request_audit_details(http_request)
        await get_audit_logger().log_logout(
            user.get("username"),
            ip_address=details.get("ip"),
            details=details,
        )
        return {"message": "Logged out successfully"}
    
    @app.get("/api/auth/me")
    async def get_current_user_info(user: Dict[str, Any] = Depends(get_current_user)):
        """Get current user info."""
        return user

    @app.get("/api/security/audit-events")
    async def get_security_audit_events(
        event_type: Optional[str] = None,
        username: Optional[str] = None,
        limit: int = 200,
        recent_minutes: Optional[int] = 1440,
        user: Dict[str, Any] = Depends(require_permission(Permission.AUDIT_VIEW)),
    ):
        """Return WebUI security and operation audit events."""
        audit_logger = get_audit_logger()
        limit = max(1, min(int(limit or AUDIT_EVENT_RETENTION_LIMIT), AUDIT_EVENT_RETENTION_LIMIT))
        since = None
        if recent_minutes is not None and int(recent_minutes or 0) > 0:
            since = datetime.utcnow() - timedelta(minutes=max(1, min(int(recent_minutes), 60 * 24 * 30)))
        events = await audit_logger.get_event_dicts(
            event_type=event_type,
            username=username,
            limit=limit,
            since=since,
        )
        stats = {
            "total_events": len(events),
            "failed_events": sum(1 for event in events if event.get("success") is False),
            "by_type": {},
            "by_user": {},
            "recent_minutes": recent_minutes,
            "limit": limit,
        }
        for event in events:
            event_type_key = str(event.get("event_type") or "unknown")
            stats["by_type"][event_type_key] = stats["by_type"].get(event_type_key, 0) + 1
            username_key = str(event.get("username") or "")
            if username_key:
                stats["by_user"][username_key] = stats["by_user"].get(username_key, 0) + 1
        return {
            "events": events,
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Device key endpoints (for browser extension based login)
    # ------------------------------------------------------------------
    @app.post("/api/device-keys", response_model=DeviceKeyWithTokenResponse)
    async def create_device_key(
        request: DeviceKeyCreateRequest,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        """Create a new device key for current user."""
        username = user.get("username")
        mgr = get_device_key_manager()
        record = mgr.create_key(
            username=username,
            name=request.name,
            device_fingerprint=request.device_fingerprint or {},
        )
        return DeviceKeyWithTokenResponse(**record)

    @app.get("/api/device-keys", response_model=List[DeviceKeyResponse])
    async def list_device_keys(user: Dict[str, Any] = Depends(get_current_user)):
        """List all device keys of current user."""
        username = user.get("username")
        mgr = get_device_key_manager()
        records = mgr.list_keys_for_user(username)
        return [DeviceKeyResponse(**r) for r in records]

    @app.post("/api/device-keys/{key_id}/enable", response_model=DeviceKeyResponse)
    async def enable_device_key(
        key_id: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        """Enable a specific device key."""
        username = user.get("username")
        mgr = get_device_key_manager()
        try:
            rec = mgr.set_status(username, key_id, DeviceKeyStatus.ENABLED)
        except KeyError:
            raise HTTPException(status_code=404, detail="Device key not found")
        return DeviceKeyResponse(
            key_id=rec["key_id"],
            name=rec.get("name", ""),
            status=rec.get("status", ""),
            created_at=rec.get("created_at"),
            last_used_at=rec.get("last_used_at"),
            device_fingerprint=rec.get("device_fingerprint") or {},
        )

    @app.post("/api/device-keys/{key_id}/disable", response_model=DeviceKeyResponse)
    async def disable_device_key(
        key_id: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        """Disable a specific device key."""
        username = user.get("username")
        mgr = get_device_key_manager()
        try:
            rec = mgr.set_status(username, key_id, DeviceKeyStatus.DISABLED)
        except KeyError:
            raise HTTPException(status_code=404, detail="Device key not found")
        return DeviceKeyResponse(
            key_id=rec["key_id"],
            name=rec.get("name", ""),
            status=rec.get("status", ""),
            created_at=rec.get("created_at"),
            last_used_at=rec.get("last_used_at"),
            device_fingerprint=rec.get("device_fingerprint") or {},
        )

    @app.delete("/api/device-keys/{key_id}")
    async def delete_device_key(
        key_id: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        """Delete a specific device key."""
        username = user.get("username")
        mgr = get_device_key_manager()
        ok = mgr.delete_key(username, key_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Device key not found")
        return {"deleted": True}

    class DeviceLoginRequest(BaseModel):
        """Request body for device key based login."""

        device_key: Optional[str] = None
        device_fingerprint: Dict[str, Any] = {}

    @app.post("/api/auth/device-login", response_model=LoginResponse)
    async def device_login(body: DeviceLoginRequest, http_request: Request):
        """
        Login using a device key issued earlier.
        """
        mgr = get_device_key_manager()
        opaque = body.device_key
        if not opaque:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="device_key is required",
            )

        username = mgr.authenticate(
            opaque_token=opaque,
            device_fingerprint=body.device_fingerprint or {},
        )
        audit_details = await _request_audit_details(http_request, body.device_fingerprint)
        if not username:
            await get_audit_logger().log_access_denied(
                username="unknown",
                resource="auth",
                action="device-login",
                reason="Invalid device key",
                ip_address=audit_details.get("ip"),
                details=audit_details,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device key",
            )

        auth_manager = get_auth_manager()
        token = await auth_manager.create_session_for_user(username)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not available for login",
            )

        # 
        await get_audit_logger().log(
            AuditEvent(
                event_type=AuditEventType.AUTH_LOGIN,
                timestamp=datetime.utcnow(),
                username=username,
                ip_address=audit_details.get("ip"),
                action="device-login",
                success=True,
                details={**audit_details, "auth_method": "device-key"},
            )
        )

        return LoginResponse(access_token=token)
    
    # Plugin management endpoints
    @app.get("/api/plugins", response_model=List[PluginInfo])
    async def list_plugins(user: Dict[str, Any] = Depends(require_permission(Permission.PLUGIN_VIEW))):
        """Get list of all plugins (loaded and discovered)."""
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        plugin_base = _resolve_plugin_base_dir()
        thread_pool = getattr(app, 'blocking_task_pool', None)

        discovered_plugins = await _discover_plugins_on_disk(plugin_base, thread_pool=thread_pool)

        settings_map: Dict[tuple, Any] = {}
        if db_manager:
            try:
                settings = await asyncio.wait_for(
                    db_manager.list_plugin_settings(enabled_only=False),
                    timeout=5.0
                )
                settings_map = {
                    (setting.plugin_author, setting.plugin_name): setting
                    for setting in settings
                }
            except asyncio.TimeoutError:
                logger.warning("Timeout loading plugin settings while listing plugins")
            except Exception as e:
                logger.warning("Failed to read plugin settings while listing plugins: %s", e)

        all_plugins = []
        for plugin in discovered_plugins:
            author = plugin["author"]
            plugin_name = plugin["name"]
            metadata = plugin["metadata"]

            enabled = False
            priority = plugin["priority"]
            config_data = plugin["default_config"]

            db_setting = settings_map.get((author, plugin_name))
            if db_setting:
                enabled = bool(db_setting.enabled)
                if isinstance(db_setting.config, dict) and db_setting.config:
                    config_data = db_setting.config
                priority = db_setting.priority

            all_plugins.append({
                "name": plugin_name,
                "enabled": enabled,
                "metadata": metadata,
                "system_data": {
                    "enabled": enabled,
                    "priority": priority,
                    "config": config_data,
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
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        # Find plugin directory
        plugin_base = _resolve_plugin_base_dir()
        plugin_dir = plugin_base / plugin_name
        
        if not plugin_dir.exists():
            raise HTTPException(status_code=404, detail="Plugin not found")
        
        if not plugin_manifest_exists(plugin_dir):
            raise HTTPException(status_code=404, detail="Plugin metadata not found")
        
        # Load plugin manifest using thread pool
        app = get_app()
        thread_pool = getattr(app, 'blocking_task_pool', None)
        
        try:
            plugin_config = await _load_plugin_manifest_async(plugin_dir, thread_pool)
            
            author = plugin_config.get("author", "Unknown")
            name = plugin_config.get("name", plugin_name)
            metadata = build_plugin_api_metadata(plugin_config, plugin_name)
        except Exception as e:
            logger.error(f"Failed to load plugin manifest: {e}")
            raise HTTPException(status_code=500, detail="Failed to load plugin metadata")
        
        # Get status from database
        enabled = False
        config_data = metadata.get("default_config", {})
        # Priority: database (always if exists) > metadata.yaml > default (100)
        priority_from_manifest = plugin_config.get("priority")
        priority = 100  # Default: 100 (lower = earlier execution)
        
        if db_manager:
            try:
                db_setting = await db_manager.get_plugin_setting(author, name)
                if db_setting:
                    enabled = db_setting.enabled
                    config_data = db_setting.config or config_data
                    # Always use database priority if it exists (even if it's 100)
                    # User may have explicitly set it to 100, so we should respect that
                    priority = db_setting.priority
                else:
                    # No database setting, use metadata.yaml priority if available
                    if priority_from_manifest is not None:
                        priority = priority_from_manifest
            except Exception as e:
                logger.error(f"Failed to get plugin status: {e}")
        
        return {
            "name": name,
            "enabled": enabled,
            "metadata": metadata,
            "config": config_data,
            "system_data": {
                "enabled": enabled,
                "priority": priority,
                "config": config_data
            }
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
            plugin_dir = _resolve_plugin_base_dir() / plugin_name
            
            if not plugin_dir.exists():
                raise HTTPException(status_code=404, detail=f"Plugin {plugin_name} not found")
            
            # Load plugin manifest to get author and default_config (for cleaning upload blobs)
            author = "Unknown"
            name = plugin_name
            manifest_default_config: Optional[Dict[str, Any]] = None
            
            if plugin_manifest_exists(plugin_dir):
                try:
                    thread_pool = getattr(app, 'blocking_task_pool', None)
                    metadata = await _load_plugin_manifest_async(plugin_dir, thread_pool)
                    author = metadata.get('author', 'Unknown')
                    name = metadata.get('name', plugin_name)
                    manifest_default_config = metadata.get("default_config") or None
                except Exception as e:
                    logger.warning(f"Failed to read plugin manifest: {e}")
            
            # Delete from database (order: config-file uploads -> settings -> plugin-scoped binaries)
            if db_manager:
                # 0. Web UI uploaded config files stored in this plugin's private binary storage
                try:
                    existing = await db_manager.get_plugin_setting(author, name)
                    await db_manager.delete_plugin_config_upload_blobs(
                        f"{author}/{name}",
                        existing.config if existing else None,
                        manifest_default_config,
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete plugin config upload blobs: {e}")
                
                # 1. Delete plugin settings
                deleted = await db_manager.delete_plugin_setting(author, name)
                if deleted:
                    logger.info(f"Deleted plugin {author}/{name} settings from database")
                else:
                    logger.warning(f"Plugin {author}/{name} settings not found in database")
                
                # 2. Delete all binary storage data for this plugin (runtime plugin API storage)
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
        http_request: Request,
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
        
        # Helper function to get author from metadata.yaml
        async def get_plugin_author(plugin_name: str) -> tuple[str, str]:
            """Get author and name from plugin manifest. Returns (author, name)."""
            plugin_dir = _resolve_plugin_base_dir() / plugin_name
            
            if plugin_manifest_exists(plugin_dir):
                try:
                    thread_pool = getattr(app, 'blocking_task_pool', None)
                    metadata = await _load_plugin_manifest_async(plugin_dir, thread_pool)
                    author = metadata.get('author', 'Unknown')
                    name = metadata.get('name', plugin_name)
                    return author, name
                except Exception as e:
                    logger.warning(f"Failed to read plugin manifest for {plugin_name}: {e}")
            
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
            details = await _request_audit_details(http_request)
            await get_audit_logger().log_access_denied(
                username=username,
                resource=f"plugin:{plugin_name}",
                action=action.action,
                reason="Insufficient permissions",
                ip_address=details.get("ip"),
                details=details,
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
        """Reload all plugins and update their metadata from manifest files to database."""
        from ..core.app import get_app
        from pathlib import Path
        import json
        
        username = user.get("username", "unknown")
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        
        updated_count = 0
        created_count = 0
        failed_plugins = []
        
        # Get thread pool for file operations
        app = get_app()
        thread_pool = getattr(app, 'blocking_task_pool', None)
        
        # Scan all plugins and update database
        if db_manager:
            plugin_base = _resolve_plugin_base_dir()
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
                    if not plugin_manifest_exists(plugin_dir):
                        continue
                    
                    try:
                        plugin_metadata = await _load_plugin_manifest_async(plugin_dir, thread_pool)
                        
                        author = plugin_metadata.get('author', 'Unknown')
                        name = plugin_metadata.get('name', plugin_dir.name)
                        version = plugin_metadata.get('version', '1.0.0')
                        default_config = plugin_metadata.get('default_config', {})
                        priority = coerce_plugin_priority(plugin_metadata.get('priority'), 100)
                        
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
                                priority=priority,
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
        
        app = get_app()
        db_manager = app.db_manager if hasattr(app, 'db_manager') and app.db_manager else None
        plugin_connector = app.plugin_connector if hasattr(app, 'plugin_connector') and app.plugin_connector else None
        
        if not db_manager:
            raise HTTPException(status_code=500, detail="Database manager not available")

        identity = await _resolve_plugin_identity(plugin_name, app)
        plugin_metadata = identity["manifest"]
        config_schema = plugin_metadata.get("config_schema", {})
        default_config = plugin_metadata.get("default_config", {})
        author = identity["author"]
        name = identity["name"]
        plugin_owner = identity["plugin_owner"]
        
        normalized_config = normalize_plugin_config_by_schema(
            config_update.config,
            config_schema,
            default_config,
        )
        
        # Save config to database
        updated_config = normalized_config  # Default to normalized_config
        try:
            setting = await db_manager.get_plugin_setting(author, name)
            previous_config = setting.config if setting and setting.config else {}
            
            # Get priority: request > database > metadata.yaml > default (100)
            priority_from_manifest = plugin_metadata.get('priority')
            
            # Priority: request priority (if provided) > current database value > metadata.yaml > default
            # If user explicitly sets priority, always use it (even if it's 100)
            if hasattr(config_update, 'priority') and config_update.priority is not None:
                # User explicitly set priority, use it
                priority = config_update.priority
            elif setting:
                # No priority in request, use database value (even if it's 100)
                priority = setting.priority
            elif priority_from_manifest is not None:
                # No database setting, use metadata.yaml
                priority = priority_from_manifest
            else:
                # Default to 100
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
                # Update existing setting (always update priority if provided in request)
                update_data = {'config': normalized_config}
                # Always update priority if it was provided in the request
                if hasattr(config_update, 'priority') and config_update.priority is not None:
                    update_data['priority'] = config_update.priority
                await db_manager.update_plugin_setting(author, name, **update_data)
            
            logger.info(f"Updated config for plugin {author}/{name}, priority={priority}")
            
            # Get the updated config and priority from database to return to frontend
            updated_setting = await db_manager.get_plugin_setting(author, name)
            if updated_setting:
                if updated_setting.config:
                    updated_config = updated_setting.config
                # Get the actual saved priority from database
                saved_priority = updated_setting.priority
            else:
                saved_priority = priority

            removed_upload_keys = (
                collect_plugin_config_upload_keys(previous_config)
                - collect_plugin_config_upload_keys(normalized_config)
            )
            if removed_upload_keys:
                await db_manager.delete_plugin_config_upload_keys(plugin_owner, removed_upload_keys)
            
            # Reload only this plugin in runtime (avoids full subprocess restart)
            if plugin_connector:
                try:
                    await plugin_connector.reload_plugin(f"{author}/{name}")
                except Exception as e:
                    logger.warning(f"Failed to reload plugin after config update: {e}")
            
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save plugin config: {str(e)}")
        
        await get_audit_logger().log_plugin_action(
            "configure",
            plugin_name,
            user.get("username"),
            True,
            {"config": normalized_config, "priority": saved_priority}
        )
        
        # Return updated config and priority so frontend doesn't need to reload
        return {
            "message": "Configuration updated successfully",
            "config": updated_config,
            "priority": saved_priority
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
    
    @app.post("/api/plugins/{plugin_name}/config-files")
    async def upload_plugin_config_file(
        plugin_name: str,
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

        identity = await _resolve_plugin_identity(plugin_name, app)
        plugin_owner = identity["plugin_owner"]
        
        # Check file size (10MB limit)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Generate unique file key with original extension
        original_filename = file.filename or "file"
        _, ext = os.path.splitext(original_filename)
        file_key = f'plugin_config_{uuid.uuid4().hex}{ext}'
        
        # Save file using plugin-private binary storage.
        try:
            await db_manager.set_binary('plugin', plugin_owner, file_key, file_bytes)
            logger.info(
                f"Uploaded plugin config file: {file_key}, size: {len(file_bytes)} bytes, plugin={plugin_owner}"
            )
            return {"file_key": file_key}
        except Exception as e:
            logger.error(f"Failed to save config file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    @app.delete("/api/plugins/{plugin_name}/config-files/{file_key}")
    async def delete_plugin_config_file(
        plugin_name: str,
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

        identity = await _resolve_plugin_identity(plugin_name, app)
        plugin_owner = identity["plugin_owner"]
        
        try:
            success = await db_manager.delete_binary('plugin', plugin_owner, file_key)
            if success:
                logger.info(f"Deleted plugin config file: {file_key}, plugin={plugin_owner}")
                return {"deleted": True}
            else:
                raise HTTPException(status_code=404, detail="File not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete config file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    
    @app.get("/api/plugins/install-progress/{task_id}")
    async def get_plugin_install_progress(
        task_id: str,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get plugin installation progress via SSE."""
        async def event_generator():
            while True:
                if task_id in _plugin_install_progress:
                    progress_data = _plugin_install_progress[task_id]
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    
                    # If completed or failed, close connection
                    if progress_data.get('status') in ['completed', 'failed']:
                        # Clean up after a delay
                        await asyncio.sleep(1)
                        _plugin_install_progress.pop(task_id, None)
                        break
                else:
                    # Task not found
                    yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                    break
                
                await asyncio.sleep(0.5)  # Update every 500ms
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
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
        
        # Generate task ID for progress tracking
        task_id = str(uuid.uuid4())
        _plugin_install_progress[task_id] = {
            'status': 'downloading',
            'progress': 0,
            'message': '开始下载...'
        }
        
        # Download ZIP from GitHub with progress tracking
        download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / f"{repo}.zip"
            
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                    logger.info(f"Downloading plugin from GitHub: {owner}/{repo}")
                    
                    # Try main branch first
                    async with client.stream('GET', download_url) as response:
                        # Try master branch if main doesn't exist
                        if response.status_code == 404:
                            download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip"
                            async with client.stream('GET', download_url) as response2:
                                response2.raise_for_status()
                                total_size = int(response2.headers.get('content-length', 0))
                                zip_path = await _download_with_progress(response2, task_id, total_size, zip_path)
                        else:
                            response.raise_for_status()
                            total_size = int(response.headers.get('content-length', 0))
                            zip_path = await _download_with_progress(response, task_id, total_size, zip_path)
                            
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to download plugin from GitHub: {e}")
                _plugin_install_progress[task_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': f'下载失败: HTTP {e.response.status_code}'
                }
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to download from GitHub. Please check the repository URL and ensure it's public."
                )
            except Exception as e:
                logger.error(f"Error downloading plugin: {e}")
                _plugin_install_progress[task_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': f'下载错误: {str(e)}'
                }
                raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")
            
            # Install plugin
            try:
                _plugin_install_progress[task_id] = {
                    'status': 'installing',
                    'progress': 90,
                    'message': '正在安装插件...'
                }
                
                result = await _install_plugin_from_zip(zip_path, config, db_manager, plugin_connector, user)
                
                _plugin_install_progress[task_id] = {
                    'status': 'completed',
                    'progress': 100,
                    'message': '安装完成！',
                    'result': result
                }
                
                # Log action
                await get_audit_logger().log_plugin_action(
                    action="install_from_github",
                    plugin_name=result.get('plugin_name', repo),
                    username=username,
                    success=True,
                    details={"repo": f"{owner}/{repo}"}
                )
                
                return {"task_id": task_id, **result}
            except Exception as e:
                _plugin_install_progress[task_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': f'安装失败: {str(e)}'
                }
                await get_audit_logger().log_plugin_action(
                    action="install_from_github",
                    plugin_name=repo,
                    username=username,
                    success=False,
                    details={"repo": f"{owner}/{repo}", "error": str(e)}
                )
                raise
    
    async def _download_with_progress(response, task_id: str, total_size: int, zip_path: Path):
        """Download file with progress tracking."""
        downloaded = 0
        
        with open(zip_path, 'wb') as f:
            async for chunk in response.aiter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                
                if total_size > 0:
                    progress = int((downloaded / total_size) * 90)  # 90% for download, 10% for install
                    _plugin_install_progress[task_id] = {
                        'status': 'downloading',
                        'progress': progress,
                        'message': f'下载中... {downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB'
                    }
                else:
                    # If total size is unknown, show indeterminate progress
                    _plugin_install_progress[task_id] = {
                        'status': 'downloading',
                        'progress': min(90, downloaded // 1024 // 1024),  # Rough estimate
                        'message': f'下载中... {downloaded // 1024 // 1024}MB'
                    }
        
        return zip_path
    
    async def _install_plugin_from_zip(zip_path: Path, config, db_manager, plugin_connector, user):
        """Helper function to install plugin from ZIP file.
        
        Standard plugin repository structure:
          repo/
            main/         <- plugin content always lives here
              metadata.yaml
              settings.json
              main.py
              ...
            README.md     <- anything else can go outside main/
        
        GitHub ZIP extracts to: repo-name-branch/main/metadata.yaml
        Plain ZIP should contain: main/metadata.yaml and main/settings.json
        (or wrap in one folder: folder/main/metadata.yaml and folder/main/settings.json)
        """
        extract_dir = zip_path.parent / "extracted"
        extract_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP file")
        
        # Find plugin directory: always located in a `main/` subdirectory.
        # GitHub ZIP format: extracted/repo-branch/main/metadata.yaml + settings.json
        # Plain ZIP format:  extracted/main/metadata.yaml + settings.json
        #                or  extracted/any-folder/main/metadata.yaml + settings.json
        plugin_dir = None
        
        # Check direct: extracted/main/metadata.yaml + settings.json
        candidate = extract_dir / "main"
        if plugin_manifest_exists(candidate):
            plugin_dir = extract_dir / "main"
            logger.info("Found plugin in main/ (direct structure)")
        else:
            # Check one level deep: extracted/repo-branch/main/metadata.yaml + settings.json
            first_level_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            for first_dir in first_level_dirs:
                candidate = first_dir / "main"
                if plugin_manifest_exists(candidate):
                    plugin_dir = first_dir / "main"
                    logger.info(f"Found plugin in {first_dir.name}/main/ (GitHub ZIP structure)")
                    break
        
        if not plugin_dir:
            raise HTTPException(
                status_code=400,
                detail=(
                    "未找到插件内容。插件仓库必须将所有插件文件放在 main/ 子目录中，"
                    "例如：仓库根/main/metadata.yaml、仓库根/main/settings.json、仓库根/main/main.py。"
                    "GitHub ZIP 格式：repo-branch/main/metadata.yaml。"
                )
            )
        
        plugin_folder_name = plugin_dir.name  # always "main"
        
        # Validate and parse plugin manifest using thread pool
        try:
            app = get_app()
            thread_pool = getattr(app, 'blocking_task_pool', None)
            plugin_metadata = await _load_plugin_manifest_async(plugin_dir, thread_pool)
                
            plugin_author = plugin_metadata.get('author', 'Unknown')
            plugin_name = plugin_metadata['name']
            plugin_version = plugin_metadata['version']
            default_config = plugin_metadata.get('default_config', {})
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid settings.json format")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading plugin manifest: {str(e)}")
        
        # Target directory: plugins/{name}
        target_dir = _resolve_plugin_base_dir() / plugin_name
        
        # Copy to plugin directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        # Ensure parent directory exists
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        # Copy the plugin directory
        shutil.copytree(plugin_dir, target_dir)
        
        # Auto-install dependencies
        from src.plugins.runtime.connector import install_plugin_dependencies
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
                # Get priority from metadata.yaml if available, otherwise use default 100
                priority_from_manifest = plugin_metadata.get('priority')
                initial_priority = priority_from_manifest if priority_from_manifest is not None else 100
                
                await db_manager.create_plugin_setting(
                    author=plugin_author,
                    name=plugin_name,
                    enabled=False,
                    priority=initial_priority,
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
                # Load schema from split manifest files first to get correct author
                thread_pool = getattr(app, 'blocking_task_pool', None)
                author = "Unknown"
                name = plugin_name
                
                plugin_dir = _resolve_plugin_base_dir() / name
                
                config_schema = {}
                default_config = {}
                
                if plugin_manifest_exists(plugin_dir):
                    plugin_data = await _load_plugin_manifest_async(plugin_dir, thread_pool)
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
                
                if plugin_manifest_exists(plugin_dir):
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
            
            # 
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
            #  access_token  token 
            update_data["onebot_access_token"] = config_update["access_token"]
        if "secret" in config_update:
            #  secret 
            update_data["onebot_secret"] = config_update["secret"]
        if "version" in config_update:
            update_data["onebot_version"] = config_update["version"]
        
        # Update configuration in TOML file
        # Find config.toml file in project root (go up from src/ui/api.py to onebot_framework/)
        # api.py is at: onebot_framework/src/ui/api.py
        # config.toml is at: onebot_framework/config.toml
        toml_file = get_config_file_path()
        
        # Read existing TOML file
        # Use tomlkit to preserve comments and formatting
        try:
            import tomlkit
        except ImportError:
            logger.error("tomlkit is not installed. Please install it: pip install tomlkit")
            raise HTTPException(
                status_code=500,
                detail="TOML support not available. Please install tomlkit to preserve comments."
            )
        
        # Use thread pool for synchronous file IO
        app = get_app()
        thread_pool = getattr(app, 'blocking_task_pool', None)
        
        config_data = {}
        if toml_file.exists():
            if thread_pool:
                def read_toml_file():
                    with open(toml_file, "r", encoding="utf-8") as f:
                        return tomlkit.load(f)
                config_data = await thread_pool.run_in_executor(read_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "r", encoding="utf-8") as f:
                    config_data = tomlkit.load(f)
        
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
        
        # Write back to TOML file using thread pool (tomlkit preserves comments)
        if thread_pool:
            def write_toml_file():
                with open(toml_file, "w", encoding="utf-8") as f:
                    tomlkit.dump(config_data, f)
            await thread_pool.run_in_executor(write_toml_file)
        else:
            # Fallback to sync operation if thread pool not available
            with open(toml_file, "w", encoding="utf-8") as f:
                tomlkit.dump(config_data, f)
        
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
        after_row_id: Optional[int] = None,
        include_notices: bool = True,
        include_requests: bool = True,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get message log from persistent DB, including messages, notices, and requests."""
        limit = max(1, min(int(limit or 100), 500))
        db_manager = get_database_manager()
        rows = await db_manager.list_message_events(
            limit=limit,
            after_row_id=after_row_id,
            include_notices=include_notices,
            include_requests=include_requests,
        )

        all_events = []
        self_message_ids = {
            str((row.payload or {}).get("message_id", "")).strip()
            for row in rows
            if row.event_name == "onebot.message"
            and isinstance(row.payload, dict)
            and bool((row.payload or {}).get("is_self"))
            and str((row.payload or {}).get("message_id", "")).strip()
        }
        for row in rows:
            payload = row.payload
            if not isinstance(payload, dict):
                continue
            
            event_data = None
            
            # Message events
            if row.event_name in ("onebot.message", "onebot.message_sent"):
                message_id = str(payload.get("message_id", "")).strip()
                # Avoid duplicate self-sent rows when both onebot.message and onebot.message_sent exist.
                if (
                    row.event_name == "onebot.message_sent"
                    and message_id
                    and message_id in self_message_ids
                ):
                    continue

                raw_text = payload.get("raw_message") or payload.get("message") or ""
                sender = payload.get("sender", {})
                if not isinstance(sender, dict):
                    sender = {}
                if row.event_name == "onebot.message_sent" and not sender.get("nickname"):
                    sender["nickname"] = "Bot"

                event_data = {
                    "id": row.event_id,
                    "db_row_id": row.id,
                    "timestamp": row.event_time.isoformat(),
                    "time": row.event_time.isoformat(),
                    "event_type": "message",
                    "post_type": "message_sent" if row.event_name == "onebot.message_sent" else "message",
                    "message_id": message_id,
                    "message_type": payload.get("message_type", "unknown"),
                    "user_id": str(payload.get("user_id", "")),
                    "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                    "target_id": str(payload.get("target_id", "")) if payload.get("target_id") else None,
                    "raw_message": raw_text,
                    "message": raw_text,
                    "sender": sender,
                    "is_self": payload.get("is_self", row.event_name == "onebot.message_sent"),  # Mark if self-sent
                    "source_plugin": payload.get("source_plugin"),
                    "source": payload.get("source"),
                }
            
            # Notice events
            elif row.event_name == "onebot.notice" and include_notices:
                # Debug log to see what we're receiving
                logger.debug(f"Formatting notice event: {payload.get('notice_type', 'NO_TYPE')} | payload keys: {list(payload.keys())}")
                
                formatted_text = _format_notice_event(payload)
                event_data = {
                    "id": row.event_id,
                    "db_row_id": row.id,
                    "timestamp": row.event_time.isoformat(),
                    "time": row.event_time.isoformat(),
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
            elif row.event_name == "onebot.request" and include_requests:
                formatted_text = _format_request_event(payload)
                event_data = {
                    "id": row.event_id,
                    "db_row_id": row.id,
                    "timestamp": row.event_time.isoformat(),
                    "time": row.event_time.isoformat(),
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

        return all_events

    @app.get("/api/messages/session-log")
    async def get_session_message_log(
        limit: int = 300,
        include_notices: bool = True,
        include_requests: bool = True,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get only the current-startup message stream for the message log page."""
        return _session_message_log_store.list_events(
            limit=limit,
            include_notices=include_notices,
            include_requests=include_requests,
        )
    
    @app.websocket("/ws/messages")
    async def websocket_messages(websocket: WebSocket):
        """WebSocket endpoint for real-time message updates."""
        await _ws_manager.connect(websocket)
        try:
            # Keep connection alive and handle incoming messages (e.g., ping/pong)
            # Use asyncio.wait to handle both receive and timeout
            ping_interval = 30  # Send ping every 30 seconds to keep connection alive
            
            while True:
                try:
                    # Wait for message with timeout to allow periodic ping
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=ping_interval
                        )
                        # Echo back for keep-alive - send as JSON to match frontend expectations
                        if data == "ping":
                            await websocket.send_json({"type": "pong"})
                    except asyncio.TimeoutError:
                        # Timeout reached, send ping to keep connection alive
                        try:
                            await websocket.send_json({"type": "ping"})
                        except Exception as ping_error:
                            # If ping fails, connection is likely dead
                            logger.debug(f"Failed to send ping, connection may be dead: {ping_error}")
                            break
                except WebSocketDisconnect:
                    logger.debug("WebSocket client disconnected normally")
                    break
                except Exception as e:
                    # Log error but don't break immediately - some errors are recoverable
                    error_msg = str(e)
                    if "1000" in error_msg or "1001" in error_msg:
                        # Normal closure codes, break gracefully
                        logger.debug(f"WebSocket closed normally: {e}")
                        break
                    else:
                        logger.warning(f"WebSocket error (will retry): {e}")
                        # Wait a bit before breaking to avoid rapid reconnection loops
                        await asyncio.sleep(1)
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
        
        contacts = {
            "groups": [],
            "friends": []
        }
        
        try:
            app_instance = get_app()
            
            if not hasattr(app_instance, 'onebot_adapter') or not app_instance.onebot_adapter:
                logger.warning("OneBot adapter not available")
                return contacts
            
            # Check if adapter is running
            if not hasattr(app_instance.onebot_adapter, '_running') or not app_instance.onebot_adapter._running:
                logger.warning("OneBot adapter is not running")
                return contacts
            
            # Get group list with retry mechanism
            groups = []
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    group_result = await asyncio.wait_for(
                        app_instance.onebot_adapter.call_api("get_group_list", {}),
                        timeout=10.0
                    )
                    if isinstance(group_result, dict) and "data" in group_result:
                        groups = group_result["data"]
                    elif isinstance(group_result, list):
                        groups = group_result
                    else:
                        groups = []
                    break  # Success, exit retry loop
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.warning(f"Timeout getting group list (attempt {attempt + 1}/{max_retries}), retrying...")
                        await asyncio.sleep(1)  # Wait 1 second before retry
                    else:
                        logger.error("Timeout getting group list after all retries")
                except asyncio.CancelledError as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Group list call cancelled (attempt {attempt + 1}/{max_retries}), "
                            f"likely OneBot reconnect: {e}; retrying..."
                        )
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning("Group list call cancelled after all retries; returning empty group list")
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to get group list (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"Failed to get group list after all retries: {e}", exc_info=True)
            
            for group in groups:
                contacts["groups"].append({
                    "id": str(group.get("group_id", "")),
                    "name": group.get("group_name", "未知群"),
                    "avatar": f"http://p.qlogo.cn/gh/{group.get('group_id', '')}/{group.get('group_id', '')}/640/",
                    "member_count": group.get("member_count", 0),
                    "max_member_count": group.get("max_member_count", 0)
                })
            
            # Get friend list with retry mechanism
            friends = []
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    friend_result = await asyncio.wait_for(
                        app_instance.onebot_adapter.call_api("get_friend_list", {}),
                        timeout=10.0
                    )
                    if isinstance(friend_result, dict) and "data" in friend_result:
                        friends = friend_result["data"]
                    elif isinstance(friend_result, list):
                        friends = friend_result
                    else:
                        friends = []
                    break  # Success, exit retry loop
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.warning(f"Timeout getting friend list (attempt {attempt + 1}/{max_retries}), retrying...")
                        await asyncio.sleep(1)  # Wait 1 second before retry
                    else:
                        logger.error("Timeout getting friend list after all retries")
                except asyncio.CancelledError as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Friend list call cancelled (attempt {attempt + 1}/{max_retries}), "
                            f"likely OneBot reconnect: {e}; retrying..."
                        )
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning("Friend list call cancelled after all retries; returning empty friend list")
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to get friend list (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"Failed to get friend list after all retries: {e}", exc_info=True)
            
            for friend in friends:
                contacts["friends"].append({
                    "id": str(friend.get("user_id", "")),
                    "name": friend.get("nickname", "") or friend.get("remark", "") or "未知好友",
                    "avatar": f"http://q.qlogo.cn/headimg_dl?dst_uin={friend.get('user_id', '')}&spec=640",
                    "remark": friend.get("remark", "")
                })
                
        except asyncio.CancelledError as e:
            logger.warning(f"Contacts request cancelled or interrupted during OneBot reconnect: {e}")
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}", exc_info=True)
        
        return contacts
    
    @app.post("/api/chat/send")
    async def send_chat_message(
        request: Dict[str, Any],
        http_request: Request,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Send a message to group or friend."""
        from ..core.app import get_app
        app_instance = get_app()
        
        chat_type = request.get("type")  # "group" or "private"
        chat_id = request.get("id")  # group_id or user_id
        message = request.get("message")
        request_username = str(user.get("username") or "unknown").strip() or "unknown"
        send_source = f"webui:{request_username}"
        
        if not all([chat_type, chat_id, message]):
            raise HTTPException(status_code=400, detail="Missing required fields: type, id, message")
        
        if not hasattr(app_instance, 'onebot_adapter') or not app_instance.onebot_adapter:
            raise HTTPException(status_code=503, detail="OneBot adapter not available")

        async def rewrite_media_cq_for_send(raw_message: str) -> tuple[str, str]:
            """Prepare CQ media for OneBot send and WebUI display separately."""
            if not isinstance(raw_message, str) or "[CQ:" not in raw_message:
                return raw_message, raw_message

            from ..ui.image_cache import get_image_cache_manager
            import re
            import base64
            import binascii
            from urllib.parse import unquote_to_bytes

            image_cache = get_image_cache_manager()
            cq_pattern = re.compile(r"\[CQ:(image|video|record|file),([^\]]+)\]")

            def parse_params(params_str: str) -> Dict[str, str]:
                params: Dict[str, str] = {}
                allowed_keys = {
                    "file",
                    "url",
                    "type",
                    "cache",
                    "proxy",
                    "timeout",
                    "name",
                    "id",
                    "size",
                    "md5",
                    "sha1",
                    "sub_type",
                    "summary",
                }
                key_pattern = re.compile(r"(?:^|,)([A-Za-z_][A-Za-z0-9_-]*)=")
                key_matches = list(key_pattern.finditer(params_str))
                key_matches = [m for m in key_matches if m.group(1).strip() in allowed_keys]
                for idx, m in enumerate(key_matches):
                    key = m.group(1).strip()
                    value_start = m.end()
                    value_end = key_matches[idx + 1].start() if idx + 1 < len(key_matches) else len(params_str)
                    value = params_str[value_start:value_end].strip()
                    if value.endswith(","):
                        value = value[:-1]
                    if key and value:
                        params[key] = value
                return params

            def build_cq(cq_type: str, params: Dict[str, str]) -> str:
                parts = [f"{k}={v}" for k, v in params.items() if v is not None and str(v).strip() != ""]
                return f"[CQ:{cq_type}{',' + ','.join(parts) if parts else ''}]"

            def data_url_to_base64_file(data_url: str) -> Optional[str]:
                match = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data_url, re.DOTALL)
                if not match:
                    return None
                is_base64 = bool(match.group(2))
                payload = match.group(3) or ""
                if is_base64:
                    try:
                        base64.b64decode(payload, validate=True)
                        return f"base64://{payload}"
                    except (binascii.Error, ValueError):
                        return None
                try:
                    return f"base64://{base64.b64encode(unquote_to_bytes(payload)).decode('ascii')}"
                except Exception:
                    return None

            send_out: List[str] = []
            display_out: List[str] = []
            last = 0
            for match in cq_pattern.finditer(raw_message):
                send_out.append(raw_message[last:match.start()])
                display_out.append(raw_message[last:match.start()])
                cq_type = match.group(1)
                params_str = match.group(2)
                params = parse_params(params_str)

                media_ref = (params.get("url") or params.get("file") or "").strip()
                if not media_ref:
                    send_out.append(match.group(0))
                    display_out.append(match.group(0))
                    last = match.end()
                    continue

                media_kind_map = {
                    "image": "image",
                    "video": "video",
                    "record": "record",
                    "file": "file",
                }
                media_kind = media_kind_map.get(cq_type, "file")

                send_params = dict(params)
                display_params = dict(params)
                cached_path = None
                if media_ref.startswith("data:"):
                    cached_path = await image_cache.save_data_url_media(media_ref, media_kind=media_kind)
                    base64_ref = data_url_to_base64_file(media_ref)
                    if base64_ref:
                        send_params["file"] = base64_ref
                        send_params.pop("url", None)
                else:
                    # Keep the original outgoing ref. NapCat may run in Docker/Linux and cannot read
                    # framework-local Windows file:// paths. Cache only for WebUI display/history.
                    cached_path = await image_cache.download_and_cache_media(
                        media_ref,
                        onebot_adapter=app_instance.onebot_adapter,
                        media_kind=media_kind,
                    )

                if cached_path and Path(cached_path).exists():
                    display_params["file"] = Path(cached_path).resolve().as_uri()
                    display_params.pop("url", None)
                    display_out.append(build_cq(cq_type, display_params))
                else:
                    display_out.append(match.group(0))

                send_out.append(build_cq(cq_type, send_params))
                last = match.end()

            send_out.append(raw_message[last:])
            display_out.append(raw_message[last:])
            return "".join(send_out), "".join(display_out)

        async def get_bot_identity() -> Dict[str, str]:
            """Best-effort bot identity lookup; never block sending if OneBot lookup is flaky."""
            adapter = app_instance.onebot_adapter
            self_id = str(getattr(adapter, "self_id", "") or "")
            self_nickname = str(getattr(adapter, "self_nickname", "") or "Bot")

            try:
                login_info = await asyncio.wait_for(
                    adapter.call_api("get_login_info", {}, source=send_source),
                    timeout=5.0,
                )
                login_data = login_info.get("data", login_info) if isinstance(login_info, dict) else {}
                if isinstance(login_data, dict):
                    self_id = str(login_data.get("user_id") or self_id or "")
                    self_nickname = str(login_data.get("nickname") or self_nickname or "Bot")
            except asyncio.TimeoutError:
                logger.warning("Timed out getting bot login info before WebUI send; continuing with cached identity")
            except Exception as e:
                logger.warning(f"Unable to get bot login info before WebUI send; continuing with cached identity: {e}")

            return {
                "self_id": self_id,
                "self_nickname": self_nickname or "Bot",
                "avatar": f"https://q.qlogo.cn/headimg_dl?dst_uin={self_id}&spec=640" if self_id else "",
            }
        
        try:
            # Uploaded browser images are sent to OneBot as base64://, while WebUI history uses local cache paths.
            message, display_message = await rewrite_media_cq_for_send(message)
            bot_identity = await get_bot_identity()
            self_id = bot_identity["self_id"]
            self_nickname = bot_identity["self_nickname"]
            sender_payload = {
                "user_id": self_id,
                "nickname": self_nickname,
                "card": "",
                "role": "owner",
                "avatar": bot_identity["avatar"],
            }
            
            # Send message
            if chat_type == "group":
                result = await app_instance.onebot_adapter.call_api(
                    "send_group_msg",
                    {
                        "group_id": int(chat_id),
                        "message": message,
                        "_xq_meta": {
                            "self_id": self_id,
                            "self_nickname": self_nickname,
                            "sender": sender_payload,
                            "display_message": display_message,
                        },
                    },
                    source=send_source,
                )
            elif chat_type == "private":
                result = await app_instance.onebot_adapter.call_api(
                    "send_private_msg",
                    {
                        "user_id": int(chat_id),
                        "message": message,
                        "_xq_meta": {
                            "self_id": self_id,
                            "self_nickname": self_nickname,
                            "sender": sender_payload,
                            "display_message": display_message,
                        },
                    },
                    source=send_source,
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
            
            message_obj = {
                "id": f"sent-{message_id or uuid.uuid4()}",
                "db_row_id": None,
                "timestamp": datetime.now().isoformat(),
                "message_id": str(message_id or ""),
                "message_type": chat_type,
                "user_id": str(self_id),
                "target_id": str(chat_id) if chat_type == "private" else None,
                "group_id": str(chat_id) if chat_type == "group" else None,
                "message": display_message,
                "sender": sender_payload,
                "is_self": True,
                "source": send_source,
            }

            await get_audit_logger().log_webui_action(
                username=request_username,
                action="send_message",
                resource=f"chat:{chat_type}:{chat_id}",
                success=True,
                ip_address=_client_ip_from_request(http_request),
                details={
                    "chat_type": chat_type,
                    "chat_id": str(chat_id),
                    "message": display_message,
                    "message_id": str(message_id or ""),
                    "source": send_source,
                },
            )
            
            return {
                "success": True,
                "message_id": message_id,
                "message": message_obj
            }
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    
    @app.get("/api/chat/media-proxy")
    async def proxy_chat_media(
        kind: str = "image",
        url: str = None,
        file: str = None,
    ):
        """Proxy chat media (image/video/record/file) via local cache for stable display."""
        from ..ui.image_cache import get_image_cache_manager
        from fastapi.responses import FileResponse, Response
        import httpx
        import mimetypes
        from urllib.parse import unquote, urlparse

        def _media_type_for_path(path: str) -> str:
            suffix = Path(path).suffix.lower()
            if suffix == ".amr":
                return "audio/amr"
            if suffix == ".silk":
                return "audio/x-silk"
            guessed, _ = mimetypes.guess_type(path)
            return guessed or "application/octet-stream"
        
        try:
            media_ref = file if (kind or "image").strip().lower() == "record" and file else (url or file)
            if not media_ref:
                raise HTTPException(status_code=400, detail="Missing 'url' or 'file' parameter")

            media_kind = (kind or "image").strip().lower()
            if media_kind not in {"image", "video", "record", "file"}:
                media_kind = "image"

            image_cache = get_image_cache_manager()

            # URL decode if needed
            if media_ref.startswith("http%3A") or media_ref.startswith("https%3A") or media_ref.startswith("file%3A"):
                media_ref = unquote(media_ref)

            # Serve local file:// path directly
            if media_ref.startswith("file://"):
                local_path = Path(urlparse(media_ref).path)
                if not local_path.exists() and media_ref.startswith("file:///") and len(media_ref) > 8:
                    # Windows compatibility: /C:/...
                    local_path = Path(media_ref.replace("file:///", "", 1))
                if local_path.exists() and local_path.is_file():
                    serve_path = str(local_path)
                    if media_kind == "record":
                        serve_path = await image_cache.ensure_browser_playable_record(serve_path)
                    return FileResponse(serve_path, media_type=_media_type_for_path(serve_path))

            onebot_adapter = None
            app = get_app()
            if app and hasattr(app, "onebot_adapter"):
                onebot_adapter = app.onebot_adapter

            # For QQ voice, prefer OneBot-side conversion (no local ffmpeg required).
            if media_kind == "record" and file and onebot_adapter:
                fail_until = float(_record_proxy_fail_until.get(file, 0.0) or 0.0)
                now_ts = time.time()
                skip_get_record = fail_until > now_ts
                try:
                    if not skip_get_record:
                        converted = await onebot_adapter.call_api(
                            "get_record",
                            {"file": file, "out_format": "wav"},
                        )
                        converted_ref = None
                        if isinstance(converted, dict):
                            converted_ref = (
                                converted.get("file")
                                or converted.get("url")
                                or (converted.get("data", {}) or {}).get("file")
                                or (converted.get("data", {}) or {}).get("url")
                            )
                        if isinstance(converted_ref, str) and converted_ref.strip():
                            converted_ref = converted_ref.strip()
                            if converted_ref.startswith("http://") or converted_ref.startswith("https://") or converted_ref.startswith("file://"):
                                media_ref = converted_ref
                            else:
                                local_candidate = Path(converted_ref)
                                if local_candidate.exists() and local_candidate.is_file():
                                    media_ref = local_candidate.resolve().as_uri()
                        logger.debug(f"get_record conversion attempted for {file}, using ref: {media_ref[:120]}")
                    else:
                        logger.debug(f"Skipping get_record for recently failed ref: {file}")
                except asyncio.CancelledError as e:
                    # OneBot WS reconnect can cancel pending get_record request.
                    # Degrade gracefully to original media ref instead of failing entire HTTP request.
                    logger.warning(f"get_record conversion cancelled for {file}, fallback to original ref: {e}")
                except Exception as e:
                    message = str(e).lower()
                    if "file not found" in message:
                        # Avoid spamming OneBot get_record for known invalid refs.
                        _record_proxy_fail_until[file] = time.time() + 300.0
                    logger.debug(f"get_record conversion unavailable for {file}: {e}")

            # Try cache
            cached_path = await image_cache.get_cached_media_path(media_ref, media_kind=media_kind)
            if cached_path and Path(cached_path).exists():
                serve_path = cached_path
                if media_kind == "record":
                    serve_path = await image_cache.ensure_browser_playable_record(serve_path)
                return FileResponse(serve_path, media_type=_media_type_for_path(serve_path))

            # Download and cache
            cached_path = await image_cache.download_and_cache_media(
                media_ref,
                onebot_adapter=onebot_adapter,
                media_kind=media_kind,
            )
            if cached_path and Path(cached_path).exists():
                serve_path = cached_path
                if media_kind == "record":
                    serve_path = await image_cache.ensure_browser_playable_record(serve_path)
                return FileResponse(serve_path, media_type=_media_type_for_path(serve_path))

            # Fallback direct proxy (HTTP/HTTPS only)
            if not (media_ref.startswith("http://") or media_ref.startswith("https://")):
                raise HTTPException(status_code=404, detail="Media unavailable")

            headers = {
                "Referer": "https://qzone.qq.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.get(media_ref, headers=headers)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    # Typical case for QQ temp links: expired URLs are expected; don't escalate as 500.
                    body = (response.text or "")[:300].lower()
                    if response.status_code in (400, 403, 404) and "download url has expired" in body:
                        raise HTTPException(status_code=410, detail="Media URL expired")
                    raise HTTPException(status_code=404, detail="Media unavailable")
                return Response(
                    content=response.content,
                    media_type=response.headers.get("content-type", "application/octet-stream")
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to proxy media: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load media: {str(e)}")

    @app.get("/api/chat/image-proxy")
    async def proxy_chat_image(
        url: str = None,
        file: str = None,
    ):
        """Backward-compatible image proxy endpoint."""
        return await proxy_chat_media(kind="image", url=url, file=file)
    
    @app.get("/api/chat/history/{chat_type}/{chat_id}")
    async def get_chat_history(
        chat_type: str,
        chat_id: str,
        limit: int = 50,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get chat history for a specific group or friend from persisted DB."""
        if chat_type not in ("group", "private"):
            raise HTTPException(status_code=400, detail="Invalid chat type")

        db_manager = get_database_manager()
        rows = await db_manager.list_chat_message_events(chat_type, chat_id, limit=limit)

        logger.debug(f"Getting chat history for {chat_type} {chat_id}, total rows: {len(rows)}")

        messages = []
        seen_self_message_ids = set()
        for row in rows:
            payload = row.payload
            if not isinstance(payload, dict):
                continue

            payload_is_self = payload.get("is_self", row.source == "self")
            message_id = str(payload.get("message_id", "")).strip()

            # Double-check filters in Python for type-safety across mixed JSON numeric/string values.
            if chat_type == "group":
                if str(payload.get("group_id", "")) != str(chat_id):
                    continue
            else:
                if payload.get("message_type") != "private":
                    continue
                is_from_user = str(payload.get("user_id", "")) == str(chat_id)
                is_to_user = str(payload.get("target_id", "")) == str(chat_id) and payload_is_self
                if not (is_from_user or is_to_user):
                    continue

            sender = payload.get("sender", {})
            if not isinstance(sender, dict):
                sender = {}

            if payload_is_self and message_id:
                if message_id in seen_self_message_ids:
                    continue
                seen_self_message_ids.add(message_id)

            messages.append({
                "id": row.event_id,
                "db_row_id": row.id,
                "timestamp": row.event_time.isoformat(),
                "message_id": message_id,
                "message_type": payload.get("message_type", chat_type),
                "user_id": str(payload.get("user_id", "") or sender.get("user_id", "")),
                "group_id": str(payload.get("group_id", "")) if payload.get("group_id") else None,
                "target_id": str(payload.get("target_id", "")) if payload.get("target_id") else None,
                "message": payload.get("raw_message") or payload.get("message") or "",
                "sender": sender,
                "is_self": payload_is_self,
                "source_plugin": payload.get("source_plugin"),
                "source": payload.get("source"),
            })

        logger.debug(f"Returning {len(messages)} messages for {chat_type} {chat_id}")
        return messages[-limit:]
    
    @app.get("/api/chat/groups/{group_id}/members")
    async def get_group_members(
        group_id: str,
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get group member list."""
        try:
            app = get_app()
            if not hasattr(app, 'onebot_adapter') or not app.onebot_adapter:
                raise HTTPException(status_code=503, detail="OneBot adapter not available")
            
            # Call get_group_member_list API
            try:
                result = await asyncio.wait_for(
                    app.onebot_adapter.call_api("get_group_member_list", {"group_id": int(group_id)}),
                    timeout=30.0
                )
                
                # Normalize result format
                if isinstance(result, dict) and "data" in result:
                    members = result["data"]
                elif isinstance(result, list):
                    members = result
                else:
                    members = []
                
                # Format member data
                formatted_members = []
                for member in members:
                    formatted_members.append({
                        "user_id": str(member.get("user_id", "")),
                        "nickname": member.get("nickname", ""),
                        "card": member.get("card", ""),
                        "role": member.get("role", "member"),  # owner, admin, member
                        "title": member.get("title", ""),
                        "level": member.get("level", ""),
                        "join_time": member.get("join_time", 0),
                        "last_sent_time": member.get("last_sent_time", 0),
                    })
                
                return {
                    "group_id": group_id,
                    "members": formatted_members,
                    "count": len(formatted_members)
                }
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="Timeout getting group members")
            except Exception as e:
                logger.error(f"Failed to get group members: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to get group members: {str(e)}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get_group_members: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.get("/api/onebot/login-info")
    async def get_login_info(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get OneBot login information."""
        try:
            app = get_app()
            if not hasattr(app, 'onebot_adapter') or not app.onebot_adapter:
                return {
                    "status": "error",
                    "message": "OneBot adapter not available",
                    "data": None
                }
            adapter = app.onebot_adapter
            connection_type = str(getattr(adapter, "connection_type", "http"))
            target = _onebot_target_hint(adapter)
            
            # Check if adapter is running
            if not hasattr(adapter, '_running') or not adapter._running:
                return {
                    "status": "error",
                    "message": "OneBot adapter not running",
                    "connection_type": connection_type,
                    "target": target,
                    "data": None
                }

            # In reverse WS mode, if no reverse client is connected, avoid fallback HTTP noise.
            if connection_type == "ws_reverse" and not getattr(adapter, "_reverse_clients", []):
                return {
                    "status": "error",
                    "message": "Reverse WebSocket client not connected",
                    "reason": "reverse_ws_disconnected",
                    "connection_type": connection_type,
                    "target": target,
                    "data": None
                }
            
            # Call get_login_info API (with timeout to prevent hanging)
            try:
                result = await asyncio.wait_for(
                    adapter.call_api("get_login_info", {}),
                    timeout=10.0
                )
                logger.debug(f"Login info API result: {result}")
                
                return {
                    "status": "ok",
                    "connection_type": connection_type,
                    "target": target,
                    "data": result
                }
            except asyncio.TimeoutError:
                logger.warning("Timeout getting OneBot login info")
                return {
                    "status": "error",
                    "message": "Timeout getting login info",
                    "reason": "timeout",
                    "connection_type": connection_type,
                    "target": target,
                    "data": None
                }
            except Exception as e:
                if _is_expected_onebot_connectivity_error(e):
                    if _should_log_onebot_connectivity_issue():
                        logger.warning(
                            f"OneBot login info unavailable: {e} "
                            f"(type={connection_type}, target={target})"
                        )
                    else:
                        logger.debug(
                            f"OneBot login info still unavailable: {e} "
                            f"(type={connection_type}, target={target})"
                        )
                    return {
                        "status": "error",
                        "message": "OneBot API unreachable",
                        "reason": "connect_error",
                        "connection_type": connection_type,
                        "target": target,
                        "data": None
                    }
                logger.error(f"Failed to get login info: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": str(e),
                    "connection_type": connection_type,
                    "target": target,
                    "data": None
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
            all_plugins = await asyncio.wait_for(
                db_manager.list_plugin_settings(),
                timeout=5.0
            )
            enabled_count = sum(1 for p in all_plugins if p.enabled)

            return {
                "total": len(all_plugins),
                "enabled": enabled_count
            }
        except asyncio.TimeoutError:
            logger.warning("Timeout getting plugin stats")
            return {"total": 0, "enabled": 0}
        except Exception as e:
            logger.warning(f"Failed to get plugin stats: {e}")
            return {"total": 0, "enabled": 0}
    
    @app.get("/api/system/status")
    async def get_system_status(user: Dict[str, Any] = Depends(get_current_user)):
        """Get system status."""
        try:
            import platform
            import psutil
            from datetime import datetime, timedelta
            event_bus = get_event_bus()
            application = get_app()
            config = get_config()
            db_manager = application.db_manager if hasattr(application, 'db_manager') and application.db_manager else None
        except Exception as e:
            logger.error(f"Failed to initialize system status: {e}", exc_info=True)
            # Return minimal status on error
            return {
                "status": "error",
                "error": str(e),
                "event_bus": {"total_events": 0, "today_received": 0, "today_sent": 0},
                "plugins": {"total": 0, "enabled": 0},
                "uptime": "N/A",
                "bot_status": {"online": False, "status_text": "错误"},
            }
        
        # Calculate uptime
        uptime_str = "N/A"
        try:
            if hasattr(application, '_start_time') and application._start_time:
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
        except Exception as e:
            logger.warning(f"Failed to calculate uptime: {e}")
            uptime_str = "N/A"
        
        # Get event bus stats (with error handling)
        try:
            event_stats = event_bus.get_stats() if event_bus else {}
        except Exception as e:
            logger.warning(f"Failed to get event bus stats: {e}")
            event_stats = {}
        
        # Get today's message statistics from event bus counters
        # (These are maintained by event bus and reset at midnight)
        today_received = event_stats.get("today_received", 0)
        today_sent = event_stats.get("today_sent", 0)
        
        # Fallback: If counters not available, count from event history
        try:
            if today_received == 0 and today_sent == 0 and event_bus and hasattr(event_bus, '_event_history'):
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
        except Exception as e:
            logger.debug(f"Error counting messages from event history: {e}")
        
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
        
        # Get plugin stats (with error handling)
        try:
            plugin_stats = await _get_plugin_stats(db_manager)
        except Exception as e:
            logger.warning(f"Failed to get plugin stats: {e}")
            plugin_stats = {"total": 0, "enabled": 0}
        
        # Get bot status (with error handling)
        try:
            bot_status = _get_bot_status(application)
        except Exception as e:
            logger.warning(f"Failed to get bot status: {e}")
            bot_status = {"online": False, "connection_type": None, "status_text": "错误"}
        
        # Get system info (with error handling)
        try:
            system_info = {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
            }
        except Exception as e:
            logger.warning(f"Failed to get system info: {e}")
            system_info = {
                "platform": "Unknown",
                "platform_version": "Unknown",
                "architecture": "Unknown",
                "python_version": "Unknown",
            }
        
        # Get versions (with error handling)
        try:
            versions_info = {
                "framework": config.app_version,
                "onebot": config.onebot_version,
                "webui": "NEXT",  # Vite + React
                "python": platform.python_version(),
                "typescript": "5.2.2",  # From package.json
                "react": "18.2.0",  # From package.json
                "vite": "5.0.8",  # From package.json
            }
        except Exception as e:
            logger.warning(f"Failed to get versions: {e}")
            versions_info = {
                "framework": "Unknown",
                "onebot": "Unknown",
                "webui": "NEXT",
                "python": "Unknown",
            }
        
        return {
            "status": "running" if application.is_running() else "stopped",
            "event_bus": {
                **event_stats,
                "total_events": event_stats.get("total_events_processed", event_stats.get("history_size", 0)),
                "today_received": today_received,
                "today_sent": today_sent,
            },
            "plugins": plugin_stats,
            "uptime": uptime_str,
            "bot_status": bot_status,
            "system": system_info,
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "network": network_info,
            "disk_io": disk_io_info,
            "versions": versions_info
        }

    @app.get("/api/ai/workspace-config")
    async def get_ai_workspace_config(
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get AI workspace configuration."""
        config = get_config()
        mode = str(getattr(config, "ai_workspace_mode", "agent")).strip().lower()
        if mode not in {"agent", "assistant"}:
            mode = "agent"
        return {"mode": mode}

    @app.post("/api/ai/workspace-config")
    async def update_ai_workspace_config(
        config_update: AIWorkspaceConfigUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Update AI workspace configuration."""
        mode = str(config_update.mode).strip().lower()
        if mode not in {"agent", "assistant"}:
            raise HTTPException(status_code=400, detail="Invalid mode, must be 'agent' or 'assistant'")

        toml_file = get_config_file_path()

        try:
            import tomlkit
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="TOML support not available. Please install tomlkit to preserve comments."
            )

        app = get_app()
        thread_pool = getattr(app, 'blocking_task_pool', None)

        if toml_file.exists():
            if thread_pool:
                def read_toml_file():
                    with open(toml_file, "r", encoding="utf-8") as f:
                        return tomlkit.load(f)
                toml_data = await thread_pool.run_in_executor(read_toml_file)
            else:
                with open(toml_file, "r", encoding="utf-8") as f:
                    toml_data = tomlkit.load(f)
        else:
            toml_data = tomlkit.document()

        if "ai_workspace" not in toml_data:
            toml_data["ai_workspace"] = {}
        toml_data["ai_workspace"]["mode"] = mode

        try:
            if thread_pool:
                def write_toml_file():
                    with open(toml_file, "w", encoding="utf-8") as f:
                        tomlkit.dump(toml_data, f)
                await thread_pool.run_in_executor(write_toml_file)
            else:
                with open(toml_file, "w", encoding="utf-8") as f:
                    tomlkit.dump(toml_data, f)
        except Exception as e:
            logger.error(f"Failed to write AI workspace config: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save AI workspace configuration: {str(e)}"
            )

        try:
            config_manager = get_config_manager()
            config_manager.update(ai_workspace_mode=mode)
            reload_config()
        except Exception as e:
            logger.warning(f"Failed to reload config after AI workspace update: {e}")

        return {"message": "AI workspace configuration updated successfully", "mode": mode}

    @app.get("/api/ai/assistant-config")
    async def get_ai_assistant_config(
        user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get Assistant mode configuration."""
        config_path = _get_ai_assistant_config_path()
        if not config_path.exists():
            return {"config": {}}

        app_instance = get_app()
        thread_pool = getattr(app_instance, 'blocking_task_pool', None)

        try:
            if thread_pool:
                def read_config_file():
                    with open(config_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                config = await thread_pool.run_in_executor(read_config_file)
            else:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Assistant config file is invalid JSON: {config_path}")
            return {"config": {}}
        except Exception as e:
            logger.error(f"Failed to read Assistant config: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to read Assistant config: {str(e)}")

        config = _normalize_ai_assistant_preset_references(config if isinstance(config, dict) else {})
        return {"config": assistant_config_for_response(config)}

    @app.post("/api/ai/assistant-config")
    async def update_ai_assistant_config(
        config_update: AIAssistantConfigUpdate,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Persist Assistant mode configuration."""
        config_path = _get_ai_assistant_config_path()
        incoming = _normalize_ai_assistant_preset_references(dict(config_update.config or {}))

        app_instance = get_app()
        thread_pool = getattr(app_instance, 'blocking_task_pool', None)

        try:
            existing_config: Dict[str, Any] = {}
            if config_path.exists():
                def read_existing_config():
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data if isinstance(data, dict) else {}
                if thread_pool:
                    existing_config = await thread_pool.run_in_executor(read_existing_config)
                else:
                    existing_config = read_existing_config()

            payload = assistant_config_for_storage(incoming, existing_config)
            payload["updated_at"] = datetime.now().isoformat()

            if thread_pool:
                def write_config_file():
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2)
                await thread_pool.run_in_executor(write_config_file)
            else:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to write Assistant config: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to save Assistant config: {str(e)}")

        return {"message": "Assistant configuration updated successfully", "config": assistant_config_for_response(payload)}

    @app.post("/api/ai/assistant-memory/clear")
    async def clear_ai_assistant_memory(
        request: AIAssistantMemoryClearRequest,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Clear Assistant session/long memory for a group or private target."""
        scope = str(request.scope or "").strip()
        target_id = str(request.target_id or "").strip()
        memory_type = str(request.memory_type or "").strip()

        if scope not in {"group", "private"}:
            raise HTTPException(status_code=400, detail="scope must be group or private")
        if memory_type not in {"session", "long", "all"}:
            raise HTTPException(status_code=400, detail="memory_type must be session, long or all")
        if not target_id:
            raise HTTPException(status_code=400, detail="target_id is required")

        from ..assistant.runtime import get_assistant_runtime

        cleared = await get_assistant_runtime().clear_memory(scope, target_id, memory_type)
        return {"message": "Assistant memory cleared", "cleared": cleared}

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
            "log_level": config.log_level,
            "plugin_auto_load": config.plugin_auto_load,
            "web_ui_enabled": config.web_ui_enabled,
            "web_ui_username": config.web_ui_username,
            "blocking_task_pool_enabled": getattr(config, 'blocking_task_pool_enabled', True),
            "blocking_task_pool_max_workers": getattr(config, 'blocking_task_pool_max_workers', 0),
        }
        # Add Tencent Cloud TTS config if exists
        config_manager = get_config_manager()
        config_obj = config_manager.get()
        toml_file = get_config_file_path()
        
        tencent_config = {}
        if toml_file.exists():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            
            # Use thread pool for synchronous file IO
            app = get_app()
            thread_pool = getattr(app, 'blocking_task_pool', None)
            
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
            if "plugins" in toml_data:
                plugins_config = toml_data["plugins"]
                safe_config["blocking_task_pool_enabled"] = plugins_config.get("blocking_task_pool_enabled", True)
                safe_config["blocking_task_pool_max_workers"] = int(
                    plugins_config.get("blocking_task_pool_max_workers", 0) or 0
                )
        
        safe_config["tencent_cloud"] = tencent_config
        return safe_config
    
    @app.get("/api/system/threadpool-stats")
    async def get_threadpool_stats(user: Dict[str, Any] = Depends(get_current_user)):
        """Get thread pool statistics."""
        stats = {
            "blocking_task_pool": None
        }

        # Try to get blocking task pool stats
        try:
            from ..core.blocking_task_pool import _blocking_task_pool_manager

            if _blocking_task_pool_manager:
                stats["blocking_task_pool"] = _blocking_task_pool_manager.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get blocking task pool stats: {e}")
        
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
        allowed_keys = [
            "web_ui_enabled",
            "log_level",
            "plugin_auto_load",
            "blocking_task_pool_enabled",
            "blocking_task_pool_max_workers",
        ]
        for key in allowed_keys:
            if key in config_update:
                update_data[key] = config_update[key]
        
        # Handle Tencent Cloud TTS config separately (sensitive data)
        tencent_config = config_update.get("tencent_cloud")
        
        # Allow update if either update_data or tencent_config is provided
        if not update_data and tencent_config is None:
            raise HTTPException(status_code=400, detail="No valid configuration fields to update")
        
        # Update config in TOML file
        toml_file = get_config_file_path()
        
        try:
            import tomlkit
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="TOML support not available. Please install tomlkit to preserve comments."
            )
        
        # Use thread pool for synchronous file IO
        app = get_app()
        thread_pool = getattr(app, 'blocking_task_pool', None)
        
        if toml_file.exists():
            if thread_pool:
                def read_toml_file():
                    with open(toml_file, "r", encoding="utf-8") as f:
                        return tomlkit.load(f)
                toml_data = await thread_pool.run_in_executor(read_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "r", encoding="utf-8") as f:
                    toml_data = tomlkit.load(f)
        else:
            toml_data = tomlkit.document()  # Create empty tomlkit document
        
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
                
            elif key == "web_ui_enabled":
                # Save to [web_ui].enabled
                if "web_ui" not in toml_data:
                    toml_data["web_ui"] = {}
                toml_data["web_ui"]["enabled"] = value
            elif key == "plugin_auto_load":
                # Save to [plugins].auto_load
                if "plugins" not in toml_data:
                    toml_data["plugins"] = {}
                toml_data["plugins"]["auto_load"] = value
            elif key == "blocking_task_pool_enabled":
                # Save to [plugins].blocking_task_pool_enabled
                if "plugins" not in toml_data:
                    toml_data["plugins"] = {}
                toml_data["plugins"]["blocking_task_pool_enabled"] = value
            elif key == "blocking_task_pool_max_workers":
                try:
                    parsed_workers = int(value)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail="blocking_task_pool_max_workers must be an integer")
                if parsed_workers < 0:
                    raise HTTPException(status_code=400, detail="blocking_task_pool_max_workers cannot be negative")
                if "plugins" not in toml_data:
                    toml_data["plugins"] = {}
                toml_data["plugins"]["blocking_task_pool_max_workers"] = parsed_workers
                update_data["blocking_task_pool_max_workers"] = parsed_workers
        
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
        
        # Write back to TOML using thread pool (tomlkit preserves comments)
        try:
            if thread_pool:
                def write_toml_file():
                    with open(toml_file, "w", encoding="utf-8") as f:
                        tomlkit.dump(toml_data, f)
                await thread_pool.run_in_executor(write_toml_file)
            else:
                # Fallback to sync operation if thread pool not available
                with open(toml_file, "w", encoding="utf-8") as f:
                    tomlkit.dump(toml_data, f)
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

        if "blocking_task_pool_enabled" in update_data or "blocking_task_pool_max_workers" in update_data:
            try:
                from ..core.blocking_task_pool import (
                    get_blocking_task_pool_manager,
                    shutdown_blocking_task_pool,
                )

                effective_enabled = update_data.get(
                    "blocking_task_pool_enabled",
                    getattr(current_config, "blocking_task_pool_enabled", True),
                )
                effective_workers = update_data.get(
                    "blocking_task_pool_max_workers",
                    getattr(current_config, "blocking_task_pool_max_workers", 0),
                )

                shutdown_blocking_task_pool(wait=True)
                app.blocking_task_pool = None
                if effective_enabled:
                    app.blocking_task_pool = get_blocking_task_pool_manager(effective_workers)
            except Exception as e:
                logger.warning(f"Failed to reinitialize blocking task pool after config update: {e}")
        
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

    @app.post("/api/system/update-admin-username")
    async def update_admin_username(
        request: Dict[str, Any],
        http_request: Request,
        user: Dict[str, Any] = Depends(require_permission(Permission.ADMIN_ALL))
    ):
        """Update the WebUI administrator username."""
        try:
            new_username = str(request.get("username") or "").strip()
            if len(new_username) < 3 or len(new_username) > 64:
                raise HTTPException(
                    status_code=400,
                    detail="Username must be 3-64 characters long"
                )
            if any(ch.isspace() for ch in new_username):
                raise HTTPException(
                    status_code=400,
                    detail="Username cannot contain whitespace"
                )

            auth_manager = get_auth_manager()
            current_config = get_config()
            old_username = str(user.get("username") or "").strip()
            if not old_username or not auth_manager.get_user(old_username):
                old_username = (current_config.web_ui_username or "admin").strip() or "admin"

            existing_user = auth_manager.get_user(new_username)
            if existing_user and new_username != old_username:
                raise HTTPException(status_code=400, detail="Username already exists")

            renamed = await auth_manager.rename_user(old_username, new_username)
            if not renamed:
                raise HTTPException(status_code=404, detail="Admin user not found")

            try:
                get_device_key_manager().rename_user(old_username, new_username)
            except Exception as e:
                logger.warning(f"Failed to rename device keys for admin user: {e}")

            toml_file = get_config_file_path()
            try:
                import tomlkit
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="TOML support not available. Please install tomlkit to preserve comments."
                )

            app = get_app()
            thread_pool = getattr(app, 'blocking_task_pool', None)

            if toml_file.exists():
                if thread_pool:
                    def read_toml_file():
                        with open(toml_file, "r", encoding="utf-8") as f:
                            return tomlkit.load(f)
                    toml_data = await thread_pool.run_in_executor(read_toml_file)
                else:
                    with open(toml_file, "r", encoding="utf-8") as f:
                        toml_data = tomlkit.load(f)
            else:
                toml_data = tomlkit.document()

            if "web_ui" not in toml_data:
                toml_data["web_ui"] = {}
            toml_data["web_ui"]["username"] = new_username
            os.environ["WEB_UI_USERNAME"] = new_username

            if thread_pool:
                def write_toml_file():
                    with open(toml_file, "w", encoding="utf-8") as f:
                        tomlkit.dump(toml_data, f)
                await thread_pool.run_in_executor(write_toml_file)
            else:
                with open(toml_file, "w", encoding="utf-8") as f:
                    tomlkit.dump(toml_data, f)

            reload_config()

            audit_request_details = await _request_audit_details(http_request)
            await get_audit_logger().log(AuditEvent(
                event_type=AuditEventType.CONFIG_CHANGED,
                timestamp=datetime.utcnow(),
                username=new_username,
                resource="system",
                action="update_admin_username",
                success=True,
                ip_address=audit_request_details.get("ip"),
                details={
                    "old_username": old_username,
                    "new_username": new_username,
                    "request": audit_request_details,
                }
            ))

            logger.info(
                "Admin username updated successfully",
                old_username=old_username,
                new_username=new_username,
            )
            return {"message": "Admin username updated successfully", "username": new_username}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to update admin username", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update username: {str(e)}"
            )
    
    @app.post("/api/system/reset-admin-password")
    async def reset_admin_password(
        request: Dict[str, Any],
        http_request: Request,
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
            admin_username = (get_config().web_ui_username or user.get("username") or "admin").strip() or "admin"
            if admin_username not in auth_manager._users and user.get("username") in auth_manager._users:
                admin_username = user.get("username")

            if admin_username not in auth_manager._users:
                raise HTTPException(
                    status_code=404,
                    detail="Admin user not found"
                )
            
            auth_manager._users[admin_username]["password_hash"] = get_password_hash(new_password)
            
            # Also update in config file
            config_manager = get_config_manager()
            toml_file = get_config_file_path()
            
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
                thread_pool = getattr(app, 'blocking_task_pool', None)
                
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
            
            audit_request_details = await _request_audit_details(http_request)
            await get_audit_logger().log(AuditEvent(
                event_type=AuditEventType.CONFIG_CHANGED,
                timestamp=datetime.utcnow(),
                username=user.get("username"),
                resource="system",
                action="reset_admin_password",
                success=True,
                ip_address=audit_request_details.get("ip"),
                details={"request": audit_request_details}
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

    @app.get("/api/system/log-files")
    async def get_system_log_files(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """List historical daily log files."""
        from ..core.logger import list_history_log_files

        try:
            return list_history_log_files()
        except Exception as e:
            logger.error(f"Failed to list system log files: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to list system log files: {str(e)}")

    @app.get("/api/system/log-files/{file_name}")
    async def get_system_log_file_content(
        file_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Read a complete historical log file."""
        from ..core.logger import read_history_log_file

        try:
            return read_history_log_file(file_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Log file not found")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to read system log file {file_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to read system log file: {str(e)}")

    @app.delete("/api/system/log-files/{file_name}")
    async def delete_system_log_file(
        file_name: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Delete a historical log file."""
        from ..core.logger import delete_history_log_file

        try:
            delete_history_log_file(file_name)
            logger.info("Deleted historical system log file", file_name=file_name, username=user.get("username"))
            return {"ok": True, "deleted": file_name}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Log file not found")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to delete system log file {file_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to delete system log file: {str(e)}")
    
    # Splash screen endpoints
    @app.get("/api/splash/check")
    async def check_splash_screen():
        """Check if splash screen should be shown."""
        try:
            config = get_config()
            #  WebUI 
            if not config.web_ui_enabled:
                return {"should_show": False, "reason": "webui_disabled"}
            
            #  data 
            #  webui 
            data_dir = get_runtime_base_dir() / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # 
            marker_file = data_dir / ".splash_shown"
            if marker_file.exists():
                return {"should_show": False, "reason": "already_shown"}
            
            return {"should_show": True}
        except Exception as e:
            logger.error(f"Failed to check splash screen: {e}", exc_info=True)
            # 
            return {"should_show": False, "reason": "error", "error": str(e)}
    
    @app.post("/api/splash/mark-shown")
    async def mark_splash_screen_shown():
        """Mark splash screen as shown. No authentication required."""
        try:
            config = get_config()
            #  WebUI 
            if not config.web_ui_enabled:
                return {"success": True, "message": "WebUI disabled, splash screen skipped"}
            
            #  data 
            data_dir = get_runtime_base_dir() / "data"
            
            #  data 
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as mkdir_error:
                # 
                logger.debug(f"Cannot create data directory: {mkdir_error}")
                return {"success": True, "message": "Cannot create data directory, splash screen skipped"}
            
            # 
            try:
                marker_file = data_dir / ".splash_shown"
                marker_file.touch()
                logger.info(f"Splash screen marked as shown. Marker file: {marker_file}")
                return {"success": True, "message": "Splash screen marked as shown"}
            except Exception as touch_error:
                # 
                logger.debug(f"Cannot create splash screen marker file: {touch_error}")
                return {"success": True, "message": "Cannot create marker file, but operation completed"}
        except Exception as e:
            logger.error(f"Failed to mark splash screen as shown: {e}", exc_info=True)
            # 
            return {"success": True, "message": "Error occurred but operation completed", "error": str(e)}
    
    # Health check
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    # ==================== Sandbox (Web UI testing) ====================

    def _sandbox_norm_opt(s: Optional[str]) -> Optional[str]:
        if s is None or (isinstance(s, str) and s.strip() == ""):
            return None
        return s

    @app.get("/api/sandbox/list")
    async def sandbox_list(user: Dict[str, Any] = Depends(get_current_user)):
        """List all sandboxes."""
        db = get_database_manager()
        rows = await db.list_sandboxes()
        return {"ok": True, "sandboxes": [r.to_dict() for r in rows]}

    @app.post("/api/sandbox/create")
    async def sandbox_create(
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        """Create a new sandbox."""
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        name = (body.get("name") or "").strip()
        mock_user_id = (body.get("mock_user_id") or "").strip()
        if not name or not mock_user_id:
            raise HTTPException(status_code=400, detail="name and mock_user_id are required")

        mgr = get_sandbox_manager()
        try:
            sandbox = await mgr.create_sandbox(
                name=name,
                mock_user_id=mock_user_id,
                description=_sandbox_norm_opt(body.get("description")),
                mock_user_nickname=(body.get("mock_user_nickname") or "") or "",
                mock_group_id=_sandbox_norm_opt(body.get("mock_group_id")),
                mock_group_name=_sandbox_norm_opt(body.get("mock_group_name")),
                use_plugins=bool(body.get("use_plugins", True)),
                use_ai=bool(body.get("use_ai", True)),
                ai_model_uuid=_sandbox_norm_opt(body.get("ai_model_uuid")),
                ai_preset_uuid=_sandbox_norm_opt(body.get("ai_preset_uuid")),
            )
            return {"ok": True, "sandbox": sandbox.to_dict()}
        except Exception as e:
            logger.error(f"sandbox_create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sandbox/{sandbox_uuid}/update")
    async def sandbox_update(
        sandbox_uuid: str,
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.database import get_database_manager

        db = get_database_manager()
        row = await db.get_sandbox(sandbox_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Sandbox not found")

        fields: Dict[str, Any] = {}
        if "name" in body:
            fields["name"] = (body.get("name") or "").strip() or row.name
        if "description" in body:
            fields["description"] = body.get("description")
        if "mock_user_id" in body:
            fields["mock_user_id"] = (body.get("mock_user_id") or "").strip() or row.mock_user_id
        if "mock_user_nickname" in body:
            fields["mock_user_nickname"] = body.get("mock_user_nickname") or ""
        if "mock_group_id" in body:
            fields["mock_group_id"] = _sandbox_norm_opt(body.get("mock_group_id"))
        if "mock_group_name" in body:
            fields["mock_group_name"] = _sandbox_norm_opt(body.get("mock_group_name"))
        if "use_plugins" in body:
            fields["use_plugins"] = bool(body.get("use_plugins"))
        if "use_ai" in body:
            fields["use_ai"] = bool(body.get("use_ai"))
        if "ai_model_uuid" in body:
            fields["ai_model_uuid"] = _sandbox_norm_opt(body.get("ai_model_uuid"))
        if "ai_preset_uuid" in body:
            fields["ai_preset_uuid"] = _sandbox_norm_opt(body.get("ai_preset_uuid"))
        if "enabled" in body:
            fields["enabled"] = bool(body.get("enabled"))

        updated = await db.update_sandbox(sandbox_uuid, **fields)
        if not updated:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        return {"ok": True, "sandbox": updated.to_dict()}

    @app.delete("/api/sandbox/{sandbox_uuid}")
    async def sandbox_delete(
        sandbox_uuid: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        mgr = get_sandbox_manager()
        try:
            await mgr.delete_sandbox(sandbox_uuid)
            return {"ok": True}
        except Exception as e:
            logger.error(f"sandbox_delete failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sandbox/{sandbox_uuid}/messages")
    async def sandbox_messages(
        sandbox_uuid: str,
        limit: int = 100,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        db = get_database_manager()
        row = await db.get_sandbox(sandbox_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        msgs = await db.list_sandbox_messages(sandbox_uuid, limit=limit)
        return {"ok": True, "messages": [m.to_dict() for m in msgs]}

    @app.delete("/api/sandbox/{sandbox_uuid}/messages")
    async def sandbox_clear_messages(
        sandbox_uuid: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        db = get_database_manager()
        row = await db.get_sandbox(sandbox_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        await db.clear_sandbox_messages(sandbox_uuid)
        return {"ok": True}

    @app.post("/api/sandbox/{sandbox_uuid}/send")
    async def sandbox_send(
        sandbox_uuid: str,
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        msg = (body.get("message") or "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="message is required")
        mtype = body.get("message_type") or "private"
        mgr = get_sandbox_manager()
        try:
            result = await mgr.send_message_to_sandbox(sandbox_uuid, msg, message_type=mtype)
            return {"ok": True, **result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_send failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sandbox/{sandbox_uuid}/shell")
    async def sandbox_shell(
        sandbox_uuid: str,
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        cmd = body.get("command") or ""
        timeout = int(body.get("timeout") or 30)
        cwd = body.get("cwd")
        mgr = get_sandbox_manager()
        try:
            result = await mgr.execute_shell(sandbox_uuid, cmd, cwd=cwd, timeout=timeout)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_shell failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sandbox/{sandbox_uuid}/python")
    async def sandbox_python(
        sandbox_uuid: str,
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        code = body.get("code") or ""
        kernel_id = body.get("kernel_id")
        timeout = int(body.get("timeout") or 30)
        mgr = get_sandbox_manager()
        try:
            result = await mgr.execute_python(sandbox_uuid, code, kernel_id=kernel_id, timeout=timeout)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_python failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sandbox/{sandbox_uuid}/files")
    async def sandbox_files_list(
        sandbox_uuid: str,
        path: str = ".",
        show_hidden: bool = False,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        mgr = get_sandbox_manager()
        try:
            result = await mgr.list_files(sandbox_uuid, path=path, show_hidden=show_hidden)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_files_list failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sandbox/{sandbox_uuid}/files/read")
    async def sandbox_files_read(
        sandbox_uuid: str,
        path: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        mgr = get_sandbox_manager()
        try:
            result = await mgr.read_file(sandbox_uuid, path=path)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_files_read failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sandbox/{sandbox_uuid}/files/write")
    async def sandbox_files_write(
        sandbox_uuid: str,
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        path = body.get("path") or ""
        content = body.get("content")
        if content is None:
            content = ""
        mgr = get_sandbox_manager()
        try:
            result = await mgr.write_file(sandbox_uuid, path=path, content=content)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_files_write failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/sandbox/{sandbox_uuid}/files/mkdir")
    async def sandbox_files_mkdir(
        sandbox_uuid: str,
        body: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        path = body.get("path") or ""
        mgr = get_sandbox_manager()
        try:
            result = await mgr.create_directory(sandbox_uuid, path=path)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_files_mkdir failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/sandbox/{sandbox_uuid}/files")
    async def sandbox_files_delete(
        sandbox_uuid: str,
        path: str,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        mgr = get_sandbox_manager()
        try:
            result = await mgr.delete_file(sandbox_uuid, path=path)
            return {"ok": True, "result": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"sandbox_files_delete failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.websocket("/api/sandbox/{sandbox_uuid}/ws")
    async def sandbox_websocket(websocket: WebSocket, sandbox_uuid: str):
        """Realtime sandbox messages (requires token in query string)."""
        from ..core.sandbox.sandbox_manager import get_sandbox_manager

        token = websocket.query_params.get("token") or ""
        auth_manager = get_auth_manager()
        session_info = await auth_manager.verify_session(token)
        if not session_info:
            await websocket.close(code=4401)
            return

        db = get_database_manager()
        row = await db.get_sandbox(sandbox_uuid)
        if not row:
            await websocket.close(code=4404)
            return

        await websocket.accept()
        mgr = get_sandbox_manager()

        async def forward(msg: Dict[str, Any]):
            try:
                await websocket.send_json({"type": "message", "data": msg})
            except Exception:
                pass

        mgr.register_message_callback(sandbox_uuid, forward)
        try:
            await websocket.send_json(
                {"type": "connected", "sandbox": row.to_dict()}
            )
            while True:
                try:
                    raw = await websocket.receive_text()
                    if raw == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    break
        finally:
            mgr.unregister_message_callback(sandbox_uuid, forward)

    # ===== NapCat Management Routes =====

    @app.get("/api/napcat/status")
    async def get_napcat_status(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get the framework-managed NapCat status."""
        from ..napcat import get_napcat_manager

        return get_napcat_manager().get_status()

    @app.post("/api/napcat/install")
    async def install_napcat(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Start a NapCat install job under the framework runtime directory."""
        from ..napcat import get_napcat_manager

        napcat_mgr = get_napcat_manager()
        active_job = napcat_mgr.get_active_install_job()
        if active_job:
            return active_job

        job = napcat_mgr.create_install_job()

        async def run_job():
            await run_in_blocking_pool(napcat_mgr.install, job["job_id"])

        asyncio.create_task(run_job())
        return job

    @app.get("/api/napcat/progress/{job_id}")
    async def get_napcat_install_progress(
        job_id: str,
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get a NapCat install job progress."""
        from ..napcat import get_napcat_manager

        job = get_napcat_manager().get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="NapCat install job not found")
        return job

    @app.post("/api/napcat/start")
    async def start_napcat(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Start the framework-managed NapCat process."""
        from ..napcat import get_napcat_manager

        result = get_napcat_manager().start()
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to start NapCat"))
        return result

    @app.post("/api/napcat/stop")
    async def stop_napcat(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Stop the framework-managed NapCat process."""
        from ..napcat import get_napcat_manager

        result = get_napcat_manager().stop()
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to stop NapCat"))
        return result

    @app.get("/api/napcat/logs")
    async def get_napcat_logs(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get framework-captured NapCat runtime logs."""
        from ..napcat import get_napcat_manager

        return get_napcat_manager().get_logs()

    @app.get("/api/napcat/webui")
    async def get_napcat_webui(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get the detected NapCat WebUI URL.

        WebUI startup is asynchronous, so "not ready yet" is a normal state.
        """
        from ..napcat import get_napcat_manager

        return get_napcat_manager().get_webui_info()

    @app.get("/api/napcat/qrcode")
    async def get_napcat_qrcode(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Return the current NapCat login QR code from the managed workdir."""
        from ..napcat import get_napcat_manager

        qrcode_path = get_napcat_manager().get_qrcode_path()
        if not qrcode_path.exists() or not qrcode_path.is_file():
            raise HTTPException(status_code=404, detail="NapCat QR code not found")
        return FileResponse(
            str(qrcode_path),
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/napcat/qrcode/info")
    async def get_napcat_qrcode_info(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Return metadata for the current NapCat login QR code."""
        from ..napcat import get_napcat_manager

        return get_napcat_manager().get_qrcode_info()

    @app.get("/api/napcat/config")
    async def get_napcat_config_center(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get framework-managed NapCat config files."""
        from ..napcat import get_napcat_manager

        return get_napcat_manager().get_config_center()

    @app.post("/api/napcat/config")
    async def save_napcat_config_center(
        payload: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Save framework-managed NapCat config files."""
        from ..napcat import get_napcat_manager

        try:
            return get_napcat_manager().save_config_center(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/napcat/onebot/apply-framework")
    async def apply_framework_onebot_to_napcat(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Write a NapCat OneBot config that matches the current framework OneBot settings."""
        from ..napcat import get_napcat_manager

        try:
            return get_napcat_manager().apply_framework_onebot_config(get_config())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/napcat/login-status")
    async def get_napcat_login_status(
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_VIEW))
    ):
        """Get NapCat process, QR code, and framework OneBot login status."""
        from ..napcat import get_napcat_manager

        napcat_mgr = get_napcat_manager()
        napcat_status = napcat_mgr.get_status()
        qrcode_info = napcat_mgr.get_qrcode_info()
        app_instance = get_app()
        adapter = getattr(app_instance, "onebot_adapter", None)

        onebot_status: Dict[str, Any] = {
            "available": bool(adapter),
            "running": False,
            "connected": False,
            "connection_type": "",
            "self_id": "",
            "self_nickname": "",
            "login_info": None,
            "error": "",
        }

        if adapter:
            reverse_clients = getattr(adapter, "_reverse_clients", []) or []
            connection_type = getattr(adapter, "connection_type", "")
            onebot_status.update({
                "running": bool(getattr(adapter, "_running", False)),
                "connected": bool(getattr(adapter, "_ws", None)) or bool(reverse_clients) or connection_type == "http",
                "connection_type": connection_type,
                "self_id": str(getattr(adapter, "self_id", "") or ""),
                "self_nickname": str(getattr(adapter, "self_nickname", "") or ""),
            })

            if onebot_status["running"]:
                try:
                    login_info = await asyncio.wait_for(
                        adapter.call_api("get_login_info", {}, source="napcat-manager"),
                        timeout=8.0,
                    )
                    if isinstance(login_info, dict):
                        onebot_status["login_info"] = login_info
                        onebot_status["self_id"] = str(login_info.get("user_id") or onebot_status["self_id"])
                        onebot_status["self_nickname"] = str(login_info.get("nickname") or onebot_status["self_nickname"])
                        onebot_status["connected"] = True
                    else:
                        onebot_status["login_info"] = login_info
                except Exception as exc:
                    onebot_status["connected"] = False
                    onebot_status["error"] = str(exc)

        return {
            "napcat": napcat_status,
            "qrcode": qrcode_info,
            "webui": napcat_status.get("webui") or napcat_mgr.get_webui_info(),
            "onebot": onebot_status,
        }

    @app.post("/api/napcat/onebot/debug-call")
    async def debug_onebot_api_from_napcat_page(
        payload: Dict[str, Any] = Body(...),
        user: Dict[str, Any] = Depends(require_permission(Permission.SYSTEM_CONFIG_EDIT))
    ):
        """Call a OneBot API through the framework adapter for debugging."""
        action = str(payload.get("action") or "").strip()
        if not action:
            raise HTTPException(status_code=400, detail="OneBot action is required")

        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="OneBot params must be a JSON object")

        try:
            timeout_seconds = float(payload.get("timeout", 20))
        except (TypeError, ValueError):
            timeout_seconds = 20.0
        timeout_seconds = max(1.0, min(timeout_seconds, 60.0))

        app_instance = get_app()
        adapter = getattr(app_instance, "onebot_adapter", None)
        if not adapter or not getattr(adapter, "_running", False):
            raise HTTPException(status_code=503, detail="OneBot adapter is not running")

        started_at = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                adapter.call_api(action, params, source="napcat-debugger"),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail=f"OneBot API timeout: {action}") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {
            "ok": True,
            "action": action,
            "params": params,
            "result": result,
            "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
        }

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
        
        # Check if webui static files (build output) exist
        # Note: We check for the built files, not the source directory
        static_assets_dir = static_dir_path / "assets"
        webui_built = static_assets_dir.exists() and static_assets_dir.is_dir()
        
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
            # Return JSON guidance instead of HTML fallback page.
            if not webui_built:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "WebUI not built",
                        "message": "WebUI static files are missing in src/ui/static.",
                        "suggestions": [
                            "Disable WebUI in config.toml with [web_ui].enabled = false",
                            "Build WebUI with: cd webui && npm install && npm run build",
                            "Or use build.bat (Windows) / build.sh (Linux/Mac)"
                        ]
                    }
                )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "WebUI entry missing",
                    "message": "WebUI assets exist but src/ui/static/index.html is missing.",
                    "suggestions": [
                        "Rebuild WebUI with: cd webui && npm run build",
                        "Or use build.bat (Windows) / build.sh (Linux/Mac)"
                    ]
                }
            )
    
    return app


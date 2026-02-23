"""OneBot protocol adapter (v11/v12 compatible)."""

# Python 3.13 compatibility fix for hyperframe/httpx/h2
# collections abstract base classes were moved to collections.abc in Python 3.13
import collections
if not hasattr(collections, 'MutableSet'):
    import collections.abc
    # Restore removed ABCs for backward compatibility
    collections.MutableSet = collections.abc.MutableSet
    collections.MutableMapping = collections.abc.MutableMapping
    collections.MutableSequence = collections.abc.MutableSequence
    collections.Mapping = collections.abc.Mapping
    collections.Sequence = collections.abc.Sequence
    collections.Set = collections.abc.Set

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
import websockets
from websockets.client import WebSocketClientProtocol
from websockets.server import serve, WebSocketServerProtocol

from .base import ProtocolAdapter, MessageEnvelope, MessageSegment
from ..core.logger import get_logger

logger = get_logger(__name__)


class OneBotAdapter(ProtocolAdapter):
    """OneBot protocol adapter with v11/v12 support."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.version = config.get("version", "v11")
        self.connection_type = config.get("connection_type", "http")  # http, ws, ws_reverse
        
        # HTTP 配置
        self.http_url = config.get("http_url", "http://localhost:5700")
        
        # 正向 WebSocket 配置
        self.ws_url = config.get("ws_url", "ws://localhost:5700")
        
        # 反向 WebSocket 配置
        self.ws_reverse_host = config.get("ws_reverse_host", "0.0.0.0")
        self.ws_reverse_port = config.get("ws_reverse_port", 8080)
        self.ws_reverse_path = config.get("ws_reverse_path", "/onebot/v11/ws")
        
        # 认证配置
        self.access_token = config.get("access_token", "")
        self.secret = config.get("secret", "")
        
        # 连接状态
        self._ws: Optional[WebSocketClientProtocol] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_server = None
        self._ws_server_task: Optional[asyncio.Task] = None
        self._reverse_clients: List[WebSocketServerProtocol] = []
        
        # API 响应等待队列（用于 WebSocket 调用 API 时等待响应）
        self._api_responses: Dict[str, asyncio.Future] = {}
        self._echo_counter = 0
        self._cleanup_task: Optional[asyncio.Task] = None  # 清理任务
        
        # Timeout 配置
        self.http_timeout = config.get("http_timeout", 120.0)  # HTTP 请求超时（发送消息、上传文件等）
        self.ws_api_timeout = config.get("ws_api_timeout", 60.0)  # WebSocket API 调用超时
        
        # Event handlers
        self._event_handlers: List = []

    def on_event(self, handler):
        """Register an event handler.
        
        Args:
            handler: Async function that takes event dict as parameter
        """
        if handler is None:
            logger.warning("Attempted to register None as event handler, ignoring")
            return
        if not callable(handler):
            logger.warning(f"Attempted to register non-callable object as event handler: {type(handler)}, ignoring")
            return
        self._event_handlers.append(handler)
        logger.info(f"Registered event handler, total handlers: {len(self._event_handlers)}")
    
    async def start(self) -> None:
        """Start the OneBot adapter."""
        if self._running:
            logger.warning("OneBot adapter already running")
            return

        logger.info(
            "Starting OneBot adapter",
            version=self.version,
            connection_type=self.connection_type
        )

        # Initialize HTTP client
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        self._http_client = httpx.AsyncClient(
            base_url=self.http_url,
            headers=headers,
            timeout=self.http_timeout
        )

        # Start connection based on type
        # 支持 ws 和 ws_forward 作为正向 WebSocket
        if self.connection_type in ("ws", "ws_forward"):
            # 正向 WebSocket
            logger.info("Connecting to forward WebSocket", url=self.ws_url)
            self._ws_task = asyncio.create_task(self._ws_forward_handler())
        elif self.connection_type == "ws_reverse":
            # 反向 WebSocket
            logger.info(
                "Starting reverse WebSocket server",
                host=self.ws_reverse_host,
                port=self.ws_reverse_port,
                path=self.ws_reverse_path
            )
            self._ws_server_task = asyncio.create_task(self._ws_reverse_server())
        else:
            # HTTP only
            logger.info("Using HTTP connection", url=self.http_url)

        self._running = True
        
        # Start cleanup task for expired API responses
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_responses())
        
        logger.info("OneBot adapter started")

    async def stop(self) -> None:
        """Stop the OneBot adapter."""
        if not self._running:
            return

        logger.info("Stopping OneBot adapter")

        self._running = False

        # Close forward WebSocket
        if self._ws:
            await self._ws.close()
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        # Close reverse WebSocket server
        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        
        if self._ws_server_task:
            self._ws_server_task.cancel()
            try:
                await self._ws_server_task
            except asyncio.CancelledError:
                pass
        
        # Close all reverse clients
        for client in self._reverse_clients:
            await client.close()
        self._reverse_clients.clear()

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
        
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all pending API response futures
        self._cancel_all_pending_responses()

        logger.info("OneBot adapter stopped")

    async def _ws_forward_handler(self) -> None:
        """Handle forward WebSocket connection."""
        while self._running:
            try:
                # Build connection parameters with token authentication
                connect_kwargs = {}
                if self.access_token:
                    # Try to detect websockets version and use appropriate parameter
                    # websockets >= 12.0 uses additional_headers (list of tuples)
                    # websockets < 12.0 uses extra_headers (dict)
                    import inspect
                    sig = inspect.signature(websockets.connect)
                    
                    if 'additional_headers' in sig.parameters:
                        # websockets >= 12.0
                        connect_kwargs["additional_headers"] = [
                            ("Authorization", f"Bearer {self.access_token}")
                        ]
                    elif 'extra_headers' in sig.parameters:
                        # websockets < 12.0
                        connect_kwargs["extra_headers"] = {
                            "Authorization": f"Bearer {self.access_token}"
                        }
                    else:
                        logger.warning("Cannot determine websockets header parameter, trying extra_headers")
                        connect_kwargs["extra_headers"] = {
                            "Authorization": f"Bearer {self.access_token}"
                        }

                logger.info(f"Connecting to forward WebSocket: {self.ws_url}")
                if self.access_token:
                    logger.info("Using access token for authentication")
                try:
                    ws = await websockets.connect(self.ws_url, **connect_kwargs)
                    self._ws = ws
                    logger.info("Forward WebSocket connected successfully", url=self.ws_url)
                    logger.info("Waiting for messages from OneBot implementation...")
                    
                    try:
                        # Keep connection alive and process messages
                        async for message in ws:
                            try:
                                data = json.loads(message)
                                
                                # Check if it's an API response (has echo field but no post_type)
                                if data.get("echo") is not None and data.get("post_type") is None:
                                    echo = data.get("echo")
                                    # Skip empty echo (some implementations send empty echo)
                                    if not echo or echo == "":
                                        logger.debug(f"Received API response with empty echo, ignoring")
                                        continue
                                    
                                    logger.debug(f"Received API response with echo: {echo}, data: {data}")
                                    if echo in self._api_responses:
                                        future = self._api_responses.pop(echo)
                                        if not future.done():
                                            logger.debug(f"Setting result for echo: {echo}")
                                            future.set_result(data)
                                        else:
                                            logger.warning(f"Future already done for echo: {echo}")
                                        continue
                                    else:
                                        # Only warn if echo is not empty (empty echo is common and harmless)
                                        # This might be a delayed response from a previous request that already timed out
                                        active_echoes = list(self._api_responses.keys())
                                        if active_echoes:
                                            logger.debug(f"Received delayed response for echo: {echo} (not in active echoes: {active_echoes})")
                                        else:
                                            logger.debug(f"Received response for echo: {echo} but no active requests (likely timeout)")
                                
                                post_type = data.get("post_type", "unknown")
                                # Meta events (heartbeat) are very frequent, log at debug level
                                if post_type == "meta_event":
                                    logger.debug(f"Received WebSocket message: {post_type}", 
                                              post_type=post_type,
                                              message_type=data.get("message_type"),
                                              user_id=data.get("user_id"))
                                else:
                                    logger.info(f"Received WebSocket message: {post_type}", 
                                              post_type=post_type,
                                              message_type=data.get("message_type"),
                                              user_id=data.get("user_id"))
                                await self._handle_event(data)
                            except json.JSONDecodeError as e:
                                logger.error("Invalid JSON in WebSocket message", error=str(e))
                            except Exception as e:
                                logger.error("Error handling WebSocket message", error=str(e), exc_info=True)
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning("WebSocket connection closed", code=e.code, reason=e.reason)
                        # Cancel all pending API response futures when connection closes
                        self._cancel_all_pending_responses()
                    finally:
                        # Close connection
                        if ws:
                            await ws.close()
                        self._ws = None
                        # Cancel all pending API response futures
                        self._cancel_all_pending_responses()
                        logger.warning("WebSocket connection closed normally")
                        
                except websockets.exceptions.InvalidURI as e:
                    logger.error(f"Invalid WebSocket URL: {self.ws_url}")
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
                except ConnectionRefusedError as e:
                    logger.error(f"Connection refused: {self.ws_url} - Please check if the OneBot implementation is running")
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
                except websockets.exceptions.InvalidMessage as e:
                    error_msg = str(e)
                    # Extract key information from error message
                    if "did not receive a valid HTTP response" in error_msg:
                        logger.error(f"WebSocket connection failed: Server did not respond correctly (URL: {self.ws_url})")
                    elif "connection closed" in error_msg.lower():
                        logger.error(f"WebSocket connection closed unexpectedly: {self.ws_url}")
                    else:
                        logger.error(f"WebSocket connection error: {error_msg}")
                    # Cancel all pending API response futures on connection error
                    self._cancel_all_pending_responses()
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)
                    # Provide friendly error message based on error type
                    if "InvalidMessage" in error_type or "did not receive" in error_msg:
                        logger.error(f"WebSocket connection failed: Invalid response from server ({self.ws_url})")
                    elif "Connection" in error_type:
                        logger.error(f"WebSocket connection error: {error_msg} (URL: {self.ws_url})")
                    else:
                        logger.error(f"WebSocket connection error: {error_msg}")
                    # Cancel all pending API response futures on connection error
                    self._cancel_all_pending_responses()
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
            except Exception as e:
                # Catch any unexpected errors in the outer try block
                error_msg = str(e)
                logger.error(f"Unexpected WebSocket handler error: {error_msg}")
                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
    
    async def _ws_reverse_server(self) -> None:
        """Start reverse WebSocket server."""
        async def handle_client(websocket: WebSocketServerProtocol, path: str):
            """Handle reverse WebSocket client connection."""
            # 验证路径（支持带查询参数的路径）
            expected_path = self.ws_reverse_path.rstrip('/')
            actual_path = path.split('?')[0].rstrip('/')  # Remove query params and trailing slashes
            
            logger.info(f"Reverse WebSocket connection attempt", path=path, expected=self.ws_reverse_path)
            
            if actual_path != expected_path:
                logger.warning("Invalid WebSocket path", path=path, expected=self.ws_reverse_path)
                await websocket.close()
                return
            
            # 验证 access_token
            if self.access_token:
                auth_header = websocket.request_headers.get("Authorization", "")
                if auth_header != f"Bearer {self.access_token}":
                    logger.warning("Invalid access token")
                    await websocket.close()
                    return
            
            logger.info("Reverse WebSocket client connected", remote=websocket.remote_address, path=path)
            self._reverse_clients.append(websocket)
            
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Check if it's an API response (has echo field but no post_type)
                        if data.get("echo") is not None and data.get("post_type") is None:
                            echo = data.get("echo")
                            # Skip empty echo (some implementations send empty echo)
                            if not echo or echo == "":
                                logger.debug(f"Received API response (reverse) with empty echo, ignoring")
                                continue
                            
                            logger.debug(f"Received API response (reverse) with echo: {echo}, data: {data}")
                            if echo in self._api_responses:
                                future = self._api_responses.pop(echo)
                                if not future.done():
                                    logger.debug(f"Setting result for echo: {echo}")
                                    future.set_result(data)
                                else:
                                    logger.warning(f"Future already done for echo: {echo}")
                                continue
                            else:
                                # Only warn if echo is not empty (empty echo is common and harmless)
                                logger.debug(f"No waiting future found for echo: {echo}, active echoes: {list(self._api_responses.keys())}")
                        
                        logger.debug("Received reverse WebSocket message", post_type=data.get("post_type", "unknown"))
                        await self._handle_event(data)
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON in reverse WebSocket message", error=str(e))
                    except Exception as e:
                        logger.error("Error handling reverse WebSocket message", error=str(e), exc_info=True)
            except websockets.exceptions.ConnectionClosed:
                logger.info("Reverse WebSocket client disconnected")
            finally:
                # Ensure the client is removed from the list
                if websocket in self._reverse_clients:
                    self._reverse_clients.remove(websocket)
                # Cancel all pending API response futures when client disconnects
                self._cancel_all_pending_responses()
        
        try:
            self._ws_server = await serve(
                handle_client,
                self.ws_reverse_host,
                self.ws_reverse_port
            )
            logger.info(
                "Reverse WebSocket server started",
                host=self.ws_reverse_host,
                port=self.ws_reverse_port,
                path=self.ws_reverse_path
            )
            await self._ws_server.wait_closed()
        except Exception as e:
            logger.error("Reverse WebSocket server error", error=str(e))

    async def _handle_event(self, data: Dict[str, Any]) -> None:
        """Handle incoming OneBot event."""
        post_type = data.get("post_type")
        
        # Filter out meta events and self messages (like old project)
        if post_type == "meta_event":
            # Meta events (heartbeat, etc.) - skip processing but log at debug level
            meta_type = data.get("meta_event_type", "unknown")
            if meta_type == "heartbeat":
                # Heartbeat is very frequent, only log at debug level
                logger.debug("Heartbeat received", interval=data.get("interval"))
            else:
                logger.debug("Skipping meta event", meta_event_type=meta_type)
            return
        
        # Check if it's an API response (has echo field)
        if data.get("echo") is not None:
            # This is an API response, not an event - skip
            logger.debug("Skipping API response", echo=data.get("echo"))
            return
        
        # Check if it's a self message (user_id == self_id)
        # BUT allow message_sent events (self-sent messages) for chat history
        user_id = data.get("user_id")
        self_id = data.get("self_id")
        if user_id and self_id and str(user_id) == str(self_id) and post_type != "message_sent":
            logger.debug("Skipping self message", user_id=user_id, post_type=post_type)
            return
        
        # Log received event (similar to old project)
        if post_type == "message" or post_type == "message_sent":
            message_type = data.get("message_type", "unknown")
            group_id = data.get("group_id")
            message_text = data.get("raw_message", "")
            
            if message_type == "group" and group_id:
                logger.info(f"收到来自群 {group_id} 中 {user_id} 的消息：{message_text}")
            elif message_type == "private":
                logger.info(f"收到 {user_id} 的消息：{message_text}")
            else:
                logger.info(f"收到消息：{message_text}", message_type=message_type, user_id=user_id, group_id=group_id)
        else:
            logger.info(
                "Received OneBot event",
                post_type=post_type,
                message_type=data.get("message_type"),
                user_id=user_id,
                group_id=data.get("group_id")
            )
        
        if post_type == "message":
            # Convert to MessageEnvelope
            envelope = self._parse_message_event(data)
            logger.debug(
                "Processing message event",
                message_id=envelope.message_id,
                message_type=envelope.message_type,
                user_id=envelope.user_id
            )
            await self._emit_event({
                "type": "message",
                "envelope": envelope.to_dict(),  # Convert to dict for serialization
                "raw": data
            })
        elif post_type == "message_sent":
            # Handle self-sent messages for chat history
            # Mark as is_self=True so it can be identified in history
            data_with_self_flag = data.copy()
            data_with_self_flag["is_self"] = True
            
            envelope = self._parse_message_event(data_with_self_flag)
            logger.debug(
                "Processing self-sent message event",
                message_id=envelope.message_id,
                message_type=envelope.message_type,
                user_id=envelope.user_id
            )
            await self._emit_event({
                "type": "message",  # Emit as message type for history
                "envelope": envelope.to_dict(),
                "raw": data_with_self_flag
            })
        elif post_type == "notice":
            notice_type = data.get("notice_type", "unknown")
            logger.info(f"Processing notice event: {notice_type}", 
                       notice_type=notice_type, 
                       sub_type=data.get("sub_type"),
                       user_id=user_id,
                       group_id=data.get("group_id"))
            await self._emit_event({
                "type": "notice",
                "data": data,
                "raw": data
            })
        elif post_type == "request":
            logger.debug("Processing request event", request_type=data.get("request_type"))
            await self._emit_event({
                "type": "request",
                "data": data,
                "raw": data
            })
        elif post_type == "meta_event":
            # Meta events (heartbeat, etc.) - log at debug level
            logger.debug("Processing meta event", meta_event_type=data.get("meta_event_type"))
            await self._emit_event({
                "type": "meta_event",
                "data": data,
                "raw": data
            })
        else:
            logger.warning("Unknown post_type", post_type=post_type, data=data)

    def _parse_message_event(self, data: Dict[str, Any]) -> MessageEnvelope:
        """Parse OneBot message event to MessageEnvelope."""
        message_type = data.get("message_type", "private")
        
        # Parse message segments
        segments = []
        message_data = data.get("message", [])
        
        if isinstance(message_data, str):
            segments = [MessageSegment.text(message_data)]
        elif isinstance(message_data, list):
            for seg in message_data:
                segments.append(MessageSegment(
                    type=seg.get("type", "text"),
                    data=seg.get("data", {})
                ))

        return MessageEnvelope(
            message_id=str(data.get("message_id", "")),
            message_type=message_type,
            user_id=str(data.get("user_id", "")),
            timestamp=datetime.fromtimestamp(data.get("time", 0)),
            raw_message=data.get("raw_message", ""),
            message=segments,
            group_id=str(data.get("group_id")) if data.get("group_id") else None,
            sender=data.get("sender", {}),
            metadata={
                "self_id": data.get("self_id"),
                "sub_type": data.get("sub_type"),
            }
        )

    async def send_message(
        self,
        target: str,
        message: Any,
        message_type: str = "private"
    ) -> Dict[str, Any]:
        """Send a message via OneBot."""
        # Prepare message
        if isinstance(message, str):
            message_data = message
        elif isinstance(message, list):
            message_data = [
                seg.to_dict() if isinstance(seg, MessageSegment) else seg
                for seg in message
            ]
        else:
            message_data = str(message)

        # Prepare request
        endpoint = f"send_{message_type}_msg"
        payload = {"message": message_data}
        
        if message_type == "private":
            payload["user_id"] = int(target)
        elif message_type == "group":
            payload["group_id"] = int(target)
        else:
            raise ValueError(f"Unknown message type: {message_type}")

        logger.debug(
            "Sending message",
            endpoint=endpoint,
            target=target,
            message_type=message_type
        )

        # Send via WebSocket or HTTP
        if self.connection_type in ("ws", "ws_forward") and self._ws:
            # Send via forward WebSocket
            await self._ws.send(json.dumps({
                "action": endpoint,
                "params": payload,
                "echo": None
            }))
            # Emit event for message sent statistics (WebSocket)
            try:
                from ..core.event_bus import get_event_bus
                event_bus = get_event_bus()
                if event_bus:
                    await event_bus.publish("onebot.message_sent", {
                        "message_type": message_type,
                        "target": target,
                        "message_id": None,  # WebSocket doesn't return immediately
                        "timestamp": datetime.now()
                    })
            except Exception as e:
                logger.debug(f"Failed to emit message_sent event: {e}")
            return {"message_id": None}  # WebSocket doesn't return immediately
        elif self.connection_type == "ws_reverse" and self._reverse_clients:
            # Send via reverse WebSocket
            for client in self._reverse_clients:
                await client.send(json.dumps({
                    "action": endpoint,
                    "params": payload,
                    "echo": None
                }))
            # Emit event for message sent statistics (Reverse WebSocket)
            try:
                from ..core.event_bus import get_event_bus
                event_bus = get_event_bus()
                if event_bus:
                    await event_bus.publish("onebot.message_sent", {
                        "message_type": message_type,
                        "target": target,
                        "message_id": None,  # WebSocket doesn't return immediately
                        "timestamp": datetime.now()
                    })
            except Exception as e:
                logger.debug(f"Failed to emit message_sent event: {e}")
            return {"message_id": None}
        else:
            # Send via HTTP
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized")
            
            response = await self._http_client.post(f"/{endpoint}", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "ok":
                message_id = result.get("data", {}).get("message_id")
                logger.info("Message sent", message_id=message_id)
                
                # Emit event for message sent statistics
                try:
                    from ..core.event_bus import get_event_bus
                    event_bus = get_event_bus()
                    if event_bus:
                        await event_bus.publish("onebot.message_sent", {
                            "message_type": message_type,
                            "target": target,
                            "message_id": message_id,
                            "timestamp": datetime.now()
                        })
                except Exception as e:
                    logger.debug(f"Failed to emit message_sent event: {e}")
                
                return result.get("data", {})
            else:
                logger.error("Failed to send message", result=result)
                raise RuntimeError(f"Failed to send message: {result}")

    async def send_forward_msg(
        self,
        target: str,
        messages: List[Dict[str, Any]],
        message_type: str = "group"
    ) -> Dict[str, Any]:
        """Send forward message (合并转发).
        
        Args:
            target: Group ID or User ID
            messages: List of node messages
            message_type: 'group' or 'private'
        
        Returns:
            Response dict with message_id
        
        Example nodes format:
            [
                {
                    "type": "node",
                    "data": {
                        "name": "发送者昵称",
                        "uin": "10001",
                        "content": "消息内容1"
                    }
                },
                {
                    "type": "node",
                    "data": {
                        "name": "发送者昵称2",
                        "uin": "10002",
                        "content": [
                            {"type": "text", "data": {"text": "消息内容2"}},
                            {"type": "image", "data": {"file": "xxx.jpg"}}
                        ]
                    }
                }
            ]
        """
        endpoint = f"send_{message_type}_forward_msg"
        payload = {"messages": messages}
        
        if message_type == "private":
            payload["user_id"] = int(target)
        elif message_type == "group":
            payload["group_id"] = int(target)
        else:
            raise ValueError(f"Unknown message type: {message_type}")
        
        logger.debug(
            "Sending forward message",
            endpoint=endpoint,
            target=target,
            message_type=message_type,
            node_count=len(messages)
        )
        
        # Send via WebSocket or HTTP
        if self.connection_type in ("ws", "ws_forward") and self._ws:
            await self._ws.send(json.dumps({
                "action": endpoint,
                "params": payload,
                "echo": None
            }))
            # Emit event for WebSocket (message_id not available immediately)
            try:
                from ..core.event_bus import get_event_bus
                event_bus = get_event_bus()
                if event_bus:
                    await event_bus.publish("onebot.message_sent", {
                        "message_type": message_type,
                        "target": target,
                        "message_id": None,
                        "timestamp": datetime.now()
                    })
            except Exception as e:
                logger.debug(f"Failed to emit message_sent event: {e}")
            return {"message_id": None}
        elif self.connection_type == "ws_reverse" and self._reverse_clients:
            for client in self._reverse_clients:
                await client.send(json.dumps({
                    "action": endpoint,
                    "params": payload,
                    "echo": None
                }))
            # Emit event for reverse WebSocket (message_id not available immediately)
            try:
                from ..core.event_bus import get_event_bus
                event_bus = get_event_bus()
                if event_bus:
                    await event_bus.publish("onebot.message_sent", {
                        "message_type": message_type,
                        "target": target,
                        "message_id": None,
                        "timestamp": datetime.now()
                    })
            except Exception as e:
                logger.debug(f"Failed to emit message_sent event: {e}")
            return {"message_id": None}
        else:
            # Send via HTTP
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized")
            
            response = await self._http_client.post(f"/{endpoint}", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "ok":
                message_id = result.get("data", {}).get("message_id")
                logger.info("Forward message sent", message_id=message_id)
                
                # Emit event for message sent statistics
                try:
                    from ..core.event_bus import get_event_bus
                    event_bus = get_event_bus()
                    if event_bus:
                        await event_bus.publish("onebot.message_sent", {
                            "message_type": message_type,
                            "target": target,
                            "message_id": message_id,
                            "timestamp": datetime.now()
                        })
                except Exception as e:
                    logger.debug(f"Failed to emit message_sent event: {e}")
                
                return result.get("data", {})
            else:
                logger.error("Failed to send forward message", result=result)
                raise RuntimeError(f"Failed to send forward message: {result}")
    
    async def delete_message(self, message_id: str) -> bool:
        """Delete a message."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        try:
            response = await self._http_client.post(
                "/delete_msg",
                json={"message_id": int(message_id)}
            )
            result = response.json()
            return result.get("status") == "ok"
        except Exception as e:
            logger.error("Failed to delete message", error=str(e))
            return False

    async def get_message(self, message_id: str) -> Optional[MessageEnvelope]:
        """Get message by ID."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        try:
            response = await self._http_client.post(
                "/get_msg",
                json={"message_id": int(message_id)}
            )
            result = response.json()
            
            if result.get("status") == "ok":
                data = result.get("data", {})
                return self._parse_message_event(data)
            return None
        except Exception as e:
            logger.error("Failed to get message", error=str(e))
            return None

    def _parse_api_error(self, result: Dict[str, Any], action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse API error and provide friendly error message.
        
        Args:
            result: Error response from API
            action: API action name
            params: API parameters
            
        Returns:
            Dict with 'message' and 'suggestion' keys
        """
        retcode = result.get("retcode", 0)
        message = result.get("message", "")
        wording = result.get("wording", "")
        
        # Try to extract errMsg from EventChecker error
        err_msg = None
        try:
            import re
            import json
            # Try to parse EventRet JSON from wording
            if "EventRet:" in wording:
                # Extract JSON part after EventRet:
                json_match = re.search(r'EventRet:\s*(\{[^}]+\})', wording.replace('\n', ' '))
                if json_match:
                    event_ret = json.loads(json_match.group(1))
                    err_msg = event_ret.get("errMsg")
        except:
            pass
        
        # Build simple error message
        if err_msg:
            # Use the extracted errMsg directly
            error_msg = err_msg
        elif wording:
            # Try to extract meaningful part from wording
            if "ERR_" in wording:
                # Extract error code
                import re
                match = re.search(r'(ERR_\w+)', wording)
                if match:
                    error_code = match.group(1)
                    # Map common error codes to friendly messages
                    error_map = {
                        "ERR_NOT_GROUP_ADMIN": "机器人权限不足（需要管理员或群主权限）",
                        "ERR_NOT_FRIEND": "对方不是好友",
                        "ERR_NO_PERMISSION": "权限不足"
                    }
                    error_msg = error_map.get(error_code, wording)
                else:
                    error_msg = wording
            else:
                error_msg = wording
        elif message:
            error_msg = message
        else:
            error_msg = f"API调用失败: {action} (retcode: {retcode})"
        
        return {
            "message": error_msg,
            "suggestion": "",
            "retcode": retcode,
            "internal_code": None
        }
    
    async def call_api(self, action: str, params: Dict[str, Any], source_plugin: Optional[str] = None) -> Dict[str, Any]:
        """Call OneBot API.
        
        Args:
            action: API action name
            params: API parameters
            source_plugin: Plugin ID that initiated the call (if any)
        """
        logger.debug(f"call_api called: action={action}, params={params}, connection_type={self.connection_type}, source_plugin={source_plugin}")
        
        # Check if this is a message-sending action
        # Include all OneBot message sending APIs
        message_actions = [
            'send_group_msg',           # 发送群消息
            'send_private_msg',         # 发送私聊消息
            'send_msg',                 # 发送消息（通用）
            'send_group_forward_msg',   # 发送合并转发群消息
            'send_private_forward_msg', # 发送合并转发私聊消息
            'send_forward_msg',         # 发送合并转发消息（通用）
        ]
        is_message_action = action in message_actions
        
        # Emit event with context before sending message (allows plugins to modify/block)
        # Note: Plugin-initiated calls are already handled by interceptors in connector.py
        # So we only need to process framework-initiated calls here
        if is_message_action and not source_plugin:
            from ..core.event_context import EventContext
            from ..core.app import get_app
            
            app = get_app()
            if app and hasattr(app, 'plugin_connector') and app.plugin_connector:
                # Create event context for message before send
                ctx = EventContext(
                    event_name='message.before_send',
                    event_data={
                        'action': action,
                        'params': params
                    },
                    source="onebot"
                )
                
                # Emit with context (allows plugins to modify/block)
                # Only for framework-initiated calls (plugin calls use interceptors)
                modified_ctx = await app.event_bus.emit_event_with_context(
                    'message.before_send',
                    {
                        'action': action,
                        'params': params
                    },
                    source="onebot",
                    plugin_connector=app.plugin_connector
                )
                
                if modified_ctx and modified_ctx.is_prevented_default():
                    logger.info(f"Message send blocked by plugin: {action}")
                    raise RuntimeError("Message send blocked by plugin")
                
                # Use modified params if changed
                if modified_ctx and modified_ctx.is_modified():
                    modified_data = modified_ctx.event_data
                    if 'params' in modified_data:
                        params = modified_data['params']
                        logger.info(f"Message params modified by plugin: {action}")
        elif is_message_action and source_plugin:
            # Plugin-initiated calls: interceptors already handled in connector.py
            # No need to trigger message.before_send event (to avoid blocking)
            logger.debug(f"Plugin-initiated message send: {action} from {source_plugin} (handled by interceptors)")
        
        # Helper function to emit message_sent event
        async def emit_message_sent_event(result_data: Dict[str, Any] = None):
            """Emit message_sent event for statistics."""
            try:
                from ..core.event_bus import get_event_bus
                event_bus = get_event_bus()
                if not event_bus:
                    logger.warning("EventBus not available, cannot emit message_sent event")
                    return
                
                # Determine message type from action
                if "group" in action:
                    message_type = "group"
                    target = str(params.get("group_id") or "")
                elif "private" in action:
                    message_type = "private"
                    target = str(params.get("user_id") or "")
                else:
                    # For generic send_msg or send_forward_msg, try to determine from params
                    if "group_id" in params:
                        message_type = "group"
                        target = str(params.get("group_id") or "")
                    elif "user_id" in params:
                        message_type = "private"
                        target = str(params.get("user_id") or "")
                    else:
                        message_type = "unknown"
                        target = ""
                
                message_id = result_data.get("message_id") if result_data else None
                
                logger.debug(
                    f"Emitting message_sent event: action={action}, message_type={message_type}, "
                    f"target={target}, message_id={message_id}"
                )
                
                await event_bus.publish("onebot.message_sent", {
                    "message_type": message_type,
                    "target": target,
                    "message_id": message_id,
                    "timestamp": datetime.now()
                })
                
                logger.debug(f"Successfully emitted message_sent event for {action}")
            except Exception as e:
                logger.error(f"Failed to emit message_sent event: {e}", exc_info=True)
        
        # Use WebSocket if available (forward or reverse)
        if self.connection_type in ("ws", "ws_forward") and self._ws:
            # Send via forward WebSocket with echo
            echo = str(uuid.uuid4())
            logger.debug(f"Sending API request via WebSocket: action={action}, echo={echo}")
            
            # Create future to wait for response
            future = asyncio.Future()
            self._api_responses[echo] = future
            
            try:
                payload = {
                    "action": action,
                    "params": params,
                    "echo": echo
                }
                logger.debug(f"WebSocket payload: {json.dumps(payload)}")
                await self._ws.send(json.dumps(payload))
                logger.debug(f"WebSocket message sent, waiting for response (echo={echo})")
                
                # Wait for response (使用配置的超时时间)
                try:
                    result = await asyncio.wait_for(future, timeout=self.ws_api_timeout)
                    logger.debug(f"Received API response: {result}")
                    if result.get("status") == "ok":
                        data = result.get("data", {})
                        # Emit message_sent event for message-sending actions
                        if is_message_action:
                            await emit_message_sent_event(data)
                        return data
                    else:
                        # Parse error and provide friendly error message
                        error_info = self._parse_api_error(result, action, params)
                        logger.error(f"API call failed: {error_info['message']}")
                        raise RuntimeError(error_info['message'])
                except asyncio.TimeoutError:
                    logger.error(f"API call timeout: {action} (echo={echo})")
                    raise RuntimeError(f"API call timeout: {action}")
            except Exception as e:
                logger.error(f"Failed to call API via WebSocket: {e}", exc_info=True)
                raise RuntimeError(f"Failed to call API via WebSocket: {e}")
            finally:
                # Always remove the future from the dictionary to prevent memory leaks
                self._api_responses.pop(echo, None)
                
        elif self.connection_type == "ws_reverse" and self._reverse_clients:
            # Send via reverse WebSocket
            echo = str(uuid.uuid4())
            
            # Create future to wait for response
            future = asyncio.Future()
            self._api_responses[echo] = future
            
            try:
                # Send to first available client
                if self._reverse_clients:
                    await self._reverse_clients[0].send(json.dumps({
                        "action": action,
                        "params": params,
                        "echo": echo
                    }))
                    
                    # Wait for response (使用配置的超时时间)
                    try:
                        result = await asyncio.wait_for(future, timeout=self.ws_api_timeout)
                        if result.get("status") == "ok":
                            data = result.get("data", {})
                            # Emit message_sent event for message-sending actions
                            if is_message_action:
                                await emit_message_sent_event(data)
                            return data
                        else:
                            # Parse error and provide friendly error message
                            error_info = self._parse_api_error(result, action, params)
                            logger.error(f"API call failed: {error_info['message']}")
                            raise RuntimeError(error_info['message'])
                    except asyncio.TimeoutError:
                        raise RuntimeError(f"API call timeout: {action}")
            except Exception as e:
                raise RuntimeError(f"Failed to call API via reverse WebSocket: {e}")
            finally:
                # Always remove the future from the dictionary to prevent memory leaks
                self._api_responses.pop(echo, None)
        else:
            # Fallback to HTTP
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized and WebSocket not available")

            response = await self._http_client.post(f"/{action}", json=params)
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "ok":
                data = result.get("data", {})
                # Emit message_sent event for message-sending actions
                if is_message_action:
                    await emit_message_sent_event(data)
                return data
            else:
                # Parse error and provide friendly error message
                error_info = self._parse_api_error(result, action, params)
                logger.error(f"API call failed: {error_info['message']}")
                raise RuntimeError(error_info['message'])

    def get_protocol_name(self) -> str:
        """Get protocol name."""
        return "OneBot"

    def get_protocol_version(self) -> str:
        """Get protocol version."""
        return self.version

    async def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit event to registered handlers."""
        logger.debug(f"Emitting event to {len(self._event_handlers)} handlers: {event['type']}", event_type=event['type'])
        
        # Call all registered event handlers
        for handler in self._event_handlers:
            try:
                if handler is None or not callable(handler):
                    logger.warning(f"Skipping invalid handler: {handler}")
                    continue
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}", exc_info=True)
    
    async def _cleanup_expired_responses(self) -> None:
        """Periodically cleanup expired API response futures."""
        try:
            while self._running:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Make a copy of the current responses to avoid race conditions
                current_responses = dict(self._api_responses)
                
                if not current_responses:
                    continue
                
                expired = []
                for echo, future in current_responses.items():
                    if future.done():
                        # Check if future has exception set before accessing it
                        try:
                            if future.exception() is not None:
                                logger.debug(f"Future has exception for echo: {echo}")
                        except asyncio.InvalidStateError:
                            # Future is done but no result or exception set yet
                            pass
                        expired.append(echo)
                
                for echo in expired:
                    # Double-check the item still exists before removing
                    if echo in self._api_responses:
                        self._api_responses.pop(echo, None)
                        logger.debug(f"Cleaned up expired API response future: {echo}")
                
                # Log warning if too many pending responses
                if len(self._api_responses) > 100:
                    logger.warning(f"Too many pending API responses: {len(self._api_responses)}, possible memory leak")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}", exc_info=True)
    
    def _cancel_all_pending_responses(self) -> None:
        """Cancel all pending API response futures (e.g., when WebSocket disconnects)."""
        # Create a copy of the items to avoid modifying the dictionary during iteration
        responses_copy = dict(self._api_responses)
        
        count = 0
        for echo, future in responses_copy.items():
            if echo in self._api_responses:  # Double-check the item still exists
                if not future.done():
                    try:
                        future.cancel()
                        count += 1
                    except Exception:
                        # Ignore errors when cancelling futures
                        pass
                # Remove from the original dictionary
                self._api_responses.pop(echo, None)
        
        if count > 0:
            logger.warning(f"Cancelled {count} pending API response futures due to connection close")
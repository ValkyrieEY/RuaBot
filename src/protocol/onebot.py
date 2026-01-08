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
        
        # Event handlers
        self._event_handlers: List = []

    def on_event(self, handler):
        """Register an event handler.
        
        Args:
            handler: Async function that takes event dict as parameter
        """
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
            timeout=30.0
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

        logger.info("OneBot adapter stopped")

    async def _ws_forward_handler(self) -> None:
        """Handle forward WebSocket connection."""
        while self._running:
            try:
                # Build connection parameters
                # For websockets >= 12.0 (Python 3.13 compatible), use additional_headers (list of tuples)
                # For older versions, use extra_headers (dict)
                connect_kwargs = {}
                if self.access_token:
                    # Try additional_headers first (websockets >= 12.0, Python 3.13 compatible)
                    # This is a list of (header_name, header_value) tuples
                    connect_kwargs["additional_headers"] = [
                        ("Authorization", f"Bearer {self.access_token}")
                    ]

                logger.info(f"Connecting to forward WebSocket: {self.ws_url}")
                if self.access_token:
                    logger.info("🔑 Using access token for authentication")
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
                                        logger.warning(f"No waiting future found for echo: {echo}, active echoes: {list(self._api_responses.keys())}")
                                
                                post_type = data.get("post_type", "unknown")
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
                    finally:
                        # Close connection
                        if ws:
                            await ws.close()
                        self._ws = None
                        logger.warning("WebSocket connection closed normally")
                        
                except websockets.exceptions.InvalidURI as e:
                    logger.error("Invalid WebSocket URL", url=self.ws_url, error=str(e))
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
                except ConnectionRefusedError as e:
                    logger.error("Connection refused", url=self.ws_url, error=str(e))
                    logger.info("Please check if the OneBot implementation is running and accessible")
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
                except Exception as e:
                    logger.error("Forward WebSocket connection error", error=str(e), error_type=type(e).__name__, exc_info=True)
                    if self._running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)
            except Exception as e:
                # Catch any unexpected errors in the outer try block
                logger.error("Unexpected error in WebSocket handler", error=str(e), exc_info=True)
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
                                logger.warning(f"No waiting future found for echo: {echo}, active echoes: {list(self._api_responses.keys())}")
                        
                        logger.debug("Received reverse WebSocket message", post_type=data.get("post_type", "unknown"))
                        await self._handle_event(data)
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON in reverse WebSocket message", error=str(e))
                    except Exception as e:
                        logger.error("Error handling reverse WebSocket message", error=str(e), exc_info=True)
            except websockets.exceptions.ConnectionClosed:
                logger.info("Reverse WebSocket client disconnected")
            finally:
                if websocket in self._reverse_clients:
                    self._reverse_clients.remove(websocket)
        
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
        user_id = data.get("user_id")
        self_id = data.get("self_id")
        if user_id and self_id and str(user_id) == str(self_id):
            logger.debug("Skipping self message", user_id=user_id)
            return
        
        # Log received event (similar to old project)
        if post_type == "message":
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
            return {"message_id": None}  # WebSocket doesn't return immediately
        elif self.connection_type == "ws_reverse" and self._reverse_clients:
            # Send via reverse WebSocket
            for client in self._reverse_clients:
                await client.send(json.dumps({
                    "action": endpoint,
                    "params": payload,
                    "echo": None
                }))
            return {"message_id": None}
        else:
            # Send via HTTP
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized")
            
            response = await self._http_client.post(f"/{endpoint}", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "ok":
                logger.info("Message sent", message_id=result.get("data", {}).get("message_id"))
                return result.get("data", {})
            else:
                logger.error("Failed to send message", result=result)
                raise RuntimeError(f"Failed to send message: {result}")

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

    async def call_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call OneBot API."""
        logger.debug(f"call_api called: action={action}, params={params}, connection_type={self.connection_type}")
        
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
                
                # Wait for response (timeout: 10 seconds)
                try:
                    result = await asyncio.wait_for(future, timeout=10.0)
                    logger.debug(f"Received API response: {result}")
                    if result.get("status") == "ok":
                        return result.get("data", {})
                    else:
                        logger.error(f"API call failed: {result}")
                        raise RuntimeError(f"API call failed: {result}")
                except asyncio.TimeoutError:
                    self._api_responses.pop(echo, None)
                    logger.error(f"API call timeout: {action} (echo={echo})")
                    raise RuntimeError(f"API call timeout: {action}")
            except Exception as e:
                self._api_responses.pop(echo, None)
                logger.error(f"Failed to call API via WebSocket: {e}", exc_info=True)
                raise RuntimeError(f"Failed to call API via WebSocket: {e}")
                
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
                    
                    # Wait for response (timeout: 10 seconds)
                    try:
                        result = await asyncio.wait_for(future, timeout=10.0)
                        if result.get("status") == "ok":
                            return result.get("data", {})
                        else:
                            raise RuntimeError(f"API call failed: {result}")
                    except asyncio.TimeoutError:
                        self._api_responses.pop(echo, None)
                        raise RuntimeError(f"API call timeout: {action}")
            except Exception as e:
                self._api_responses.pop(echo, None)
                raise RuntimeError(f"Failed to call API via reverse WebSocket: {e}")
        else:
            # Fallback to HTTP
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized and WebSocket not available")

            response = await self._http_client.post(f"/{action}", json=params)
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "ok":
                return result.get("data", {})
            else:
                raise RuntimeError(f"API call failed: {result}")

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
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}", exc_info=True)



"""MCP (Model Context Protocol) client implementation."""

import json
import asyncio
import subprocess
import os
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import httpx
import uuid as uuid_lib

from ..core.logger import get_logger

logger = get_logger(__name__)


class MCPClient:
    """MCP client for stdio and SSE modes."""
    
    def __init__(self, mode: str, config: Dict[str, Any]):
        """
        Initialize MCP client.
        
        Args:
            mode: 'stdio' or 'sse'
            config: Configuration dict
                - stdio: command, args, env
                - sse: url, headers, timeout
        """
        self.mode = mode
        self.config = config
        self._process: Optional[asyncio.subprocess.Process] = None
        self._sse_client: Optional[httpx.AsyncClient] = None
        self._request_id = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._connected = False
        self._server_info: Optional[Dict[str, Any]] = None
        
    async def connect(self) -> bool:
        """Connect to MCP server."""
        try:
            if self.mode == 'stdio':
                return await self._connect_stdio()
            elif self.mode == 'sse':
                return await self._connect_sse()
            else:
                logger.error(f"Unknown MCP mode: {self.mode}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}", exc_info=True)
            return False
    
    async def _connect_stdio(self) -> bool:
        """Connect via stdio (subprocess)."""
        try:
            command = self.config.get('command')
            if not command:
                logger.error("stdio mode requires 'command' in config")
                return False
            
            args = self.config.get('args', [])
            env = self.config.get('env', {})
            
            # Start subprocess
            self._process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(os.environ), **env} if env else None
            )
            
            # Start reader task
            asyncio.create_task(self._stdio_reader())
            
            # Initialize connection
            result = await self._send_request('initialize', {
                'protocolVersion': '2024-11-05',
                'capabilities': {
                    'tools': {}
                },
                'clientInfo': {
                    'name': 'Xiaoyi_QQ',
                    'version': '0.0.1'
                }
            })
            
            if result:
                self._server_info = result.get('serverInfo', {})
                # Send initialized notification
                await self._send_notification('notifications/initialized', {})
                self._connected = True
                logger.info(f"MCP stdio client connected: {self._server_info.get('name', 'unknown')}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"stdio connection error: {e}", exc_info=True)
            return False
    
    async def _connect_sse(self) -> bool:
        """Connect via SSE (HTTP)."""
        try:
            url = self.config.get('url')
            if not url:
                logger.error("sse mode requires 'url' in config")
                return False
            
            headers = self.config.get('headers', {})
            timeout = self.config.get('timeout', 10)
            
            self._sse_client = httpx.AsyncClient(
                timeout=timeout,
                headers=headers
            )
            
            # SSE connection - send initialize via POST
            init_response = await self._sse_request('initialize', {
                'protocolVersion': '2024-11-05',
                'capabilities': {
                    'tools': {}
                },
                'clientInfo': {
                    'name': 'Xiaoyi_QQ',
                    'version': '0.0.1'
                }
            }, url)
            
            if init_response:
                self._server_info = init_response.get('serverInfo', {})
                # Send initialized notification
                await self._sse_request('notifications/initialized', {}, url)
                self._connected = True
                logger.info(f"MCP SSE client connected: {self._server_info.get('name', 'unknown')}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"SSE connection error: {e}", exc_info=True)
            return False
    
    async def _stdio_reader(self):
        """Read messages from stdio."""
        try:
            buffer = ""
            while True:
                if not self._process or not self._process.stdout:
                    break
                
                data = await self._process.stdout.read(4096)
                if not data:
                    break
                
                buffer += data.decode('utf-8', errors='ignore')
                
                # Process complete JSON messages (newline-delimited)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            await self._handle_message(message)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON from MCP server: {line[:100]}")
        except Exception as e:
            logger.error(f"stdio reader error: {e}", exc_info=True)
        finally:
            self._connected = False
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send JSON-RPC request via stdio."""
        if not self._process or not self._process.stdin:
            return None
        
        self._request_id += 1
        request_id = str(self._request_id)
        
        request = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
            'params': params
        }
        
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            message = json.dumps(request) + '\n'
            self._process.stdin.write(message.encode('utf-8'))
            await self._process.stdin.drain()
            
            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(future, timeout=30.0)
                return response
            except asyncio.TimeoutError:
                logger.warning(f"MCP request timeout: {method}")
                self._pending_requests.pop(request_id, None)
                return None
        except Exception as e:
            logger.error(f"Error sending MCP request: {e}", exc_info=True)
            self._pending_requests.pop(request_id, None)
            return None
    
    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return
        
        notification = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params
        }
        
        try:
            message = json.dumps(notification) + '\n'
            self._process.stdin.write(message.encode('utf-8'))
            await self._process.stdin.drain()
        except Exception as e:
            logger.error(f"Error sending MCP notification: {e}", exc_info=True)
    
    async def _sse_request(self, method: str, params: Dict[str, Any], base_url: str) -> Optional[Dict[str, Any]]:
        """Send request via SSE (HTTP POST)."""
        if not self._sse_client:
            return None
        
        request_id = str(uuid_lib.uuid4())
        request = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
            'params': params
        }
        
        try:
            # For SSE, we use POST for requests
            response = await self._sse_client.post(
                base_url,
                json=request,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            result = response.json()
            
            if 'error' in result:
                logger.error(f"MCP error: {result['error']}")
                return None
            
            return result.get('result')
        except Exception as e:
            logger.error(f"SSE request error: {e}", exc_info=True)
            return None
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from server."""
        if 'id' in message:
            # Response to a request
            request_id = str(message.get('id'))
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if 'error' in message:
                    future.set_exception(Exception(f"MCP error: {message['error']}"))
                else:
                    future.set_result(message.get('result'))
        elif 'method' in message:
            # Notification or request from server
            method = message.get('method')
            params = message.get('params', {})
            logger.debug(f"MCP server notification: {method}")
            # Handle server notifications if needed
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server."""
        if not self._connected:
            return []
        
        try:
            if self.mode == 'stdio':
                result = await self._send_request('tools/list', {})
            else:
                result = await self._sse_request('tools/list', {}, self.config.get('url'))
            
            if result:
                return result.get('tools', [])
            return []
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}", exc_info=True)
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        if not self._connected:
            raise RuntimeError("MCP client not connected")
        
        try:
            if self.mode == 'stdio':
                result = await self._send_request('tools/call', {
                    'name': tool_name,
                    'arguments': arguments
                })
            else:
                result = await self._sse_request('tools/call', {
                    'name': tool_name,
                    'arguments': arguments
                }, self.config.get('url'))
            
            if result:
                return result
            raise RuntimeError(f"Tool call failed: {tool_name}")
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}", exc_info=True)
            raise
    
    async def disconnect(self):
        """Disconnect from MCP server."""
        self._connected = False
        
        if self.mode == 'stdio' and self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                await self._process.wait()
            except Exception as e:
                logger.warning(f"Error terminating stdio process: {e}")
            finally:
                self._process = None
        
        if self.mode == 'sse' and self._sse_client:
            try:
                await self._sse_client.aclose()
            except Exception as e:
                logger.warning(f"Error closing SSE client: {e}")
            finally:
                self._sse_client = None
        
        self._pending_requests.clear()
        logger.info("MCP client disconnected")
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected
    
    @property
    def server_info(self) -> Optional[Dict[str, Any]]:
        """Get server info."""
        return self._server_info


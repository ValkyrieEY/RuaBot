"""MCP (Model Context Protocol) server manager."""

import uuid
import asyncio
from typing import Optional, List, Dict, Any
from ..core.database import DatabaseManager, get_database_manager
from ..core.models.ai import MCPServer
from ..core.logger import get_logger
from .mcp_client import MCPClient

logger = get_logger(__name__)


class MCPManager:
    """Manages MCP servers."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or get_database_manager()
        self._servers_cache: Dict[str, MCPServer] = {}
        self._connections: Dict[str, MCPClient] = {}  # Runtime connections
        self._tools_cache: Dict[str, List[Dict[str, Any]]] = {}  # Cached tools per server
    
    async def initialize(self):
        """Initialize MCP manager and connect to enabled servers."""
        await self._refresh_cache()
        
        # Connect to enabled servers
        servers = await self.db_manager.list_mcp_servers(enabled_only=True)
        for server in servers:
            try:
                await self.connect_server(server.uuid)
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {server.uuid}: {e}", exc_info=True)
        
        logger.info(f"MCPManager initialized with {len(self._connections)} connections")
    
    async def _refresh_cache(self):
        """Refresh servers cache."""
        servers = await self.db_manager.list_mcp_servers()
        self._servers_cache = {server.uuid: server for server in servers}
    
    async def list_servers(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all MCP servers with connection status."""
        servers = await self.db_manager.list_mcp_servers(enabled_only)
        result = []
        for server in servers:
            server_dict = server.to_dict()
            # Add connection status
            if server.uuid in self._connections:
                client = self._connections[server.uuid]
                server_dict['status'] = 'connected' if client.is_connected else 'disconnected'
                server_dict['server_info'] = client.server_info
            else:
                server_dict['status'] = 'disconnected' if server.enabled else 'disabled'
            result.append(server_dict)
        return result
    
    async def get_server(self, server_uuid: str) -> Optional[Dict[str, Any]]:
        """Get MCP server by UUID."""
        server = await self.db_manager.get_mcp_server(server_uuid)
        if server:
            server_dict = server.to_dict()
            # Add connection status
            if server_uuid in self._connections:
                client = self._connections[server_uuid]
                server_dict['status'] = 'connected' if client.is_connected else 'disconnected'
                server_dict['server_info'] = client.server_info
            else:
                server_dict['status'] = 'disconnected' if server.enabled else 'disabled'
            return server_dict
        return None
    
    async def create_server(
        self,
        name: str,
        mode: str,
        enabled: bool = False,
        description: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new MCP server."""
        server_uuid = str(uuid.uuid4())
        
        server = await self.db_manager.create_mcp_server(
            uuid=server_uuid,
            name=name,
            mode=mode,
            enabled=enabled,
            description=description,
            command=command,
            args=args or [],
            env=env or {},
            url=url,
            headers=headers or {},
            timeout=timeout,
            config=config or {}
        )
        
        await self._refresh_cache()
        
        if enabled:
            await self.connect_server(server_uuid)
        
        logger.info(f"MCP server created: {name} ({server_uuid})")
        return await self.get_server(server_uuid) or server.to_dict()
    
    async def update_server(
        self,
        server_uuid: str,
        **kwargs
    ) -> bool:
        """Update MCP server."""
        success = await self.db_manager.update_mcp_server(server_uuid, **kwargs)
        if success:
            await self._refresh_cache()
            
            # Reconnect if enabled status changed
            if 'enabled' in kwargs:
                server = await self.db_manager.get_mcp_server(server_uuid)
                if server:
                    if server.enabled:
                        await self.connect_server(server_uuid)
                    else:
                        await self.disconnect_server(server_uuid)
            
            logger.info(f"MCP server updated: {server_uuid}")
        return success
    
    async def delete_server(self, server_uuid: str) -> bool:
        """Delete MCP server."""
        # Disconnect if connected
        await self.disconnect_server(server_uuid)
        
        success = await self.db_manager.delete_mcp_server(server_uuid)
        if success:
            if server_uuid in self._servers_cache:
                del self._servers_cache[server_uuid]
            if server_uuid in self._tools_cache:
                del self._tools_cache[server_uuid]
            logger.info(f"MCP server deleted: {server_uuid}")
        return success
    
    async def connect_server(self, server_uuid: str) -> bool:
        """Connect to MCP server."""
        # Disconnect if already connected
        if server_uuid in self._connections:
            await self.disconnect_server(server_uuid)
        
        server = await self.db_manager.get_mcp_server(server_uuid)
        if not server:
            logger.error(f"MCP server not found: {server_uuid}")
            return False
        
        try:
            # Build client config
            config = {}
            if server.mode == 'stdio':
                config = {
                    'command': server.command,
                    'args': server.args or [],
                    'env': server.env or {}
                }
            elif server.mode == 'sse':
                config = {
                    'url': server.url,
                    'headers': server.headers or {},
                    'timeout': server.timeout or 10
                }
            else:
                logger.error(f"Unknown MCP mode: {server.mode}")
                return False
            
            # Create and connect client
            client = MCPClient(server.mode, config)
            connected = await client.connect()
            
            if connected:
                self._connections[server_uuid] = client
                # Refresh tools cache
                await self._refresh_tools(server_uuid)
                logger.info(f"Connected to MCP server: {server.name} ({server_uuid})")
                return True
            else:
                logger.error(f"Failed to connect to MCP server: {server_uuid}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to MCP server {server_uuid}: {e}", exc_info=True)
            return False
    
    async def disconnect_server(self, server_uuid: str) -> bool:
        """Disconnect from MCP server."""
        if server_uuid in self._connections:
            client = self._connections[server_uuid]
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting MCP client: {e}")
            del self._connections[server_uuid]
            
            if server_uuid in self._tools_cache:
                del self._tools_cache[server_uuid]
            
            logger.info(f"Disconnected from MCP server: {server_uuid}")
            return True
        return False
    
    async def _refresh_tools(self, server_uuid: str):
        """Refresh tools cache for a server."""
        if server_uuid not in self._connections:
            return
        
        client = self._connections[server_uuid]
        try:
            tools = await client.list_tools()
            self._tools_cache[server_uuid] = tools
            logger.debug(f"Refreshed {len(tools)} tools from server {server_uuid}")
        except Exception as e:
            logger.error(f"Error refreshing tools for server {server_uuid}: {e}", exc_info=True)
            self._tools_cache[server_uuid] = []
    
    async def get_server_tools(self, server_uuid: str) -> List[Dict[str, Any]]:
        """Get tools from MCP server."""
        # Return cached tools if available
        if server_uuid in self._tools_cache:
            return self._tools_cache[server_uuid]
        
        # Try to refresh if connected
        if server_uuid in self._connections:
            await self._refresh_tools(server_uuid)
            return self._tools_cache.get(server_uuid, [])
        
        return []
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all connected MCP servers."""
        all_tools = []
        for server_uuid in self._connections.keys():
            tools = await self.get_server_tools(server_uuid)
            # Add server UUID to each tool for identification
            for tool in tools:
                tool['_mcp_server'] = server_uuid
            all_tools.extend(tools)
        return all_tools
    
    async def call_tool(
        self,
        server_uuid: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Call a tool from MCP server."""
        if server_uuid not in self._connections:
            raise RuntimeError(f"MCP server {server_uuid} not connected")
        
        client = self._connections[server_uuid]
        if not client.is_connected:
            raise RuntimeError(f"MCP server {server_uuid} connection lost")
        
        try:
            result = await client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name} on server {server_uuid}: {e}", exc_info=True)
            raise
    
    async def convert_mcp_tools_to_openai_format(self) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format."""
        all_tools = await self.get_all_tools()
        openai_tools = []
        
        for tool in all_tools:
            server_uuid = tool.get('_mcp_server', 'unknown')
            tool_name = tool.get('name', 'unknown')
            
            # Convert MCP tool format to OpenAI format
            # MCP tool format: {name, description, inputSchema}
            # OpenAI format: {type: "function", function: {name, description, parameters}}
            input_schema = tool.get('inputSchema', {})
            
            openai_tool = {
                "type": "function",
                "function": {
                    "name": f"mcp_{server_uuid}_{tool_name}",
                    "description": tool.get('description', f"MCP tool: {tool_name}"),
                    "parameters": input_schema if input_schema else {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    def get_mcp_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Parse MCP tool name and return server UUID and tool name.
        
        Args:
            tool_name: Tool name in format "mcp_{server_uuid}_{tool_name}"
        
        Returns:
            Dict with 'server_uuid' and 'tool_name', or None if invalid
        """
        if not tool_name.startswith('mcp_'):
            return None
        
        parts = tool_name.split('_', 2)
        if len(parts) >= 3:
            return {
                'server_uuid': parts[1],
                'tool_name': parts[2]
            }
        return None

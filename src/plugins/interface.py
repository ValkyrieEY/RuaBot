"""Plugin interface definition."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class PluginPermission(str, Enum):
    """Plugin permission levels."""
    READ_ONLY = "read_only"
    PLUGIN_LIMITED_ACCESS = "plugin_limited_access"
    PLUGIN_FULL_ACCESS = "plugin_full_access"
    SYSTEM_SENSITIVE = "system_sensitive"


@dataclass
class PluginMetadata:
    """Plugin metadata information."""
    
    name: str
    version: str
    author: str
    description: str
    
    # Requirements
    required_permissions: List[PluginPermission] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Configuration
    config_schema: Optional[Dict[str, Any]] = None
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Tags and categories
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    
    # URLs
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "required_permissions": [p.value for p in self.required_permissions],
            "required_capabilities": self.required_capabilities,
            "dependencies": self.dependencies,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "tags": self.tags,
            "category": self.category,
            "homepage": self.homepage,
            "repository": self.repository,
            "documentation": self.documentation,
        }


class PluginInterface(ABC):
    """Base plugin interface that all plugins must implement."""

    def __init__(self):
        self._metadata: Optional[PluginMetadata] = None
        self._config: Dict[str, Any] = {}
        self._enabled: bool = True

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata.
        
        Returns:
            PluginMetadata with plugin information
        """
        pass

    @abstractmethod
    async def on_load(self, context: Dict[str, Any]) -> None:
        """
        Called when plugin is loaded.
        
        Args:
            context: Global context with shared resources
        """
        pass

    @abstractmethod
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass

    @abstractmethod
    async def on_enable(self) -> None:
        """Called when plugin is enabled."""
        pass

    @abstractmethod
    async def on_disable(self) -> None:
        """Called when plugin is disabled."""
        pass

    async def on_event(self, event_name: str, payload: Any) -> None:
        """
        Handle events from event bus.
        
        Args:
            event_name: Name of the event
            payload: Event payload data
        """
        pass

    async def on_command(self, command: str, args: Dict[str, Any]) -> Any:
        """
        Handle commands directed to this plugin.
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Command result
        """
        pass

    async def on_message(self, envelope: Any) -> Optional[Any]:
        """
        Handle incoming messages.
        
        Args:
            envelope: Message envelope
            
        Returns:
            Response or None
        """
        pass

    def get_config(self) -> Dict[str, Any]:
        """Get plugin configuration."""
        return self._config.copy()

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update plugin configuration."""
        self._config.update(config)

    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Set plugin enabled state."""
        self._enabled = enabled

    def validate_permissions(self, required: List[PluginPermission]) -> bool:
        """
        Validate if plugin has required permissions.
        
        Args:
            required: List of required permissions
            
        Returns:
            True if plugin has all required permissions
        """
        metadata = self.get_metadata()
        plugin_perms = set(metadata.required_permissions)
        required_perms = set(required)
        return required_perms.issubset(plugin_perms)


class BasePlugin(PluginInterface):
    """Base plugin implementation with common functionality."""

    def __init__(self, metadata: PluginMetadata):
        super().__init__()
        self._metadata = metadata

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        if self._metadata is None:
            raise RuntimeError("Plugin metadata not initialized")
        return self._metadata

    async def on_load(self, context: Dict[str, Any]) -> None:
        """Default load implementation."""
        self._config = self._metadata.default_config.copy() if self._metadata else {}

    async def on_unload(self) -> None:
        """Default unload implementation."""
        pass

    async def on_enable(self) -> None:
        """Default enable implementation."""
        self._enabled = True

    async def on_disable(self) -> None:
        """Default disable implementation."""
        self._enabled = False


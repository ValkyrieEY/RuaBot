"""Plugin system with hot-reloading and permission management."""

from .interface import PluginInterface, PluginMetadata, PluginPermission
from .manager import PluginManager, get_plugin_manager
from .capability_registry import CapabilityRegistry, Capability

__all__ = [
    "PluginInterface",
    "PluginMetadata",
    "PluginPermission",
    "PluginManager",
    "get_plugin_manager",
    "CapabilityRegistry",
    "Capability",
]


"""Plugin manager with hot-reloading support."""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import inspect
import json
from datetime import datetime

from .interface import PluginInterface, PluginMetadata, PluginPermission
from .capability_registry import CapabilityRegistry, get_capability_registry
from ..core.logger import get_logger
from ..core.event_bus import EventBus, get_event_bus

logger = get_logger(__name__)


class PluginDependency:
    """插件依赖"""
    
    def __init__(self, name: str, version: str = "*", required: bool = True):
        self.name = name
        self.version = version
        self.required = required
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "required": self.required
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginDependency":
        return cls(
            name=data["name"],
            version=data.get("version", "*"),
            required=data.get("required", True)
        )


class PluginManager:
    """Manage plugin lifecycle with hot-reloading."""

    def __init__(
        self,
        plugin_dir: str,
        event_bus: Optional[EventBus] = None,
        capability_registry: Optional[CapabilityRegistry] = None
    ):
        # Resolve relative paths relative to project root
        plugin_path = Path(plugin_dir)
        if not plugin_path.is_absolute():
            # Get project root (onebot_framework directory)
            # manager.py is at: onebot_framework/src/plugins/manager.py
            project_root = Path(__file__).parent.parent.parent
            plugin_path = (project_root / plugin_dir).resolve()
        self.plugin_dir = plugin_path
        self.event_bus = event_bus or get_event_bus()
        self.capability_registry = capability_registry or get_capability_registry()
        
        self._plugins: Dict[str, PluginInterface] = {}
        self._plugin_modules: Dict[str, Any] = {}
        self._plugin_contexts: Dict[str, Dict[str, Any]] = {}
        self._plugin_dependencies: Dict[str, List[PluginDependency]] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._disabled_plugins: List[str] = []
        
        # Create plugin directory if it doesn't exist
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Load disabled plugins list
        self._load_disabled_list()

    def _load_disabled_list(self):
        """加载禁用插件列表"""
        disabled_file = self.plugin_dir / ".disabled"
        if disabled_file.exists():
            try:
                with open(disabled_file, 'r') as f:
                    self._disabled_plugins = [line.strip() for line in f if line.strip()]
            except Exception as e:
                logger.error(f"Failed to load disabled plugins list: {e}")
    
    def _save_disabled_list(self):
        """保存禁用插件列表"""
        disabled_file = self.plugin_dir / ".disabled"
        try:
            with open(disabled_file, 'w') as f:
                for plugin_name in self._disabled_plugins:
                    f.write(f"{plugin_name}\n")
        except Exception as e:
            logger.error(f"Failed to save disabled plugins list: {e}")
    
    def _load_plugin_config(self, plugin_name: str, plugin_dir: Path) -> Dict[str, Any]:
        """加载插件配置文件 plugin.json"""
        config_file = plugin_dir / "plugin.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load plugin config for {plugin_name}: {e}")
        return {}
    
    def _load_plugin_system_data(self, plugin_name: str, plugin_dir: Path) -> Dict[str, Any]:
        """加载插件系统数据 system.json"""
        system_file = plugin_dir / "system.json"
        if system_file.exists():
            try:
                with open(system_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load system data for {plugin_name}: {e}")
        return {
            "adapter": None,
            "enabled": False,
            "config": {},
            "load_time": None,
            "last_modified": None
        }
    
    def _save_plugin_system_data(self, plugin_name: str, plugin_dir: Path, system_data: Dict[str, Any]) -> None:
        """保存插件系统数据 system.json"""
        system_file = plugin_dir / "system.json"
        try:
            system_data["last_modified"] = datetime.now().isoformat()
            with open(system_file, 'w', encoding='utf-8') as f:
                json.dump(system_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save system data for {plugin_name}: {e}")
    
    def _load_plugin_dependencies(self, plugin_config: Dict[str, Any]) -> List[PluginDependency]:
        """加载插件依赖"""
        dependencies = []
        deps_data = plugin_config.get("dependencies", [])
        for dep in deps_data:
            if isinstance(dep, str):
                dependencies.append(PluginDependency(dep))
            elif isinstance(dep, dict):
                dependencies.append(PluginDependency.from_dict(dep))
        return dependencies
    
    def _check_dependencies(self, plugin_name: str, dependencies: List[PluginDependency]) -> bool:
        """检查插件依赖是否满足"""
        for dep in dependencies:
            if dep.name not in self._plugins:
                if dep.required:
                    logger.error(f"Plugin {plugin_name} requires {dep.name} but it's not loaded")
                    return False
                else:
                    logger.warning(f"Optional dependency {dep.name} not loaded for {plugin_name}")
        return True

    async def load_plugin(
        self,
        plugin_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Load a plugin by name.
        
        Args:
            plugin_name: Name of the plugin (module name)
            context: Context to pass to plugin
            
        Returns:
            True if loaded successfully
        """
        if plugin_name in self._plugins:
            logger.warning("Plugin already loaded", plugin=plugin_name)
            return False
        
        # Check if plugin is disabled
        if plugin_name in self._disabled_plugins:
            logger.info(f"Plugin {plugin_name} is disabled, skipping")
            return False

        try:
            # Plugins must be in folders with plugin.json
            plugin_dir = self.plugin_dir / plugin_name
            
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                logger.error("Plugin directory not found", plugin=plugin_name)
                return False
            
            # Check for plugin.json (required)
            if not (plugin_dir / "plugin.json").exists():
                logger.error("Plugin plugin.json not found", plugin=plugin_name)
                return False
            
            # Load plugin configuration and system data
            plugin_config = self._load_plugin_config(plugin_name, plugin_dir)
            system_data = self._load_plugin_system_data(plugin_name, plugin_dir)
            self._plugin_configs[plugin_name] = plugin_config
            
            # Check if plugin is enabled
            if not system_data.get("enabled", False):
                logger.info(f"Plugin {plugin_name} is disabled, skipping load")
                return False
            
            # Check if plugin has an adapter assigned
            adapter_name = system_data.get("adapter")
            if not adapter_name:
                logger.warning(f"Plugin {plugin_name} has no adapter assigned, cannot load")
                return False
            
            # Load dependencies
            dependencies = self._load_plugin_dependencies(plugin_config)
            if dependencies:
                self._plugin_dependencies[plugin_name] = dependencies
                if not self._check_dependencies(plugin_name, dependencies):
                    return False

            # Load plugin via adapter (required)
            from .adapters import get_adapter_manager
            adapter_manager = get_adapter_manager()
            adapter = adapter_manager.get_adapter(adapter_name)
            
            if not adapter:
                logger.error(f"Adapter {adapter_name} not found for plugin {plugin_name}")
                return False
            
            if not adapter.is_loaded():
                logger.error(f"Adapter {adapter_name} is not loaded for plugin {plugin_name}")
                return False
            
            logger.info(f"Loading plugin {plugin_name} via adapter {adapter_name}")
            try:
                # Pass plugin directory path to adapter, let adapter decide entry file
                plugin_path = str(plugin_dir)
                adapter_config = adapter.get_config()
                
                plugin_instance = await adapter.load_plugin(
                    plugin_path,
                    plugin_config,
                    adapter_config
                )
                
                # Create context
                plugin_context = context or {}
                plugin_context.update({
                    "event_bus": self.event_bus,
                    "capability_registry": self.capability_registry,
                    "plugin_manager": self,
                    "plugin_config": plugin_config,
                    "adapter": adapter,
                    "adapter_name": adapter_name,
                    "app": context.get("app") if context else None,
                    "plugin_dir": str(plugin_dir),
                    "data_dir": str(plugin_dir / "data"),
                })
                
                self._plugin_contexts[plugin_name] = plugin_context
                
                # Load config from data/config.json if exists, otherwise use default_config
                data_config_file = plugin_dir / "data" / "config.json"
                if data_config_file.exists():
                    try:
                        with open(data_config_file, 'r', encoding='utf-8') as f:
                            saved_config = json.load(f)
                        # Merge with default_config (saved config takes precedence)
                        final_config = {**plugin_config.get("default_config", {}), **saved_config}
                        plugin_instance._config = final_config
                        logger.debug(f"Loaded config from {data_config_file} for plugin {plugin_name}")
                    except Exception as e:
                        logger.warning(f"Failed to load config from {data_config_file}: {e}")
                        # Fall back to default_config
                        plugin_instance._config = plugin_config.get("default_config", {}).copy()
                else:
                    # Use default_config
                    plugin_instance._config = plugin_config.get("default_config", {}).copy()
                
                # Call plugin lifecycle methods
                if hasattr(plugin_instance, "on_load"):
                    try:
                        await plugin_instance.on_load(plugin_context)
                        logger.debug(f"Plugin {plugin_name} on_load called")
                    except Exception as e:
                        logger.error(f"Error calling on_load for plugin {plugin_name}: {e}", exc_info=True)
                
                # Enable plugin if it's enabled in system data
                if system_data.get("enabled", False):
                    if hasattr(plugin_instance, "on_enable"):
                        try:
                            await plugin_instance.on_enable()
                            logger.debug(f"Plugin {plugin_name} on_enable called")
                        except Exception as e:
                            logger.error(f"Error calling on_enable for plugin {plugin_name}: {e}", exc_info=True)
                
                # Store plugin instance
                self._plugins[plugin_name] = plugin_instance
                
                # Update system data
                system_data["load_time"] = datetime.now().isoformat()
                self._save_plugin_system_data(plugin_name, plugin_dir, system_data)
                
                logger.info(f"Plugin {plugin_name} loaded successfully via adapter {adapter_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name} via adapter {adapter_name}: {e}", exc_info=True)
                return False

            # Publish load event
            await self.event_bus.publish(
                "plugin.loaded",
                {
                    "plugin": plugin_name,
                    "metadata": metadata.to_dict()
                },
                source="plugin_manager"
            )

            logger.info("Plugin loaded successfully", plugin=plugin_name)
            return True

        except Exception as e:
            logger.error(
                "Failed to load plugin",
                plugin=plugin_name,
                error=str(e),
                exc_info=True
            )
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self._plugins:
            logger.warning("Plugin not loaded", plugin=plugin_name)
            return False

        try:
            plugin = self._plugins[plugin_name]
            
            # Call on_unload
            await plugin.on_unload()
            
            # Unregister capabilities
            self.capability_registry.unregister_provider(plugin_name)
            
            # Remove from registry
            del self._plugins[plugin_name]
            del self._plugin_contexts[plugin_name]
            
            # Remove module
            if plugin_name in self._plugin_modules:
                del self._plugin_modules[plugin_name]
            if plugin_name in sys.modules:
                del sys.modules[plugin_name]

            # Publish unload event
            await self.event_bus.publish(
                "plugin.unloaded",
                {"plugin": plugin_name},
                source="plugin_manager"
            )

            logger.info("Plugin unloaded", plugin=plugin_name)
            return True

        except Exception as e:
            logger.error(
                "Failed to unload plugin",
                plugin=plugin_name,
                error=str(e),
                exc_info=True
            )
            return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if reloaded successfully
        """
        context = self._plugin_contexts.get(plugin_name, {})
        
        if await self.unload_plugin(plugin_name):
            return await self.load_plugin(plugin_name, context)
        return False

    async def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin."""
        plugin_dir = self.plugin_dir / plugin_name
        if not plugin_dir.exists():
            logger.error(f"Plugin directory not found: {plugin_name}")
            return False
        
        # Update system.json
        system_data = self._load_plugin_system_data(plugin_name, plugin_dir)
        system_data["enabled"] = True
        self._save_plugin_system_data(plugin_name, plugin_dir, system_data)
        
        # If plugin is not loaded, load it
        if plugin_name not in self._plugins:
            load_success = await self.load_plugin(plugin_name)
            if not load_success:
                return False
        
        plugin = self._plugins[plugin_name]
        if plugin.is_enabled():
            return True

        try:
            await plugin.on_enable()
            plugin.set_enabled(True)
            
            await self.event_bus.publish(
                "plugin.enabled",
                {"plugin": plugin_name},
                source="plugin_manager"
            )
            
            logger.info("Plugin enabled", plugin=plugin_name)
            return True

        except Exception as e:
            logger.error("Failed to enable plugin", plugin=plugin_name, error=str(e))
            return False

    async def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin."""
        plugin_dir = self.plugin_dir / plugin_name
        if not plugin_dir.exists():
            logger.error(f"Plugin directory not found: {plugin_name}")
            return False
        
        # Update system.json
        system_data = self._load_plugin_system_data(plugin_name, plugin_dir)
        system_data["enabled"] = False
        self._save_plugin_system_data(plugin_name, plugin_dir, system_data)
        
        if plugin_name not in self._plugins:
            return True

        plugin = self._plugins[plugin_name]
        if not plugin.is_enabled():
            return True

        try:
            await plugin.on_disable()
            plugin.set_enabled(False)
            
            await self.event_bus.publish(
                "plugin.disabled",
                {"plugin": plugin_name},
                source="plugin_manager"
            )
            
            logger.info("Plugin disabled", plugin=plugin_name)
            return True

        except Exception as e:
            logger.error("Failed to disable plugin", plugin=plugin_name, error=str(e))
            return False

    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a loaded plugin by name."""
        return self._plugins.get(plugin_name)

    def get_all_plugins(self) -> Dict[str, PluginInterface]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    def get_plugin_list(self) -> List[Dict[str, Any]]:
        """Get list of all plugins with metadata."""
        plugins = []
        for name, plugin in self._plugins.items():
            metadata = plugin.get_metadata()
            plugins.append({
                "name": name,
                "enabled": plugin.is_enabled(),
                "metadata": metadata.to_dict()
            })
        return plugins

    async def load_all_plugins(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """
        Load all enabled plugins from plugin directory.
        Only loads plugins that are enabled in system.json.
        
        Args:
            context: Optional context to pass to plugins during loading
        
        Returns:
            Dict mapping plugin names to load success status
        """
        results = {}
        
        # Discover all plugins
        plugin_names = self.discover_plugins()

        for plugin_name in plugin_names:
            results[plugin_name] = await self.load_plugin(plugin_name, context)

        logger.info(
            "Plugin loading completed",
            total=len(results),
            successful=sum(1 for v in results.values() if v)
        )

        return results

    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in plugin directory.
        Plugins must be in folders with plugin.json.
        
        Returns:
            List of plugin names
        """
        plugins = []
        
        # Only discover folder-based plugins with plugin.json
        for directory in self.plugin_dir.glob("*/"):
            if directory.is_dir() and not directory.name.startswith("_"):
                # Check for plugin.json (required)
                # Entry file is determined by adapter, so we only check plugin.json
                if (directory / "plugin.json").exists():
                    plugins.append(directory.name)
        
        return plugins
    
    def mark_plugin_disabled(self, plugin_name: str) -> bool:
        """标记插件为禁用状态"""
        if plugin_name not in self._disabled_plugins:
            self._disabled_plugins.append(plugin_name)
            self._save_disabled_list()
            logger.info(f"Plugin {plugin_name} marked as disabled")
            return True
        return False
    
    def mark_plugin_enabled(self, plugin_name: str) -> bool:
        """标记插件为启用状态"""
        if plugin_name in self._disabled_plugins:
            self._disabled_plugins.remove(plugin_name)
            self._save_disabled_list()
            logger.info(f"Plugin {plugin_name} marked as enabled")
            return True
        return False
    
    def get_plugin_dependencies(self, plugin_name: str) -> List[PluginDependency]:
        """获取插件依赖"""
        return self._plugin_dependencies.get(plugin_name, [])
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件配置"""
        return self._plugin_configs.get(plugin_name, {})
    
    def get_plugin_system_data(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件系统数据"""
        plugin_dir = self.plugin_dir / plugin_name
        if plugin_dir.exists():
            return self._load_plugin_system_data(plugin_name, plugin_dir)
        return {}
    
    def set_plugin_adapter(self, plugin_name: str, adapter_name: Optional[str]) -> bool:
        """设置插件绑定的适配器"""
        plugin_dir = self.plugin_dir / plugin_name
        if not plugin_dir.exists():
            logger.error(f"Plugin directory not found: {plugin_name}")
            return False
        
        system_data = self._load_plugin_system_data(plugin_name, plugin_dir)
        system_data["adapter"] = adapter_name
        self._save_plugin_system_data(plugin_name, plugin_dir, system_data)
        
        # If plugin is loaded, unload it (will need to reload with new adapter)
        if plugin_name in self._plugins:
            # Don't actually unload, just mark for reload
            logger.info(f"Plugin {plugin_name} adapter changed to {adapter_name}, will reload on next enable")
        
        return True
    
    async def delete_plugin(self, plugin_name: str) -> bool:
        """删除插件目录"""
        import shutil
        
        # First, unload the plugin if it's loaded
        if plugin_name in self._plugins:
            await self.unload_plugin(plugin_name)
        
        # Disable the plugin if it's enabled
        if plugin_name not in self._disabled_plugins:
            self.mark_plugin_disabled(plugin_name)
        
        # Remove from disabled list
        if plugin_name in self._disabled_plugins:
            self._disabled_plugins.remove(plugin_name)
            self._save_disabled_list()
        
        # Delete plugin directory
        plugin_dir = self.plugin_dir / plugin_name
        if plugin_dir.exists():
            try:
                shutil.rmtree(plugin_dir)
                logger.info(f"Plugin directory deleted: {plugin_name}")
                
                # Publish delete event
                await self.event_bus.publish(
                    "plugin.deleted",
                    {"plugin": plugin_name},
                    source="plugin_manager"
                )
                
                return True
            except Exception as e:
                logger.error(
                    f"Failed to delete plugin directory: {plugin_name}",
                    error=str(e),
                    exc_info=True
                )
                return False
        else:
            logger.warning(f"Plugin directory not found: {plugin_name}")
            return False


# Global plugin manager
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        from ..core.config import get_config
        config = get_config()
        _plugin_manager = PluginManager(config.plugin_dir)
    return _plugin_manager


def set_plugin_manager(manager: PluginManager) -> None:
    """Set the global plugin manager."""
    global _plugin_manager
    _plugin_manager = manager


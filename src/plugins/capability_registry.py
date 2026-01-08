"""Capability registry for plugin features."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

from ..core.logger import get_logger

logger = get_logger(__name__)


class CapabilityType(str, Enum):
    """Types of capabilities."""
    COMMAND = "command"
    EVENT_HANDLER = "event_handler"
    API_ENDPOINT = "api_endpoint"
    SCHEDULED_TASK = "scheduled_task"
    MIDDLEWARE = "middleware"
    CUSTOM = "custom"


@dataclass
class Capability:
    """Capability definition."""
    
    name: str
    type: CapabilityType
    provider: str  # Plugin name
    handler: Callable
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type.value,
            "provider": self.provider,
            "metadata": self.metadata,
            "dependencies": self.dependencies,
            "enabled": self.enabled,
        }


class CapabilityRegistry:
    """Registry for plugin capabilities."""

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._providers: Dict[str, Set[str]] = {}  # plugin_name -> capability_names
        self._types: Dict[CapabilityType, Set[str]] = {
            cap_type: set() for cap_type in CapabilityType
        }

    def register(self, capability: Capability) -> None:
        """
        Register a capability.
        
        Args:
            capability: Capability to register
        """
        cap_id = f"{capability.provider}:{capability.name}"
        
        if cap_id in self._capabilities:
            logger.warning(
                "Capability already registered, overwriting",
                capability_id=cap_id
            )
        
        self._capabilities[cap_id] = capability
        
        # Track by provider
        if capability.provider not in self._providers:
            self._providers[capability.provider] = set()
        self._providers[capability.provider].add(cap_id)
        
        # Track by type
        self._types[capability.type].add(cap_id)
        
        logger.info(
            "Capability registered",
            name=capability.name,
            type=capability.type.value,
            provider=capability.provider
        )

    def unregister(self, provider: str, name: str) -> bool:
        """
        Unregister a capability.
        
        Args:
            provider: Plugin name
            name: Capability name
            
        Returns:
            True if unregistered, False if not found
        """
        cap_id = f"{provider}:{name}"
        
        if cap_id not in self._capabilities:
            return False
        
        capability = self._capabilities[cap_id]
        
        # Remove from all tracking
        del self._capabilities[cap_id]
        self._providers.get(provider, set()).discard(cap_id)
        self._types[capability.type].discard(cap_id)
        
        logger.info(
            "Capability unregistered",
            name=name,
            provider=provider
        )
        
        return True

    def unregister_provider(self, provider: str) -> int:
        """
        Unregister all capabilities from a provider.
        
        Args:
            provider: Plugin name
            
        Returns:
            Number of capabilities unregistered
        """
        if provider not in self._providers:
            return 0
        
        cap_ids = list(self._providers[provider])
        count = 0
        
        for cap_id in cap_ids:
            if cap_id in self._capabilities:
                capability = self._capabilities[cap_id]
                del self._capabilities[cap_id]
                self._types[capability.type].discard(cap_id)
                count += 1
        
        del self._providers[provider]
        
        logger.info(
            "All capabilities unregistered for provider",
            provider=provider,
            count=count
        )
        
        return count

    def get(self, provider: str, name: str) -> Optional[Capability]:
        """Get a capability by provider and name."""
        cap_id = f"{provider}:{name}"
        return self._capabilities.get(cap_id)

    def get_by_type(self, cap_type: CapabilityType) -> List[Capability]:
        """Get all capabilities of a specific type."""
        cap_ids = self._types.get(cap_type, set())
        return [
            self._capabilities[cap_id]
            for cap_id in cap_ids
            if cap_id in self._capabilities
        ]

    def get_by_provider(self, provider: str) -> List[Capability]:
        """Get all capabilities from a provider."""
        cap_ids = self._providers.get(provider, set())
        return [
            self._capabilities[cap_id]
            for cap_id in cap_ids
            if cap_id in self._capabilities
        ]

    def get_all(self) -> List[Capability]:
        """Get all registered capabilities."""
        return list(self._capabilities.values())

    def enable_capability(self, provider: str, name: str) -> bool:
        """Enable a capability."""
        capability = self.get(provider, name)
        if capability:
            capability.enabled = True
            logger.info("Capability enabled", provider=provider, name=name)
            return True
        return False

    def disable_capability(self, provider: str, name: str) -> bool:
        """Disable a capability."""
        capability = self.get(provider, name)
        if capability:
            capability.enabled = False
            logger.info("Capability disabled", provider=provider, name=name)
            return True
        return False

    def is_enabled(self, provider: str, name: str) -> bool:
        """Check if a capability is enabled."""
        capability = self.get(provider, name)
        return capability.enabled if capability else False

    def find_providers(self, capability_name: str) -> List[str]:
        """Find all providers that offer a specific capability."""
        providers = []
        for cap_id, capability in self._capabilities.items():
            if capability.name == capability_name:
                providers.append(capability.provider)
        return providers

    def validate_dependencies(self, capability: Capability) -> List[str]:
        """
        Validate that capability dependencies are met.
        
        Returns:
            List of missing dependencies
        """
        missing = []
        for dep in capability.dependencies:
            if not any(
                cap.name == dep
                for cap in self._capabilities.values()
            ):
                missing.append(dep)
        return missing

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_capabilities": len(self._capabilities),
            "providers": len(self._providers),
            "by_type": {
                cap_type.value: len(cap_ids)
                for cap_type, cap_ids in self._types.items()
            },
            "enabled": sum(1 for cap in self._capabilities.values() if cap.enabled),
            "disabled": sum(1 for cap in self._capabilities.values() if not cap.enabled),
        }


# Global capability registry
_capability_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """Get the global capability registry."""
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry


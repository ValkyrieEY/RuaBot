"""LLM model manager."""

import uuid
from typing import Optional, List, Dict, Any
from ..core.database import DatabaseManager, get_database_manager
from ..core.models.ai import LLMModel
from ..core.logger import get_logger

logger = get_logger(__name__)


class ModelManager:
    """Manages LLM models."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or get_database_manager()
        self._models_cache: Dict[str, LLMModel] = {}
    
    async def initialize(self):
        """Initialize model manager."""
        await self._refresh_cache()
        logger.info("ModelManager initialized")
    
    async def _refresh_cache(self):
        """Refresh models cache."""
        models = await self.db_manager.list_llm_models()
        self._models_cache = {model.uuid: model for model in models}
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List all models."""
        models = await self.db_manager.list_llm_models()
        return [model.to_dict(include_secret=False) for model in models]
    
    async def get_model(self, model_uuid: str) -> Optional[Dict[str, Any]]:
        """Get model by UUID."""
        model = await self.db_manager.get_llm_model(model_uuid)
        if model:
            return model.to_dict(include_secret=False)
        return None
    
    async def get_model_with_secret(self, model_uuid: str) -> Optional[Dict[str, Any]]:
        """Get model with API key (for internal use)."""
        model = await self.db_manager.get_llm_model(model_uuid)
        if model:
            return model.to_dict(include_secret=True)
        return None
    
    async def create_model(
        self,
        name: str,
        provider: str,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        is_default: bool = False,
        supports_tools: bool = False,
        supports_vision: bool = False,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new model."""
        model_uuid = str(uuid.uuid4())
        
        model = await self.db_manager.create_llm_model(
            uuid=model_uuid,
            name=name,
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            is_default=is_default,
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            description=description,
            config=config or {}
        )
        
        await self._refresh_cache()
        logger.info(f"Model created: {name} ({model_uuid})")
        return model.to_dict(include_secret=False)
    
    async def update_model(
        self,
        model_uuid: str,
        **kwargs
    ) -> bool:
        """Update model."""
        success = await self.db_manager.update_llm_model(model_uuid, **kwargs)
        if success:
            await self._refresh_cache()
            logger.info(f"Model updated: {model_uuid}")
        return success
    
    async def delete_model(self, model_uuid: str) -> bool:
        """Delete model."""
        success = await self.db_manager.delete_llm_model(model_uuid)
        if success:
            if model_uuid in self._models_cache:
                del self._models_cache[model_uuid]
            logger.info(f"Model deleted: {model_uuid}")
        return success
    
    async def get_default_model(self) -> Optional[Dict[str, Any]]:
        """Get default model."""
        model = await self.db_manager.get_default_llm_model()
        if model:
            return model.to_dict(include_secret=False)
        return None
    
    async def set_default_model(self, model_uuid: str) -> bool:
        """Set default model."""
        return await self.update_model(model_uuid, is_default=True)
    
    async def get_providers(self) -> List[str]:
        """Get list of available providers."""
        models = await self.db_manager.list_llm_models()
        providers = set()
        for model in models:
            providers.add(model.provider)
        return sorted(list(providers))


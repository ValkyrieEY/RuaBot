"""Learning Features Configuration Manager.

Manages configuration for all learning features:
- Expression learning
- Jargon learning
- Sticker learning
- Knowledge graph
- HeartFlow
"""

from typing import Dict, Any, Optional
from ..core.logger import get_logger
from ..core.database import get_database_manager

logger = get_logger(__name__)


class LearningConfig:
    """Learning features configuration manager."""
    
    # Default configuration
    DEFAULT_CONFIG = {
        'expression_learning': {
            'enabled': True,
            'use_expressions': True,  # Use learned expressions in replies
            'auto_check': True,  # Auto check expression quality
        },
        'jargon_learning': {
            'enabled': True,
            'explain_jargons': True,  # Explain jargons in replies
        },
        'sticker_learning': {
            'enabled': True,
            'use_stickers': True,  # Use learned stickers in replies
        },
        'knowledge_graph': {
            'enabled': True,
            'extract_triples': True,  # Extract knowledge triples
            'max_triples_per_message': 5,  # Max triples to extract per message
        },
        'heartflow': {
            'enabled': True,
            'track_emotions': True,  # Track emotional states
            'track_atmosphere': True,  # Track conversation atmosphere
        },
        'person_profiling': {
            'enabled': True,
            'min_messages': 5,  # Minimum messages needed to profile a user
            'update_interval': 3600,  # Update profile every hour (if new messages)
        }
    }
    
    def __init__(self):
        """Initialize learning config manager."""
        self.db_manager = get_database_manager()
    
    async def get_config(
        self,
        config_type: str = 'global',
        target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get learning configuration.
        
        Args:
            config_type: 'global', 'group', or 'user'
            target_id: Group ID or user ID (None for global)
            
        Returns:
            Configuration dict with all learning feature settings
        """
        try:
            # Get AI config
            config = await self.db_manager.get_ai_config(config_type, target_id)
            
            if not config:
                # Return default config
                return self.DEFAULT_CONFIG.copy()
            
            # Get learning config from config JSON field
            learning_config = config.config.get('learning', {})
            
            # Merge with defaults
            result = self.DEFAULT_CONFIG.copy()
            for feature, settings in learning_config.items():
                if feature in result:
                    result[feature].update(settings)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get learning config: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    async def update_config(
        self,
        learning_config: Dict[str, Any],
        config_type: str = 'global',
        target_id: Optional[str] = None
    ) -> bool:
        """Update learning configuration.
        
        Args:
            learning_config: Learning configuration dict
            config_type: 'global', 'group', or 'user'
            target_id: Group ID or user ID (None for global)
            
        Returns:
            True if successful
        """
        try:
            # Get or create AI config
            config = await self.db_manager.get_ai_config(config_type, target_id)
            
            if not config:
                # Create new config
                await self.db_manager.create_ai_config(
                    config_type=config_type,
                    target_id=target_id,
                    enabled=True,
                    config={'learning': learning_config}
                )
            else:
                # Update existing config
                current_config = config.config.copy()
                current_config['learning'] = learning_config
                await self.db_manager.update_ai_config(
                    config_type=config_type,
                    target_id=target_id,
                    config=current_config
                )
            
            logger.info(f"Learning config updated: {config_type}:{target_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update learning config: {e}")
            return False
    
    def is_feature_enabled(
        self,
        feature_name: str,
        config: Dict[str, Any]
    ) -> bool:
        """Check if a learning feature is enabled.
        
        Args:
            feature_name: Feature name (e.g., 'expression_learning')
            config: Configuration dict from get_config()
            
        Returns:
            True if feature is enabled
        """
        feature_config = config.get(feature_name, {})
        return feature_config.get('enabled', False)
    
    def get_feature_config(
        self,
        feature_name: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get configuration for a specific feature.
        
        Args:
            feature_name: Feature name
            config: Configuration dict from get_config()
            
        Returns:
            Feature configuration dict
        """
        return config.get(feature_name, {})


# Global instance
_learning_config: Optional[LearningConfig] = None


def get_learning_config() -> LearningConfig:
    """Get global learning config instance."""
    global _learning_config
    if _learning_config is None:
        _learning_config = LearningConfig()
    return _learning_config


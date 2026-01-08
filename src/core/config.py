"""Configuration management with hot reload support."""

import os
import tomllib
import tomli_w
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration with environment variable support."""

    # Application
    app_name: str = Field(default="OneBot Framework", alias="APP_NAME")
    app_version: str = Field(default="0.0.1", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # OneBot Configuration
    onebot_version: str = Field(default="v11", alias="ONEBOT_VERSION")
    onebot_connection_type: str = Field(default="ws_reverse", alias="ONEBOT_CONNECTION_TYPE")
    onebot_http_url: str = Field(default="http://localhost:5700", alias="ONEBOT_HTTP_URL")
    onebot_ws_url: str = Field(default="ws://localhost:5700", alias="ONEBOT_WS_URL")
    onebot_ws_reverse_host: str = Field(default="0.0.0.0", alias="ONEBOT_WS_REVERSE_HOST")
    onebot_ws_reverse_port: int = Field(default=8080, alias="ONEBOT_WS_REVERSE_PORT")
    onebot_ws_reverse_path: str = Field(default="/onebot/v11/ws", alias="ONEBOT_WS_REVERSE_PATH")
    onebot_access_token: str = Field(default="", alias="ONEBOT_ACCESS_TOKEN")
    onebot_secret: str = Field(default="", alias="ONEBOT_SECRET")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/onebot_framework.db",
        alias="DATABASE_URL"
    )

    # Security
    secret_key: str = Field(
        default="change-this-secret-key-in-production",
        alias="SECRET_KEY"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/onebot_framework.log", alias="LOG_FILE")

    # Plugin Configuration
    plugin_dir: str = Field(default="./plugins", alias="PLUGIN_DIR")
    plugin_auto_load: bool = Field(default=True, alias="PLUGIN_AUTO_LOAD")
    adapter_dir: str = Field(default="./adapters", alias="ADAPTER_DIR")

    # Web UI
    web_ui_enabled: bool = Field(default=True, alias="WEB_UI_ENABLED")
    web_ui_username: str = Field(default="admin", alias="WEB_UI_USERNAME")
    web_ui_password: str = Field(default="admin123", alias="WEB_UI_PASSWORD")
    
    # Tencent Cloud TTS
    tencent_cloud_secret_id: str = Field(default="", alias="TENCENT_CLOUD_SECRET_ID")
    tencent_cloud_secret_key: str = Field(default="", alias="TENCENT_CLOUD_SECRET_KEY")
    
    # AI Thread Pool
    ai_thread_pool_enabled: bool = Field(default=True, alias="AI_THREAD_POOL_ENABLED")
    ai_thread_pool_workers: int = Field(default=5, alias="AI_THREAD_POOL_WORKERS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @classmethod
    def from_toml(cls, toml_path: Path) -> "Config":
        """Load configuration from TOML file."""
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
                # Convert TOML to environment variables format
                env_vars = {}
                _flatten_toml(data, env_vars, prefix="")
                # Clear existing config-related environment variables first
                # to avoid conflicts from previous runs
                config_keys = [
                    "LOG_LEVEL", "DEBUG", "APP_DEBUG", "LOGGING_LEVEL", "APP_LOG_LEVEL",
                    "WEB_UI_ENABLED", "PLUGIN_AUTO_LOAD"
                ]
                for key in config_keys:
                    os.environ.pop(key, None)
                # Set environment variables from TOML
                for key, value in env_vars.items():
                    os.environ[key] = str(value)
        # Create config instance (will read from environment variables)
        return cls()

    def get_plugin_path(self) -> Path:
        """Get the plugin directory path."""
        return Path(self.plugin_dir).resolve()

    def get_data_dir(self) -> Path:
        """Get the data directory path."""
        db_path = self.database_url.split("///")[-1]
        return Path(db_path).parent.resolve()

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


def _flatten_toml(data: Dict[str, Any], result: Dict[str, str], prefix: str = "") -> None:
    """Flatten nested TOML structure to environment variable format."""
    for key, value in data.items():
        full_key = f"{prefix}_{key}" if prefix else key
        if isinstance(value, dict):
            _flatten_toml(value, result, full_key)
        else:
            # Convert to uppercase and use underscore
            env_key = full_key.upper().replace("-", "_")
            
            # Special mappings to match Config class aliases
            # [logging].level -> LOG_LEVEL (not LOGGING_LEVEL)
            if env_key == "LOGGING_LEVEL":
                result["LOG_LEVEL"] = value
            # [app].debug -> DEBUG (not APP_DEBUG)
            elif env_key == "APP_DEBUG":
                result["DEBUG"] = value
            # [app].log_level -> LOG_LEVEL (not APP_LOG_LEVEL)
            elif env_key == "APP_LOG_LEVEL":
                result["LOG_LEVEL"] = value
            
            # Always set the original key too (for backwards compatibility)
            result[env_key] = value


class ConfigManager:
    """Configuration manager with hot reload support."""

    def __init__(self) -> None:
        self._config: Optional[Config] = None
        self._callbacks: list = []

    def load(self, config_path: Optional[str] = None) -> Config:
        """Load configuration from TOML file or environment."""
        # Try to load from config.toml first
        project_root = Path(__file__).parent.parent.parent  # onebot_framework/
        toml_file = project_root / "config.toml"
        
        if toml_file.exists():
            self._config = Config.from_toml(toml_file)
        elif config_path and os.path.exists(config_path):
            os.environ.setdefault("ENV_FILE", config_path)
            self._config = Config()
        else:
            self._config = Config()
        
        return self._config

    def reload(self) -> Config:
        """Reload configuration and notify callbacks."""
        old_config = self._config
        # Force reload from TOML file
        project_root = Path(__file__).parent.parent.parent  # onebot_framework/
        toml_file = project_root / "config.toml"
        
        if toml_file.exists():
            self._config = Config.from_toml(toml_file)
        else:
            self._config = Config()
        
        # Notify all registered callbacks
        for callback in self._callbacks:
            try:
                callback(old_config, self._config)
            except Exception as e:
                print(f"Error in config reload callback: {e}")
        
        return self._config

    def register_reload_callback(self, callback) -> None:
        """Register a callback to be called when config is reloaded."""
        self._callbacks.append(callback)

    def get(self) -> Config:
        """Get the current configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def update(self, **kwargs: Any) -> None:
        """Update configuration values."""
        if self._config is None:
            self._config = self.load()
        
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)


# Global config manager instance
_config_manager = ConfigManager()


@lru_cache()
def get_config() -> Config:
    """Get the global configuration instance."""
    return _config_manager.get()


def reload_config() -> Config:
    """Reload the global configuration."""
    get_config.cache_clear()
    return _config_manager.reload()


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    return _config_manager


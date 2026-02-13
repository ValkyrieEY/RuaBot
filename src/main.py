"""Main application entry point."""

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

import sys
import asyncio
from pathlib import Path

# Windows + Python 3.13 compatibility: set ProactorEventLoop policy
if sys.platform == 'win32':
    try:
        # Check Python version
        if sys.version_info >= (3, 13):
            # Set ProactorEventLoop policy for Windows (required for subprocess support)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        # If setting policy fails, continue anyway (may work with default policy)
        pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_config, get_config_manager
from src.core.logger import setup_logger, get_logger
from src.ui.api import create_app

# Setup logger first
# Force reload config from file on startup to ensure we have the latest values
config_manager = get_config_manager()
config_manager.reload()  # Force reload from TOML file
get_config.cache_clear() if hasattr(get_config, 'cache_clear') else None
config = get_config()

# Sync debug and log_level on startup: ensure they are consistent
# - if debug=true, log_level should be DEBUG
# - if debug=false and log_level is DEBUG, log_level should be INFO
import tomllib
import tomli_w

project_root = Path(__file__).parent.parent
toml_file = project_root / "config.toml"

if toml_file.exists():
    try:
        with open(toml_file, "rb") as f:
            toml_data = tomllib.load(f)
        
        needs_update = False
        
        if config.debug and config.log_level.upper() != "DEBUG":
            # Debug mode is enabled but log_level is not DEBUG, update it
            if "logging" not in toml_data:
                toml_data["logging"] = {}
            toml_data["logging"]["level"] = "DEBUG"
            if "app" not in toml_data:
                toml_data["app"] = {}
            toml_data["app"]["log_level"] = "DEBUG"
            needs_update = True
        elif not config.debug and config.log_level.upper() == "DEBUG":
            # Debug mode is disabled but log_level is DEBUG, update it to INFO
            if "logging" not in toml_data:
                toml_data["logging"] = {}
            toml_data["logging"]["level"] = "INFO"
            if "app" not in toml_data:
                toml_data["app"] = {}
            toml_data["app"]["log_level"] = "INFO"
            needs_update = True
        
        if needs_update:
            # Save back to file
            with open(toml_file, "wb") as f:
                tomli_w.dump(toml_data, f)
            
            # Reload config to get updated log_level
            config_manager.reload()
            get_config.cache_clear() if hasattr(get_config, 'cache_clear') else None
            config = get_config()
    except Exception as e:
        # If file update fails, override log_level for this session
        if config.debug:
            config.log_level = "DEBUG"
        elif config.log_level.upper() == "DEBUG":
            config.log_level = "INFO"
        print(f"Warning: Failed to sync log_level with debug mode in config file: {e}")
        print(f"Using {config.log_level} log level for this session.")

setup_logger(
    name="xiaoyi_qq",
    level=config.log_level,
    log_file=config.log_file,
    log_max_bytes=config.log_max_bytes,
    log_backup_count=config.log_backup_count
)

# Use the main logger (not __name__ logger to ensure DEBUG level works)
logger = get_logger("xiaoyi_qq")

# Log the current configuration for debugging
logger.info(f"Configuration loaded: debug={config.debug}, log_level={config.log_level}")
if config.debug:
    logger.debug("DEBUG MODE IS ENABLED")
    logger.debug("If you see this message, DEBUG logging is working correctly")

# Create FastAPI app with API endpoints and React UI
app = create_app()


def main():
    """Main entry point."""
    import uvicorn
    
    # Windows + Python 3.13 compatibility: ensure ProactorEventLoop policy is set before uvicorn starts
    if sys.platform == 'win32' and sys.version_info >= (3, 13):
        try:
            # Ensure policy is set (may have been set at module level, but ensure it's still set)
            current_policy = asyncio.get_event_loop_policy()
            if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                logger.info("Set ProactorEventLoop policy for Windows + Python 3.13 compatibility (before uvicorn start)")
        except Exception as e:
            logger.warning(f"Failed to set ProactorEventLoop policy before uvicorn start: {e}")
    
    config = get_config()
    
    # Beautiful startup banner
    print("\n")
    print(" __  _____    _    _____   _____     ___   ___  ")
    print(" \\ \\/ /_ _|  / \\  / _ \\ \\ / /_ _|   / _ \\ / _ \\ ")
    print("  \\  / | |  / _ \\| | | \\ V / | |   | | | | | | |")
    print("  /  \\ | | / ___ \\ |_| || |  | |   | |_| | |_| |")
    print(" /_/\\_\\___/_/   \\_\\___/ |_| |___|___\\__\\_\\\\__\\_\\")
    print("                               |_____|          ")
    print("\n" + "=" * 60)
    if config.web_ui_enabled:
        print(f"  Web UI:     http://{config.host}:{config.port}/")
        print(f"  Login:      admin / admin123")
    print(f"  API Docs:   http://{config.host}:{config.port}/docs")
    print("=" * 60 + "\n")
    
    # Custom loop setup for Windows + Python 3.13 compatibility
    def custom_loop_setup(loop=None):
        """Setup event loop with ProactorEventLoop policy for Windows."""
        if sys.platform == 'win32' and sys.version_info >= (3, 13):
            # Set ProactorEventLoop policy
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return loop or asyncio.new_event_loop()
    
    # Prepare uvicorn config
    uvicorn_config = {
        "app": "src.main:app",
        "host": config.host,
        "port": config.port,
        "reload": config.auto_reload,  # Use auto_reload config instead of debug
        "log_config": {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)-7s %(message)s",
                    "datefmt": "%H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"handlers": ["default"], "level": "WARNING"},  # Reduce HTTP request logs
            },
        }
    }
    
    # Add loop setup for Windows + Python 3.13
    if sys.platform == 'win32' and sys.version_info >= (3, 13):
        uvicorn_config["loop"] = "asyncio"
        # Note: loop_setup is not directly supported in uvicorn.run(), 
        # so we ensure the policy is set before starting
        logger.info("Using asyncio event loop with ProactorEventLoop policy for Windows + Python 3.13")
    
    # Run FastAPI with React UI
    uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    main()


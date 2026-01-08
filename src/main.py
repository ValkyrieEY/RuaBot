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
from pathlib import Path

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

setup_logger(
    name="xiaoyi_qq",
    level=config.log_level,
    log_file=config.log_file
)

logger = get_logger(__name__)

# Create FastAPI app with API endpoints and React UI
app = create_app()


def main():
    """Main entry point."""
    import uvicorn
    
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
    print(f"  Web UI:     http://{config.host}:{config.port}/")
    print(f"  API Docs:   http://{config.host}:{config.port}/docs")
    print(f"  Login:      admin / admin123")
    print("=" * 60 + "\n")
    
    # Run FastAPI with React UI
    uvicorn.run(
        "src.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_config={
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
    )


if __name__ == "__main__":
    main()


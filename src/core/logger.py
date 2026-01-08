"""Structured logging with multiple output targets."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text


class SimpleConsoleRenderer:
    """Simple console renderer with minimal formatting."""
    
    def __call__(self, logger, name, event_dict):
        """Render log event to a simple string."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = event_dict.get("level", "info").upper()
        event = event_dict.get("event", "")
        
        # Format: [HH:MM:SS] LEVEL  message
        output = f"[{timestamp}] {level:<7} {event}"
        
        # Add extra fields if present (but filter out common structlog fields)
        skip_keys = {"event", "level", "timestamp", "logger"}
        extras = {k: v for k, v in event_dict.items() if k not in skip_keys}
        if extras:
            extras_str = " ".join(f"{k}={v}" for k, v in extras.items())
            output += f" | {extras_str}"
        
        return output


# Global logger registry (using string literal to avoid forward reference)
_loggers: Dict[str, Any] = {}

# In-memory log storage for WebUI
_memory_logs: List[Dict[str, Any]] = []
_max_memory_logs: int = 5000  # Store up to 5000 log entries (reduced for memory efficiency)
_max_memory_size_mb: float = 50.0  # Maximum memory usage in MB (approximately)


class MemoryLogHandler(logging.Handler):
    """Custom handler that stores logs in memory for WebUI with memory limits."""
    
    def emit(self, record: logging.LogRecord) -> None:
        """Store log record in memory with memory management."""
        try:
            # Convert log record to dict
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            
            # Add exception info if present (limit exception size)
            if record.exc_info:
                import traceback
                exception_text = ''.join(traceback.format_exception(*record.exc_info))
                # Limit exception size to 10KB
                if len(exception_text) > 10000:
                    exception_text = exception_text[:10000] + "\n... (truncated)"
                log_entry["exception"] = exception_text
            
            # Limit message size to 5KB
            if len(log_entry["message"]) > 5000:
                log_entry["message"] = log_entry["message"][:5000] + "... (truncated)"
            
            # Add extra fields from record (limit to prevent huge objects)
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                              'levelname', 'levelno', 'lineno', 'module', 'msecs', 'message',
                              'pathname', 'process', 'processName', 'relativeCreated', 'thread',
                              'threadName', 'exc_info', 'exc_text', 'stack_info']:
                    # Convert value to string and limit size
                    try:
                        value_str = str(value)
                        if len(value_str) > 1000:
                            value_str = value_str[:1000] + "... (truncated)"
                        log_entry[key] = value_str
                    except Exception:
                        pass  # Skip if can't convert
            
            # Add to memory logs
            _memory_logs.append(log_entry)
            
            # Memory management: limit by count
            if len(_memory_logs) > _max_memory_logs:
                # Remove oldest 20% when limit is reached (more efficient than removing one by one)
                remove_count = int(_max_memory_logs * 0.2)
                for _ in range(remove_count):
                    if _memory_logs:
                        _memory_logs.pop(0)
            
            # Memory management: limit by approximate size
            # Rough estimate: each log entry is about 1-2KB on average
            estimated_size_mb = len(_memory_logs) * 1.5 / 1024 / 1024
            if estimated_size_mb > _max_memory_size_mb:
                # Remove oldest 30% when size limit is reached
                remove_count = int(len(_memory_logs) * 0.3)
                for _ in range(remove_count):
                    if _memory_logs:
                        _memory_logs.pop(0)
        except Exception:
            pass  # Ignore errors in log handler


class Logger:
    """Structured logger with rich formatting."""

    def __init__(self, name: str, level: str = "INFO", log_file: Optional[str] = None):
        self.name = name
        self.level = level
        self.log_file = log_file
        self._logger: Optional[structlog.BoundLogger] = None

    def setup(self) -> structlog.BoundLogger:
        """Setup structured logger with processors."""
        # Ensure log directory exists
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.filter_by_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Setup standard library logger
        stdlib_logger = logging.getLogger(self.name)
        stdlib_logger.setLevel(getattr(logging, self.level.upper()))

        # Clear existing handlers
        stdlib_logger.handlers.clear()

        # Console handler with simplified formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.level.upper()))
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=SimpleConsoleRenderer(),
        )
        console_handler.setFormatter(console_formatter)
        stdlib_logger.addHandler(console_handler)

        # File handler - only record ERROR and above
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(logging.ERROR)  # Only record ERROR and CRITICAL
            file_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(),
            )
            file_handler.setFormatter(file_formatter)
            stdlib_logger.addHandler(file_handler)
        
        # Memory handler for WebUI
        memory_handler = MemoryLogHandler()
        memory_handler.setLevel(getattr(logging, self.level.upper()))
        stdlib_logger.addHandler(memory_handler)

        self._logger = structlog.get_logger(self.name)
        return self._logger

    def get(self) -> structlog.BoundLogger:
        """Get the logger instance."""
        if self._logger is None:
            self._logger = self.setup()
        return self._logger

    def bind(self, **kwargs: Any) -> structlog.BoundLogger:
        """Bind context to logger."""
        return self.get().bind(**kwargs)


def setup_logger(
    name: str = "onebot_framework",
    level: str = "INFO",
    log_file: Optional[str] = None
) -> structlog.BoundLogger:
    """Setup and register a logger."""
    logger = Logger(name, level, log_file)
    _loggers[name] = logger
    return logger.setup()


def get_logger(name: str = "onebot_framework") -> structlog.BoundLogger:
    """Get a logger by name."""
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name].get()


def bind_logger(name: str = "onebot_framework", **kwargs: Any) -> structlog.BoundLogger:
    """Get a logger with bound context."""
    return get_logger(name).bind(**kwargs)


def get_memory_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Get logs from memory storage."""
    return _memory_logs[-limit:]


def clear_memory_logs() -> None:
    """Clear all logs from memory."""
    global _memory_logs
    _memory_logs = []


def update_log_level(level: str) -> None:
    """Update log level for all registered loggers."""
    level_upper = level.upper()
    if level_upper not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise ValueError(f"Invalid log level: {level}")
    
    # Update all registered loggers
    for logger_name, logger_instance in _loggers.items():
        logger_instance.level = level_upper
        # Re-setup the logger with new level
        logger_instance._logger = None  # Clear cached logger
        logger_instance.setup()  # Re-setup with new level
    
    # Also update root logger
    import logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level_upper))
    
    # Update all handlers
    for handler in root_logger.handlers:
        handler.setLevel(getattr(logging, level_upper))
    
    # Update handlers for all registered loggers
    for logger_name, logger_instance in _loggers.items():
        stdlib_logger = logging.getLogger(logger_instance.name)
        for handler in stdlib_logger.handlers:
            handler.setLevel(getattr(logging, level_upper))

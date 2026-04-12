"""Structured logging with console, memory and daily file outputs."""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog


class SimpleConsoleRenderer:
    """Simple console renderer with minimal formatting."""

    def __call__(self, logger, name, event_dict):
        """Render log event to a simple string."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = event_dict.get("level", "info").upper()
        event = event_dict.get("event", "")

        output = f"[{timestamp}] {level:<7} {event}"

        skip_keys = {"event", "level", "timestamp", "logger"}
        extras = {k: v for k, v in event_dict.items() if k not in skip_keys}
        if extras:
            extras_str = " ".join(f"{k}={v}" for k, v in extras.items())
            output += f" | {extras_str}"

        return output


class FileRenderer:
    """File renderer with full timestamp and readable format."""

    def __call__(self, logger, name, event_dict):
        """Render log event to a readable string for file output."""
        if "timestamp" in event_dict:
            try:
                if isinstance(event_dict["timestamp"], str):
                    ts = datetime.fromisoformat(event_dict["timestamp"].replace("Z", "+00:00"))
                else:
                    ts = datetime.fromtimestamp(event_dict["timestamp"])
                timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        level = event_dict.get("level", "info").upper()
        event = event_dict.get("event", "")
        logger_name = event_dict.get("logger", name)

        output = f"[{timestamp}] {level:<7} [{logger_name}] {event}"

        skip_keys = {"event", "level", "timestamp", "logger"}
        extras = {k: v for k, v in event_dict.items() if k not in skip_keys}
        if extras:
            extras_str = " ".join(f"{k}={v}" for k, v in extras.items())
            output += f" | {extras_str}"

        return output


class DailyLogFileHandler(logging.Handler):
    """Write logs to a daily file named as YYYY-MM-DD."""

    terminator = "\n"

    def __init__(self, log_file: str, encoding: str = "utf-8") -> None:
        super().__init__()
        configured_path = Path(log_file)
        self.log_dir = configured_path.parent if configured_path.parent != Path("") else Path(".")
        self.extension = configured_path.suffix or ".log"
        self.encoding = encoding
        self._stream = None
        self._current_date: Optional[str] = None
        self._current_path: Optional[Path] = None

    def _resolve_log_path(self, date_str: str) -> Path:
        return (self.log_dir / f"{date_str}{self.extension}").resolve()

    def _ensure_stream(self) -> None:
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self._stream is not None and self._current_date == current_date:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)

        if self._stream is not None:
            try:
                self._stream.flush()
            finally:
                self._stream.close()

        self._current_date = current_date
        self._current_path = self._resolve_log_path(current_date)
        self._stream = open(self._current_path, mode="a", encoding=self.encoding, buffering=1)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.acquire()
            try:
                self._ensure_stream()
                if self._stream is not None:
                    self._stream.write(msg + self.terminator)
                    self._stream.flush()
            finally:
                self.release()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self.acquire()
        try:
            if self._stream is not None:
                try:
                    self._stream.flush()
                finally:
                    self._stream.close()
                self._stream = None
        finally:
            self.release()
        super().close()


_DATE_LOG_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(?P<ext>\.[A-Za-z0-9._-]+)?$")

# Global logger registry (using string literal to avoid forward reference)
_loggers: Dict[str, Any] = {}

# In-memory log storage for WebUI
_memory_logs: List[Dict[str, Any]] = []
_max_memory_logs: int = 5000
_max_memory_size_mb: float = 50.0


def _clear_handlers(stdlib_logger: logging.Logger) -> None:
    """Close and remove handlers from a logger."""
    for handler in list(stdlib_logger.handlers):
        try:
            handler.flush()
        except Exception:
            pass
        try:
            handler.close()
        except Exception:
            pass
        stdlib_logger.removeHandler(handler)


def _get_primary_logger() -> Optional["Logger"]:
    for logger_name in ("xiaoyi_qq", "onebot_framework"):
        logger_instance = _loggers.get(logger_name)
        if logger_instance and getattr(logger_instance, "log_file", None):
            return logger_instance

    for logger_instance in _loggers.values():
        if getattr(logger_instance, "log_file", None):
            return logger_instance
    return None


def get_log_directory() -> Path:
    """Return the directory used for daily log files."""
    logger_instance = _get_primary_logger()
    log_file = getattr(logger_instance, "log_file", None) if logger_instance else None
    configured_path = Path(log_file) if log_file else Path("logs/app.log")
    log_dir = configured_path.parent if configured_path.parent != Path("") else Path(".")
    return log_dir.resolve()


def get_log_file_extension() -> str:
    """Return the configured log file extension for daily files."""
    logger_instance = _get_primary_logger()
    if logger_instance and logger_instance.log_file:
        suffix = Path(logger_instance.log_file).suffix
        if suffix:
            return suffix
    return ".log"


def get_active_log_file_name() -> str:
    """Return today's active daily log file name."""
    return f"{datetime.now().strftime('%Y-%m-%d')}{get_log_file_extension()}"


def list_history_log_files() -> List[Dict[str, Any]]:
    """List daily log files sorted from newest to oldest."""
    log_dir = get_log_directory()
    extension = get_log_file_extension()
    files: List[Dict[str, Any]] = []

    if not log_dir.exists():
        return files

    for path in sorted(log_dir.iterdir(), key=lambda item: item.name, reverse=True):
        if not path.is_file():
            continue
        if path.suffix != extension:
            continue
        if not _DATE_LOG_PATTERN.match(path.name):
            continue

        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "path": str(path),
                "active": path.name == get_active_log_file_name(),
            }
        )

    return files


def _resolve_history_log_path(file_name: str) -> Path:
    """Resolve a historical log filename safely inside the log directory."""
    if not _DATE_LOG_PATTERN.match(file_name):
        raise ValueError("Invalid log file name")

    log_dir = get_log_directory()
    resolved = (log_dir / file_name).resolve()
    try:
        resolved.relative_to(log_dir)
    except ValueError as exc:
        raise ValueError("Invalid log file path") from exc
    return resolved


def read_history_log_file(file_name: str) -> Dict[str, Any]:
    """Read a historical log file."""
    path = _resolve_history_log_path(file_name)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(file_name)

    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "name": path.name,
        "content": content,
        "size": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "active": path.name == get_active_log_file_name(),
    }


def delete_history_log_file(file_name: str) -> None:
    """Delete a historical log file if it is not today's active file."""
    if file_name == get_active_log_file_name():
        raise ValueError("Active log file cannot be deleted")

    path = _resolve_history_log_path(file_name)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(file_name)

    os.remove(path)


class MemoryLogHandler(logging.Handler):
    """Custom handler that stores logs in memory for WebUI with memory limits."""

    def emit(self, record: logging.LogRecord) -> None:
        """Store log record in memory with memory management."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            if record.exc_info:
                import traceback

                exception_text = "".join(traceback.format_exception(*record.exc_info))
                if len(exception_text) > 10000:
                    exception_text = exception_text[:10000] + "\n... (truncated)"
                log_entry["exception"] = exception_text

            if len(log_entry["message"]) > 5000:
                log_entry["message"] = log_entry["message"][:5000] + "... (truncated)"

            for key, value in record.__dict__.items():
                if key not in [
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ]:
                    try:
                        value_str = str(value)
                        if len(value_str) > 1000:
                            value_str = value_str[:1000] + "... (truncated)"
                        log_entry[key] = value_str
                    except Exception:
                        pass

            _memory_logs.append(log_entry)

            if len(_memory_logs) > _max_memory_logs:
                remove_count = int(_max_memory_logs * 0.2)
                for _ in range(remove_count):
                    if _memory_logs:
                        _memory_logs.pop(0)

            estimated_size_mb = len(_memory_logs) * 1.5 / 1024 / 1024
            if estimated_size_mb > _max_memory_size_mb:
                remove_count = int(len(_memory_logs) * 0.3)
                for _ in range(remove_count):
                    if _memory_logs:
                        _memory_logs.pop(0)
        except Exception:
            pass


class Logger:
    """Structured logger with console, memory and daily file outputs."""

    def __init__(
        self,
        name: str,
        level: str = "INFO",
        log_file: Optional[str] = None,
        log_max_bytes: int = 10 * 1024 * 1024,
        log_backup_count: int = 5,
    ):
        self.name = name
        self.level = level
        self.log_file = log_file
        self.log_max_bytes = log_max_bytes
        self.log_backup_count = log_backup_count
        self._logger: Optional[structlog.BoundLogger] = None

    def setup(self) -> structlog.BoundLogger:
        """Setup structured logger with processors."""
        if self.log_file:
            get_log_directory().mkdir(parents=True, exist_ok=True)

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

        stdlib_logger = logging.getLogger(self.name)
        stdlib_logger.setLevel(getattr(logging, self.level.upper()))
        stdlib_logger.propagate = False
        _clear_handlers(stdlib_logger)

        console_stream = sys.stderr if os.environ.get("XQNEXT_LOG_STDERR") == "1" else sys.stdout
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(getattr(logging, self.level.upper()))
        console_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=SimpleConsoleRenderer(),
            )
        )
        stdlib_logger.addHandler(console_handler)

        if self.log_file:
            file_handler = DailyLogFileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(getattr(logging, self.level.upper()))
            file_handler.setFormatter(
                structlog.stdlib.ProcessorFormatter(
                    processor=FileRenderer(),
                )
            )
            stdlib_logger.addHandler(file_handler)

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
    log_file: Optional[str] = None,
    log_max_bytes: int = 10 * 1024 * 1024,
    log_backup_count: int = 5,
) -> structlog.BoundLogger:
    """Setup and register a logger."""
    clear_memory_logs()

    logger = Logger(name, level, log_file, log_max_bytes, log_backup_count)
    _loggers[name] = logger
    return logger.setup()


def get_logger(name: str = "onebot_framework") -> structlog.BoundLogger:
    """Get a logger by name."""
    if name not in _loggers:
        main_logger_name = None
        if "xiaoyi_qq" in _loggers:
            main_logger_name = "xiaoyi_qq"
        elif "onebot_framework" in _loggers:
            main_logger_name = "onebot_framework"

        if main_logger_name:
            main_logger = _loggers[main_logger_name]
            _loggers[name] = Logger(
                name,
                level=main_logger.level,
                log_file=main_logger.log_file,
                log_max_bytes=main_logger.log_max_bytes,
                log_backup_count=main_logger.log_backup_count,
            )
        else:
            _loggers[name] = Logger(name, level="INFO")
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

    for logger_instance in _loggers.values():
        logger_instance.level = level_upper
        logger_instance._logger = None
        logger_instance.setup()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level_upper))

    for handler in root_logger.handlers:
        handler.setLevel(getattr(logging, level_upper))

    for logger_instance in _loggers.values():
        stdlib_logger = logging.getLogger(logger_instance.name)
        for handler in stdlib_logger.handlers:
            handler.setLevel(getattr(logging, level_upper))

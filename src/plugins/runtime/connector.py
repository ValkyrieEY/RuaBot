"""Plugin runtime connector (inspired by LangBot).

Manages communication with plugin runtime process via stdio.
"""

import asyncio
import json
import sys
import os
import inspect
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Coroutine, List, Tuple
import asyncio
from datetime import datetime

from ...core.blocking_task_pool import get_blocking_task_pool_manager, run_in_blocking_pool
from ...core.logger import get_logger
from ...core.event_bus import EventBus
from ...core.database import DatabaseManager
from ..manifest import load_plugin_manifest, plugin_manifest_exists
from ..interceptor import InterceptorRegistry, MessageInterceptor, InterceptorResult, ExecutionMode

logger = get_logger(__name__)

PLUGIN_DEPS_DIR_NAME = ".deps"
DependencyProgressCallback = Optional[Callable[[str], None]]


def _get_blocking_task_pool(app: Any = None):
    """Get the shared blocking task pool, preferring the app-bound instance."""
    return getattr(app, "blocking_task_pool", None) or get_blocking_task_pool_manager()


def get_plugin_dependency_dir(plugin_path: Path) -> Path:
    """Return the private dependency target directory for a plugin."""
    return plugin_path.parent / PLUGIN_DEPS_DIR_NAME / plugin_path.name


async def _load_plugin_manifest_async(plugin_dir: Path, thread_pool: Any = None) -> Dict[str, Any]:
    """Load split plugin manifest files with optional thread-pool offloading."""
    if thread_pool:
        def read_manifest() -> Dict[str, Any]:
            return load_plugin_manifest(plugin_dir)

        return await thread_pool.run_in_executor(read_manifest)

    return await run_in_blocking_pool(load_plugin_manifest, plugin_dir)


def _build_dependency_install_args(plugin_path: Path, plugin_metadata: Dict[str, Any]) -> List[str]:
    """Build pip install requirement arguments from plugin metadata and requirements.txt."""
    args: List[str] = []
    seen = set()

    def add_arg(value: str) -> None:
        value = value.strip()
        if value and value not in seen:
            args.append(value)
            seen.add(value)

    deps = plugin_metadata.get('dependencies')
    if isinstance(deps, list):
        for dep in deps:
            if isinstance(dep, dict):
                dep_name = str(dep.get('name', '')).strip()
                dep_version = str(dep.get('version', '')).strip()
                if not dep_name:
                    continue
                if dep_version:
                    if dep_version.startswith(("=", "<", ">", "!", "~")):
                        add_arg(f"{dep_name}{dep_version}")
                    else:
                        add_arg(f"{dep_name}=={dep_version}")
                else:
                    add_arg(dep_name)
            elif isinstance(dep, str):
                add_arg(dep)

    requirements_file = plugin_path / "requirements.txt"
    if requirements_file.exists():
        args.extend(["-r", str(requirements_file)])

    return args


def _build_dependency_fingerprint(plugin_path: Path, pip_requirement_args: List[str]) -> str:
    """Create a stable fingerprint for plugin dependency inputs."""
    import hashlib

    requirements_file = plugin_path / "requirements.txt"
    requirements_hash = ""
    if requirements_file.exists():
        requirements_hash = hashlib.sha256(requirements_file.read_bytes()).hexdigest()

    payload = json.dumps(
        {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "platform": sys.platform,
            "args": pip_requirement_args,
            "requirements_hash": requirements_hash,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _log_pip_output(
    plugin_name: str,
    text: str,
    progress_callback: DependencyProgressCallback = None,
) -> None:
    """Log pip output without flooding empty/control-only lines."""
    for raw_line in text.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if line:
            logger.info("pip[%s] %s", plugin_name, line)
            if progress_callback:
                progress_callback(line)


class _PipLogWriter:
    """File-like writer that forwards pip stdout/stderr to the application logger."""

    def __init__(self, plugin_name: str, progress_callback: DependencyProgressCallback = None):
        self.plugin_name = plugin_name
        self.progress_callback = progress_callback
        self._buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0

        self._buffer += text
        while "\n" in self._buffer or "\r" in self._buffer:
            newline_index = self._buffer.find("\n")
            carriage_index = self._buffer.find("\r")
            indexes = [i for i in (newline_index, carriage_index) if i >= 0]
            split_index = min(indexes)
            chunk = self._buffer[:split_index]
            self._buffer = self._buffer[split_index + 1:]
            _log_pip_output(self.plugin_name, chunk, self.progress_callback)
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            _log_pip_output(self.plugin_name, self._buffer, self.progress_callback)
        self._buffer = ""


def _run_pip_subprocess(
    plugin_path: Path,
    pip_args: List[str],
    progress_callback: DependencyProgressCallback = None,
) -> Tuple[bool, str]:
    """Run source-mode pip and stream output to logs."""
    import subprocess

    cmd = [sys.executable, "-m", "pip", *pip_args]
    logger.info("pip[%s] running: %s", plugin_path.name, " ".join(cmd))

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception as e:
        return False, str(e)

    output_tail: List[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            stripped = line.strip()
            if stripped:
                output_tail.append(stripped)
                output_tail = output_tail[-20:]
            _log_pip_output(plugin_path.name, line, progress_callback)

        return_code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        return False, "pip did not exit cleanly after output stream ended"
    except Exception as e:
        process.kill()
        return False, str(e)

    if return_code == 0:
        return True, "\n".join(output_tail)
    return False, "\n".join(output_tail) or f"pip exited with code {return_code}"


def _run_pip_install_for_plugin(
    plugin_path: Path,
    pip_requirement_args: List[str],
    progress_callback: DependencyProgressCallback = None,
) -> Tuple[bool, str]:
    """Install dependencies into a plugin-private target directory."""
    deps_dir = get_plugin_dependency_dir(plugin_path)
    deps_dir.mkdir(parents=True, exist_ok=True)

    pip_args = [
        "install",
        "--upgrade",
        "--disable-pip-version-check",
        "--no-warn-script-location",
        "--progress-bar",
        "raw",
        "--target",
        str(deps_dir),
        *pip_requirement_args,
    ]

    if getattr(sys, "frozen", False):
        try:
            from pip._internal.cli.main import main as pip_main
        except Exception as e:
            return (
                False,
                "pip is not bundled in this package. Rebuild with pip hidden imports "
                f"or install dependencies manually. Original error: {e}",
            )

        try:
            import contextlib

            writer = _PipLogWriter(plugin_path.name, progress_callback)
            logger.info("pip[%s] running in bundled mode", plugin_path.name)
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                exit_code = pip_main(pip_args)
            writer.flush()
            if exit_code == 0:
                return True, ""
            return False, f"pip exited with code {exit_code}"
        except SystemExit as e:
            try:
                writer.flush()
            except Exception:
                pass
            code = e.code if isinstance(e.code, int) else 1
            if code == 0:
                return True, ""
            return False, f"pip exited with code {code}"
        except Exception as e:
            return False, str(e)

    return _run_pip_subprocess(plugin_path, pip_args, progress_callback)


async def install_plugin_dependencies(
    plugin_path: Path,
    plugin_metadata: Dict[str, Any],
    progress_callback: DependencyProgressCallback = None,
) -> bool:
    """Install plugin dependencies automatically.
    
    Supports two methods:
    1. From plugin metadata dependencies field
    2. From requirements.txt file
    
    Args:
        plugin_path: Plugin directory path
        plugin_metadata: Plugin metadata from metadata.yaml
        
    Returns:
        True if installation succeeded or no dependencies, False on error
    """
    pip_requirement_args = _build_dependency_install_args(plugin_path, plugin_metadata)

    if not pip_requirement_args:
        logger.info(f"No dependencies found for plugin at {plugin_path}")
        return True

    deps_dir = get_plugin_dependency_dir(plugin_path)
    logger.info(
        "Installing dependencies for plugin %s into %s",
        plugin_path.name,
        deps_dir,
    )

    try:
        deps_dir.mkdir(parents=True, exist_ok=True)
        marker_file = deps_dir / ".xqnext-deps.json"
        fingerprint = _build_dependency_fingerprint(plugin_path, pip_requirement_args)
        if marker_file.exists():
            try:
                marker_data = json.loads(marker_file.read_text(encoding="utf-8"))
                if marker_data.get("fingerprint") == fingerprint:
                    logger.info("Dependencies already satisfied for plugin: %s", plugin_path.name)
                    return True
            except Exception as e:
                logger.debug("Ignoring invalid dependency marker for %s: %s", plugin_path.name, e)

        success, output = await run_in_blocking_pool(
            _run_pip_install_for_plugin,
            plugin_path,
            pip_requirement_args,
            progress_callback,
        )
        if success:
            marker_file.write_text(
                json.dumps(
                    {
                        "fingerprint": fingerprint,
                        "installed_at": datetime.now().isoformat(),
                        "args": pip_requirement_args,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            logger.info("Dependencies installed successfully for plugin: %s", plugin_path.name)
            return True

        logger.warning("Failed to install dependencies for %s: %s", plugin_path.name, output)
        return False
    except Exception as e:
        logger.error(f"Error installing plugin dependencies: {e}", exc_info=True)
        return False


class ProxyMessageInterceptor(MessageInterceptor):
    """ - """
    
    def __init__(self, plugin_id: str, connector, priority: int = 100):
        """
        
        Args:
            plugin_id: ID
            connector: PluginRuntimeConnector
            priority: 
        """
        super().__init__(plugin_id, priority)
        self.connector = connector
        self.plugin_id = plugin_id
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        """ - """
        import uuid
        
        # 
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        
        # futureconnector
        if not hasattr(self.connector, '_interceptor_futures'):
            self.connector._interceptor_futures = {}
        self.connector._interceptor_futures[request_id] = future
        
        # 
        await self.connector._send_to_runtime({
            'type': 'intercept_message',
            'data': {
                'request_id': request_id,
                'plugin_id': self.plugin_id,
                'action': action,
                'params': params,
                'source_plugin': source_plugin
            }
        })
        
        try:
            # 3
            result = await asyncio.wait_for(future, timeout=3.0)
            logger.debug(f"拦截器响应成功: {self.plugin_id}, allow={result.allow}")
            return result
        except asyncio.TimeoutError:
            # 
            logger.warning(f"拦截器响应超时: {self.plugin_id}, 放行消息")
            return InterceptorResult(allow=True)
        except Exception as e:
            logger.error(f"拦截器执行错误： {self.plugin_id}, {e}")
            return InterceptorResult(allow=True)
        finally:
            self.connector._interceptor_futures.pop(request_id, None)


class PluginRuntimeConnector:
    """Plugin runtime connector.
    
    Manages plugin runtime process and handles communication via stdio.
    Inspired by LangBot's PluginRuntimeConnector.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        db_manager: DatabaseManager,
        app: Optional[Any] = None,
        runtime_script: Optional[str] = None,
        interceptor_mode: ExecutionMode = ExecutionMode.HYBRID
    ):
        """Initialize plugin runtime connector.
        
        Args:
            event_bus: Event bus for framework events
            db_manager: Database manager for plugin settings
            app: Application instance (for accessing OneBot adapter)
            runtime_script: Path to plugin runtime script (default: auto-detect)
            interceptor_mode: Execution mode for interceptors (default: HYBRID)
        """
        self.event_bus = event_bus
        self.db_manager = db_manager
        self.app = app
        
        # Runtime process
        self.runtime_process: Optional[asyncio.subprocess.Process] = None
        self.runtime_task: Optional[asyncio.Task] = None
        self.runtime_stderr_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Runtime script path
        if runtime_script:
            self.runtime_script = Path(runtime_script)
        else:
            # Default: src/plugins/runtime/main.py
            self.runtime_script = Path(__file__).parent / "main.py"
        
        # State
        self.is_running = False
        self.is_enabled = True
        
        # Callbacks
        self.disconnect_callback: Optional[Callable[[], Coroutine]] = None
        
        # Interceptor registry for high-privilege plugins (with optimized execution)
        self.interceptor_registry = InterceptorRegistry(execution_mode=interceptor_mode)
        
        # Configure interceptor optimization settings
        self.interceptor_registry.configure_circuit_breaker(
            threshold=3,    # Open circuit after 3 consecutive failures
            duration=30.0   # Keep circuit open for 30 seconds
        )
        self.interceptor_registry.configure_timeouts(
            base_timeout=3.0,   # Base timeout for interceptors
            max_timeout=10.0    # Maximum adaptive timeout
        )
        
        logger.info(
            f"Initialized interceptor registry with mode: {interceptor_mode.value}, "
            f"circuit breaker enabled"
        )
        
        # Interceptor futures for async communication
        self._interceptor_futures: Dict[str, asyncio.Future] = {}
        
        # Pending requests for event context communication
        self.pending_requests: Dict[str, asyncio.Future] = {}
        
        # Cleanup task for expired requests
        self._cleanup_task: Optional[asyncio.Task] = None

    def _is_runtime_process_alive(self) -> bool:
        """Check whether runtime process is alive."""
        if not self.runtime_process:
            return False

        try:
            if hasattr(self.runtime_process, 'returncode'):
                return self.runtime_process.returncode is None
            if hasattr(self.runtime_process, 'poll'):
                return self.runtime_process.poll() is None
        except Exception as e:
            logger.debug(f"Failed to check runtime process state: {e}")
            return False

        # Unknown process wrapper type: assume alive until proven otherwise.
        return True

    def _get_runtime_returncode(self) -> Optional[int]:
        """Best-effort runtime process return code."""
        if not self.runtime_process:
            return None
        try:
            if hasattr(self.runtime_process, 'returncode'):
                return self.runtime_process.returncode
            if hasattr(self.runtime_process, 'poll'):
                return self.runtime_process.poll()
        except Exception:
            return None
        return None

    def _is_runtime_stdin_writable(self) -> bool:
        """Check whether runtime stdin stream can still be written."""
        if not self.runtime_process or not getattr(self.runtime_process, 'stdin', None):
            return False

        stdin = self.runtime_process.stdin

        try:
            if hasattr(stdin, 'is_closing') and stdin.is_closing():
                return False
        except Exception:
            return False

        closed = getattr(stdin, 'closed', None)
        if closed is True:
            return False

        transport = getattr(stdin, 'transport', None) or getattr(stdin, '_transport', None)
        if transport and hasattr(transport, 'is_closing'):
            try:
                if transport.is_closing():
                    return False
            except Exception:
                return False

        return True

    async def _wait_for_runtime_process(self, timeout: Optional[float] = None) -> Optional[int]:
        """Wait for runtime process termination for both asyncio and Popen wrappers."""
        if not self.runtime_process or not hasattr(self.runtime_process, 'wait'):
            return None

        wait_method = self.runtime_process.wait

        if inspect.iscoroutinefunction(wait_method):
            if timeout is not None:
                return await asyncio.wait_for(wait_method(), timeout=timeout)
            return await wait_method()

        blocking_pool = _get_blocking_task_pool(self.app)
        wait_future = blocking_pool.run_in_executor(wait_method)
        if timeout is not None:
            return await asyncio.wait_for(wait_future, timeout=timeout)
        return await wait_future

    def _is_closed_transport_error(self, error: Exception) -> bool:
        """Check whether an exception indicates a closed runtime transport."""
        error_type = type(error).__name__
        error_msg = str(error).lower()
        return (
            isinstance(error, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError))
            or "handler is closed" in error_msg
            or "transport closed" in error_msg
            or "connection lost" in error_msg
            or "closed=true" in error_msg
            or ("runtimeerror" in error_type.lower() and "closed" in error_msg)
        )

    def _is_frozen_runtime(self) -> bool:
        """Return whether current process is running from a frozen executable."""
        return bool(getattr(sys, "frozen", False))

    def _build_runtime_command(self) -> List[str]:
        """Build subprocess command for plugin runtime."""
        if self._is_frozen_runtime():
            # Frozen executable cannot execute arbitrary .py paths directly.
            return [sys.executable, "--runtime-mode"]
        return [sys.executable, "-m", "src.plugins.runtime.main"]

    def _get_runtime_process_match_token(self) -> str:
        """Token used to detect runtime subprocesses in process list."""
        if self._is_frozen_runtime():
            return "--runtime-mode"
        return "src.plugins.runtime.main"
    
    def _get_resolved_plugin_base(self) -> Path:
        """Resolved absolute path to the configured plugins directory (``plugins/``)."""
        from ...core.config import get_config, get_runtime_base_dir
        
        config = get_config()
        plugin_dir = Path(config.plugin_dir)
        if not plugin_dir.is_absolute():
            plugin_dir = (get_runtime_base_dir() / config.plugin_dir).resolve()
        else:
            plugin_dir = plugin_dir.resolve()
        return plugin_dir
    
    async def _prune_orphaned_plugin_records(self) -> None:
        """Drop DB and binary storage for plugins whose folder was removed from disk."""
        if not self.db_manager:
            return
        try:
            base = self._get_resolved_plugin_base()
            pruned = await self.db_manager.prune_orphaned_plugin_settings(base)
            if pruned:
                logger.info("Orphan plugin cleanup at startup: %s", pruned)
        except Exception as e:
            logger.warning("Orphan plugin prune failed (continuing startup): %s", e, exc_info=True)

    async def _sync_plugin_records_from_disk(self, plugin_dir_name: Optional[str] = None) -> None:
        """Register missing plugin settings by scanning manifest files from filesystem.

        Args:
            plugin_dir_name: Optional plugin directory name to sync only one plugin.
        """
        if not self.db_manager:
            return

        plugin_base = self._get_resolved_plugin_base()
        if not plugin_base.exists() or not plugin_base.is_dir():
            return

        thread_pool = getattr(self.app, 'blocking_task_pool', None) if self.app else None

        if thread_pool:
            def scan_plugin_dirs():
                dirs = [
                    d for d in plugin_base.iterdir()
                    if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')
                ]
                if plugin_dir_name:
                    dirs = [d for d in dirs if d.name == plugin_dir_name]
                return dirs
            plugin_dirs = await thread_pool.run_in_executor(scan_plugin_dirs)
        else:
            plugin_dirs = [
                d for d in plugin_base.iterdir()
                if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')
            ]
            if plugin_dir_name:
                plugin_dirs = [d for d in plugin_dirs if d.name == plugin_dir_name]

        existing_by_key: Dict[Tuple[str, str], Any] = {}
        try:
            existing_rows = await self.db_manager.list_plugin_settings(enabled_only=False)
            existing_by_key = {
                (row.plugin_author, row.plugin_name): row
                for row in existing_rows
            }
        except Exception as e:
            logger.warning("Plugin sync failed to read existing settings: %s", e)

        created = 0
        updated = 0
        synced_at = datetime.now().isoformat()

        for plugin_dir in plugin_dirs:
            if not plugin_manifest_exists(plugin_dir):
                continue

            try:
                metadata = await _load_plugin_manifest_async(plugin_dir, thread_pool)
            except Exception as e:
                logger.warning("Skip plugin sync for invalid manifest %s: %s", plugin_dir, e)
                continue

            author = str(metadata.get('author', 'Unknown')).strip() or 'Unknown'
            name = str(metadata.get('name', plugin_dir.name)).strip() or plugin_dir.name
            version = str(metadata.get('version', '1.0.0'))
            default_config = metadata.get('default_config', {})
            if not isinstance(default_config, dict):
                default_config = {}
            try:
                priority = int(metadata.get('priority', 100))
            except (TypeError, ValueError):
                priority = 100

            try:
                existing = existing_by_key.get((author, name))
                if existing:
                    install_info = existing.install_info or {}
                    info_changed = False
                    if install_info.get('version') != version:
                        install_info['version'] = version
                        info_changed = True
                    install_info['last_synced_at'] = synced_at
                    info_changed = True

                    if info_changed:
                        await self.db_manager.update_plugin_setting(
                            author,
                            name,
                            install_info=install_info
                        )
                        updated += 1
                    continue

                install_info = {
                    'source': 'filesystem',
                    'version': version,
                    'synced_at': synced_at,
                }

                await self.db_manager.create_plugin_setting(
                    author=author,
                    name=name,
                    enabled=False,
                    priority=priority,
                    config=default_config,
                    install_source='manual',
                    install_info=install_info
                )
                created += 1
            except Exception as e:
                logger.warning("Failed syncing plugin setting for %s/%s: %s", author, name, e)

        if created or updated:
            scope = plugin_dir_name or "all"
            logger.info(
                "Plugin settings sync completed (%s): created=%s, updated=%s",
                scope,
                created,
                updated,
            )
    
    async def initialize(self):
        """Initialize plugin runtime."""
        if not self.is_enabled:
            logger.info("Plugin system is disabled")
            return
        
        if not self._is_frozen_runtime() and not self.runtime_script.exists():
            logger.error(f"Plugin runtime script not found", path=str(self.runtime_script))
            return
        
        try:
            # Start runtime process
            await self._start_runtime_process()
            
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Start cleanup task for expired requests
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_requests())
            
            # DB rows for plugins whose directory was deleted manually (align with Web UI delete)
            await self._prune_orphaned_plugin_records()
            
            # Register plugins copied directly into plugins/ before loading enabled set.
            await self._sync_plugin_records_from_disk()
            
            # Initialize plugins
            await self._initialize_plugins()
            
            # Subscribe to OneBot events
            self._subscribe_to_events()
            
            logger.info("Plugin runtime initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin runtime: {e}", exc_info=True)
            raise
    
    def _subscribe_to_events(self):
        """Subscribe to EventBus events and forward to plugins."""
        # Check if already subscribed (prevent duplicate subscriptions)
        if hasattr(self, '_events_subscribed') and self._events_subscribed:
            logger.warning("Events already subscribed, skipping duplicate subscription")
            return
        
        # Import Event class
        from ...core.event_bus import Event
        
        # Subscribe to all OneBot events
        async def forward_event(event: Event):
            """Forward event to plugin runtime.
            
            Args:
                event: Event object from EventBus
            """
            logger.debug(f"Forwarding event {event.name} to plugins", 
                       source=event.source, event_id=event.event_id)
            # Extract payload and forward to plugins
            await self.emit_event(event.name, event.payload, source=event.source)
        
        # Subscribe to specific OneBot event types (EventBus doesn't support wildcards)
        onebot_events = ["onebot.message", "onebot.notice", "onebot.request", "onebot.meta_event"]
        for event_name in onebot_events:
            self.event_bus.subscribe(event_name, forward_event)
            logger.info(f"Subscribed to event: {event_name}")
        
        self._events_subscribed = True
        logger.info("All OneBot event subscriptions complete")
    
    async def _start_runtime_process(self):
        """Start plugin runtime process."""
        # Stop existing reader tasks before starting a fresh runtime process.
        if self.runtime_task and not self.runtime_task.done():
            self.runtime_task.cancel()
            try:
                await self.runtime_task
            except asyncio.CancelledError:
                pass
        self.runtime_task = None

        if self.runtime_stderr_task and not self.runtime_stderr_task.done():
            self.runtime_stderr_task.cancel()
            try:
                await self.runtime_stderr_task
            except asyncio.CancelledError:
                pass
        self.runtime_stderr_task = None

        # Ensure old process is terminated before starting new one
        if self.runtime_process:
            # Check if process is still running
            is_running = False
            if hasattr(self.runtime_process, 'returncode'):
                is_running = self.runtime_process.returncode is None
            elif hasattr(self.runtime_process, 'poll'):
                is_running = self.runtime_process.poll() is None
            
            if is_running:
                logger.warning("Old runtime process still running, terminating it first...")
                try:
                    self.runtime_process.terminate()
                    await self._wait_for_runtime_process(timeout=2.0)
                    logger.info("Old runtime process terminated")
                except (asyncio.TimeoutError, ProcessLookupError):
                    try:
                        logger.warning("Force killing old runtime process...")
                        self.runtime_process.kill()
                        await self._wait_for_runtime_process()
                        logger.info("Old runtime process killed")
                    except Exception as e:
                        logger.error(f"Failed to kill old runtime process: {e}")
                except Exception as e:
                    logger.error(f"Error terminating old runtime process: {e}")
        
        # Check for orphaned processes (processes running the runtime script)
        # This helps detect if previous processes weren't cleaned up
        try:
            import psutil
            current_pid = os.getpid()
            process_match_token = self._get_runtime_process_match_token()
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue
                    
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and process_match_token in ' '.join(cmdline):
                        logger.warning(f"Found orphaned plugin runtime process: PID {proc.info['pid']}, terminating...")
                        try:
                            proc_obj = psutil.Process(proc.info['pid'])
                            proc_obj.terminate()
                            proc_obj.wait(timeout=2)
                            logger.info(f"Orphaned process {proc.info['pid']} terminated")
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            try:
                                proc_obj.kill()
                                logger.info(f"Orphaned process {proc.info['pid']} killed")
                            except psutil.NoSuchProcess:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.debug("psutil not available, skipping orphaned process check")
        except Exception as e:
            logger.warning(f"Error checking for orphaned processes: {e}")
        
        runtime_cmd = self._build_runtime_command()
        from ...core.config import get_runtime_base_dir
        runtime_cwd = str(get_runtime_base_dir())
        logger.info(
            "Starting plugin runtime process",
            script=str(self.runtime_script),
            command=" ".join(runtime_cmd),
            cwd=runtime_cwd,
        )
        
        # Start subprocess with stdio pipes
        # Windows + Python 3.13 compatibility: ensure ProactorEventLoop policy is set
        if sys.platform == 'win32' and sys.version_info >= (3, 13):
            try:
                current_policy = asyncio.get_event_loop_policy()
                if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
                    # Try to set ProactorEventLoop policy
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    logger.info("Set ProactorEventLoop policy for subprocess support")
            except Exception as e:
                logger.warning(f"Failed to set ProactorEventLoop policy: {e}")
        
        try:
            self.runtime_process = await asyncio.create_subprocess_exec(
                *runtime_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=runtime_cwd,
            )
        except NotImplementedError as e:
            # Fallback to subprocess.Popen for Windows + Python 3.13
            if sys.platform == 'win32' and sys.version_info >= (3, 13):
                logger.warning("asyncio.create_subprocess_exec not supported, using subprocess.Popen fallback")
                try:
                    import subprocess
                    # Use subprocess.Popen as fallback
                    popen_process = subprocess.Popen(
                        runtime_cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,  # Unbuffered
                        cwd=runtime_cwd,
                    )
                    # Wrap Popen in a simple async-compatible interface
                    # Create a minimal wrapper that mimics asyncio.subprocess.Process
                    class PopenWrapper:
                        def __init__(self, popen_proc):
                            self._popen = popen_proc
                            self.stdin = popen_proc.stdin
                            self.stdout = popen_proc.stdout
                            self.stderr = popen_proc.stderr
                            self.pid = popen_proc.pid
                        
                        def poll(self):
                            return self._popen.poll()
                        
                        def wait(self):
                            return self._popen.wait()
                        
                        def terminate(self):
                            self._popen.terminate()
                        
                        def kill(self):
                            self._popen.kill()
                    
                    self.runtime_process = PopenWrapper(popen_process)
                    logger.info(f"Plugin runtime started with Popen fallback, pid={self.runtime_process.pid}")
                except Exception as fallback_error:
                    error_msg = (
                        f"Failed to create subprocess with both asyncio and Popen fallback: {e}. "
                        f"Fallback error: {fallback_error}"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
            else:
                error_msg = (
                    f"Failed to create subprocess: {e}. "
                    "On Windows with Python 3.13+, ProactorEventLoop policy is required."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
        
        # Set larger limit for stdout to handle large base64 images (10MB)
        if self.runtime_process.stdout and hasattr(self.runtime_process.stdout, '_limit'):
            try:
                self.runtime_process.stdout._limit = 10 * 1024 * 1024  # 10MB
            except AttributeError:
                # Popen fallback doesn't have _limit attribute, that's OK
                pass
        
        self.is_running = True
        
        # Start output readers
        self.runtime_task = asyncio.create_task(self._read_runtime_output())
        self.runtime_stderr_task = asyncio.create_task(self._read_runtime_stderr())
        
        logger.info("Plugin runtime process started", pid=self.runtime_process.pid)
    
    async def _read_runtime_output(self):
        """Read and process runtime output."""
        if not self.runtime_process or not self.runtime_process.stdout:
            return
        
        # Check if this is asyncio subprocess or Popen fallback
        is_async_process = hasattr(self.runtime_process.stdout, 'readline') and asyncio.iscoroutinefunction(self.runtime_process.stdout.readline)
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        should_call_disconnect = False
        
        try:
            while self.is_running:
                try:
                    if is_async_process:
                        # Asyncio subprocess - add timeout to prevent indefinite blocking
                        try:
                            line = await asyncio.wait_for(
                                self.runtime_process.stdout.readline(),
                                timeout=60.0  # 60 second timeout
                            )
                        except asyncio.TimeoutError:
                            # Timeout is OK, just check if process is still alive
                            if not self._is_runtime_process_alive():
                                logger.warning("Runtime process terminated")
                                should_call_disconnect = True
                                break
                            # Continue reading
                            continue
                    else:
                        # Popen fallback - use sync readline in executor with timeout
                        blocking_pool = _get_blocking_task_pool(self.app)
                        try:
                            line = await asyncio.wait_for(
                                blocking_pool.run_in_executor(self.runtime_process.stdout.readline),
                                timeout=60.0  # 60 second timeout
                            )
                        except asyncio.TimeoutError:
                            # Timeout is OK, check if process is still alive
                            if not self._is_runtime_process_alive():
                                logger.warning("Runtime process terminated")
                                should_call_disconnect = True
                                break
                            # Continue reading
                            continue
                    
                    if not line:
                        # EOF means runtime stdout pipe is no longer readable.
                        logger.warning("Runtime stdout closed (EOF)")
                        if self._is_runtime_process_alive():
                            logger.warning("Runtime stdout pipe closed while process is still alive")
                        else:
                            logger.warning(
                                f"Runtime process terminated (returncode={self._get_runtime_returncode()})"
                            )
                        should_call_disconnect = True
                        break
                    
                    # Reset error counter on successful read
                    consecutive_errors = 0
                    
                    try:
                        # Parse JSON message -  utf-8 
                        try:
                            message = json.loads(line.decode('utf-8').strip())
                        except UnicodeDecodeError:
                            # UTF-8
                            try:
                                message = json.loads(line.decode('gbk').strip())
                            except UnicodeDecodeError:
                                # Latin-1
                                message = json.loads(line.decode('latin-1').strip())
                        await self._handle_runtime_message(message)
                    except json.JSONDecodeError as e:
                        # Don't log the full line if it's too long (might contain base64)
                        try:
                            line_str = line.decode('utf-8').strip()
                        except UnicodeDecodeError:
                            try:
                                line_str = line.decode('gbk').strip()
                            except UnicodeDecodeError:
                                line_str = line.decode('latin-1').strip()
                        if len(line_str) > 500:
                            line_preview = line_str[:200] + f"... (truncated, total {len(line_str)} chars)"
                        else:
                            line_preview = line_str
                        logger.warning(f"Invalid JSON from runtime: {line_preview}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive JSON decode errors ({consecutive_errors}), stopping reader")
                            break
                    except Exception as e:
                        logger.error(f"Error handling runtime message: {e}", exc_info=True)
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping reader")
                            break
                
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error reading from runtime stdout: {e}", exc_info=True)
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive read errors ({consecutive_errors}), stopping reader")
                        should_call_disconnect = True
                        break
                    # Wait before retrying
                    await asyncio.sleep(0.5)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Runtime output reader fatal error: {e}", exc_info=True)
        finally:
            # Mark as not running, but don't immediately call disconnect_callback
            # Let the heartbeat and other mechanisms handle reconnection
            self.is_running = False
            if self.runtime_process and not self._is_runtime_process_alive():
                self.runtime_process = None
            logger.warning("Runtime output reader stopped. Plugin runtime may be disconnected.")
            
            # Only call disconnect callback if we have one and it's a real disconnection
            # (not just a temporary read error)
            if self.disconnect_callback and should_call_disconnect:
                try:
                    await self.disconnect_callback()
                except Exception as callback_error:
                    logger.error(f"Error in disconnect callback: {callback_error}", exc_info=True)

    async def _read_runtime_stderr(self):
        """Read runtime stderr and forward it to framework logs."""
        if not self.runtime_process or not self.runtime_process.stderr:
            return

        is_async_process = (
            hasattr(self.runtime_process.stderr, 'readline')
            and asyncio.iscoroutinefunction(self.runtime_process.stderr.readline)
        )

        try:
            while self.is_running:
                if is_async_process:
                    line = await self.runtime_process.stderr.readline()
                else:
                    blocking_pool = _get_blocking_task_pool(self.app)
                    line = await blocking_pool.run_in_executor(self.runtime_process.stderr.readline)

                if not line:
                    break

                if isinstance(line, bytes):
                    text = line.decode('utf-8', errors='replace').rstrip()
                else:
                    text = str(line).rstrip()

                if text:
                    logger.error(f"[Runtime stderr] {text}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading runtime stderr: {e}", exc_info=True)
    
    async def _handle_runtime_message(self, message: Dict[str, Any]):
        """Handle message from plugin runtime.
        
        Args:
            message: Message dict with 'type' and 'data' fields
        """
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'log':
            # Log message from plugin
            level = data.get('level', 'info')
            text = data.get('message', '')
            plugin = data.get('plugin', 'unknown')
            
            log_func = getattr(logger, level, logger.info)
            log_func(f"[Plugin:{plugin}] {text}")
        
        elif msg_type == 'event':
            # Plugin wants to emit event
            event_name = data.get('event')
            event_data = data.get('data', {})
            await self.event_bus.emit(event_name, event_data)
        
        elif msg_type == 'heartbeat':
            # Heartbeat response
            logger.debug("Received heartbeat from runtime")
        
        elif msg_type == 'register_interceptor':
            # Plugin wants to register an interceptor
            plugin_id = data.get('plugin_id')
            priority = data.get('priority', 100)
            
            logger.info(f"Registering interceptor for plugin: {plugin_id}, priority: {priority}")
            
            # Create proxy interceptor
            proxy_interceptor = ProxyMessageInterceptor(plugin_id, self, priority=priority)
            self.interceptor_registry.register_message_interceptor(proxy_interceptor)
            logger.info(f"拦截器已注册: {plugin_id}")
        
        elif msg_type == 'unregister_interceptor':
            # Plugin wants to unregister an interceptor
            plugin_id = data.get('plugin_id')
            
            logger.info(f"Unregistering interceptor for plugin: {plugin_id}")
            self.interceptor_registry.unregister_message_interceptor(plugin_id)
            logger.info(f"拦截器已注销: {plugin_id}")
        
        elif msg_type == 'intercept_message_response':
            # Response from plugin runtime for intercept_message request
            request_id = data.get('request_id')
            allow = data.get('allow', True)
            modified_data = data.get('modified_data')
            block_reason = data.get('block_reason')
            
            if request_id in self._interceptor_futures:
                future = self._interceptor_futures.pop(request_id)
                if not future.done():
                    result = InterceptorResult(
                        allow=allow,
                        modified_data=modified_data,
                        block_reason=block_reason
                    )
                    future.set_result(result)
        
        elif msg_type == 'event_with_context_response':
            # Response from plugin runtime for event_with_context request
            request_id = data.get('request_id')
            success = data.get('success', True)
            event_context_dict = data.get('event_context')
            error = data.get('error')
            
            logger.debug(f"Received event_with_context_response: request_id={request_id}, success={success}, has_context={event_context_dict is not None}")
            
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    result = {
                        'success': success,
                        'event_context': event_context_dict,
                        'error': error
                    }
                    try:
                        future.set_result(result)
                        logger.debug(f"Set result for request {request_id}")
                    except Exception as e:
                        # Future may have been cancelled or already set
                        logger.debug(f"Failed to set result for request {request_id}: {e}")
                else:
                    logger.debug(f"Future already done for request_id={request_id} (likely timeout, but response arrived)")
            else:
                # Response arrived but future was already cleaned up (likely due to timeout)
                logger.debug(f"No pending request found for request_id={request_id} (likely timeout, response arrived late)")
        
        elif msg_type == 'storage_request':
            # Plugin wants to access storage
            request_id = data.get('request_id')
            action = data.get('action')  # 'get_config_upload', 'get_binary', 'set_binary', 'delete_binary', 'list_binary_keys'
            plugin_id = data.get('plugin_id')
            
            logger.debug(f"Storage request: {action} from plugin {plugin_id}, request_id: {request_id}")
            
            # Use handler to process storage request
            from .handler import RuntimeConnectionHandler
            handler = RuntimeConnectionHandler(self.db_manager)
            
            # Prepare handler data
            handler_data = {
                'owner': plugin_id,
                'key': data.get('key'),
                'value': data.get('value')  # base64 encoded for set_binary
            }
            
            try:
                # Call appropriate handler method
                if action == 'get_config_upload':
                    result = await handler._handle_get_config_upload(handler_data)
                elif action == 'get_binary':
                    result = await handler._handle_get_binary(handler_data)
                elif action == 'set_binary':
                    result = await handler._handle_set_binary(handler_data)
                elif action == 'delete_binary':
                    result = await handler._handle_delete_binary(handler_data)
                elif action == 'list_binary_keys':
                    result = await handler._handle_list_binary_keys(handler_data)
                else:
                    result = {'success': False, 'error': f'Unknown storage action: {action}'}
                
                # Send response back to plugin
                await self._send_to_runtime({
                    'type': 'storage_response',
                    'data': {
                        'request_id': request_id,
                        **result
                    }
                })
            except Exception as e:
                logger.error(f"Error handling storage request: {e}", exc_info=True)
                await self._send_to_runtime({
                    'type': 'storage_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
                    }
                })
        
        elif msg_type == 'api_call':
            # Plugin wants to call OneBot API
            request_id = data.get('request_id')
            action = data.get('action')
            params = data.get('params', {})
            source_plugin = data.get('source_plugin')  # Plugin ID that initiated the call
            
            logger.info(f"Plugin API call: {action} with params {params}, request_id: {request_id}, source: {source_plugin}")
            
            # Check if this is a message-sending action that should be intercepted
            message_actions = ['send_group_msg', 'send_private_msg', 'send_msg']
            is_message_action = action in message_actions
            skip_interceptors = bool(params.pop('__skip_relay', False))
            
            if is_message_action and not skip_interceptors:
                # Run message interceptors
                logger.debug(
                    f"Running interceptors for {action} from {source_plugin}, "
                    f"registered: {len(self.interceptor_registry.get_message_interceptors())}"
                )
                allow, modified_params = await self.interceptor_registry.intercept_message(
                    action, params, source_plugin
                )
                
                if not allow:
                    logger.warning(f"Message blocked by interceptor: {action} from {source_plugin}")
                    if request_id:
                        await self._send_to_runtime({
                            'type': 'api_response',
                            'data': {
                                'request_id': request_id,
                                'success': False,
                                'error': 'Message blocked by interceptor'
                            }
                        })
                    return
                
                # Use modified params if any interceptor changed them
                if modified_params != params:
                    logger.info(f"Message modified by interceptor: {action}")
                    params = modified_params

                try:
                    from ...core.sandbox.sandbox_manager import get_sandbox_manager

                    sandbox_result = await get_sandbox_manager().record_plugin_api_call(
                        source_plugin=source_plugin or "",
                        action=action,
                        params=params,
                    )
                    if sandbox_result is not None:
                        logger.info(
                            f"Plugin API call captured by sandbox: {action} "
                            f"from {source_plugin}, result={sandbox_result}"
                        )
                        if request_id:
                            await self._send_to_runtime({
                                'type': 'api_response',
                                'data': {
                                    'request_id': request_id,
                                    'success': True,
                                    'result': sandbox_result
                                }
                            })
                        return
                except Exception as e:
                    logger.error(f"Failed to route plugin API call to sandbox: {e}", exc_info=True)
            
            # Get OneBot adapter from app
            if self.app and hasattr(self.app, 'onebot_adapter'):
                try:
                    # Call OneBot API with source_plugin info to skip message.before_send processing
                    onebot = self.app.onebot_adapter
                    result = await onebot.call_api(action, params, source_plugin=source_plugin)
                    
                    logger.info(f"API call {action} succeeded: {result}")
                    
                    # Send response back to plugin
                    if request_id:
                        await self._send_to_runtime({
                            'type': 'api_response',
                            'data': {
                                'request_id': request_id,
                                'success': True,
                                'result': result
                            }
                        })
                except Exception as e:
                    logger.error(f"API call {action} failed: {e}", exc_info=True)
                    # Send error response back to plugin
                    if request_id:
                        await self._send_to_runtime({
                            'type': 'api_response',
                            'data': {
                                'request_id': request_id,
                                'success': False,
                                'error': str(e)
                            }
                        })
            else:
                logger.warning("OneBot adapter not available for API call")
                if request_id:
                    await self._send_to_runtime({
                        'type': 'api_response',
                        'data': {
                            'request_id': request_id,
                            'success': False,
                            'error': 'OneBot adapter not available'
                        }
                    })
        
        elif msg_type == 'reload_plugin_request':
            # Plugin wants to reload itself (from within plugin)
            request_id = data.get('request_id')
            plugin_name = data.get('plugin_name')
            
            logger.info(f"Plugin {plugin_name} requested reload from within plugin")
            
            try:
                # Use connector's reload_plugin method which gets config from database
                success = await self.reload_plugin(plugin_name)
                
                # Send response back to plugin
                await self._send_to_runtime({
                    'type': 'reload_plugin_response',
                    'data': {
                        'request_id': request_id,
                        'success': success
                    }
                })
            except Exception as e:
                logger.error(f"Error handling reload_plugin_request: {e}", exc_info=True)
                await self._send_to_runtime({
                    'type': 'reload_plugin_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
                    }
                })
        
        elif msg_type == 'config_request':
            # Plugin wants to update config
            request_id = data.get('request_id')
            action = data.get('action')  # 'set_config'
            author = data.get('author')
            name = data.get('name')
            config = data.get('config', {})
            
            logger.debug(f"Config request: {action} for plugin {author}/{name}, request_id: {request_id}")
            
            # Use handler to process config request
            from .handler import RuntimeConnectionHandler
            handler = RuntimeConnectionHandler(self.db_manager)
            
            try:
                # Call handler method
                if action == 'set_config':
                    result = await handler._handle_set_config({
                        'author': author,
                        'name': name,
                        'config': config
                    })
                else:
                    result = {'success': False, 'error': f'Unknown config action: {action}'}
                
                # Send response back to plugin
                await self._send_to_runtime({
                    'type': 'config_response',
                    'data': {
                        'request_id': request_id,
                        **result
                    }
                })
            except Exception as e:
                logger.error(f"Error handling config request: {e}", exc_info=True)
                await self._send_to_runtime({
                    'type': 'config_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
                    }
                })
        
        else:
            logger.warning(f"Unknown message type from runtime: {msg_type}")
    
    async def _send_to_runtime(self, message: Dict[str, Any]) -> bool:
        """Send message to plugin runtime.
        
        Args:
            message: Message dict to send
        """
        msg_type = message.get('type', 'unknown')

        if not self.is_running and msg_type != 'shutdown':
            logger.debug(f"Skipping send to runtime because connector is not running: {msg_type}")
            return False

        if not self.runtime_process:
            logger.error("Cannot send to runtime: process not running")
            return False

        if not self._is_runtime_process_alive():
            logger.error(
                f"Cannot send to runtime: process not running (returncode={self._get_runtime_returncode()})"
            )
            self.is_running = False
            self.runtime_process = None
            return False

        if not self._is_runtime_stdin_writable():
            logger.error("Cannot send to runtime: stdin transport is closed")
            self.is_running = False
            return False

        try:
            logger.debug(f"Sending to runtime: {msg_type}")
            if msg_type == 'api_response':
                logger.debug(f"   Response data: {message.get('data', {})}")
            data = json.dumps(message) + '\n'
            
            # Check if this is asyncio subprocess or Popen fallback
            stdin = self.runtime_process.stdin
            if hasattr(stdin, 'drain'):
                # Asyncio subprocess - async IO
                stdin.write(data.encode())
                await stdin.drain()
            else:
                # Popen fallback - sync IO, use executor
                blocking_pool = _get_blocking_task_pool(self.app)
                await blocking_pool.run_in_executor(stdin.write, data.encode())
                await blocking_pool.run_in_executor(stdin.flush)
            
            logger.debug(f"Sent to runtime: {msg_type}")
            return True
        except Exception as e:
            if self._is_closed_transport_error(e):
                self.is_running = False
                if self.runtime_process and not self._is_runtime_process_alive():
                    self.runtime_process = None
                logger.warning(f"Runtime transport closed while sending {msg_type}: {e}")
                return False
            logger.error(f"Error sending to runtime: {e}", exc_info=True)
            return False
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to runtime.
        
        Inspired by LangBot: heartbeat failure doesn't immediately disconnect,
        just logs the error. This prevents false disconnections due to temporary issues.
        """
        consecutive_failures = 0
        max_consecutive_failures = 5  # Allow 5 consecutive failures before considering disconnection
        
        try:
            while self.is_running:
                await asyncio.sleep(30)  # Every 30 seconds
                
                try:
                    sent = await self._send_to_runtime({
                        'type': 'heartbeat',
                        'data': {'timestamp': datetime.utcnow().isoformat()}
                    })
                    if sent:
                        consecutive_failures = 0  # Reset on success
                        logger.debug("Heartbeat sent successfully")
                    else:
                        consecutive_failures += 1
                        logger.debug(f"Heartbeat failed ({consecutive_failures}/{max_consecutive_failures})")
                except Exception as e:
                    consecutive_failures += 1
                    logger.debug(f"Heartbeat failed ({consecutive_failures}/{max_consecutive_failures}): {e}")

                # Only log warning after multiple failures
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        f"Heartbeat failed {consecutive_failures} times consecutively. "
                        f"Plugin runtime may be disconnected."
                    )
                    # Don't immediately disconnect - let the read loop detect actual disconnection
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat loop fatal error: {e}", exc_info=True)
    
    async def _cleanup_expired_requests(self):
        """Periodically cleanup expired pending requests."""
        try:
            while self.is_running:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                expired = []
                for request_id, future in list(self.pending_requests.items()):
                    if future.done() or future.cancelled():
                        expired.append(request_id)
                
                for request_id in expired:
                    self.pending_requests.pop(request_id, None)
                    logger.debug(f"Cleaned up expired request: {request_id}")
                
                # Also cleanup interceptor futures
                expired_interceptors = []
                for request_id, future in list(self._interceptor_futures.items()):
                    if future.done() or future.cancelled():
                        expired_interceptors.append(request_id)
                
                for request_id in expired_interceptors:
                    self._interceptor_futures.pop(request_id, None)
                    logger.debug(f"Cleaned up expired interceptor future: {request_id}")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Cleanup task error: {e}", exc_info=True)
    
    async def _initialize_plugins(self):
        """Initialize all enabled plugins."""
        try:
            # Get enabled plugins from database
            plugins = await self.db_manager.list_plugin_settings(enabled_only=True)
            
            logger.info(f"Found {len(plugins)} enabled plugins")
            
            # Send init command to runtime
            # Priority: database > metadata.yaml > default (100)
            plugin_list = []
            plugin_dir = self._get_resolved_plugin_base()
            thread_pool = getattr(self.app, 'blocking_task_pool', None) if self.app else None
            for p in plugins:
                plugin_path = plugin_dir / p.plugin_name
                if not plugin_manifest_exists(plugin_path):
                    logger.warning(
                        "Skipping enabled plugin %s/%s: manifest missing in %s",
                        p.plugin_author,
                        p.plugin_name,
                        plugin_path,
                    )
                    continue

                # Try to get priority from metadata.yaml
                priority_from_manifest = None
                try:
                    plugin_metadata = await _load_plugin_manifest_async(plugin_path, thread_pool)
                    priority_from_manifest = plugin_metadata.get('priority')
                except Exception as e:
                    logger.warning(
                        "Skipping enabled plugin %s/%s: failed to load manifest from %s: %s",
                        p.plugin_author,
                        p.plugin_name,
                        plugin_path,
                        e,
                    )
                    continue

                dependencies_ok = await install_plugin_dependencies(plugin_path, plugin_metadata)
                if not dependencies_ok:
                    logger.warning(
                        "Skipping enabled plugin %s/%s: dependency installation failed",
                        p.plugin_author,
                        p.plugin_name,
                    )
                    continue
                
                # Priority: database > metadata.yaml > default
                final_priority = p.priority
                if p.priority == 100 and priority_from_manifest is not None:
                    # Database has default, use metadata.yaml if available
                    final_priority = priority_from_manifest
                
                plugin_list.append({
                    'author': p.plugin_author,
                    'name': p.plugin_name,
                    'config': p.config,
                    'priority': final_priority
                })
            
            await self._send_to_runtime({
                'type': 'init_plugins',
                'data': {
                    'plugins': plugin_list
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize plugins: {e}", exc_info=True)
    
    async def emit_event(self, event_name: str, data: Dict[str, Any], source: Optional[str] = None):
        """Emit event to all plugins.
        
        Args:
            event_name: Event name
            data: Event data
            source: Event source (optional)
        """
        # Run event interceptors
        allow, modified_data = await self.interceptor_registry.intercept_event(
            event_name, data, source
        )
        
        if not allow:
            logger.debug(f"Event blocked by interceptor: {event_name} from {source}")
            return
        
        # Use modified data if any interceptor changed it
        if modified_data != data:
            logger.debug(f"Event modified by interceptor: {event_name}")
            data = modified_data
        
        await self._send_to_runtime({
            'type': 'event',
            'data': {
                'event': event_name,
                'data': data
            }
        })
    
    async def emit_event_with_context(
        self,
        event_context: 'EventContext',
        bound_plugins: Optional[List[str]] = None
    ) -> Optional['EventContext']:
        """Emit event with context to plugins (similar to LangBot).
        
        Plugins can modify the event context and prevent default behavior.
        
        Args:
            event_context: EventContext instance
            bound_plugins: List of plugin IDs to include (None = all enabled plugins)
            
        Returns:
            Modified EventContext or None if event was blocked
        """
        from ...core.event_context import EventContext
        
        if not self.is_running:
            return event_context
        
        # Check if runtime process is actually alive
        if self.runtime_process is not None:
            try:
                # Check if process is still running
                if hasattr(self.runtime_process, 'returncode'):
                    if self.runtime_process.returncode is not None:
                        logger.error(f"Runtime process has exited with code {self.runtime_process.returncode}")
                        self.is_running = False
                        return event_context
                elif hasattr(self.runtime_process, 'poll'):
                    if self.runtime_process.poll() is not None:
                        logger.error(f"Runtime process has exited")
                        self.is_running = False
                        return event_context
            except Exception as e:
                logger.warning(f"Error checking runtime process status: {e}")
        
        # Send event context to runtime for plugin processing
        import uuid
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future
        
        logger.debug(f"Emitting event_with_context to runtime: {event_context.event_name}, request_id={request_id}")
        await self._send_to_runtime({
            'type': 'event_with_context',
            'data': {
                'request_id': request_id,
                'event_context': event_context.to_dict(),
                'bound_plugins': bound_plugins
            }
        })
        
        try:
            # Wait for response (with timeout)
            #  
            # - before_send: 2
            # - message.received: 10
            # - : 30
            if event_context.event_name == 'message.before_send':
                timeout = 2.0  # API
            elif event_context.event_name == 'message.received':
                timeout = 10.0  # 1030
            else:
                timeout = 30.0  # 30
            logger.debug(f"Waiting for event_with_context response: {event_context.event_name}, timeout={timeout}s")
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.debug(f"Received event_with_context response: {event_context.event_name}, success={result.get('success', True)}")
            
            if result.get('success', True):  # Default to True if not specified
                # Get modified context from result
                modified_ctx_dict = result.get('event_context')
                if modified_ctx_dict:
                    logger.debug(f"Returning modified context for {event_context.event_name}")
                    return EventContext.from_dict(modified_ctx_dict)
                # No modification, return original context
                logger.debug(f"Returning original context for {event_context.event_name} (no modifications)")
                return event_context
            else:
                # Event was blocked
                logger.debug(f"Event blocked by plugin: {event_context.event_name}")
                return None
                
        except asyncio.TimeoutError:
            # Remove future from pending_requests to prevent memory leak
            # If response arrives later, it will be ignored (future already timed out)
            self.pending_requests.pop(request_id, None)
            logger.warning(f"Event context timeout: {event_context.event_name} (request_id={request_id})")
            # Return original context to allow processing to continue
            return event_context
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            logger.error(f"Error emitting event with context: {e}", exc_info=True)
            return event_context
    
    async def _get_enabled_plugins_with_priority(
        self,
        bound_plugins: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get enabled plugins with priority information."""
        try:
            from ...core.database import get_database_manager
            from ...core.models.plugin import PluginSetting
            
            db_manager = get_database_manager()
            if not db_manager:
                return []
            
            # Get all plugin settings
            async with db_manager.session() as session:
                from sqlalchemy import select
                result = await session.execute(select(PluginSetting))
                settings = result.scalars().all()
                
                enabled_plugins = []
                for setting in settings:
                    if not setting.enabled:
                        continue
                    
                    plugin_id = f"{setting.plugin_author}/{setting.plugin_name}"
                    
                    # Filter by bound_plugins if specified
                    if bound_plugins is not None and plugin_id not in bound_plugins:
                        continue
                    
                    enabled_plugins.append({
                        'plugin_id': plugin_id,
                        'author': setting.plugin_author,
                        'name': setting.plugin_name,
                        'priority': getattr(setting, 'priority', 100),  # Default priority: 100
                    })
                
                return enabled_plugins
        except Exception as e:
            logger.error(f"Error getting enabled plugins: {e}", exc_info=True)
            return []
    
    async def install_plugin(self, author: str, name: str, source: str):
        """Install a plugin.
        
        Args:
            author: Plugin author
            name: Plugin name
            source: Installation source (path, url, etc.)
            
        Returns:
            True if successful
        """
        logger.info(f"Installing plugin: {author}/{name} from {source}")
        
        try:
            plugins_dir = self._get_resolved_plugin_base()
            plugin_path = plugins_dir / name
            deps_dir = get_plugin_dependency_dir(plugin_path)
            
            # 
            if plugin_path.exists():
                logger.warning(f"Plugin {name} already exists at {plugin_path}")
                return False
            
            # source
            if source.startswith('http://') or source.startswith('https://'):
                # URLGitHub
                logger.info(f"Downloading plugin from URL: {source}")
                
                try:
                    import aiohttp
                    import tempfile
                    import zipfile
                    
                    # 
                    temp_dir = Path(tempfile.gettempdir()) / f"plugin_install_{name}_{datetime.now().timestamp()}"
                    temp_dir.mkdir(exist_ok=True)
                    temp_zip = temp_dir / f"{name}.zip"
                    
                    # GitHub URL
                    if 'github.com' in source:
                        # GitHubURL
                        if source.endswith('.zip'):
                            download_url = source
                        elif '/archive/' in source:
                            download_url = source
                        else:
                            # URL/archive/refs/heads/main.zip
                            if source.endswith('/'):
                                source = source[:-1]
                            if not source.endswith('.zip'):
                                # mainzip
                                download_url = f"{source}/archive/refs/heads/main.zip"
                            else:
                                download_url = source
                    else:
                        download_url = source
                    
                    # 
                    async with aiohttp.ClientSession() as session:
                        async with session.get(download_url) as response:
                            if response.status != 200:
                                logger.error(f"Failed to download plugin: HTTP {response.status}")
                                return False
                            
                            # 
                            with open(temp_zip, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    f.write(chunk)
                    
                    # ZIP
                    with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                        # 
                        zip_names = zip_ref.namelist()
                        if zip_names:
                            # GitHub zip -/
                            root_dir = zip_names[0].split('/')[0]
                            # 
                            extract_dir = temp_dir / "extracted"
                            zip_ref.extractall(extract_dir)
                            
                            # 
                            extracted_root = extract_dir / root_dir
                            if extracted_root.exists():
                                # metadata.yaml + settings.json
                                if plugin_manifest_exists(extracted_root):
                                    source_path = extracted_root
                                else:
                                    plugin_dirs = [
                                        d for d in extracted_root.iterdir()
                                        if d.is_dir() and plugin_manifest_exists(d)
                                    ]
                                    if plugin_dirs:
                                        source_path = plugin_dirs[0]
                                    else:
                                        logger.error("Could not find metadata.yaml/settings.json in downloaded archive")
                                        import shutil
                                        shutil.rmtree(temp_dir, ignore_errors=True)
                                        return False
                            else:
                                logger.error("Failed to extract plugin archive")
                                import shutil
                                shutil.rmtree(temp_dir, ignore_errors=True)
                                return False
                            
                            # 
                            import shutil
                            shutil.copytree(source_path, plugin_path)
                            logger.info(f"Downloaded and installed plugin from {source} to {plugin_path}")
                            
                            # 
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        else:
                            logger.error("Downloaded archive is empty")
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return False
                        
                except Exception as e:
                    logger.error(f"Failed to download plugin from URL: {e}", exc_info=True)
                    # 
                    try:
                        import shutil
                        if 'temp_dir' in locals() and temp_dir.exists():
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    except:
                        pass
                    return False
            elif Path(source).exists():
                # 
                source_path = Path(source)
                if source_path.is_dir():
                    # 
                    import shutil
                    shutil.copytree(source_path, plugin_path)
                    logger.info(f"Copied plugin from {source_path} to {plugin_path}")
                elif source_path.is_file() and source_path.suffix == '.zip':
                    # ZIP
                    import zipfile
                    with zipfile.ZipFile(source_path, 'r') as zip_ref:
                        zip_ref.extractall(plugin_path)
                    logger.info(f"Extracted plugin from {source_path} to {plugin_path}")
                else:
                    logger.error(f"Unsupported source type: {source}")
                    return False
            else:
                logger.error(f"Source not found: {source}")
                return False
            
            if not plugin_manifest_exists(plugin_path):
                logger.error(f"Plugin {name} missing metadata.yaml/settings.json, installation failed")
                # 
                import shutil
                if plugin_path.exists():
                    shutil.rmtree(plugin_path)
                return False
            
            plugin_metadata = load_plugin_manifest(plugin_path)
            
            # 
            logger.info(f"Checking dependencies for plugin: {author}/{name}")
            if not await install_plugin_dependencies(plugin_path, plugin_metadata):
                logger.error(f"Plugin dependency installation failed: {author}/{name}")
                import shutil
                shutil.rmtree(plugin_path, ignore_errors=True)
                deps_dir = get_plugin_dependency_dir(plugin_path)
                shutil.rmtree(deps_dir, ignore_errors=True)
                return False
            
            # 
            if self.db_manager:
                
                # 
                existing_setting = await self.db_manager.get_plugin_setting(author, name)
                
                default_config = plugin_metadata.get('default_config', {})
                install_info = {
                    'source': source,
                    'version': plugin_metadata.get('version', '1.0.0'),
                    'installed_at': datetime.now().isoformat()
                }
                
                if existing_setting:
                    # 
                    success = await self.db_manager.update_plugin_setting(
                        author, name,
                        enabled=False,
                        config=default_config,
                        install_source='local' if Path(source).exists() else 'url',
                        install_info=install_info
                    )
                else:
                    # 
                    try:
                        await self.db_manager.create_plugin_setting(
                            author, name,
                            enabled=False,
                            config=default_config,
                            install_source='local' if Path(source).exists() else 'url',
                            install_info=install_info
                        )
                        success = True
                    except Exception as e:
                        logger.error(f"Failed to create plugin setting: {e}")
                        success = False
                
                if success:
                    logger.info(f"Plugin {author}/{name} installed successfully")
                    # 
                    await self.reload_plugin(f"{author}/{name}")
                    return True
                else:
                    logger.error(f"Failed to register plugin in database")
                    return False
            else:
                logger.warning("Database manager not available, plugin installed but not registered")
                return True
                
        except Exception as e:
            logger.error(f"Failed to install plugin {author}/{name}: {e}", exc_info=True)
            # 
            try:
                if plugin_path.exists():
                    import shutil
                    shutil.rmtree(plugin_path)
            except:
                pass
            return False
    
    async def uninstall_plugin(self, author: str, name: str):
        """Uninstall a plugin completely.
        
        This will:
        1. Unload plugin from runtime
        2. Delete plugin directory
        3. Delete all plugin storage data from database
        4. Delete plugin settings from database
        
        Args:
            author: Plugin author
            name: Plugin name
            
        Returns:
            True if successful
        """
        logger.info(f"Uninstalling plugin: {author}/{name}")
        
        plugin_id = f"{author}/{name}"
        
        try:
            # 1. runtime
            await self.unload_plugin(plugin_id)
            
            plugins_dir = self._get_resolved_plugin_base()
            plugin_path = plugins_dir / name
            
            # 2. Read manifest before deleting directory (for Web UI upload keys in default_config)
            manifest_default_config: Optional[Dict[str, Any]] = None
            if plugin_manifest_exists(plugin_path):
                try:
                    manifest_default_config = load_plugin_manifest(plugin_path).get("default_config") or None
                except Exception as e:
                    logger.warning(f"Failed to read plugin manifest before uninstall: {e}")
            
            # 3. Database cleanup (before rmtree)
            if self.db_manager:
                # 3.0 Web UI config-file uploads stored in this plugin's private binary storage
                try:
                    existing = await self.db_manager.get_plugin_setting(author, name)
                    await self.db_manager.delete_plugin_config_upload_blobs(
                        plugin_id,
                        existing.config if existing else None,
                        manifest_default_config,
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete plugin config upload blobs: {e}")
                
                # 3.1 Runtime plugin binary storage
                try:
                    storage_keys = await self.db_manager.list_binary_keys('plugin', plugin_id)
                    deleted_count = 0
                    for key in storage_keys:
                        try:
                            await self.db_manager.delete_binary('plugin', plugin_id, key)
                            deleted_count += 1
                            logger.debug(f"Deleted storage key: {key} for plugin {plugin_id}")
                        except Exception as e:
                            logger.warning(f"Failed to delete storage key {key}: {e}")
                    if storage_keys:
                        logger.info(f"Deleted {deleted_count}/{len(storage_keys)} storage keys for plugin {plugin_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete plugin storage data: {e}")
                
                # 3.2 Plugin settings row
                try:
                    success = await self.db_manager.delete_plugin_setting(author, name)
                    if success:
                        logger.info(f"Deleted plugin settings for {author}/{name}")
                    else:
                        logger.warning(f"Plugin settings not found in database: {author}/{name}")
                except Exception as e:
                    logger.error(f"Failed to delete plugin settings: {e}")
                    return False
                
                logger.info(f"Plugin {author}/{name} uninstalled successfully (all data deleted)")
            else:
                logger.warning("Database manager not available, plugin directory will still be removed")
            
            # 4. Delete plugin directory
            if plugin_path.exists():
                import shutil
                try:
                    shutil.rmtree(plugin_path)
                    logger.info(f"Deleted plugin directory: {plugin_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete plugin directory: {e}")

            if deps_dir.exists():
                import shutil
                try:
                    shutil.rmtree(deps_dir)
                    logger.info(f"Deleted plugin dependency directory: {deps_dir}")
                except Exception as e:
                    logger.warning(f"Failed to delete plugin dependency directory: {e}")
            
            return True
                
        except Exception as e:
            logger.error(f"Failed to uninstall plugin {author}/{name}: {e}", exc_info=True)
            return False
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a single plugin without reloading.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
            
        Returns:
            True if unloaded successfully
        """
        logger.info(f"Unloading plugin: {plugin_name}")
        
        try:
            # Send unload message to runtime
            await self._send_to_runtime({
                'type': 'unload_plugin',
                'data': {
                    'plugin_name': plugin_name
                }
            })
            
            # Wait a bit for the unload to complete
            await asyncio.sleep(0.3)
            
            logger.info(f"Plugin {plugin_name} unloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    async def reload_plugin(
        self,
        plugin_name: str,
        progress_callback: DependencyProgressCallback = None,
    ) -> bool:
        """Reload a single plugin.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
            
        Returns:
            True if reloaded successfully
        """
        logger.info(f"Reloading single plugin: {plugin_name}")
        
        try:
            # Refresh DB metadata for this plugin when users click reload.
            target_dir_name = plugin_name.split('/', 1)[1] if '/' in plugin_name else plugin_name
            await self._sync_plugin_records_from_disk(plugin_dir_name=target_dir_name)

            plugin_path_for_deps = self._get_resolved_plugin_base() / target_dir_name
            if plugin_manifest_exists(plugin_path_for_deps):
                thread_pool = getattr(self.app, 'blocking_task_pool', None) if self.app else None
                plugin_metadata = await _load_plugin_manifest_async(plugin_path_for_deps, thread_pool)
                if not await install_plugin_dependencies(
                    plugin_path_for_deps,
                    plugin_metadata,
                    progress_callback=progress_callback,
                ):
                    logger.error("Cannot reload plugin %s: dependency installation failed", plugin_name)
                    return False

            # Get fresh config from database to pass to runtime
            # This avoids SQLite cross-process caching issues
            plugin_config = {}  # None
            
            if self.db_manager:
                # Parse plugin name to get author/name
                if '/' in plugin_name:
                    author, name = plugin_name.split('/', 1)
                else:
                    # Try to get author from metadata.yaml
                    plugin_path = self._get_resolved_plugin_base() / plugin_name
                    if plugin_manifest_exists(plugin_path):
                        thread_pool = getattr(self.app, 'blocking_task_pool', None)
                        metadata = await _load_plugin_manifest_async(plugin_path, thread_pool)
                        author = metadata.get('author', 'Unknown')
                        name = plugin_name
                    else:
                        author = 'Unknown'
                        name = plugin_name
                
                # Get latest config from database
                setting = await self.db_manager.get_plugin_setting(author, name)
                if setting and setting.config:
                    plugin_config = setting.config
                    logger.debug(f"Loaded fresh config from database for {plugin_name}: {plugin_config}")
                else:
                    # 
                    plugin_config = {}
                    logger.debug(f"No config in database for {plugin_name}, using empty config")
            
            # plugin_configNone
            if plugin_config is None:
                plugin_config = {}
            
            # Send reload message to runtime with fresh config
            await self._send_to_runtime({
                'type': 'reload_plugin',
                'data': {
                    'plugin_name': plugin_name,
                    'config': plugin_config  # Pass config directly to avoid cross-process cache issues
                }
            })
            
            # Wait a bit for the reload to complete
            await asyncio.sleep(0.5)
            
            logger.info(f"Plugin {plugin_name} reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    async def reload_plugins(self):
        """Reload all plugins from database.
        
        This will restart the plugin runtime process to pick up
        any changes to plugin enabled/disabled status.
        """
        logger.info("Reloading plugins...")
        
        try:
            # Stop current runtime
            await self.dispose()
            
            # Wait a bit for cleanup
            await asyncio.sleep(0.5)
            
            # Restart runtime (re-initialize)
            await self.initialize()
            
            logger.info("Plugins reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload plugins: {e}", exc_info=True)
            raise
    
    async def dispose(self):
        """Cleanup runtime resources."""
        logger.info("Disposing plugin runtime...")
        self.is_running = False
        
        # Send shutdown message to runtime to properly unload all plugins
        try:
            logger.info("Sending shutdown message to plugin runtime...")
            await self._send_to_runtime({
                'type': 'shutdown',
                'data': {}
            })
            # Give plugins time to save data (up to 5 seconds)
            await asyncio.sleep(0.5)
            logger.info("Plugin runtime shutdown message sent")
        except Exception as e:
            logger.error(f"Error sending shutdown message: {e}")
        
        # Cancel tasks
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        if self.runtime_task and not self.runtime_task.done():
            self.runtime_task.cancel()
            try:
                await self.runtime_task
            except asyncio.CancelledError:
                pass
            self.runtime_task = None

        if self.runtime_stderr_task and not self.runtime_stderr_task.done():
            self.runtime_stderr_task.cancel()
            try:
                await self.runtime_stderr_task
            except asyncio.CancelledError:
                pass
        self.runtime_stderr_task = None
        
        # Terminate process
        if self.runtime_process:
            try:
                # Check if process is still running
                is_running = False
                if hasattr(self.runtime_process, 'returncode'):
                    is_running = self.runtime_process.returncode is None
                elif hasattr(self.runtime_process, 'poll'):
                    is_running = self.runtime_process.poll() is None
                
                if is_running:
                    # Try graceful termination first
                    self.runtime_process.terminate()
                    try:
                        await self._wait_for_runtime_process(timeout=3.0)
                        logger.info("Runtime process terminated gracefully")
                    except asyncio.TimeoutError:
                        logger.warning("Runtime process didn't terminate, killing it...")
                        self.runtime_process.kill()
                        await self._wait_for_runtime_process()
                        logger.info("Runtime process killed")
            except ProcessLookupError:
                # Process already terminated
                logger.debug("Runtime process already terminated")
            except Exception as e:
                logger.error(f"Error terminating runtime process: {e}")
            finally:
                # Clear process reference
                self.runtime_process = None
        
        # Clear stdin/stdout references
        self.runtime_stdin = None
        self.runtime_stdout = None
        
        logger.info("Plugin runtime disposed")
    
    async def cleanup_orphan_processes(self) -> int:
        """Manually cleanup orphaned plugin runtime processes.
        
        Returns:
            Number of processes cleaned up
        """
        logger.info("Manually cleaning up orphaned plugin runtime processes...")
        cleaned_count = 0
        
        try:
            import psutil
            current_pid = os.getpid()
            process_match_token = self._get_runtime_process_match_token()
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue
                    
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and process_match_token in ' '.join(cmdline):
                        logger.info(f"Found orphaned plugin runtime process: PID {proc.info['pid']}, terminating...")
                        try:
                            proc_obj = psutil.Process(proc.info['pid'])
                            proc_obj.terminate()
                            proc_obj.wait(timeout=2)
                            logger.info(f"Orphaned process {proc.info['pid']} terminated")
                            cleaned_count += 1
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            try:
                                proc_obj.kill()
                                logger.info(f"Orphaned process {proc.info['pid']} killed")
                                cleaned_count += 1
                            except psutil.NoSuchProcess:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.warning("psutil not available, cannot cleanup orphaned processes")
        except Exception as e:
            logger.error(f"Error cleaning up orphaned processes: {e}", exc_info=True)
        
        logger.info(f"Cleaned up {cleaned_count} orphaned plugin runtime process(es)")
        return cleaned_count


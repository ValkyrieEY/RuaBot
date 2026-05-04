"""Local sandbox booter for executing code on the local machine."""
import asyncio
import os
import sys
import io
import contextlib
import tempfile
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, List
from ...blocking_task_pool import run_in_blocking_pool
from ...logger import get_logger
from .base import ComputerBooter, ShellComponent, PythonComponent, FileSystemComponent
logger = get_logger(__name__)
class LocalShellComponent(ShellComponent):
    """Local shell execution component."""
    IDLE_TIMEOUT_SECONDS = 30 * 60

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.current_cwd = work_dir.resolve()
        self.session_env: Dict[str, str] = {}
        self._process: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        self._idle_task: Optional[asyncio.Task] = None
        self._last_used_at = 0.0

    def _build_exec_env(self, env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        exec_env = os.environ.copy()
        exec_env.update(self.session_env)
        if env:
            exec_env.update(env)
        return exec_env

    def _decode_output(self, data: bytes) -> str:
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            if sys.platform == 'win32':
                text = data.decode('gbk', errors='replace')
            else:
                text = data.decode('utf-8', errors='replace')
        return text.replace("\x08 \x08", "").replace("\x08", "")

    def _wrap_stateful_command(self, command: str, marker: str, cwd: Optional[Path] = None) -> str:
        exit_marker = f"__XQNEXT_SANDBOX_EXIT_{marker}__"
        cwd_marker = f"__XQNEXT_SANDBOX_CWD_{marker}__"
        env_marker = f"__XQNEXT_SANDBOX_ENV_{marker}__"
        done_marker = f"__XQNEXT_SANDBOX_DONE_{marker}__"

        if sys.platform == 'win32':
            lines = []
            if cwd is not None:
                lines.append(f'cd /d "{str(cwd).replace("\"", "\"\"")}"')
            lines.extend([
                command,
                'set "__XQNEXT_SANDBOX_EXIT=%ERRORLEVEL%"',
                f"echo {exit_marker}%__XQNEXT_SANDBOX_EXIT%",
                f"echo {cwd_marker}",
                "cd",
                f"echo {env_marker}",
                "set",
                f"echo {done_marker}",
            ])
            return "\r\n".join(lines)

        lines = []
        if cwd is not None:
            quoted_cwd = "'" + str(cwd).replace("'", "'\"'\"'") + "'"
            lines.append(f"cd {quoted_cwd}")
        lines.extend([
            command,
            "__xqnext_sandbox_exit=$?",
            f"printf '\\n{exit_marker}%s\\n' \"$__xqnext_sandbox_exit\"",
            f"printf '{cwd_marker}\\n'",
            "pwd",
            f"printf '{env_marker}\\n'",
            "env",
            f"printf '{done_marker}\\n'",
        ])
        return "\n".join(lines)

    def _write_stateful_script(self, work_dir: Path, command: str, marker: str) -> Path:
        suffix = ".cmd" if sys.platform == 'win32' else ".sh"
        script_path = work_dir / f".xqnext_sandbox_{marker}{suffix}"
        script_path.write_text(
            self._wrap_stateful_command(command, marker),
            encoding="utf-8",
            newline="" if sys.platform == 'win32' else "\n",
        )
        if sys.platform != 'win32':
            try:
                script_path.chmod(script_path.stat().st_mode | 0o700)
            except Exception:
                pass
        return script_path

    def _split_stateful_output(self, stdout: str, marker: str) -> tuple[str, Optional[int]]:
        exit_marker = f"__XQNEXT_SANDBOX_EXIT_{marker}__"
        cwd_marker = f"__XQNEXT_SANDBOX_CWD_{marker}__"
        env_marker = f"__XQNEXT_SANDBOX_ENV_{marker}__"
        done_marker = f"__XQNEXT_SANDBOX_DONE_{marker}__"

        if exit_marker not in stdout or cwd_marker not in stdout or env_marker not in stdout:
            return stdout, None

        user_stdout, state_output = stdout.split(exit_marker, 1)
        exit_output, state_output = state_output.split(cwd_marker, 1)
        cwd_output, env_output = state_output.split(env_marker, 1)
        env_output = env_output.split(done_marker, 1)[0]

        exit_code = None
        exit_lines = [line.strip() for line in exit_output.splitlines() if line.strip()]
        if exit_lines:
            try:
                exit_code = int(exit_lines[0])
            except ValueError:
                exit_code = None

        cwd_lines = [line.strip() for line in cwd_output.splitlines() if line.strip()]
        if cwd_lines:
            next_cwd = Path(cwd_lines[-1])
            if next_cwd.exists():
                self.current_cwd = next_cwd.resolve()

        next_env: Dict[str, str] = {}
        for line in env_output.splitlines():
            if not line or "=" not in line:
                continue
            # Windows `set` includes pseudo variables like `=C:=C:\...`.
            if line.startswith("="):
                continue
            key, value = line.split("=", 1)
            if key == "__XQNEXT_SANDBOX_EXIT":
                continue
            next_env[key] = value
        if next_env:
            self.session_env = next_env

        return user_stdout.rstrip("\r\n"), exit_code

    async def _ensure_shell_process(self, work_dir: Path, exec_env: Dict[str, str]) -> None:
        if self._process and self._process.returncode is None:
            return

        if sys.platform == 'win32':
            exec_env = dict(exec_env)
            exec_env["PROMPT"] = "$H"
            self._process = await asyncio.create_subprocess_exec(
                "cmd.exe",
                "/d",
                "/q",
                cwd=str(work_dir),
                env=exec_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            init_marker = f"__XQNEXT_SANDBOX_INIT_{uuid.uuid4().hex}__"
            await self._write_to_shell(f"chcp 65001 > nul\r\necho {init_marker}\r\n")
            await self._read_until_text(init_marker, timeout=5)
        else:
            self._process = await asyncio.create_subprocess_exec(
                "/bin/sh",
                cwd=str(work_dir),
                env=exec_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        self.current_cwd = work_dir

    async def _write_to_shell(self, text: str) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("Shell process is not running")
        self._process.stdin.write(text.encode("utf-8", errors="replace"))
        await self._process.stdin.drain()

    async def _read_until_text(self, needle: str, timeout: int) -> str:
        if not self._process or not self._process.stdout:
            raise RuntimeError("Shell process is not running")

        chunks: List[str] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError()
            line = await asyncio.wait_for(self._process.stdout.readline(), timeout=remaining)
            if not line:
                raise RuntimeError("Shell process exited")
            text = self._decode_output(line)
            chunks.append(text)
            if needle in text:
                return "".join(chunks)

    async def _read_until_done(self, marker: str, timeout: Optional[int]) -> str:
        if not self._process or not self._process.stdout:
            raise RuntimeError("Shell process is not running")

        done_marker = f"__XQNEXT_SANDBOX_DONE_{marker}__"
        chunks: List[str] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout or 30)

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError()
            line = await asyncio.wait_for(self._process.stdout.readline(), timeout=remaining)
            if not line:
                raise RuntimeError("Shell process exited")
            text = self._decode_output(line)
            chunks.append(text)
            if done_marker in text:
                break
        return "".join(chunks)

    def _schedule_idle_shutdown(self) -> None:
        self._last_used_at = asyncio.get_running_loop().time()
        if self._idle_task:
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._shutdown_after_idle())

    async def _shutdown_after_idle(self) -> None:
        try:
            await asyncio.sleep(self.IDLE_TIMEOUT_SECONDS)
            now = asyncio.get_running_loop().time()
            if now - self._last_used_at >= self.IDLE_TIMEOUT_SECONDS:
                await self.shutdown()
        except asyncio.CancelledError:
            pass

    async def shutdown(self) -> None:
        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None
        process = self._process
        self._process = None
        if process and process.returncode is None:
            try:
                if process.stdin:
                    exit_command = "exit\r\n" if sys.platform == 'win32' else "exit\n"
                    process.stdin.write(exit_command.encode("utf-8"))
                    await process.stdin.drain()
                await asyncio.wait_for(process.wait(), timeout=3)
            except Exception:
                process.kill()
                await process.wait()

    async def exec(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = 30,
        shell: bool = True,
        background: bool = False,
    ) -> Dict[str, Any]:
        """Execute shell command locally."""
        original_command = command
        try:
            work_dir = Path(cwd) if cwd else self.current_cwd
            work_dir.mkdir(parents=True, exist_ok=True)
            work_dir = work_dir.resolve()
            exec_env = self._build_exec_env(env)
            if background:
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    cwd=str(work_dir),
                    env=exec_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return {
                    "pid": process.pid,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": None,
                    "success": True,
                    "command": original_command,
                    "cwd": str(work_dir),
                }

            if shell:
                async with self._lock:
                    await self._ensure_shell_process(work_dir, exec_env)
                    marker = uuid.uuid4().hex
                    cwd_override = work_dir if cwd else None
                    await self._write_to_shell(self._wrap_stateful_command(command, marker, cwd_override))
                    await self._write_to_shell("\r\n" if sys.platform == 'win32' else "\n")
                    try:
                        raw_stdout = await self._read_until_done(marker, timeout)
                        stdout, parsed_exit_code = self._split_stateful_output(raw_stdout, marker)
                        exit_code = parsed_exit_code if parsed_exit_code is not None else 0
                        self._schedule_idle_shutdown()
                    except asyncio.TimeoutError:
                        await self.shutdown()
                        return {
                            "stdout": "",
                            "stderr": f"Command timed out after {timeout} seconds",
                            "exit_code": -1,
                            "success": False,
                            "command": original_command,
                            "cwd": str(work_dir),
                        }
                return {
                    "stdout": stdout,
                    "stderr": "",
                    "exit_code": exit_code,
                    "success": exit_code == 0,
                    "command": original_command,
                    "cwd": str(self.current_cwd),
                    "persistent": True,
                }

            process = await asyncio.create_subprocess_exec(
                command,
                cwd=str(work_dir),
                env=exec_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                stdout = self._decode_output(stdout_bytes)
                stderr = self._decode_output(stderr_bytes)
                exit_code = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": -1,
                    "success": False,
                    "command": original_command,
                    "cwd": str(work_dir),
                }
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "success": exit_code == 0,
                "command": original_command,
                "cwd": str(self.current_cwd),
            }
        except Exception as e:
            logger.error(f"Shell execution error: {e}", exc_info=True)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "success": False,
                "command": original_command,
            }
class LocalPythonComponent(PythonComponent):
    """Local Python code execution component."""
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.kernels: Dict[str, Dict[str, Any]] = {}
    async def exec(
        self,
        code: str,
        kernel_id: Optional[str] = None,
        timeout: int = 30,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """Execute Python code locally."""
        try:
            if kernel_id:
                if kernel_id not in self.kernels:
                    self.kernels[kernel_id] = {
                        '__builtins__': __builtins__,
                        '__name__': '__main__',
                    }
                namespace = self.kernels[kernel_id]
            else:
                namespace = {
                    '__builtins__': __builtins__,
                    '__name__': '__main__',
                }
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            def run_code():
                with contextlib.redirect_stdout(stdout_buffer), \
                     contextlib.redirect_stderr(stderr_buffer):
                    try:
                        old_cwd = os.getcwd()
                        os.chdir(str(self.work_dir))
                        compiled = compile(code, '<sandbox>', 'exec')
                        exec(compiled, namespace)
                        os.chdir(old_cwd)
                        return None
                    except Exception as e:
                        os.chdir(old_cwd)
                        return e
            try:
                error = await asyncio.wait_for(
                    run_in_blocking_pool(run_code),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                error = TimeoutError(f"Code execution timed out after {timeout} seconds")
            stdout_text = stdout_buffer.getvalue()
            stderr_text = stderr_buffer.getvalue()
            if error:
                stderr_text += f"\n{type(error).__name__}: {str(error)}"
            if silent:
                stdout_text = ""
            return {
                "success": error is None,
                "output": stdout_text,
                "error": stderr_text,
                "data": {
                    "output": {
                        "text": stdout_text,
                        "images": []
                    },
                    "error": stderr_text,
                },
                "code": code,
            }
        except Exception as e:
            logger.error(f"Python execution error: {e}", exc_info=True)
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "data": {
                    "output": {
                        "text": "",
                        "images": []
                    },
                    "error": str(e),
                },
                "code": code,
            }
class LocalFileSystemComponent(FileSystemComponent):
    """Local filesystem operations component."""
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
    def _resolve_path(self, path: str) -> Path:
        """Resolve and validate path within work directory."""
        normalized_path = path.replace('\\', '/').replace('//', '/')
        if not normalized_path or normalized_path == '.':
            return self.work_dir
        target = (self.work_dir / normalized_path).resolve()
        try:
            target.relative_to(self.work_dir.resolve())
        except ValueError:
            raise ValueError(f"Path {path} is outside sandbox work directory")
        return target
    async def read_file(self, path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file from sandbox."""
        try:
            target = self._resolve_path(path)
            content = target.read_text(encoding=encoding)
            return {
                "success": True,
                "path": path,
                "content": content,
            }
        except Exception as e:
            logger.error(f"Read file error: {e}")
            return {
                "success": False,
                "path": path,
                "content": "",
                "error": str(e),
            }
    async def write_file(
        self,
        path: str,
        content: str,
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Write file to sandbox."""
        try:
            target = self._resolve_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding=encoding)
            return {
                "success": True,
                "path": path,
            }
        except Exception as e:
            logger.error(f"Write file error: {e}")
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }
    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file from sandbox."""
        try:
            target = self._resolve_path(path)
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            return {
                "success": True,
                "path": path,
            }
        except Exception as e:
            logger.error(f"Delete file error: {e}")
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }
    async def list_dir(
        self,
        path: str = ".",
        show_hidden: bool = False,
    ) -> Dict[str, Any]:
        """List directory contents."""
        try:
            target = self._resolve_path(path)
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
            if not target.is_dir():
                return {
                    "success": False,
                    "path": path,
                    "entries": [],
                    "error": f"Not a directory: {path}",
                }
            entries = []
            work_dir_resolved = self.work_dir.resolve()
            for entry in sorted(target.iterdir()):
                if not show_hidden and entry.name.startswith('.'):
                    continue
                try:
                    stat = entry.stat()
                    entry_resolved = entry.resolve()
                    relative_path = entry_resolved.relative_to(work_dir_resolved)
                    normalized_path = str(relative_path).replace('\\', '/')
                    entries.append({
                        "name": entry.name,
                        "path": normalized_path,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size if entry.is_file() else 0,
                        "modified": stat.st_mtime,
                    })
                except Exception as e:
                    logger.warning(f"Failed to stat file {entry}: {e}")
                    continue
            return {
                "success": True,
                "path": path,
                "entries": entries,
            }
        except Exception as e:
            logger.error(f"List directory error: {e}", exc_info=True)
            return {
                "success": False,
                "path": path,
                "entries": [],
                "error": str(e),
            }
    async def create_dir(self, path: str) -> Dict[str, Any]:
        """Create directory."""
        try:
            target = self._resolve_path(path)
            target.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "path": path,
            }
        except Exception as e:
            logger.error(f"Create directory error: {e}")
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }
class LocalBooter(ComputerBooter):
    """Local machine booter for executing code on the host.
    
    WARNING: This executes code directly on the host machine without isolation.
    Use only for trusted code or development/testing purposes.
    """
    def __init__(self, base_work_dir: Optional[Path] = None):
        """Initialize local booter.
        
        Args:
            base_work_dir: Base directory for sandboxes (default: temp dir)
        """
        self.base_work_dir = base_work_dir or Path(tempfile.gettempdir()) / "xqnext_sandbox"
        self.work_dir: Optional[Path] = None
        self._fs: Optional[LocalFileSystemComponent] = None
        self._python: Optional[LocalPythonComponent] = None
        self._shell: Optional[LocalShellComponent] = None
        self._session_id: Optional[str] = None
    @property
    def fs(self) -> FileSystemComponent:
        if self._fs is None:
            raise RuntimeError("Sandbox not booted")
        return self._fs
    @property
    def python(self) -> PythonComponent:
        if self._python is None:
            raise RuntimeError("Sandbox not booted")
        return self._python
    @property
    def shell(self) -> ShellComponent:
        if self._shell is None:
            raise RuntimeError("Sandbox not booted")
        return self._shell
    @property
    def capabilities(self) -> Optional[List[str]]:
        return ['python', 'shell', 'filesystem']
    async def boot(self, session_id: str) -> None:
        """Boot local sandbox environment."""
        self._session_id = session_id
        self.work_dir = self.base_work_dir / session_id
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._fs = LocalFileSystemComponent(self.work_dir)
        self._python = LocalPythonComponent(self.work_dir)
        self._shell = LocalShellComponent(self.work_dir)
        logger.info(f"Local sandbox booted: {self.work_dir}")
    async def shutdown(self) -> None:
        """Shutdown and cleanup sandbox."""
        if self._shell is not None:
            await self._shell.shutdown()
        if self.work_dir and self.work_dir.exists():
            try:
                shutil.rmtree(self.work_dir)
                logger.info(f"Local sandbox cleaned up: {self.work_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox directory: {e}")
        self._fs = None
        self._python = None
        self._shell = None
        self.work_dir = None
    async def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """Upload file to sandbox (copy to work dir)."""
        try:
            if not self.work_dir:
                raise RuntimeError("Sandbox not booted")
            source = Path(local_path)
            target = self._fs._resolve_path(remote_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_file():
                shutil.copy2(source, target)
            else:
                shutil.copytree(source, target, dirs_exist_ok=True)
            return {
                "success": True,
                "file_path": remote_path,
            }
        except Exception as e:
            logger.error(f"Upload file error: {e}")
            return {
                "success": False,
                "file_path": remote_path,
                "error": str(e),
            }
    async def download_file(self, remote_path: str, local_path: str) -> None:
        """Download file from sandbox (copy from work dir)."""
        if not self.work_dir:
            raise RuntimeError("Sandbox not booted")
        source = self._fs._resolve_path(remote_path)
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
        else:
            shutil.copytree(source, target, dirs_exist_ok=True)
    async def available(self) -> bool:
        """Check whether local booter can be used."""
        return True

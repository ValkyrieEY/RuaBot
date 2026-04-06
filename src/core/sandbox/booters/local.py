"""Local sandbox booter for executing code on the local machine."""
import asyncio
import os
import sys
import io
import contextlib
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, List
from ...logger import get_logger
from .base import ComputerBooter, ShellComponent, PythonComponent, FileSystemComponent
logger = get_logger(__name__)
class LocalShellComponent(ShellComponent):
    """Local shell execution component."""
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
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
        try:
            work_dir = Path(cwd) if cwd else self.work_dir
            work_dir.mkdir(parents=True, exist_ok=True)
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)
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
                    "command": command,
                }
            if sys.platform == 'win32':
                command = f'chcp 65001 > nul && {command}'
            process = await asyncio.create_subprocess_shell(
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
                try:
                    stdout = stdout_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    if sys.platform == 'win32':
                        stdout = stdout_bytes.decode('gbk', errors='replace')
                    else:
                        stdout = stdout_bytes.decode('utf-8', errors='replace')
                try:
                    stderr = stderr_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    if sys.platform == 'win32':
                        stderr = stderr_bytes.decode('gbk', errors='replace')
                    else:
                        stderr = stderr_bytes.decode('utf-8', errors='replace')
                exit_code = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": -1,
                    "success": False,
                    "command": command,
                }
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "success": exit_code == 0,
                "command": command,
            }
        except Exception as e:
            logger.error(f"Shell execution error: {e}", exc_info=True)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "success": False,
                "command": command,
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
                    asyncio.get_event_loop().run_in_executor(None, run_code),
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
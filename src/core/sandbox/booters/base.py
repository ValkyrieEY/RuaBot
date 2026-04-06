"""Base classes for sandbox execution environment."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List


class ShellComponent(ABC):
    """Abstract interface for shell execution in sandbox."""
    
    @abstractmethod
    async def exec(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = 30,
        shell: bool = True,
        background: bool = False,
    ) -> Dict[str, Any]:
        """Execute shell command.
        
        Args:
            command: Shell command to execute
            cwd: Working directory
            env: Environment variables
            timeout: Timeout in seconds
            shell: Execute in shell mode
            background: Run in background
            
        Returns:
            Dict with stdout, stderr, exit_code, success
        """
        pass


class PythonComponent(ABC):
    """Abstract interface for Python code execution in sandbox."""
    
    @abstractmethod
    async def exec(
        self,
        code: str,
        kernel_id: Optional[str] = None,
        timeout: int = 30,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """Execute Python code.
        
        Args:
            code: Python code to execute
            kernel_id: Optional kernel ID for stateful execution
            timeout: Timeout in seconds
            silent: Suppress output
            
        Returns:
            Dict with success, output, error, data
        """
        pass


class FileSystemComponent(ABC):
    """Abstract interface for filesystem operations in sandbox."""
    
    @abstractmethod
    async def read_file(self, path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file from sandbox.
        
        Returns:
            Dict with success, path, content
        """
        pass
    
    @abstractmethod
    async def write_file(
        self,
        path: str,
        content: str,
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Write file to sandbox.
        
        Returns:
            Dict with success, path
        """
        pass
    
    @abstractmethod
    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file from sandbox.
        
        Returns:
            Dict with success, path
        """
        pass
    
    @abstractmethod
    async def list_dir(
        self,
        path: str = ".",
        show_hidden: bool = False,
    ) -> Dict[str, Any]:
        """List directory contents.
        
        Returns:
            Dict with success, path, entries (list of file info dicts)
        """
        pass
    
    @abstractmethod
    async def create_dir(self, path: str) -> Dict[str, Any]:
        """Create directory.
        
        Returns:
            Dict with success, path
        """
        pass


class ComputerBooter(ABC):
    """Abstract base class for sandbox execution environment.
    
    A booter provides isolated execution environment with shell, python,
    filesystem, and optionally browser capabilities.
    """
    
    @property
    @abstractmethod
    def fs(self) -> FileSystemComponent:
        """Get filesystem component."""
        pass
    
    @property
    @abstractmethod
    def python(self) -> PythonComponent:
        """Get Python execution component."""
        pass
    
    @property
    @abstractmethod
    def shell(self) -> ShellComponent:
        """Get shell execution component."""
        pass
    
    @property
    def capabilities(self) -> Optional[List[str]]:
        """Get sandbox capabilities.
        
        Returns:
            List of capability names: 'python', 'shell', 'filesystem', 'browser'
            None if capability introspection not supported
        """
        return None
    
    @abstractmethod
    async def boot(self, session_id: str) -> None:
        """Boot the sandbox environment.
        
        Args:
            session_id: Unique session identifier
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the sandbox environment."""
        pass
    
    @abstractmethod
    async def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """Upload file to sandbox.
        
        Returns:
            Dict with success, file_path
        """
        pass
    
    @abstractmethod
    async def download_file(self, remote_path: str, local_path: str) -> None:
        """Download file from sandbox."""
        pass
    
    @abstractmethod
    async def available(self) -> bool:
        """Check if sandbox is available and healthy."""
        pass

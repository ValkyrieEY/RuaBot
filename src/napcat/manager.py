"""NapCat installation and management functionality."""

import os
import sys
import platform
import subprocess
import signal
import shutil
import tempfile
import zipfile
import uuid
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin
import requests
import tomllib
import tomli_w

from ..core.logger import get_logger

logger = get_logger(__name__)

# Constants
NAPCAT_ONEKEY_ZIP_URL = 'https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.Windows.OneKey.zip'
NAPCAT_ONEKEY_DIRNAME = 'NapCatQQ'


class NapCatManager:
    """Manages NapCat installation and runtime."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize NapCat manager.
        
        Args:
            config_path: Path to config.toml file. If None, uses default location.
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config.toml"
        self.config_path = config_path
        self.napcat_progress: Dict[str, Dict[str, Any]] = {}
        self.napcat_processes: Dict[str, subprocess.Popen] = {}
        self.napcat_running_process: Optional[subprocess.Popen] = None
        self.napcat_logs_buffer: List[str] = []
        self._lock = threading.Lock()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, 'rb') as f:
                return tomllib.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to TOML file."""
        try:
            # Use tomlkit to preserve comments and formatting
            import tomlkit
            
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    doc = tomlkit.load(f)
            else:
                doc = tomlkit.document()
            
            # Update config
            for key, value in config.items():
                doc[key] = value
            
            # Write back
            with open(self.config_path, 'w', encoding='utf-8') as f:
                tomlkit.dump(doc, f)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def _get_napcat_config(self) -> Dict[str, Any]:
        """Get napcat-specific config section."""
        config = self._load_config()
        return config.get('napcat', {})
    
    def _set_napcat_config(self, napcat_config: Dict[str, Any]) -> bool:
        """Set napcat-specific config section."""
        config = self._load_config()
        config['napcat'] = napcat_config
        return self._save_config(config)
    
    def detect_platform(self) -> str:
        """Detect the current platform."""
        if os.environ.get('TERMUX_VERSION') or 'com.termux' in (os.environ.get('PREFIX') or ''):
            return 'termux'
        sysname = platform.system().lower()
        if 'windows' in sysname:
            return 'windows'
        if 'darwin' in sysname:
            return 'macos'
        return 'linux'
    
    def is_admin(self) -> bool:
        """Check if running as administrator/root."""
        plat = self.detect_platform()
        if plat == 'windows':
            try:
                import ctypes
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                return False
        try:
            return os.geteuid() == 0
        except Exception:
            return False
    
    def has_sudo(self) -> bool:
        """Check if sudo command is available."""
        return bool(shutil.which('sudo'))
    
    def cmd_exists(self, name: str) -> bool:
        """Check if a command exists."""
        return bool(shutil.which(name))
    
    def napcat_recommended_bases(self) -> List[str]:
        """Get recommended NapCat installer base URLs."""
        return [
            'https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/',
            'https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/'
        ]
    
    def normalize_napcat_base(self, base: str) -> str:
        """Normalize and validate NapCat installer base URL."""
        base = str(base or '').strip()
        if not base:
            raise ValueError('Empty base')
        p = urlparse(base)
        if p.scheme != 'https':
            raise ValueError('Only https is allowed')
        if p.query or p.fragment:
            raise ValueError('Query/fragment not allowed')
        if not base.endswith('/'):
            base = base + '/'
        ok_suffixes = [
            '/NapNeko/NapCat-Installer/main/script/',
            '/NapNeko/NapCat-Installer/refs/heads/main/script/',
            '/NapNeko/NapCat-Installer/refs/heads/master/script/'
        ]
        if not any(base.endswith(s) for s in ok_suffixes):
            raise ValueError('Base must end with NapCat-Installer script path')
        return base
    
    def napcat_allowed_bases(self) -> List[str]:
        """Get all allowed NapCat installer bases."""
        napcat_config = self._get_napcat_config()
        bases = []
        for b in (napcat_config.get('installer_bases') or []):
            try:
                bases.append(self.normalize_napcat_base(b))
            except Exception:
                continue
        for b in self.napcat_recommended_bases():
            try:
                bases.append(self.normalize_napcat_base(b))
            except Exception:
                continue
        uniq = []
        seen = set()
        for b in bases:
            if b not in seen:
                uniq.append(b)
                seen.add(b)
        return uniq
    
    def napcat_installer_base(self) -> str:
        """Get the current NapCat installer base URL."""
        napcat_config = self._get_napcat_config()
        base = napcat_config.get('installer_base') or ''
        try:
            base = self.normalize_napcat_base(base) if base else ''
        except Exception:
            base = ''
        allowed = self.napcat_allowed_bases()
        if base and base in allowed:
            return base
        return allowed[0] if allowed else self.normalize_napcat_base(self.napcat_recommended_bases()[0])
    
    def assert_whitelisted_url(self, url: str) -> None:
        """Assert that a URL is whitelisted."""
        url = str(url or '').strip()
        if not url:
            raise ValueError('Empty url')
        p = urlparse(url)
        if p.scheme != 'https':
            raise ValueError('Only https is allowed')
        if url == NAPCAT_ONEKEY_ZIP_URL:
            return
        allowed_bases = self.napcat_allowed_bases()
        if not any(url.startswith(b) for b in allowed_bases):
            raise ValueError('Url not allowed')
    
    def download_to(self, url: str, dest: str) -> None:
        """Download a file from URL to destination."""
        self.assert_whitelisted_url(url)
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
    
    def download_to_atomic(self, url: str, dest: str) -> None:
        """Download a file atomically."""
        tmp = dest + '.tmp'
        self.download_to(url, tmp)
        os.replace(tmp, dest)
    
    def extract_zip_safe(self, zip_path: str, dest_dir: str) -> None:
        """Extract zip file safely."""
        dest_dir = os.path.abspath(dest_dir)
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                name = info.filename
                if not name or name.endswith('/'):
                    continue
                out_path = os.path.abspath(os.path.join(dest_dir, name))
                if not (out_path == dest_dir or out_path.startswith(dest_dir + os.sep)):
                    raise ValueError('Unsafe zip entry')
            zf.extractall(dest_dir)
    
    def job_log_append(self, job_id: str, line: str) -> None:
        """Append a log line to a job."""
        with self._lock:
            job = self.napcat_progress.get(job_id)
            if not job:
                return
            logs = job.get('logs')
            if not isinstance(logs, list):
                logs = []
                job['logs'] = logs
            logs.append(line)
            if len(logs) > 2000:
                del logs[:len(logs) - 2000]
    
    def job_set(self, job_id: str, **kwargs) -> None:
        """Set job properties."""
        with self._lock:
            job = self.napcat_progress.get(job_id)
            if not job:
                return
            job.update(kwargs)
    
    def job_is_canceled(self, job_id: str) -> bool:
        """Check if a job is canceled."""
        with self._lock:
            job = self.napcat_progress.get(job_id) or {}
            return job.get('status') == 'canceled'
    
    def find_first_file(self, root_dir: str, filename: str) -> Optional[str]:
        """Find first occurrence of a file in directory tree."""
        for root, dirs, files in os.walk(root_dir):
            if filename in files:
                return os.path.join(root, filename)
        return None
    
    def as_bool(self, v: Any, default: bool = False) -> bool:
        """Convert value to boolean."""
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ['1', 'true', 'yes', 'y', 'on']:
            return True
        if s in ['0', 'false', 'no', 'n', 'off']:
            return False
        return default
    
    def validate_payload(self, payload: Dict[str, Any], platform_name: str) -> Dict[str, Any]:
        """Validate deployment payload."""
        action = (payload.get('action') or 'auto').strip().lower()
        if action not in ['auto', 'script']:
            raise ValueError('Invalid action')
        
        docker = self.as_bool(payload.get('docker'), platform_name == 'docker')
        cli = self.as_bool(payload.get('cli'), False)
        force = self.as_bool(payload.get('force'), False)
        confirm = self.as_bool(payload.get('confirm'), True)
        
        qq = str(payload.get('qq') or '').strip()
        if docker and not qq.isdigit():
            raise ValueError('QQ is required for docker mode')
        
        mode = str(payload.get('mode') or 'ws').strip().lower()
        allowed_modes = ['ws', 'reverse_ws', 'reverse_http']
        if docker and mode not in allowed_modes:
            raise ValueError('Invalid mode')
        
        proxy = None
        if 'proxy' in payload and payload.get('proxy') is not None and str(payload.get('proxy')).strip() != '':
            try:
                proxy = int(payload.get('proxy'))
            except Exception:
                raise ValueError('Invalid proxy')
            if docker:
                if proxy < 0 or proxy > 7:
                    raise ValueError('Invalid proxy')
            else:
                if proxy < 0 or proxy > 5:
                    raise ValueError('Invalid proxy')
        
        use_sudo = self.as_bool(payload.get('use_sudo'), True)
        if platform_name in ['windows', 'termux']:
            use_sudo = False
        
        install_path = str(payload.get('install_path') or '').strip()
        
        return {
            'action': action,
            'docker': docker,
            'cli': cli,
            'force': force,
            'confirm': confirm,
            'qq': qq,
            'mode': mode,
            'proxy': proxy,
            'use_sudo': use_sudo,
            'install_path': install_path
        }
    
    def build_script_text(self, platform_name: str, params: Dict[str, Any]) -> str:
        """Build installation script text."""
        base = self.napcat_installer_base()
        install_sh = urljoin(base, 'install.sh')
        install_ps1 = urljoin(base, 'install.ps1')
        install_termux = urljoin(base, 'install.termux.sh')
        
        install_dir_cmd = ''
        if params.get('install_path'):
            path = params['install_path']
            if platform_name == 'windows':
                install_dir_cmd = f'mkdir "{path}" -Force; cd "{path}"; '
            else:
                install_dir_cmd = f'mkdir -p "{path}" && cd "{path}" && '
        
        if platform_name == 'windows':
            lines = []
            lines.append('powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference=\'Stop\'; $dir=Join-Path (Get-Location) \'' + NAPCAT_ONEKEY_DIRNAME + '\'; New-Item -ItemType Directory -Force -Path $dir | Out-Null; $zip=Join-Path $dir \'NapCat.Shell.Windows.OneKey.zip\'; Invoke-WebRequest -Uri \'' + NAPCAT_ONEKEY_ZIP_URL + '\' -OutFile $zip; Expand-Archive -Path $zip -DestinationPath $dir -Force; $exe=Join-Path $dir \'NapCatInstaller.exe\'; if (!(Test-Path $exe)) { throw \'NapCatInstaller.exe not found\' }; Start-Process -FilePath $exe -Verb RunAs -Wait"')
            return '\n'.join(lines)
        
        if platform_name == 'termux':
            return f'{install_dir_cmd}curl -o napcat.termux.sh {install_termux} && bash napcat.termux.sh'
        
        args = []
        args.extend(['--docker', 'y' if params['docker'] else 'n'])
        if params['docker']:
            args.extend(['--qq', f"\"{params['qq']}\""])
            args.extend(['--mode', params['mode']])
            if params.get('proxy') is not None and params['proxy'] > 0:
                args.extend(['--proxy', str(params['proxy'])])
            if params['confirm']:
                args.append('--confirm')
        else:
            args.extend(['--cli', 'y' if params['cli'] else 'n'])
            if params.get('proxy') is not None and params['proxy'] > 0:
                args.extend(['--proxy', str(params['proxy'])])
            if params['force']:
                args.append('--force')
        
        prefix = 'sudo ' if params.get('use_sudo') else ''
        return f'{install_dir_cmd}curl -o napcat.sh {install_sh} && {prefix}bash napcat.sh ' + ' '.join(args)
    
    def build_exec(self, platform_name: str, params: Dict[str, Any], workdir: str) -> List[str]:
        """Build execution command."""
        base = self.napcat_installer_base()
        if platform_name == 'windows':
            script_url = urljoin(base, 'install.ps1')
            script_path = os.path.join(workdir, 'install.ps1')
            self.download_to(script_url, script_path)
            ps = shutil.which('pwsh') or shutil.which('powershell') or 'powershell'
            return [ps, '-ExecutionPolicy', 'ByPass', '-File', script_path, '-verb', 'runas']
        
        if platform_name == 'termux':
            script_url = urljoin(base, 'install.termux.sh')
            script_path = os.path.join(workdir, 'install.termux.sh')
            self.download_to(script_url, script_path)
            return ['bash', script_path]
        
        script_url = urljoin(base, 'install.sh')
        script_path = os.path.join(workdir, 'install.sh')
        self.download_to(script_url, script_path)
        os.chmod(script_path, 0o755)
        
        args = []
        args.extend(['--docker', 'y' if params['docker'] else 'n'])
        if params['docker']:
            args.extend(['--qq', params['qq']])
            args.extend(['--mode', params['mode']])
            if params.get('proxy') is not None and params['proxy'] > 0:
                args.extend(['--proxy', str(params['proxy'])])
            if params['confirm']:
                args.append('--confirm')
        else:
            args.extend(['--cli', 'y' if params['cli'] else 'n'])
            if params.get('proxy') is not None and params['proxy'] > 0:
                args.extend(['--proxy', str(params['proxy'])])
            if params['force']:
                args.append('--force')
        
        if params.get('use_sudo') and not self.is_admin() and self.has_sudo():
            return ['sudo', 'bash', script_path, *args]
        return ['bash', script_path, *args]
    
    def run_job_windows_onekey(self, job_id: str, params: Dict[str, Any]) -> None:
        """Run Windows one-key installation job."""
        project_root = Path(__file__).parent.parent.parent
        base_dir = os.path.abspath(os.path.join(project_root, NAPCAT_ONEKEY_DIRNAME))
        ts = time.strftime('%Y%m%d%H%M%S')
        if os.path.exists(base_dir) and os.listdir(base_dir):
            try:
                os.replace(base_dir, base_dir + '.bak-' + ts)
            except Exception:
                shutil.rmtree(base_dir, ignore_errors=True)
        os.makedirs(base_dir, exist_ok=True)
        
        zip_path = os.path.join(base_dir, 'NapCat.Shell.Windows.OneKey.zip')
        self.job_set(job_id, status='downloading', percent=15, message='Downloading OneKey zip...')
        self.job_log_append(job_id, f'[download] {NAPCAT_ONEKEY_ZIP_URL}')
        self.job_log_append(job_id, f'[download] -> {zip_path}')
        self.download_to_atomic(NAPCAT_ONEKEY_ZIP_URL, zip_path)
        if self.job_is_canceled(job_id):
            return
        
        self.job_set(job_id, status='extracting', percent=30, message='Extracting OneKey zip...')
        self.extract_zip_safe(zip_path, base_dir)
        if self.job_is_canceled(job_id):
            return
        
        exe_path = self.find_first_file(base_dir, 'NapCatInstaller.exe')
        if not exe_path or not os.path.exists(exe_path):
            raise ValueError('NapCatInstaller.exe not found after extract')
        
        self.job_set(job_id, status='running', percent=55, message='Running NapCatInstaller.exe...')
        ps = shutil.which('pwsh') or shutil.which('powershell') or 'powershell'
        cmd = [ps, '-NoProfile', '-ExecutionPolicy', 'ByPass', '-Command', f'Start-Process -FilePath "{exe_path}" -Verb RunAs -Wait']
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(exe_path),
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        with self._lock:
            self.napcat_processes[job_id] = proc
        for line in proc.stdout:
            self.job_log_append(job_id, line.rstrip('\n'))
        rc = proc.wait()
        with self._lock:
            self.napcat_processes.pop(job_id, None)
        if rc != 0:
            raise ValueError(f'NapCatInstaller.exe exited with code {rc}')
        
        if self.job_is_canceled(job_id):
            return
        
        install_dir = None
        for c in ['napcat.bat', 'launcher.bat', 'launcher-win10.bat', 'NapCatWinBootMain.exe']:
            p = self.find_first_file(base_dir, c)
            if p:
                install_dir = os.path.dirname(p)
                break
        if not install_dir:
            install_dir = base_dir
        self.job_log_append(job_id, f'[install_path] {install_dir}')
        
        napcat_config = self._get_napcat_config()
        napcat_config['install_path'] = install_dir
        self._set_napcat_config(napcat_config)
        self.job_set(job_id, status='done', percent=100, message='Done')
    
    def run_job(self, job_id: str, platform_name: str, params: Dict[str, Any]) -> None:
        """Run installation job."""
        self.job_set(job_id, status='preparing', percent=5, message='Preparing...')
        try:
            if platform_name == 'windows':
                self.run_job_windows_onekey(job_id, params)
                return
            
            install_path = params.get('install_path')
            temp_dir = None
            workdir = ''
            
            if install_path:
                try:
                    os.makedirs(install_path, exist_ok=True)
                    workdir = install_path
                except Exception as e:
                    self.job_set(job_id, status='error', percent=100, message=f'Failed to create directory: {e}')
                    return
            else:
                temp_dir = tempfile.TemporaryDirectory(prefix='napcat-')
                workdir = temp_dir.name
            
            try:
                self.job_set(job_id, status='downloading', percent=15, message='Downloading installer...')
                cmd = self.build_exec(platform_name, params, workdir)
                self.job_set(job_id, status='running', percent=30, message='Running installer...')
                
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=workdir,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                with self._lock:
                    self.napcat_processes[job_id] = proc
                
                for line in proc.stdout:
                    self.job_log_append(job_id, line.rstrip('\n'))
                
                rc = proc.wait()
                with self._lock:
                    self.napcat_processes.pop(job_id, None)
                if rc == 0:
                    self.job_set(job_id, status='done', percent=100, message='Done')
                    # Save install path to config if successful
                    if install_path:
                        napcat_config = self._get_napcat_config()
                        napcat_config['install_path'] = install_path
                        self._set_napcat_config(napcat_config)
                else:
                    self.job_set(job_id, status='error', percent=100, message=f'Failed with code {rc}')
            finally:
                if temp_dir:
                    temp_dir.cleanup()
        
        except Exception as e:
            with self._lock:
                self.napcat_processes.pop(job_id, None)
            self.job_set(job_id, status='error', percent=100, message=str(e))
    
    def terminate_process(self, proc: subprocess.Popen) -> bool:
        """Terminate a process gracefully."""
        if not proc:
            return True
        if proc.poll() is not None:
            return True
        
        plat = self.detect_platform()
        if plat == 'windows':
            try:
                subprocess.run(
                    ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            return proc.poll() is not None
        
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
        return proc.poll() is not None
    
    def napcat_log_reader(self, proc: subprocess.Popen) -> None:
        """Read logs from NapCat process."""
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                with self._lock:
                    self.napcat_logs_buffer.append(line)
                    if len(self.napcat_logs_buffer) > 2000:
                        self.napcat_logs_buffer.pop(0)
        except Exception:
            pass

    def _docker_inspect_container(self, name: str) -> Optional[Dict[str, Any]]:
        """Inspect a docker container and return basic status."""
        if not name or not self.cmd_exists('docker'):
            return None
        try:
            res = subprocess.run(
                [
                    'docker', 'inspect',
                    '--format', '{{.Name}}|{{.State.Running}}',
                    name
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5,
                check=False
            )
            if res.returncode != 0:
                return None
            out = (res.stdout or '').strip()
            if not out:
                return None
            parts = out.split('|')
            cname = parts[0].lstrip('/') if parts else name
            running = (parts[1].strip().lower() == 'true') if len(parts) > 1 else False
            return {'name': cname, 'running': running}
        except Exception:
            return None

    def _detect_napcat_docker_container(self) -> Optional[Dict[str, Any]]:
        """Auto-detect an existing docker container that looks like napcat."""
        if not self.cmd_exists('docker'):
            return None
        try:
            res = subprocess.run(
                ['docker', 'ps', '-a', '--format', '{{.Names}}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5,
                check=False
            )
            if res.returncode != 0:
                return None
            names = [n.strip() for n in (res.stdout or '').splitlines() if n.strip()]
            if not names:
                return None
            candidates = [n for n in names if 'napcat' in n.lower()]
            if not candidates:
                return None
            # Prefer exact "napcat", then shorter names.
            candidates.sort(key=lambda n: (0 if n.lower() == 'napcat' else 1, len(n)))
            info = self._docker_inspect_container(candidates[0])
            if info:
                return info
            return {'name': candidates[0], 'running': False}
        except Exception:
            return None

    def _get_docker_container(self) -> Optional[Dict[str, Any]]:
        """Get configured docker container or auto-detect one."""
        napcat_config = self._get_napcat_config()
        configured = str(napcat_config.get('docker_container') or '').strip()
        if configured:
            info = self._docker_inspect_container(configured)
            if info:
                return info
        return self._detect_napcat_docker_container()

    def list_docker_containers(self) -> List[Dict[str, Any]]:
        """List docker containers with napcat-like candidates first."""
        if not self.cmd_exists('docker'):
            return []
        try:
            res = subprocess.run(
                ['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Image}}|{{.Status}}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=6,
                check=False
            )
            if res.returncode != 0:
                return []
            rows = [r.strip() for r in (res.stdout or '').splitlines() if r.strip()]
            items: List[Dict[str, Any]] = []
            for row in rows:
                parts = row.split('|')
                name = parts[0].strip() if len(parts) > 0 else ''
                image = parts[1].strip() if len(parts) > 1 else ''
                status = parts[2].strip() if len(parts) > 2 else ''
                if not name:
                    continue
                running = status.lower().startswith('up')
                is_napcat = ('napcat' in name.lower()) or ('napcat' in image.lower())
                items.append({
                    'name': name,
                    'image': image,
                    'status': status,
                    'running': running,
                    'is_napcat': is_napcat
                })
            items.sort(key=lambda x: (0 if x.get('is_napcat') else 1, 0 if x.get('running') else 1, x.get('name', '')))
            return items
        except Exception:
            return []
    
    def get_status(self) -> Dict[str, Any]:
        """Get NapCat status."""
        running = False
        if self.napcat_running_process and self.napcat_running_process.poll() is None:
            running = True
        
        napcat_config = self._get_napcat_config()
        install_path = napcat_config.get('install_path', '')

        # Auto-detect docker napcat container when no local install path configured.
        if not install_path:
            docker_info = self._get_docker_container()
            if docker_info:
                return {
                    'running': running or bool(docker_info.get('running')),
                    'install_path': f"docker://{docker_info.get('name', '')}",
                    'docker_container': docker_info.get('name', '')
                }

        return {'running': running, 'install_path': install_path}
    
    def start_napcat(self) -> Dict[str, Any]:
        """Start NapCat process."""
        if self.napcat_running_process and self.napcat_running_process.poll() is None:
            return {'ok': False, 'error': 'Already running'}
        
        napcat_config = self._get_napcat_config()
        install_path = napcat_config.get('install_path')
        if not install_path or not os.path.exists(install_path):
            # Fallback: manage docker container if an existing napcat container is found.
            docker_info = self._get_docker_container()
            if docker_info:
                container = docker_info.get('name')
                if docker_info.get('running'):
                    return {'ok': True, 'message': f'Docker container {container} already running'}
                try:
                    res = subprocess.run(
                        ['docker', 'start', container],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=15,
                        check=False
                    )
                    if res.returncode != 0:
                        return {'ok': False, 'error': (res.stdout or '').strip() or f'Failed to start docker container {container}'}
                    napcat_config['docker_container'] = container
                    self._set_napcat_config(napcat_config)
                    return {'ok': True}
                except Exception as e:
                    return {'ok': False, 'error': str(e)}
            return {'ok': False, 'error': 'Install path not configured or not found'}
        
        plat = self.detect_platform()
        cmd = []
        if plat == 'windows':
            cmd_path = None
            candidates = ['napcat.bat', 'launcher.bat', 'launcher-win10.bat', 'NapCatWinBootMain.exe']
            
            for c in candidates:
                p = os.path.join(install_path, c)
                if os.path.exists(p):
                    cmd_path = p
                    break
            
            if not cmd_path:
                for root, dirs, files in os.walk(install_path):
                    for c in candidates:
                        if c in files:
                            cmd_path = os.path.join(root, c)
                            break
                    if cmd_path:
                        break
            
            if not cmd_path:
                return {'ok': False, 'error': 'NapCat startup script or NapCatWinBootMain.exe not found'}
            
            startup_cwd = os.path.dirname(cmd_path)
            cmd = [cmd_path]
        else:
            qq_bin = os.path.join(install_path, 'opt', 'QQ', 'qq')
            if not os.path.exists(qq_bin):
                return {'ok': False, 'error': f'QQ binary not found at {qq_bin}'}
            cmd = ['xvfb-run', '-a', qq_bin, '--no-sandbox']
            startup_cwd = os.path.dirname(qq_bin)
        
        try:
            with self._lock:
                self.napcat_logs_buffer = []
            
            if plat == 'windows' and cmd[0].endswith('.bat'):
                cmd = ['cmd', '/c', cmd[0]]
            
            popen_kwargs = {}
            if plat == 'windows':
                try:
                    popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
                except Exception:
                    pass
            else:
                popen_kwargs['start_new_session'] = True
            
            self.napcat_running_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=startup_cwd,
                text=True,
                encoding='utf-8',
                errors='replace',
                **popen_kwargs
            )
            
            t = threading.Thread(target=self.napcat_log_reader, args=(self.napcat_running_process,), daemon=True)
            t.start()
            
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}
    
    def stop_napcat(self) -> Dict[str, Any]:
        """Stop NapCat process."""
        if not self.napcat_running_process:
            # Fallback for docker-managed napcat
            docker_info = self._get_docker_container()
            if docker_info and docker_info.get('running'):
                container = docker_info.get('name')
                try:
                    res = subprocess.run(
                        ['docker', 'stop', container],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=20,
                        check=False
                    )
                    if res.returncode != 0:
                        return {'ok': False, 'error': (res.stdout or '').strip() or f'Failed to stop docker container {container}'}
                    return {'ok': True}
                except Exception as e:
                    return {'ok': False, 'error': str(e)}
            return {'ok': False, 'error': 'Not running'}
        if self.napcat_running_process.poll() is not None:
            self.napcat_running_process = None
            return {'ok': False, 'error': 'Not running'}
        
        ok = self.terminate_process(self.napcat_running_process)
        if ok:
            self.napcat_running_process = None
            return {'ok': True}
        return {'ok': False, 'error': 'Failed to stop'}
    
    def get_logs(self) -> List[str]:
        """Get NapCat logs."""
        with self._lock:
            logs = list(self.napcat_logs_buffer)
        if logs:
            return logs

        # Fallback to docker logs when not started via this process.
        docker_info = self._get_docker_container()
        if not docker_info:
            return logs
        container = docker_info.get('name')
        if not container:
            return logs
        try:
            res = subprocess.run(
                ['docker', 'logs', '--tail', '200', container],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10,
                check=False
            )
            if res.returncode != 0 and not (res.stdout or '').strip():
                return logs
            return (res.stdout or '').splitlines()
        except Exception:
            return logs
    
    def get_webui_info(self) -> Dict[str, Any]:
        """Get NapCat WebUI information."""
        napcat_config = self._get_napcat_config()
        install_path = napcat_config.get('install_path')
        
        if not install_path or not os.path.exists(install_path):
            # Fallback: try docker port mapping (default napcat webui 6099/tcp).
            docker_info = self._get_docker_container()
            if docker_info:
                container = docker_info.get('name')
                try:
                    res = subprocess.run(
                        ['docker', 'port', container, '6099/tcp'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=5,
                        check=False
                    )
                    if res.returncode == 0 and (res.stdout or '').strip():
                        mapped = (res.stdout or '').strip().splitlines()[0]
                        # e.g. "0.0.0.0:32768"
                        host, port = ('127.0.0.1', '6099')
                        if ':' in mapped:
                            host, port = mapped.rsplit(':', 1)
                            host = host.strip() or '127.0.0.1'
                            if host in ['0.0.0.0', '::']:
                                host = '127.0.0.1'
                        url = f"http://{host}:{port}/webui"
                        return {'ok': True, 'url': url, 'token': '', 'port': int(port)}
                except Exception:
                    pass
            return {'ok': False, 'error': 'Install path not found'}
        
        # Try to find webui.json
        candidates = [
            os.path.join(install_path, 'config', 'webui.json'),
            os.path.join(install_path, 'NapCat', 'config', 'webui.json')
        ]
        
        # Also search recursively if not found immediately
        if not any(os.path.exists(p) for p in candidates):
            for root, dirs, files in os.walk(install_path):
                if 'webui.json' in files:
                    candidates.append(os.path.join(root, 'webui.json'))
                    break
        
        webui_config = None
        for p in candidates:
            if os.path.exists(p):
                try:
                    import json
                    with open(p, 'r', encoding='utf-8') as f:
                        webui_config = json.load(f)
                    break
                except Exception:
                    continue
        
        if not webui_config:
            return {'ok': False, 'error': 'webui.json not found'}
        
        port = webui_config.get('port', 6099)
        token = webui_config.get('token', '')
        host = str(webui_config.get('host') or '').strip() or '127.0.0.1'
        
        if host in ['0.0.0.0', '::', '127.0.0.1', 'localhost', '']:
            host = '127.0.0.1'
        
        url = f"http://{host}:{port}/webui?token={token}"
        return {'ok': True, 'url': url, 'token': token, 'port': port}
    
    def set_install_path(self, path: str) -> Dict[str, Any]:
        """Set NapCat installation path."""
        if not path:
            return {'ok': False, 'error': 'No path provided'}

        # Allow explicit docker target like docker://napcat
        if str(path).lower().startswith('docker://'):
            container = str(path)[9:].strip()
            if not container:
                return {'ok': False, 'error': 'Invalid docker container path'}
            info = self._docker_inspect_container(container)
            if not info:
                return {'ok': False, 'error': f'Docker container not found: {container}'}
            napcat_config = self._get_napcat_config()
            napcat_config['docker_container'] = info.get('name', container)
            napcat_config['install_path'] = ''
            self._set_napcat_config(napcat_config)
            return {'ok': True}
        
        if not os.path.exists(path):
            return {'ok': False, 'error': 'Path does not exist'}
        
        # Verify it looks like a NapCat installation
        checks = ['napcat.bat', 'launcher.bat', 'launcher-win10.bat', 'napcat.sh', 
                  'launcher.sh', 'NapCatWinBootMain.exe', 'config', 'NapCat']
        is_valid = any(os.path.exists(os.path.join(path, c)) for c in checks)
        
        if not is_valid:
            return {'ok': False, 'error': 'Path does not appear to be a valid NapCat installation'}
        
        napcat_config = self._get_napcat_config()
        napcat_config['install_path'] = path
        self._set_napcat_config(napcat_config)
        
        return {'ok': True}


# Global instance
_napcat_manager: Optional[NapCatManager] = None


def get_napcat_manager() -> NapCatManager:
    """Get global NapCat manager instance."""
    global _napcat_manager
    if _napcat_manager is None:
        _napcat_manager = NapCatManager()
    return _napcat_manager
          
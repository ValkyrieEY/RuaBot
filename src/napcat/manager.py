"""Minimal framework-managed NapCat installer and process manager."""

from __future__ import annotations

import json
import os
import platform
import re
import signal
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

from ..core.config import get_runtime_base_dir
from ..core.logger import get_logger

logger = get_logger(__name__)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

WINDOWS_ONEKEY_URL = (
    "https://github.com/NapNeko/NapCatQQ/releases/latest/download/"
    "NapCat.Shell.Windows.OneKey.zip"
)
LINUX_INSTALL_SCRIPT_URL = (
    "https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.sh"
)


class NapCatManager:
    """Owns one NapCat instance under the current framework runtime directory."""

    def __init__(self) -> None:
        self.base_dir = (get_runtime_base_dir() / "napcat").resolve()
        self.work_dir = self.base_dir / "workdir"
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._process: Optional[subprocess.Popen] = None
        self._logs: List[str] = []

    def _detect_platform(self) -> str:
        system = platform.system().lower()
        if "windows" in system:
            return "windows"
        if "linux" in system:
            return "linux"
        return system or "unknown"

    def _append_runtime_log(self, line: str) -> None:
        line = self._normalize_log_line(line)
        with self._lock:
            self._logs.append(line.rstrip("\n"))
            if len(self._logs) > 4000:
                del self._logs[: len(self._logs) - 4000]

    def _append_job_log(self, job_id: str, line: str) -> None:
        line = self._normalize_log_line(line)
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            logs = job.setdefault("logs", [])
            logs.append(line.rstrip("\n"))
            if len(logs) > 4000:
                del logs[: len(logs) - 4000]

    def _set_job(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.update(kwargs)

    def create_install_job(self) -> Dict[str, Any]:
        job_id = f"napcat-{int(time.time() * 1000)}"
        platform_name = self._detect_platform()
        job = {
            "job_id": job_id,
            "status": "queued",
            "percent": 0,
            "message": "Queued",
            "platform": platform_name,
            "logs": [],
            "created_at": int(time.time()),
        }
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._copy_job(job) if job else None

    def get_active_install_job(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            for job in self._jobs.values():
                if job.get("status") in {"queued", "running"}:
                    return self._copy_job(job)
        return None

    def _copy_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        copied = dict(job)
        copied["logs"] = list(job.get("logs", []))
        return copied

    def get_status(self) -> Dict[str, Any]:
        running = self._process is not None and self._process.poll() is None
        return {
            "installed": self.is_installed(),
            "running": running,
            "platform": self._detect_platform(),
            "install_path": str(self.base_dir),
            "workdir": str(self.work_dir),
            "entry": str(self._find_start_entry() or ""),
            "webui": self.get_webui_info(),
        }

    def get_logs(self) -> Dict[str, Any]:
        with self._lock:
            return {"logs": list(self._logs)}

    def get_qrcode_path(self) -> Path:
        return self.work_dir / "cache" / "qrcode.png"

    def get_qrcode_info(self) -> Dict[str, Any]:
        qrcode_path = self.get_qrcode_path()
        if not qrcode_path.exists() or not qrcode_path.is_file():
            return {
                "exists": False,
                "path": str(qrcode_path),
                "mtime": 0,
                "size": 0,
                "version": "",
            }
        stat = qrcode_path.stat()
        mtime = int(stat.st_mtime)
        size = int(stat.st_size)
        return {
            "exists": True,
            "path": str(qrcode_path),
            "mtime": mtime,
            "size": size,
            "version": f"{mtime}-{size}",
        }

    def get_config_center(self) -> Dict[str, Any]:
        config_dir = self.work_dir / "config"
        return {
            "config_dir": str(config_dir),
            "webui_path": str(config_dir / "webui.json"),
            "napcat_path": str(config_dir / "napcat.json"),
            "onebot_path": str(config_dir / "onebot11.json"),
            "webui": self._read_json_config(config_dir / "webui.json", self._default_webui_config()),
            "napcat": self._read_json_config(config_dir / "napcat.json", self._default_napcat_config()),
            "onebot": self._read_json_config(config_dir / "onebot11.json", self._default_onebot_config()),
        }

    def save_config_center(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config_dir = self.work_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        allowed = {
            "webui": config_dir / "webui.json",
            "napcat": config_dir / "napcat.json",
            "onebot": config_dir / "onebot11.json",
        }
        saved: List[str] = []
        for key, path in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if not isinstance(value, dict):
                raise ValueError(f"{key} config must be an object")
            self._write_json_config(path, value)
            saved.append(key)
        return {"ok": True, "saved": saved, **self.get_config_center()}

    def apply_framework_onebot_config(self, framework_config: Any) -> Dict[str, Any]:
        config = self._build_onebot_config_from_framework(framework_config)
        onebot_path = self.work_dir / "config" / "onebot11.json"
        self._write_json_config(onebot_path, config)
        self._append_runtime_log(f"Framework OneBot config written to {onebot_path}")
        return {
            "ok": True,
            "path": str(onebot_path),
            "onebot": config,
            "restart_required": True,
            "message": "NapCat OneBot 配置已写入，重启 NapCat 后生效",
        }

    def _read_json_config(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**default, **data}
        except Exception:
            pass
        return default

    def _write_json_config(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _default_webui_config(self) -> Dict[str, Any]:
        return {
            "host": "::",
            "port": 6099,
            "token": "",
            "loginRate": 10,
            "autoLoginAccount": "",
            "disableWebUI": False,
            "accessControlMode": "none",
            "ipWhitelist": [],
            "ipBlacklist": [],
            "enableXForwardedFor": False,
        }

    def _default_napcat_config(self) -> Dict[str, Any]:
        return {
            "fileLog": False,
            "consoleLog": True,
            "fileLogLevel": "debug",
            "consoleLogLevel": "info",
            "packetBackend": "auto",
            "packetServer": "",
            "o3HookMode": 0,
            "autoTimeSync": True,
            "bypass": {
                "hook": True,
                "window": True,
                "module": True,
                "process": True,
                "container": True,
                "js": True,
            },
        }

    def _default_onebot_config(self) -> Dict[str, Any]:
        return {
            "network": {
                "httpServers": [],
                "httpSseServers": [],
                "httpClients": [],
                "websocketServers": [],
                "websocketClients": [],
                "plugins": [],
            },
            "musicSignUrl": "",
            "enableLocalFile2Url": False,
            "parseMultMsg": False,
            "imageDownloadProxy": "",
            "timeout": {
                "baseTimeout": 10000,
                "uploadSpeedKBps": 256,
                "downloadSpeedKBps": 256,
                "maxTimeout": 1800000,
            },
        }

    def _build_onebot_config_from_framework(self, framework_config: Any) -> Dict[str, Any]:
        onebot = self._default_onebot_config()
        network = onebot["network"]
        connection_type = getattr(framework_config, "onebot_connection_type", "ws_reverse")
        token = getattr(framework_config, "onebot_access_token", "")

        if connection_type in {"ws", "ws_forward"}:
            parsed = urlparse(getattr(framework_config, "onebot_ws_url", "ws://127.0.0.1:3001"))
            network["websocketServers"] = [{
                "name": "xqnext-ws-server",
                "enable": True,
                "host": self._bind_host_from_url(parsed.hostname),
                "port": parsed.port or 3001,
                "messagePostFormat": "array",
                "reportSelfMessage": False,
                "token": token,
                "enableForcePushEvent": True,
                "debug": False,
                "heartInterval": 30000,
            }]
        elif connection_type == "ws_reverse":
            host = getattr(framework_config, "onebot_ws_reverse_host", "127.0.0.1")
            port = getattr(framework_config, "onebot_ws_reverse_port", 8080)
            path = getattr(framework_config, "onebot_ws_reverse_path", "/onebot/v11/ws")
            if host in {"0.0.0.0", "::", ""}:
                host = "127.0.0.1"
            network["websocketClients"] = [{
                "name": "xqnext-ws-client",
                "enable": True,
                "url": f"ws://{host}:{port}{path}",
                "messagePostFormat": "array",
                "reportSelfMessage": False,
                "reconnectInterval": 5000,
                "token": token,
                "debug": False,
                "heartInterval": 30000,
            }]
        elif connection_type == "http":
            parsed = urlparse(getattr(framework_config, "onebot_http_url", "http://127.0.0.1:5700"))
            network["httpServers"] = [{
                "name": "xqnext-http-server",
                "enable": True,
                "host": self._bind_host_from_url(parsed.hostname),
                "port": parsed.port or 5700,
                "enableCors": True,
                "enableWebsocket": False,
                "messagePostFormat": "array",
                "token": token,
                "debug": False,
            }]
        else:
            raise ValueError(f"Unsupported framework OneBot connection type: {connection_type}")
        return onebot

    def _bind_host_from_url(self, host: Optional[str]) -> str:
        if not host or host in {"localhost", "127.0.0.1", "::1"}:
            return "127.0.0.1"
        return "0.0.0.0"

    def is_installed(self) -> bool:
        return self._find_start_entry() is not None

    def install(self, job_id: str) -> None:
        platform_name = self._detect_platform()
        self._set_job(
            job_id,
            status="running",
            percent=5,
            message=f"Installing NapCat for {platform_name}",
        )
        self._append_job_log(job_id, f"Install path: {self.base_dir}")
        self._append_job_log(job_id, f"Work dir: {self.work_dir}")

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.work_dir.mkdir(parents=True, exist_ok=True)

            if platform_name == "windows":
                self._install_windows(job_id)
            elif platform_name == "linux":
                self._install_linux(job_id)
            else:
                raise RuntimeError(f"Unsupported platform: {platform_name}")

            if not self.is_installed():
                raise RuntimeError("Install finished but NapCat startup entry was not found")

            self._set_job(job_id, status="done", percent=100, message="Done")
            self._append_job_log(job_id, "NapCat install completed")
        except Exception as exc:
            logger.error("NapCat install failed: %s", exc, exc_info=True)
            self._append_job_log(job_id, f"ERROR: {exc}")
            self._set_job(job_id, status="error", percent=100, message=str(exc))

    def _install_windows(self, job_id: str) -> None:
        zip_path = self.base_dir / "NapCat.Shell.Windows.OneKey.zip"
        self._set_job(job_id, percent=15, message="Downloading Windows OneKey package")
        self._download_file(job_id, WINDOWS_ONEKEY_URL, zip_path)

        self._set_job(job_id, percent=45, message="Extracting OneKey package")
        self._extract_zip(job_id, zip_path, self.base_dir)

        installer = self._find_file("NapCatInstaller.exe")
        if not installer:
            raise RuntimeError("NapCatInstaller.exe not found after extraction")

        self._set_job(job_id, percent=60, message="Running NapCatInstaller.exe")
        self._append_job_log(job_id, f"Running: {installer}")
        self._run_process_for_job(
            job_id,
            [str(installer)],
            cwd=installer.parent,
            timeout=60 * 40,
        )
        self._set_job(job_id, percent=90, message="Checking startup entry")

    def _install_linux(self, job_id: str) -> None:
        script_path = self.base_dir / "napcat.sh"
        self._set_job(job_id, percent=15, message="Downloading Linux install script")
        self._download_file(job_id, LINUX_INSTALL_SCRIPT_URL, script_path)
        self._pin_linux_install_dir(job_id, script_path)
        try:
            script_path.chmod(script_path.stat().st_mode | 0o755)
        except Exception:
            pass

        self._set_job(job_id, percent=45, message="Running Linux Shell installer")
        self._run_process_for_job(
            job_id,
            ["bash", str(script_path), "--docker", "n", "--cli", "n", "--proxy", "0", "--force"],
            cwd=self.base_dir,
            timeout=60 * 60,
        )
        self._write_linux_launcher(job_id)
        self._set_job(job_id, percent=90, message="Checking startup entry")

    def _download_file(self, job_id: str, url: str, target: Path) -> None:
        tmp = target.with_suffix(target.suffix + ".part")
        if tmp.exists():
            tmp.unlink()

        self._append_job_log(job_id, f"Downloading: {url}")
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            downloaded = 0
            last_log_at = 0.0
            with open(tmp, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if not chunk:
                        continue
                    file.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if total and now - last_log_at > 1:
                        percent = min(44, 15 + int(downloaded / total * 25))
                        self._set_job(job_id, percent=percent)
                        self._append_job_log(
                            job_id,
                            f"Downloaded {downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB",
                        )
                        last_log_at = now

        actual_size = tmp.stat().st_size
        if total and actual_size != total:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"Downloaded file is incomplete: {actual_size} bytes, expected {total} bytes"
            )
        tmp.replace(target)
        self._append_job_log(job_id, f"Downloaded file: {target} ({actual_size} bytes)")

    def _extract_zip(self, job_id: str, zip_path: Path, target_dir: Path) -> None:
        with zipfile.ZipFile(zip_path, "r") as archive:
            broken = archive.testzip()
            if broken:
                raise RuntimeError(f"Zip validation failed at {broken}")
            archive.extractall(target_dir)
        self._append_job_log(job_id, f"Extracted: {zip_path}")

    def _pin_linux_install_dir(self, job_id: str, script_path: Path) -> None:
        linux_root = self.base_dir / "linux-root"
        content = script_path.read_text(encoding="utf-8", errors="replace")
        old = 'INSTALL_BASE_DIR="$HOME/Napcat"'
        new = f'INSTALL_BASE_DIR="{self._shell_quote_path(linux_root)}"'
        if old not in content:
            raise RuntimeError("Linux installer layout changed: INSTALL_BASE_DIR was not found")
        script_path.write_text(content.replace(old, new, 1), encoding="utf-8")
        self._append_job_log(job_id, f"Linux install root pinned to: {linux_root}")

    def _write_linux_launcher(self, job_id: str) -> None:
        qq_executable = self.base_dir / "linux-root" / "opt" / "QQ" / "qq"
        if not qq_executable.exists():
            raise RuntimeError(f"Linux QQ executable not found: {qq_executable}")

        launcher = self.base_dir / "start-napcat.sh"
        launcher.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -e",
                    f'export NAPCAT_WORKDIR="{self._shell_quote_path(self.work_dir)}"',
                    f'exec xvfb-run -a "{self._shell_quote_path(qq_executable)}" --no-sandbox "$@"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        try:
            launcher.chmod(launcher.stat().st_mode | 0o755)
        except Exception:
            pass
        self._append_job_log(job_id, f"Linux launcher created: {launcher}")

    def _shell_quote_path(self, path: Path) -> str:
        return str(path).replace("\\", "\\\\").replace('"', '\\"')

    def _run_process_for_job(
        self,
        job_id: str,
        command: List[str],
        cwd: Path,
        timeout: int,
    ) -> None:
        env = self._build_env()
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding=self._console_encoding(),
            errors="replace",
            env=env,
        )
        started = time.time()
        assert process.stdout is not None
        for line in process.stdout:
            self._append_job_log(job_id, line.rstrip("\n"))
            if time.time() - started > timeout:
                self._terminate_process(process)
                raise RuntimeError("Process timed out")
        return_code = process.wait(timeout=5)
        if return_code != 0:
            raise RuntimeError(f"Process exited with code {return_code}")

    def start(self) -> Dict[str, Any]:
        if self._process and self._process.poll() is None:
            return {"ok": True, "already_running": True}

        entry = self._find_start_entry()
        if not entry:
            return {"ok": False, "error": "NapCat is not installed"}

        with self._lock:
            self._logs = []

        command = self._build_start_command(entry)
        cwd = entry.parent
        self._append_runtime_log(f"Starting NapCat: {' '.join(command)}")
        self._append_runtime_log(f"Working directory: {cwd}")
        self._append_runtime_log(f"NAPCAT_WORKDIR={self.work_dir}")

        creationflags = 0
        start_new_session = False
        if platform.system().lower().startswith("windows"):
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            start_new_session = True

        self._process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding=self._console_encoding(),
            errors="replace",
            env=self._build_env(),
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
        thread = threading.Thread(target=self._read_runtime_output, args=(self._process,), daemon=True)
        thread.start()
        return {"ok": True}

    def stop(self) -> Dict[str, Any]:
        if not self._process or self._process.poll() is not None:
            self._process = None
            return {"ok": True, "already_stopped": True}
        self._terminate_process(self._process)
        self._process = None
        self._append_runtime_log("NapCat stopped")
        return {"ok": True}

    def _read_runtime_output(self, process: subprocess.Popen) -> None:
        try:
            assert process.stdout is not None
            for line in process.stdout:
                self._append_runtime_log(line.rstrip("\n"))
        except Exception as exc:
            self._append_runtime_log(f"Runtime log reader error: {exc}")
        finally:
            code = process.poll()
            if code is not None:
                self._append_runtime_log(f"NapCat process exited with code {code}")

    def _terminate_process(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if platform.system().lower().startswith("windows"):
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except Exception:
                    process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["NAPCAT_WORKDIR"] = str(self.work_dir)
        return env

    def _console_encoding(self) -> str:
        return "utf-8"

    def _normalize_log_line(self, line: str) -> str:
        return ANSI_ESCAPE_RE.sub("", line).rstrip("\n")

    def _build_start_command(self, entry: Path) -> List[str]:
        lower_name = entry.name.lower()
        if lower_name.endswith(".bat") or lower_name.endswith(".cmd"):
            return ["cmd", "/c", str(entry)]
        if lower_name.endswith(".sh"):
            return ["bash", str(entry)]
        return [str(entry)]

    def _find_start_entry(self) -> Optional[Path]:
        if not self.base_dir.exists():
            return None
        windows_shell_entry = self._find_windows_shell_entry()
        if windows_shell_entry:
            return windows_shell_entry

        linux_entry = self.base_dir / "start-napcat.sh"
        if linux_entry.exists():
            return linux_entry

        preferred_names = [
            "launcher.bat",
            "launcher-win10.bat",
            "launcher.sh",
        ]
        for name in preferred_names:
            found = self._find_file(name)
            if found:
                return found
        return None

    def _find_windows_shell_entry(self) -> Optional[Path]:
        candidates: List[Path] = []
        for child in self.base_dir.iterdir():
            if not child.is_dir():
                continue
            lower_name = child.name.lower()
            if lower_name.startswith("napcat.") and lower_name.endswith(".shell"):
                entry = child / "napcat.bat"
                qq_executable = child / "QQ.exe"
                launcher = child / "NapCatWinBootMain.exe"
                if entry.exists() and qq_executable.exists() and launcher.exists():
                    candidates.append(entry)
        if not candidates:
            return None
        candidates.sort(key=lambda path: path.parent.stat().st_mtime, reverse=True)
        return candidates[0]

    def _find_file(self, file_name: str) -> Optional[Path]:
        if not self.base_dir.exists():
            return None
        target = file_name.lower()
        for root, _, files in os.walk(self.base_dir):
            for name in files:
                if name.lower() == target:
                    return Path(root) / name
        return None

    def get_webui_info(self) -> Dict[str, Any]:
        parsed = self._parse_webui_from_logs()
        if parsed:
            return parsed

        for config_path in self._webui_config_candidates():
            parsed_config = self._read_webui_config(config_path)
            if parsed_config:
                return parsed_config

        return {"ok": False, "url": "", "port": 6099, "token": "", "source": ""}

    def _read_webui_config(self, config_path: Path) -> Optional[Dict[str, Any]]:
        if not config_path.exists():
            return None
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            host = str(data.get("host") or "127.0.0.1")
            if host in {"0.0.0.0", "::", "localhost", ""}:
                host = "127.0.0.1"
            port = int(data.get("port") or 6099)
            token = str(data.get("token") or "")
            url = f"http://{host}:{port}/webui" + (f"?token={token}" if token else "")
            return {
                "ok": True,
                "url": url,
                "port": port,
                "token": token,
                "source": str(config_path),
            }
        except Exception:
            return None

    def _webui_config_candidates(self) -> List[Path]:
        explicit_candidates = [
            self.work_dir / "config" / "webui.json",
            self.base_dir / "config" / "webui.json",
        ]
        discovered: List[Path] = []
        if self.base_dir.exists():
            for root, dirs, files in os.walk(self.base_dir):
                if "node_modules" in dirs:
                    dirs.remove("node_modules")
                if "webui.json" in files:
                    discovered.append(Path(root) / "webui.json")

        discovered.sort(
            key=lambda path: path.stat().st_mtime if path.exists() else 0,
            reverse=True,
        )

        candidates: List[Path] = []
        seen = set()
        for path in [*explicit_candidates, *discovered]:
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(path)
        return candidates

    def _parse_webui_from_logs(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            lines = list(self._logs)

        url = ""
        token = ""
        url_re = re.compile(r"WebUi User Panel Url:\s*(https?://\S+)", re.IGNORECASE)
        token_re = re.compile(r"WebUi Token:\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
        for line in reversed(lines):
            if not url:
                match = url_re.search(line)
                if match:
                    url = match.group(1)
            if not token:
                match = token_re.search(line)
                if match:
                    token = match.group(1)
            if url and token:
                break

        if not url and not token:
            return None

        port = 6099
        if url:
            parsed = urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            if host in {"0.0.0.0", "::", "localhost"}:
                host = "127.0.0.1"
            port = parsed.port or port
            query = parse_qs(parsed.query)
            token = query.get("token", [token])[0] or token
            url = f"http://{host}:{port}/webui" + (f"?token={token}" if token else "")
        else:
            url = f"http://127.0.0.1:{port}/webui?token={token}"
        return {"ok": True, "url": url, "port": port, "token": token, "source": "runtime logs"}


_manager: Optional[NapCatManager] = None


def get_napcat_manager() -> NapCatManager:
    global _manager
    if _manager is None:
        _manager = NapCatManager()
    return _manager

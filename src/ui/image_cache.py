"""Media cache manager for chat messages.

Downloads and caches media from QQ messages to local storage,
with automatic cleanup for files older than the retention window.
"""

import asyncio
import base64
import binascii
import hashlib
import re
import httpx
import mimetypes
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import aiofiles
from urllib.parse import urlparse, parse_qs

from ..core.blocking_task_pool import run_in_blocking_pool
from ..core.logger import get_logger
from ..core.app import get_app

logger = get_logger(__name__)


class ImageCacheManager:
    """Manages media caching for chat messages."""
    
    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24 * 30):
        """
        Initialize image cache manager.
        
        Args:
            cache_dir: Cache directory path (default: ./data/image_cache)
            max_age_hours: Maximum age of cached images in hours (default: 30 days)
        """
        if cache_dir is None:
            app = get_app()
            if app:
                data_dir = app.config.get_data_dir()
            else:
                data_dir = Path("./data")
            cache_dir = data_dir / "image_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours
        # Suppress repetitive warnings for the same failing media reference.
        self._failure_suppression: Dict[str, float] = {}
        
        logger.info(f"Image cache manager initialized: {self.cache_dir}")

    def _should_log_failure(self, key: str, interval_seconds: float = 180.0) -> bool:
        """Rate-limit repetitive warning logs for the same media reference."""
        now = datetime.now().timestamp()
        last = float(self._failure_suppression.get(key, 0.0) or 0.0)
        if now - last >= interval_seconds:
            self._failure_suppression[key] = now
            return True
        return False

    _MEDIA_EXTENSIONS = {
        "image": ["jpg", "jpeg", "png", "gif", "webp", "bmp"],
        "video": ["mp4", "webm", "mov", "mkv", "avi", "flv"],
        "record": ["mp3", "wav", "ogg", "m4a", "amr", "silk"],
        "file": ["bin", "zip", "rar", "7z", "pdf", "txt", "doc", "docx", "xlsx", "pptx"],
    }
    
    def _get_image_hash(self, url: str) -> str:
        """Generate hash for image URL."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, url: str, file_extension: str = "jpg") -> Path:
        """Get cache file path for an image URL."""
        image_hash = self._get_image_hash(url)
        return self.cache_dir / f"{image_hash}.{file_extension}"

    def _guess_extension(self, resolved_url: str, content_type: str, media_kind: str) -> str:
        """Guess extension from content type / URL / media kind fallback."""
        # 0) Query hints (QQ download URL often carries ?format=amr)
        try:
            query = parse_qs(urlparse(resolved_url).query or "")
            fmt = (query.get("format") or [None])[0]
            if fmt:
                fmt = str(fmt).strip().lower()
                if fmt:
                    return fmt
        except Exception:
            pass

        # 1) Prefer content-type
        guessed_from_ct = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
        if guessed_from_ct:
            ext = guessed_from_ct.lstrip(".").lower()
            if ext:
                return ext

        # 2) Try URL suffix
        parsed = urlparse(resolved_url)
        suffix = Path(parsed.path or "").suffix.lower().lstrip(".")
        if suffix:
            return suffix

        # 3) Fallback by media kind
        if media_kind == "video":
            return "mp4"
        if media_kind == "record":
            return "amr"
        if media_kind == "file":
            return "bin"
        return "jpg"

    def _extension_from_mime(self, mime_type: str, media_kind: str) -> str:
        """Guess a safe file extension for uploaded data URLs."""
        mime_type = (mime_type or "").split(";")[0].strip().lower()
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            ext = guessed.lstrip(".").lower()
            if ext == "jpe":
                return "jpg"
            if ext:
                return ext
        if media_kind == "video":
            return "mp4"
        if media_kind == "record":
            return "amr"
        if media_kind == "file":
            return "bin"
        return "png"

    def _extension_from_bytes(self, raw_bytes: bytes, media_kind: str) -> str:
        """Guess a file extension from magic bytes when CQ media omits MIME metadata."""
        if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if raw_bytes.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if raw_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "gif"
        if raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
            return "webp"
        if raw_bytes.startswith(b"BM"):
            return "bmp"
        if media_kind == "video":
            return "mp4"
        if media_kind == "record":
            return "amr"
        if media_kind == "file":
            return "bin"
        return "png"

    async def save_base64_media(self, base64_ref: str, media_kind: str = "image") -> Optional[str]:
        """Save a CQ ``base64://`` media payload into the media cache."""
        if not isinstance(base64_ref, str):
            return None

        payload = base64_ref.strip()
        if payload.startswith("base64://"):
            payload = payload[len("base64://"):]
        if not payload:
            return None

        try:
            raw_bytes = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as e:
            logger.warning(f"Failed to decode base64 CQ media: {e}")
            return None

        if not raw_bytes:
            return None

        ext = self._extension_from_bytes(raw_bytes, media_kind)
        digest = hashlib.sha256(raw_bytes).hexdigest()
        cache_path = self.cache_dir / f"{digest}.{ext}"

        try:
            if cache_path.exists() and cache_path.stat().st_size == len(raw_bytes):
                return str(cache_path)
            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(raw_bytes)
            logger.info(
                f"Base64 CQ media cached successfully: {cache_path} ({len(raw_bytes)} bytes) "
                f"kind={media_kind}"
            )
            return str(cache_path)
        except Exception as e:
            logger.warning(f"Failed to save base64 CQ media cache: {e}", exc_info=True)
            return None

    async def save_data_url_media(self, data_url: str, media_kind: str = "image") -> Optional[str]:
        """Save a browser-uploaded data URL into the media cache and return its local path."""
        if not isinstance(data_url, str) or not data_url.startswith("data:"):
            return None

        match = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data_url, re.DOTALL)
        if not match:
            return None

        mime_type = match.group(1) or "application/octet-stream"
        is_base64 = bool(match.group(2))
        payload = match.group(3) or ""

        try:
            if is_base64:
                raw_bytes = base64.b64decode(payload, validate=True)
            else:
                from urllib.parse import unquote_to_bytes
                raw_bytes = unquote_to_bytes(payload)
        except (binascii.Error, ValueError) as e:
            logger.warning(f"Failed to decode data URL media: {e}")
            return None

        if not raw_bytes:
            return None

        ext = self._extension_from_mime(mime_type, media_kind)
        digest = hashlib.sha256(raw_bytes).hexdigest()
        cache_path = self.cache_dir / f"{digest}.{ext}"

        try:
            if cache_path.exists() and cache_path.stat().st_size == len(raw_bytes):
                return str(cache_path)
            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(raw_bytes)
            logger.info(
                f"Uploaded media cached successfully: {cache_path} ({len(raw_bytes)} bytes) kind={media_kind}"
            )
            return str(cache_path)
        except Exception as e:
            logger.warning(f"Failed to save uploaded media cache: {e}", exc_info=True)
            return None

    async def ensure_browser_playable_record(self, source_path: str) -> str:
        """Convert unsupported record formats (amr/silk) to browser-playable wav."""
        src = Path(source_path)
        if not src.exists() or not src.is_file():
            return source_path

        def detect_audio_format(path: Path) -> str:
            try:
                header = path.read_bytes()[:16]
            except Exception:
                return "unknown"
            if header.startswith(b"#!AMR"):
                return "amr"
            if header.startswith(b"#!SILK_V3"):
                return "silk"
            if header.startswith(b"RIFF"):
                return "wav"
            if header.startswith(b"OggS"):
                return "ogg"
            if header.startswith(b"ID3"):
                return "mp3"
            if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
                return "mp3"
            return "unknown"

        ext = src.suffix.lower().lstrip(".")
        actual_fmt = detect_audio_format(src)

        # Formats commonly supported by browsers (by real content, not extension).
        if actual_fmt in {"mp3", "wav", "ogg"}:
            return source_path
        if actual_fmt == "unknown" and ext in {"mp3", "wav", "ogg", "m4a", "webm"}:
            return source_path

        # Only convert formats likely unsupported in browser.
        needs_convert = actual_fmt in {"amr", "silk"} or ext in {"amr", "silk"}
        if not needs_convert:
            return source_path

        ffmpeg_bin = shutil.which("ffmpeg")

        target = src.with_suffix(".web.wav")

        def transcode_with_pyav_sync(in_path: Path, out_path: Path) -> bool:
            try:
                import av  # Optional dependency

                in_container = av.open(str(in_path))
                out_container = av.open(str(out_path), mode="w")
                out_stream = out_container.add_stream("pcm_s16le", rate=24000)
                out_stream.layout = "mono"

                for frame in in_container.decode(audio=0):
                    frame.pts = None
                    for packet in out_stream.encode(frame):
                        out_container.mux(packet)

                for packet in out_stream.encode(None):
                    out_container.mux(packet)

                out_container.close()
                in_container.close()
                return out_path.exists() and out_path.stat().st_size > 0
            except Exception:
                return False

        try:
            if (
                target.exists()
                and target.is_file()
                and target.stat().st_size > 0
                and target.stat().st_mtime >= src.stat().st_mtime
            ):
                return str(target)

            # Prefer PyAV (Python dependency) for distributable packaging.
            pyav_ok = await run_in_blocking_pool(transcode_with_pyav_sync, src, target)
            if pyav_ok:
                logger.info(f"Converted record for web playback via PyAV: {src} -> {target}")
                return str(target)

            if not ffmpeg_bin:
                logger.debug(
                    f"Neither PyAV transcode nor ffmpeg available for record: {src} "
                    f"(ext={ext}, actual={actual_fmt})"
                )
                return source_path

            proc = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-y",
                "-i",
                str(src),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "24000",
                str(target),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode == 0 and target.exists() and target.stat().st_size > 0:
                logger.info(f"Converted record for web playback: {src} -> {target}")
                return str(target)

            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
            logger.warning(
                "Failed to transcode record for web playback: "
                f"{src}, returncode={proc.returncode}, stderr={stderr.decode(errors='ignore')[:300]}"
            )
            return source_path
        except Exception as e:
            logger.warning(f"Record transcode error for {src}: {e}")
            return source_path

    async def _resolve_media_url(self, media_ref: str, onebot_adapter=None, media_kind: str = "image") -> Optional[str]:
        """Resolve OneBot file references into downloadable URL when possible."""
        if media_ref.startswith("http://") or media_ref.startswith("https://"):
            return media_ref

        # Local file URI/path can be served directly by upper layers; no download URL needed.
        if media_ref.startswith("file://"):
            return media_ref

        if not onebot_adapter:
            return None

        try:
            if media_kind == "image":
                image_info = await onebot_adapter.call_api("get_image", {"file": media_ref})
                if isinstance(image_info, dict):
                    return image_info.get("url")
                return None
        except Exception as e:
            logger.warning(f"Failed to resolve media URL from OneBot ({media_kind}): {media_ref}, error: {e}")
            return None

        # OneBot v11 has no generic "get_video"/"get_file" URL API in many implementations.
        return None

    async def get_cached_media_path(self, media_ref: str, media_kind: str = "image") -> Optional[str]:
        """Get cached media path if exists."""
        exts = self._MEDIA_EXTENSIONS.get(media_kind, self._MEDIA_EXTENSIONS["file"])
        for ext in exts:
            cache_path = self._get_cache_path(media_ref, ext)
            if cache_path.exists():
                return str(cache_path)
        return None

    async def download_and_cache_media(
        self,
        media_ref: str,
        onebot_adapter=None,
        media_kind: str = "image",
    ) -> Optional[str]:
        """Download and cache media (image/video/record/file)."""
        original_ref = media_ref
        try:
            resolved = await self._resolve_media_url(media_ref, onebot_adapter=onebot_adapter, media_kind=media_kind)
            if not resolved:
                # Common for expired/invalid voice-file refs; keep logs low-noise.
                if self._should_log_failure(f"resolve:{media_kind}:{original_ref}"):
                    logger.debug(f"Could not resolve media reference to URL: {original_ref}")
                return None

            # file:// resources should be handled by caller directly, not downloaded.
            if resolved.startswith("file://"):
                return None

            cached_existing = await self.get_cached_media_path(resolved, media_kind=media_kind)
            if cached_existing and Path(cached_existing).exists():
                return cached_existing

            headers = {
                "Referer": "https://qzone.qq.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(resolved, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                file_ext = self._guess_extension(resolved, content_type, media_kind)
                cache_path = self._get_cache_path(resolved, file_ext)
                async with aiofiles.open(cache_path, "wb") as f:
                    await f.write(response.content)
                logger.info(
                    f"Media cached successfully: {cache_path} ({len(response.content)} bytes) "
                    f"kind={media_kind} from {original_ref}"
                )
                return str(cache_path)
        except httpx.HTTPStatusError as e:
            response_text = (e.response.text or "")[:200]
            status_code = e.response.status_code
            expired_hint = "download url has expired" in response_text.lower()
            should_warn = (not expired_hint) and self._should_log_failure(
                f"http:{status_code}:{media_kind}:{original_ref}"
            )
            if should_warn:
                logger.warning(f"HTTP error caching media {original_ref}: {status_code} - {response_text[:100]}")
            else:
                logger.debug(f"Media cache miss ({status_code}) for {original_ref}: {response_text[:80]}")
            return None
        except httpx.TimeoutException:
            if self._should_log_failure(f"timeout:{media_kind}:{original_ref}"):
                logger.warning(f"Timeout caching media {original_ref}")
            return None
        except Exception as e:
            if self._should_log_failure(f"error:{media_kind}:{original_ref}"):
                logger.warning(f"Failed to cache media {original_ref}: {e}", exc_info=True)
            else:
                logger.debug(f"Failed to cache media (suppressed) {original_ref}: {e}")
            return None

    async def download_and_cache_image(self, image_url: str, onebot_adapter=None) -> Optional[str]:
        """
        Download and cache an image from URL.
        
        Args:
            image_url: Image URL or CQ image file reference
            onebot_adapter: OneBot adapter instance (optional, for getting image URL)
        
        Returns:
            Local file path if successful, None otherwise
        """
        return await self.download_and_cache_media(image_url, onebot_adapter=onebot_adapter, media_kind="image")
    
    async def get_cached_image_path(self, image_url: str) -> Optional[str]:
        """
        Get cached image path if exists.
        
        Args:
            image_url: Image URL
        
        Returns:
            Local file path if cached, None otherwise
        """
        return await self.get_cached_media_path(image_url, media_kind="image")

    @staticmethod
    def _parse_cq_params(params_str: str) -> Dict[str, str]:
        """Parse CQ params while preserving values that contain commas."""
        params: Dict[str, str] = {}
        allowed_keys = {
            "file",
            "url",
            "type",
            "cache",
            "proxy",
            "timeout",
            "name",
            "id",
            "size",
            "md5",
            "sha1",
            "sub_type",
            "summary",
        }
        key_pattern = re.compile(r"(?:^|,)([A-Za-z_][A-Za-z0-9_-]*)=")
        key_matches = [
            m for m in key_pattern.finditer(params_str or "") if m.group(1).strip() in allowed_keys
        ]
        for idx, match in enumerate(key_matches):
            key = match.group(1).strip()
            value_start = match.end()
            value_end = key_matches[idx + 1].start() if idx + 1 < len(key_matches) else len(params_str)
            value = params_str[value_start:value_end].strip()
            if value.endswith(","):
                value = value[:-1]
            if key and value:
                params[key] = value
        return params

    @staticmethod
    def _build_cq(cq_type: str, params: Dict[str, str]) -> str:
        parts = [f"{k}={v}" for k, v in params.items() if v is not None and str(v).strip() != ""]
        return f"[CQ:{cq_type}{',' + ','.join(parts) if parts else ''}]"

    async def cache_embedded_cq_media_for_display(
        self,
        raw_message: str,
        onebot_adapter=None,
    ) -> str:
        """Cache embedded CQ media and rewrite display-only refs to local file URIs."""
        if not isinstance(raw_message, str) or "[CQ:" not in raw_message:
            return raw_message

        media_kind_map = {
            "image": "image",
            "video": "video",
            "record": "record",
            "file": "file",
        }
        cq_pattern = re.compile(r"\[CQ:(image|video|record|file),([^\]]+)\]")

        out = []
        last = 0
        changed = False
        for match in cq_pattern.finditer(raw_message):
            out.append(raw_message[last:match.start()])
            cq_type = match.group(1)
            params = self._parse_cq_params(match.group(2))
            media_ref = (params.get("url") or params.get("file") or "").strip()
            media_kind = media_kind_map.get(cq_type, "file")
            cached_path = None

            if media_ref.startswith("base64://"):
                cached_path = await self.save_base64_media(media_ref, media_kind=media_kind)
            elif media_ref.startswith("data:"):
                cached_path = await self.save_data_url_media(media_ref, media_kind=media_kind)
            elif media_ref:
                cached_path = await self.download_and_cache_media(
                    media_ref,
                    onebot_adapter=onebot_adapter,
                    media_kind=media_kind,
                )

            if cached_path and Path(cached_path).exists():
                display_params = dict(params)
                display_params["file"] = Path(cached_path).resolve().as_uri()
                display_params.pop("url", None)
                out.append(self._build_cq(cq_type, display_params))
                changed = True
            else:
                out.append(match.group(0))
            last = match.end()

        out.append(raw_message[last:])
        return "".join(out) if changed else raw_message
    
    async def extract_and_cache_images(self, raw_message: str, onebot_adapter=None) -> Dict[str, str]:
        """
        Extract image URLs from CQ code and cache them.
        
        Args:
            raw_message: Raw message with CQ codes
            onebot_adapter: OneBot adapter instance (optional)
        
        Returns:
            Dictionary mapping original image references to cached file paths
        """
        image_map = {}
        
        # Extract CQ image codes: [CQ:image,file=xxx.jpg,url=xxx] or [CQ:image,file=xxx.jpg]
        image_pattern = r'\[CQ:image,([^\]]+)\]'
        matches = re.finditer(image_pattern, raw_message)
        
        for match in matches:
            params_str = match.group(1)
            # Parse parameters
            file_ref = None
            url_ref = None
            
            for param in params_str.split(','):
                if '=' in param:
                    key, value = param.split('=', 1)
                    if key.strip() == 'file':
                        file_ref = value.strip()
                    elif key.strip() == 'url':
                        url_ref = value.strip()
            
            # Prefer URL if available, otherwise use file reference
            image_ref = url_ref or file_ref
            if image_ref:
                if image_ref.startswith("base64://"):
                    cached_path = await self.save_base64_media(image_ref, media_kind="image")
                elif image_ref.startswith("data:"):
                    cached_path = await self.save_data_url_media(image_ref, media_kind="image")
                else:
                    cached_path = await self.download_and_cache_image(image_ref, onebot_adapter)
                if cached_path:
                    image_map[image_ref] = cached_path
                    # Also map the original CQ code
                    image_map[match.group(0)] = cached_path
        
        return image_map
    
    async def cleanup_old_images(self, max_age_hours: Optional[int] = None) -> int:
        """
        Clean up old cached media files.
        
        Args:
            max_age_hours: Maximum age in hours (uses self.max_age_hours if None)
        """
        if max_age_hours is None:
            max_age_hours = self.max_age_hours
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            deleted_count = 0
            total_size = 0
            
            for cache_file in self.cache_dir.glob("*.*"):
                try:
                    # Check file modification time
                    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if mtime < cutoff_time:
                        file_size = cache_file.stat().st_size
                        cache_file.unlink()
                        deleted_count += 1
                        total_size += file_size
                        logger.debug(f"Deleted old cached media: {cache_file}")
                except Exception as e:
                    logger.warning(f"Error deleting cached media {cache_file}: {e}")
            
            if deleted_count > 0:
                logger.info(
                    f"Cleaned up {deleted_count} old media cache files "
                    f"({total_size / 1024 / 1024:.2f} MB)"
                )
            return deleted_count
        except Exception as e:
            logger.error(f"Error during media cache cleanup: {e}", exc_info=True)
            return 0
    
    async def cleanup_all_images(self) -> int:
        """Clean up all cached media files."""
        try:
            deleted_count = 0
            total_size = 0
            
            for cache_file in self.cache_dir.glob("*.*"):
                try:
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    deleted_count += 1
                    total_size += file_size
                except Exception as e:
                    logger.warning(f"Error deleting cached media {cache_file}: {e}")
            
            if deleted_count > 0:
                logger.info(
                    f"Cleaned up all cached media on startup: {deleted_count} files "
                    f"({total_size / 1024 / 1024:.2f} MB)"
                )
            return deleted_count
        except Exception as e:
            logger.error(f"Error during media cache cleanup: {e}", exc_info=True)
            return 0


# Global image cache manager instance
_image_cache_manager: Optional[ImageCacheManager] = None


def get_image_cache_manager() -> ImageCacheManager:
    """Get global image cache manager instance."""
    global _image_cache_manager
    if _image_cache_manager is None:
        _image_cache_manager = ImageCacheManager()
    return _image_cache_manager


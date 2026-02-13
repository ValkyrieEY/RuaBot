"""Image cache manager for chat messages.

Downloads and caches images from QQ messages to local storage,
with automatic cleanup on startup and periodic cleanup to prevent storage overflow.
"""

import asyncio
import hashlib
import re
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import aiofiles

from ..core.logger import get_logger
from ..core.app import get_app

logger = get_logger(__name__)


class ImageCacheManager:
    """Manages image caching for chat messages."""
    
    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24):
        """
        Initialize image cache manager.
        
        Args:
            cache_dir: Cache directory path (default: ./data/image_cache)
            max_age_hours: Maximum age of cached images in hours (default: 24)
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
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"Image cache manager initialized: {self.cache_dir}")
    
    def _get_image_hash(self, url: str) -> str:
        """Generate hash for image URL."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, url: str, file_extension: str = "jpg") -> Path:
        """Get cache file path for an image URL."""
        image_hash = self._get_image_hash(url)
        return self.cache_dir / f"{image_hash}.{file_extension}"
    
    async def download_and_cache_image(self, image_url: str, onebot_adapter=None) -> Optional[str]:
        """
        Download and cache an image from URL.
        
        Args:
            image_url: Image URL or CQ image file reference
            onebot_adapter: OneBot adapter instance (optional, for getting image URL)
        
        Returns:
            Local file path if successful, None otherwise
        """
        try:
            original_ref = image_url  # Save original reference for logging
            
            # If it's a CQ image file reference (not a full URL), try to get URL from OneBot
            if not image_url.startswith('http://') and not image_url.startswith('https://'):
                if onebot_adapter:
                    try:
                        image_info = await onebot_adapter.call_api('get_image', {'file': image_url})
                        if image_info and isinstance(image_info, dict):
                            image_url = image_info.get('url', '')
                            if not image_url:
                                logger.warning(f"Could not get URL for image file: {original_ref}")
                                return None
                            logger.debug(f"Got image URL from OneBot for file {original_ref}: {image_url[:50]}...")
                        else:
                            logger.warning(f"get_image API returned invalid response for file {original_ref}: {image_info}")
                            return None
                    except Exception as e:
                        logger.warning(f"Failed to get image URL from OneBot for file {original_ref}: {e}")
                        return None
                else:
                    logger.warning(f"Image reference is not a URL and no OneBot adapter available: {original_ref}")
                    return None
            
            # Check if already cached (try all common extensions)
            for ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                cache_path = self._get_cache_path(image_url, ext)
                if cache_path.exists():
                    logger.debug(f"Image already cached: {cache_path}")
                    return str(cache_path)
            
            # Download image
            headers = {
                'Referer': 'https://qzone.qq.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(image_url, headers=headers)
                response.raise_for_status()
                
                # Determine file extension from content-type or URL
                content_type = response.headers.get('content-type', 'image/jpeg')
                if 'png' in content_type:
                    file_ext = 'png'
                elif 'gif' in content_type:
                    file_ext = 'gif'
                elif 'webp' in content_type:
                    file_ext = 'webp'
                else:
                    file_ext = 'jpg'
                
                # Update cache path with correct extension
                cache_path = self._get_cache_path(image_url, file_ext)
                
                # Save to cache
                async with aiofiles.open(cache_path, 'wb') as f:
                    await f.write(response.content)
                
                logger.info(f"Image cached successfully: {cache_path} ({len(response.content)} bytes) from {original_ref}")
                return str(cache_path)
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error caching image {original_ref}: {e.response.status_code} - {e.response.text[:100]}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"Timeout caching image {original_ref}")
            return None
        except Exception as e:
            logger.warning(f"Failed to cache image {original_ref}: {e}", exc_info=True)
            return None
    
    async def get_cached_image_path(self, image_url: str) -> Optional[str]:
        """
        Get cached image path if exists.
        
        Args:
            image_url: Image URL
        
        Returns:
            Local file path if cached, None otherwise
        """
        # Try common extensions
        for ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            cache_path = self._get_cache_path(image_url, ext)
            if cache_path.exists():
                return str(cache_path)
        return None
    
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
                # Download and cache
                cached_path = await self.download_and_cache_image(image_ref, onebot_adapter)
                if cached_path:
                    image_map[image_ref] = cached_path
                    # Also map the original CQ code
                    image_map[match.group(0)] = cached_path
        
        return image_map
    
    async def cleanup_old_images(self, max_age_hours: Optional[int] = None):
        """
        Clean up old cached images.
        
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
                        logger.debug(f"Deleted old cached image: {cache_file}")
                except Exception as e:
                    logger.warning(f"Error deleting cached image {cache_file}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old images ({total_size / 1024 / 1024:.2f} MB)")
        except Exception as e:
            logger.error(f"Error during image cache cleanup: {e}", exc_info=True)
    
    async def cleanup_all_images(self):
        """Clean up all cached images (called on startup)."""
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
                    logger.warning(f"Error deleting cached image {cache_file}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up all cached images on startup: {deleted_count} files ({total_size / 1024 / 1024:.2f} MB)")
        except Exception as e:
            logger.error(f"Error during image cache cleanup: {e}", exc_info=True)
    
    async def start_periodic_cleanup(self, interval_hours: int = 6):
        """
        Start periodic cleanup task.
        
        Args:
            interval_hours: Cleanup interval in hours (default: 6)
        """
        async def cleanup_loop():
            try:
                while True:
                    await asyncio.sleep(interval_hours * 3600)
                    await self.cleanup_old_images()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in periodic cleanup task: {e}", exc_info=True)
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started periodic image cache cleanup (every {interval_hours} hours)")
    
    async def stop_periodic_cleanup(self):
        """Stop periodic cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None


# Global image cache manager instance
_image_cache_manager: Optional[ImageCacheManager] = None


def get_image_cache_manager() -> ImageCacheManager:
    """Get global image cache manager instance."""
    global _image_cache_manager
    if _image_cache_manager is None:
        _image_cache_manager = ImageCacheManager()
    return _image_cache_manager


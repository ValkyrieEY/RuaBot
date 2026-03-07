"""Device key management for passwordless login via browser extension."""

from __future__ import annotations

import hmac
import hashlib
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.logger import get_logger
from ..core.config import get_config
from ..core.storage import get_storage

logger = get_logger(__name__)


class DeviceKeyStatus:
    ENABLED = "enabled"
    DISABLED = "disabled"
    REVOKED = "revoked"


class DeviceKeyManager:
    """Manage device keys used for password-less login from browser extensions."""

    _STORAGE_KEY = "security:device_keys"

    def __init__(self) -> None:
        self._storage = get_storage()
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load keys from persistent storage."""
        try:
            data = self._storage.get(self._STORAGE_KEY) or {}
            if isinstance(data, dict):
                self._keys = data
            else:
                logger.warning("DeviceKeyManager storage data invalid, resetting")
                self._keys = {}
        except Exception as e:
            logger.error(f"Failed to load device keys from storage: {e}")
            self._keys = {}

    def _save(self) -> None:
        """Persist keys to storage."""
        try:
            self._storage.set(self._STORAGE_KEY, self._keys)
        except Exception as e:
            logger.error(f"Failed to save device keys to storage: {e}")

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """Hash secret with HMAC-SHA256 using app secret_key."""
        cfg = get_config()
        key = str(cfg.secret_key).encode("utf-8")
        return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat() + "Z"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_keys_for_user(self, username: str) -> List[Dict[str, Any]]:
        """Return all device keys for given user (without opaque token)."""
        return [
            {
                "key_id": r["key_id"],
                "username": r["username"],
                "name": r.get("name"),
                "status": r.get("status", DeviceKeyStatus.ENABLED),
                "created_at": r.get("created_at"),
                "last_used_at": r.get("last_used_at"),
                "device_fingerprint": r.get("device_fingerprint") or {},
            }
            for r in self._keys.values()
            if r.get("username") == username
        ]

    def create_key(
        self,
        username: str,
        name: Optional[str],
        device_fingerprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new device key for a user.

        Returns dict including an opaque_token which should be stored only
        on client side (browser extension).
        """
        key_id = secrets.token_urlsafe(16)
        secret = secrets.token_urlsafe(32)
        secret_hash = self._hash_secret(secret)

        record = {
            "key_id": key_id,
            "username": username,
            "name": name or "Unnamed Device",
            "secret_hash": secret_hash,
            "status": DeviceKeyStatus.ENABLED,
            "created_at": self._now_iso(),
            "last_used_at": None,
            "device_fingerprint": device_fingerprint or {},
        }

        self._keys[key_id] = record
        self._save()

        opaque_token = f"{key_id}.{secret}"

        logger.info(
            "Device key created",
            extra={"username": username, "key_id": key_id},
        )

        return {
            "key_id": key_id,
            "name": record["name"],
            "status": record["status"],
            "created_at": record["created_at"],
            "last_used_at": record["last_used_at"],
            "device_fingerprint": record["device_fingerprint"],
            "opaque_token": opaque_token,
        }

    def set_status(self, username: str, key_id: str, status: str) -> Dict[str, Any]:
        rec = self._keys.get(key_id)
        if not rec or rec.get("username") != username:
            raise KeyError("device key not found")
        if status not in (
            DeviceKeyStatus.ENABLED,
            DeviceKeyStatus.DISABLED,
            DeviceKeyStatus.REVOKED,
        ):
            raise ValueError("invalid status")

        rec["status"] = status
        self._save()
        logger.info(
            "Device key status updated",
            extra={"username": username, "key_id": key_id, "status": status},
        )
        return rec

    def delete_key(self, username: str, key_id: str) -> bool:
        rec = self._keys.get(key_id)
        if not rec or rec.get("username") != username:
            return False
        del self._keys[key_id]
        self._save()
        logger.info(
            "Device key deleted",
            extra={"username": username, "key_id": key_id},
        )
        return True

    def authenticate(
        self,
        opaque_token: str,
        device_fingerprint: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Verify device key and return username if valid."""
        if not opaque_token or "." not in opaque_token:
            return None

        try:
            key_id, secret = opaque_token.split(".", 1)
        except ValueError:
            return None

        rec = self._keys.get(key_id)
        if not rec:
            return None

        if rec.get("status") != DeviceKeyStatus.ENABLED:
            return None

        expected_hash = rec.get("secret_hash")
        if not expected_hash:
            return None

        actual_hash = self._hash_secret(secret)
        if not hmac.compare_digest(expected_hash, actual_hash):
            return None

        stored_fp = rec.get("device_fingerprint") or {}
        if device_fingerprint and stored_fp:
            if device_fingerprint != stored_fp:
                logger.warning(
                    "Device fingerprint mismatch for device key",
                    extra={"key_id": key_id},
                )
                return None

        rec["last_used_at"] = self._now_iso()
        self._save()

        return rec.get("username")


_device_key_manager: Optional[DeviceKeyManager] = None


def get_device_key_manager() -> DeviceKeyManager:
    """Get global DeviceKeyManager instance."""
    global _device_key_manager
    if _device_key_manager is None:
        _device_key_manager = DeviceKeyManager()
    return _device_key_manager



"""Secret handling helpers for Assistant configuration."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from ..core.config import get_runtime_base_dir

ENCRYPTED_PREFIX = "enc:v1:"
MASK_PREFIX = "******"


def _secret_key_path() -> Path:
    data_dir = get_runtime_base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "assistant_secret.key"


def _fernet() -> Fernet:
    path = _secret_key_path()
    if path.exists():
        key = path.read_bytes()
    else:
        key = Fernet.generate_key()
        path.write_bytes(key)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value or value.startswith(ENCRYPTED_PREFIX) or is_masked_secret(value):
        return value
    return ENCRYPTED_PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value or not value.startswith(ENCRYPTED_PREFIX):
        return value
    token = value[len(ENCRYPTED_PREFIX):].encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_secret(value: str) -> str:
    plain = decrypt_secret(value)
    if not plain:
        return ""
    tail = plain[-4:] if len(plain) >= 4 else plain
    return f"{MASK_PREFIX}{tail}"


def is_masked_secret(value: str) -> bool:
    return value.startswith(MASK_PREFIX)


def assistant_config_for_response(config: Dict[str, Any]) -> Dict[str, Any]:
    response = copy.deepcopy(config if isinstance(config, dict) else {})
    for provider in response.get("providers", []) if isinstance(response.get("providers"), list) else []:
        if isinstance(provider, dict) and provider.get("apiKey"):
            provider["apiKey"] = mask_secret(str(provider.get("apiKey") or ""))
    return response


def assistant_config_for_storage(config: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = copy.deepcopy(config if isinstance(config, dict) else {})
    existing_providers = {
        str(item.get("id") or ""): item
        for item in (existing or {}).get("providers", [])
        if isinstance(item, dict)
    }

    for provider in payload.get("providers", []) if isinstance(payload.get("providers"), list) else []:
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id") or "")
        api_key = str(provider.get("apiKey") or "")
        if is_masked_secret(api_key):
            provider["apiKey"] = encrypt_secret(str(existing_providers.get(provider_id, {}).get("apiKey") or ""))
        elif api_key:
            provider["apiKey"] = encrypt_secret(api_key)

    return payload

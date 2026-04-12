"""Utilities for reading plugin manifests from split metadata/settings files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml

PLUGIN_METADATA_FILENAMES = ("metadata.yaml", "metadata.yml")
PLUGIN_SETTINGS_FILENAME = "settings.json"


class PluginManifestError(ValueError):
    """Raised when plugin manifest files are missing or invalid."""


def get_plugin_metadata_path(plugin_dir: Path) -> Path:
    """Return the metadata YAML path, preferring ``metadata.yaml``."""
    plugin_dir = Path(plugin_dir)
    for filename in PLUGIN_METADATA_FILENAMES:
        candidate = plugin_dir / filename
        if candidate.is_file():
            return candidate
    return plugin_dir / PLUGIN_METADATA_FILENAMES[0]


def get_plugin_settings_path(plugin_dir: Path) -> Path:
    """Return the settings JSON path."""
    return Path(plugin_dir) / PLUGIN_SETTINGS_FILENAME


def plugin_manifest_exists(plugin_dir: Path) -> bool:
    """Return whether both manifest files exist."""
    plugin_dir = Path(plugin_dir)
    return get_plugin_metadata_path(plugin_dir).is_file() and get_plugin_settings_path(plugin_dir).is_file()


def normalize_plugin_default_config(raw_config: Any) -> Dict[str, Any]:
    """Ensure plugin ``default_config`` is always a dict."""
    if isinstance(raw_config, dict):
        return raw_config
    return {}


def coerce_plugin_priority(raw_priority: Any, default: int = 100) -> int:
    """Normalize plugin priority to int."""
    try:
        return int(raw_priority)
    except (TypeError, ValueError):
        return default


def _require_mapping(payload: Any, label: str, path: Path) -> Dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise PluginManifestError(f"{label} must be an object: {path}")
    return payload


def read_plugin_metadata(plugin_dir: Path) -> Dict[str, Any]:
    """Read plugin metadata from YAML."""
    path = get_plugin_metadata_path(plugin_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Plugin metadata file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        metadata = yaml.safe_load(f)

    metadata = _require_mapping(metadata, "Plugin metadata", path)

    name = str(metadata.get("name", "")).strip()
    version = str(metadata.get("version", "")).strip()
    if not name:
        raise PluginManifestError(f"Plugin metadata missing required field 'name': {path}")
    if not version:
        raise PluginManifestError(f"Plugin metadata missing required field 'version': {path}")

    normalized = dict(metadata)
    normalized["name"] = name
    normalized["version"] = version
    normalized["author"] = str(normalized.get("author", "Unknown")).strip() or "Unknown"
    normalized["description"] = normalized.get("description", f"Plugin: {name}")

    tags = normalized.get("tags", [])
    normalized["tags"] = tags if isinstance(tags, list) else []

    dependencies = normalized.get("dependencies", [])
    normalized["dependencies"] = dependencies if isinstance(dependencies, list) else []

    normalized["category"] = normalized.get("category", "general")
    normalized["priority"] = coerce_plugin_priority(normalized.get("priority"), 100)
    return normalized


def read_plugin_settings(plugin_dir: Path) -> Dict[str, Any]:
    """Read plugin settings UI definition from JSON."""
    path = get_plugin_settings_path(plugin_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Plugin settings file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    settings = _require_mapping(settings, "Plugin settings", path)

    config_schema = settings.get("config_schema", {})
    if config_schema is None:
        config_schema = {}
    if not isinstance(config_schema, dict):
        raise PluginManifestError(f"Plugin settings field 'config_schema' must be an object: {path}")

    normalized = dict(settings)
    normalized["config_schema"] = config_schema
    normalized["default_config"] = normalize_plugin_default_config(settings.get("default_config", {}))
    return normalized


def load_plugin_manifest(plugin_dir: Path) -> Dict[str, Any]:
    """Load and merge plugin metadata and settings UI definition."""
    metadata = read_plugin_metadata(plugin_dir)
    settings = read_plugin_settings(plugin_dir)

    manifest = dict(metadata)
    manifest["config_schema"] = settings["config_schema"]
    manifest["default_config"] = settings["default_config"]
    return manifest


def build_plugin_api_metadata(manifest: Dict[str, Any], fallback_name: str | None = None) -> Dict[str, Any]:
    """Build the API metadata payload expected by the Web UI."""
    plugin_name = str(manifest.get("name") or fallback_name or "").strip()

    return {
        "name": plugin_name,
        "version": manifest.get("version", "1.0.0"),
        "author": str(manifest.get("author", "Unknown")).strip() or "Unknown",
        "description": manifest.get("description", f"Plugin: {plugin_name}"),
        "required_permissions": [],
        "required_capabilities": [],
        "dependencies": manifest.get("dependencies", []),
        "config_schema": manifest.get("config_schema"),
        "default_config": normalize_plugin_default_config(manifest.get("default_config", {})),
        "tags": manifest.get("tags", []),
        "category": manifest.get("category", "general"),
        "homepage": manifest.get("homepage"),
        "repository": manifest.get("repository"),
        "documentation": manifest.get("documentation"),
    }

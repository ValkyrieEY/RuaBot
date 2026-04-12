import json

import pytest

from src.plugins.manifest import load_plugin_manifest, plugin_manifest_exists
from src.ui.api import normalize_plugin_config_by_schema


def test_load_plugin_manifest_merges_metadata_and_settings(tmp_path):
    plugin_dir = tmp_path / "demo_plugin"
    plugin_dir.mkdir()

    (plugin_dir / "metadata.yaml").write_text(
        "\n".join(
            [
                "name: demo_plugin",
                "version: 1.2.3",
                "author: XQNEXT",
                "description: Demo plugin",
                "priority: 42",
            ]
        ),
        encoding="utf-8",
    )
    (plugin_dir / "settings.json").write_text(
        json.dumps(
            {
                "default_config": {"enabled": True},
                "config_schema": {
                    "enabled": {
                        "type": "boolean",
                        "default": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = load_plugin_manifest(plugin_dir)

    assert manifest["name"] == "demo_plugin"
    assert manifest["version"] == "1.2.3"
    assert manifest["author"] == "XQNEXT"
    assert manifest["priority"] == 42
    assert manifest["default_config"] == {"enabled": True}
    assert manifest["config_schema"]["enabled"]["type"] == "boolean"


def test_plugin_manifest_exists_requires_both_files(tmp_path):
    plugin_dir = tmp_path / "demo_plugin"
    plugin_dir.mkdir()

    (plugin_dir / "metadata.yaml").write_text("name: demo\nversion: 1.0.0\n", encoding="utf-8")
    assert plugin_manifest_exists(plugin_dir) is False

    (plugin_dir / "settings.json").write_text("{}", encoding="utf-8")
    assert plugin_manifest_exists(plugin_dir) is True


def test_load_plugin_manifest_requires_settings_json(tmp_path):
    plugin_dir = tmp_path / "demo_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "metadata.yaml").write_text("name: demo\nversion: 1.0.0\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        load_plugin_manifest(plugin_dir)


def test_settings_ui_showcase_manifest_covers_all_supported_field_types():
    manifest = load_plugin_manifest("plugins/settings_ui_showcase")
    schema = manifest["config_schema"]

    assert schema["simple_text"]["type"] == "string"
    assert schema["simple_number"]["type"] == "number"
    assert schema["simple_switch"]["type"] == "boolean"
    assert schema["simple_select"]["type"] == "select"
    assert schema["simple_textarea"]["type"] == "textarea"
    assert schema["simple_array"]["type"] == "array"
    assert schema["single_file"]["type"] == "file"
    assert schema["multi_file"]["type"] == "file_array"
    assert schema["advanced_group"]["type"] == "group"
    assert schema["deep_group_demo"]["type"] == "group"
    assert schema["object_array_demo"]["type"] == "object_array"
    assert schema["table_demo"]["type"] == "table"
    assert schema["advanced_group"]["fields"]["runtime_policy"]["type"] == "group"
    assert schema["object_array_demo"]["fields"]["advanced"]["type"] == "group"
    assert schema["object_array_demo"]["fields"]["attachment"]["type"] == "file"
    assert schema["table_demo"]["fields"]["role"]["type"] == "select"
    assert schema["table_demo"]["fields"]["remark"]["type"] == "textarea"
    assert schema["table_demo"]["fields"]["resource"]["type"] == "file"


def test_settings_ui_showcase_defaults_normalize_cleanly():
    manifest = load_plugin_manifest("plugins/settings_ui_showcase")

    normalized = normalize_plugin_config_by_schema(
        manifest["default_config"],
        manifest["config_schema"],
        manifest["default_config"],
    )

    assert normalized["simple_text"] == "这是一段单行文本"
    assert normalized["simple_number"] == 42
    assert normalized["simple_switch"] is True
    assert normalized["simple_select"] == "balanced"
    assert normalized["simple_array"] == ["管理员 10001", "管理员 10002"]
    assert normalized["single_file"] is None
    assert normalized["multi_file"] == []
    assert normalized["advanced_group"]["enabled"] is True
    assert normalized["advanced_group"]["runtime_policy"]["window_mode"] == "rolling"
    assert normalized["deep_group_demo"]["strategy"]["mode"] == "mirror"
    assert normalized["deep_group_demo"]["notes"]["owners"] == ["10001", "10002"]
    assert normalized["object_array_demo"][0]["keyword"] == "早上好"
    assert normalized["object_array_demo"][0]["advanced"]["priority"] == 1
    assert normalized["table_demo"][0]["score"] == 95
    assert normalized["table_demo"][0]["role"] == "owner"

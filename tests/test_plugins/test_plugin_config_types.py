from src.ui.api import normalize_plugin_config_by_schema


def test_normalize_plugin_config_supports_string_textarea_select():
    schema = {
        "title": {"type": "string", "default": "hello"},
        "desc": {"type": "textarea", "default": "body"},
        "mode": {"type": "select", "default": "fast"},
    }
    defaults = {
        "title": "hello",
        "desc": "body",
        "mode": "fast",
    }
    config = {
        "title": "world",
        "desc": "multiline text",
        "mode": "slow",
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["title"] == "world"
    assert normalized["desc"] == "multiline text"
    assert normalized["mode"] == "slow"


def test_normalize_plugin_config_supports_number_boolean_and_array():
    schema = {
        "port": {"type": "number", "default": 3000},
        "enabled": {"type": "boolean", "default": False},
        "admins": {"type": "array", "default": []},
    }
    defaults = {
        "port": 3000,
        "enabled": False,
        "admins": [],
    }
    config = {
        "port": "8080",
        "enabled": "true",
        "admins": "10001, 10002\n10003",
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["port"] == 8080.0
    assert normalized["enabled"] is True
    assert normalized["admins"] == ["10001", "10002", "10003"]


def test_normalize_plugin_config_supports_file_and_file_array_passthrough():
    schema = {
        "avatar": {"type": "file"},
        "attachments": {"type": "file_array"},
    }
    defaults = {
        "avatar": None,
        "attachments": [],
    }
    config = {
        "avatar": {"file_key": "plugin_config_a.png", "mimetype": "image/png"},
        "attachments": [
            {"file_key": "plugin_config_b.txt", "mimetype": "text/plain"},
            {"file_key": "plugin_config_c.txt", "mimetype": "text/plain"},
        ],
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["avatar"]["file_key"] == "plugin_config_a.png"
    assert len(normalized["attachments"]) == 2


def test_normalize_plugin_config_uses_schema_default_for_invalid_number():
    schema = {
        "retries": {"type": "number", "default": 5},
    }
    defaults = {
        "retries": 5,
    }
    config = {
        "retries": None,
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["retries"] == 5


def test_normalize_plugin_config_supports_group():
    schema = {
        "advanced": {
            "type": "group",
            "fields": {
                "enabled": {"type": "boolean", "default": False},
                "mode": {"type": "select", "default": "safe"},
            },
        }
    }
    defaults = {
        "advanced": {
            "enabled": False,
            "mode": "safe",
        }
    }
    config = {
        "advanced": {
            "enabled": True,
            "mode": "fast",
        }
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["advanced"]["enabled"] is True
    assert normalized["advanced"]["mode"] == "fast"


def test_normalize_plugin_config_supports_object_array_and_table():
    schema = {
        "rules": {
            "type": "object_array",
            "fields": {
                "keyword": {"type": "string", "default": ""},
                "enabled": {"type": "boolean", "default": True},
            },
        },
        "matrix": {
            "type": "table",
            "fields": {
                "name": {"type": "string", "default": ""},
                "score": {"type": "number", "default": 0},
            },
        },
    }
    defaults = {"rules": [], "matrix": []}
    config = {
        "rules": [{"keyword": "hi", "enabled": "false"}],
        "matrix": [{"name": "alice", "score": "99"}],
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["rules"][0]["keyword"] == "hi"
    assert normalized["rules"][0]["enabled"] is False
    assert normalized["matrix"][0]["name"] == "alice"
    assert normalized["matrix"][0]["score"] == 99.0


def test_normalize_plugin_config_supports_nested_group_inside_object_array_and_table():
    schema = {
        "rules": {
            "type": "object_array",
            "fields": {
                "keyword": {"type": "string", "default": ""},
                "advanced": {
                    "type": "group",
                    "fields": {
                        "priority": {"type": "number", "default": 1},
                        "silent": {"type": "boolean", "default": False},
                    },
                },
            },
        },
        "matrix": {
            "type": "table",
            "fields": {
                "name": {"type": "string", "default": ""},
                "role": {
                    "type": "select",
                    "default": "member",
                },
                "asset": {"type": "file"},
            },
        },
    }
    defaults = {"rules": [], "matrix": []}
    config = {
        "rules": [{"keyword": "demo", "advanced": {"priority": "7", "silent": "true"}}],
        "matrix": [
            {
                "name": "alice",
                "role": "owner",
                "asset": {"file_key": "plugin_config_demo.png", "mimetype": "image/png"},
            }
        ],
    }

    normalized = normalize_plugin_config_by_schema(config, schema, defaults)

    assert normalized["rules"][0]["keyword"] == "demo"
    assert normalized["rules"][0]["advanced"]["priority"] == 7.0
    assert normalized["rules"][0]["advanced"]["silent"] is True
    assert normalized["matrix"][0]["name"] == "alice"
    assert normalized["matrix"][0]["role"] == "owner"
    assert normalized["matrix"][0]["asset"]["file_key"] == "plugin_config_demo.png"

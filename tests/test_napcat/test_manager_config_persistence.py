import json

from src.napcat import manager as manager_module
from src.napcat.manager import NapCatManager


def make_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(manager_module, "get_runtime_base_dir", lambda: tmp_path)
    return NapCatManager()


def test_config_center_falls_back_when_json_invalid(tmp_path, monkeypatch):
    mgr = make_manager(tmp_path, monkeypatch)
    config_dir = mgr.work_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "webui.json").write_text("{bad", encoding="utf-8")

    config = mgr.get_config_center()

    assert config["webui"]["host"] == "::"
    assert config["webui"]["port"] == 6099


def test_save_config_center_persists_json_files(tmp_path, monkeypatch):
    mgr = make_manager(tmp_path, monkeypatch)
    payload = {
        "webui": {"host": "127.0.0.1", "port": 6100, "token": "secret"},
        "napcat": {"fileLog": True, "consoleLog": False},
        "onebot": {"network": {"httpServers": [], "websocketServers": [], "websocketClients": []}},
    }

    result = mgr.save_config_center(payload)

    assert result["ok"] is True
    assert sorted(result["saved"]) == ["napcat", "onebot", "webui"]

    config_dir = mgr.work_dir / "config"
    assert json.loads((config_dir / "webui.json").read_text(encoding="utf-8")) == payload["webui"]
    assert json.loads((config_dir / "napcat.json").read_text(encoding="utf-8")) == payload["napcat"]
    assert json.loads((config_dir / "onebot11.json").read_text(encoding="utf-8")) == payload["onebot"]

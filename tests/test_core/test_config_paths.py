from pathlib import Path

from src.core import config as config_module


def test_get_runtime_base_dir_uses_executable_dir_when_frozen(monkeypatch):
    exe_path = Path("C:/fake/app/XiaoyiQQ.exe")
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "executable", str(exe_path), raising=False)

    base_dir = config_module.get_runtime_base_dir()

    assert base_dir == exe_path.parent


def test_get_config_file_path_prefers_runtime_base(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_cfg = runtime_dir / "config.toml"
    runtime_cfg.write_text("[app]\nname='runtime'\n", encoding="utf-8")

    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir(parents=True, exist_ok=True)
    (cwd_dir / "config.toml").write_text("[app]\nname='cwd'\n", encoding="utf-8")

    monkeypatch.setattr(config_module, "get_runtime_base_dir", lambda: runtime_dir)
    monkeypatch.chdir(cwd_dir)

    cfg_path = config_module.get_config_file_path()

    assert cfg_path == runtime_cfg


def test_get_config_file_path_falls_back_to_cwd(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir(parents=True, exist_ok=True)
    cwd_cfg = cwd_dir / "config.toml"
    cwd_cfg.write_text("[app]\nname='cwd'\n", encoding="utf-8")

    monkeypatch.setattr(config_module, "get_runtime_base_dir", lambda: runtime_dir)
    monkeypatch.chdir(cwd_dir)

    cfg_path = config_module.get_config_file_path()

    assert cfg_path == cwd_cfg

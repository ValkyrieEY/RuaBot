from pathlib import Path

from src.plugins.runtime import main as runtime_main


def test_get_runtime_base_dir_uses_executable_dir_when_frozen(monkeypatch):
    exe_path = Path("C:/fake/app/XiaoyiQQ.exe")
    monkeypatch.setattr(runtime_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_main.sys, "executable", str(exe_path), raising=False)

    base_dir = runtime_main._get_runtime_base_dir()

    assert base_dir == exe_path.parent


def test_plugin_runtime_uses_runtime_base_dir(monkeypatch, tmp_path):
    runtime_base = tmp_path / "runtime"
    monkeypatch.setattr(runtime_main, "RUNTIME_BASE_DIR", runtime_base)

    runtime = runtime_main.PluginRuntime()

    assert runtime.base_dir == runtime_base
    assert runtime.plugins_dir == (runtime_base / "plugins").resolve()

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


def test_add_import_path_moves_existing_path_to_front(monkeypatch, tmp_path):
    first = str((tmp_path / "first").resolve())
    deps = tmp_path / "deps"
    deps.mkdir()
    deps_str = str(deps.resolve())
    monkeypatch.setattr(runtime_main.sys, "path", [first, deps_str])

    added = runtime_main.add_import_path(deps)

    assert added == deps_str
    assert runtime_main.sys.path[:2] == [deps_str, first]


def test_plugin_runtime_activates_plugin_dependency_path(monkeypatch, tmp_path):
    deps = tmp_path / "plugins" / ".deps" / "demo"
    deps.mkdir(parents=True)
    other = str((tmp_path / "other").resolve())
    deps_str = str(deps.resolve())
    monkeypatch.setattr(runtime_main.sys, "path", [other])

    runtime = runtime_main.PluginRuntime()
    runtime.plugin_dependency_paths["XQNEXT/demo"] = deps_str
    runtime._activate_plugin_import_path("XQNEXT/demo")

    assert runtime_main.sys.path[0] == deps_str

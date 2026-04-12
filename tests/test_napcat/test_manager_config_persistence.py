import os
import tomllib

from src.napcat.manager import NapCatManager


def test_set_napcat_config_fallback_when_toml_invalid(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[bad\ninvalid", encoding="utf-8")

    mgr = NapCatManager(config_path=config_path)
    assert mgr._set_napcat_config({"install_path": "C:/NapCatQQ"}) is True

    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert parsed["napcat"]["install_path"] == "C:/NapCatQQ"


def test_set_install_path_normalizes_and_persists(tmp_path):
    install_dir = tmp_path / "NapCatQQ"
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "napcat.bat").write_text("", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")

    mgr = NapCatManager(config_path=config_path)
    input_path = str(install_dir / ".")
    result = mgr.set_install_path(input_path)

    assert result["ok"] is True

    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert parsed["napcat"]["install_path"] == os.path.normpath(input_path)

import sys
import asyncio

import pytest

from src.core.sandbox.booters.local import LocalShellComponent


@pytest.mark.asyncio
async def test_local_shell_preserves_working_directory(tmp_path):
    (tmp_path / "child").mkdir()
    shell = LocalShellComponent(tmp_path)

    try:
        first = await shell.exec("cd child")
        second = await shell.exec("cd")
    finally:
        await shell.shutdown()

    assert first["success"] is True
    assert second["success"] is True
    assert second["cwd"] == str((tmp_path / "child").resolve())
    assert second["stdout"].strip() == str((tmp_path / "child").resolve())


@pytest.mark.asyncio
async def test_local_shell_preserves_environment_variables(tmp_path):
    shell = LocalShellComponent(tmp_path)

    if sys.platform == "win32":
        set_command = "set XQNEXT_SANDBOX_STATE_TEST=hello"
        echo_command = "echo %XQNEXT_SANDBOX_STATE_TEST%"
    else:
        set_command = "export XQNEXT_SANDBOX_STATE_TEST=hello"
        echo_command = "echo $XQNEXT_SANDBOX_STATE_TEST"

    try:
        first = await shell.exec(set_command)
        second = await shell.exec(echo_command)
    finally:
        await shell.shutdown()

    assert first["success"] is True
    assert second["success"] is True
    assert second["stdout"].strip() == "hello"


@pytest.mark.asyncio
async def test_local_shell_reuses_process_between_commands(tmp_path):
    shell = LocalShellComponent(tmp_path)

    try:
        first = await shell.exec("echo first")
        first_pid = shell._process.pid if shell._process else None
        second = await shell.exec("echo second")
        second_pid = shell._process.pid if shell._process else None
    finally:
        await shell.shutdown()

    assert first["success"] is True
    assert second["success"] is True
    assert first_pid is not None
    assert first_pid == second_pid


@pytest.mark.asyncio
async def test_local_shell_closes_after_idle_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalShellComponent, "IDLE_TIMEOUT_SECONDS", 0.05)
    shell = LocalShellComponent(tmp_path)

    try:
        result = await shell.exec("echo idle")
        assert result["success"] is True
        assert shell._process is not None

        await asyncio.sleep(0.2)
        assert shell._process is None
    finally:
        await shell.shutdown()

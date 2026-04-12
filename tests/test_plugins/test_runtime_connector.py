import pytest
import sys
from unittest.mock import MagicMock

from src.plugins.runtime.connector import PluginRuntimeConnector


class _FakeAsyncStdin:
    def __init__(self, write_error=None, closing=False):
        self._write_error = write_error
        self._closing = closing

    def is_closing(self):
        return self._closing

    def write(self, _data):
        if self._write_error:
            raise self._write_error

    async def drain(self):
        return


class _FakeAsyncStdout:
    async def readline(self):
        return b""


class _FakeProcess:
    def __init__(self, stdin=None, stdout=None, stderr=None, returncode=None):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class _FakeSyncWaitProcess:
    def __init__(self):
        self.wait_called = False

    def wait(self):
        self.wait_called = True
        return 0


class _FakeAsyncWaitProcess:
    def __init__(self):
        self.wait_called = False

    async def wait(self):
        self.wait_called = True
        return 0


@pytest.fixture
def connector():
    return PluginRuntimeConnector(
        event_bus=MagicMock(),
        db_manager=MagicMock(),
        app=None,
    )


@pytest.mark.asyncio
async def test_send_to_runtime_marks_disconnected_when_stdin_is_closing(connector):
    connector.runtime_process = _FakeProcess(
        stdin=_FakeAsyncStdin(closing=True),
        returncode=None,
    )
    connector.is_running = True

    sent = await connector._send_to_runtime({"type": "heartbeat", "data": {}})

    assert sent is False
    assert connector.is_running is False


@pytest.mark.asyncio
async def test_send_to_runtime_handles_closed_transport_runtime_error(connector):
    connector.runtime_process = _FakeProcess(
        stdin=_FakeAsyncStdin(write_error=RuntimeError("handler is closed")),
        returncode=None,
    )
    connector.is_running = True

    sent = await connector._send_to_runtime({"type": "heartbeat", "data": {}})

    assert sent is False
    assert connector.is_running is False


@pytest.mark.asyncio
async def test_read_runtime_output_stops_on_stdout_eof(connector):
    connector.runtime_process = _FakeProcess(
        stdout=_FakeAsyncStdout(),
        returncode=None,
    )
    connector.is_running = True

    await connector._read_runtime_output()

    assert connector.is_running is False


def test_build_runtime_command_uses_runtime_mode_when_frozen(connector, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    cmd = connector._build_runtime_command()

    assert cmd == [sys.executable, "--runtime-mode"]


@pytest.mark.asyncio
async def test_wait_for_runtime_process_supports_sync_wait(connector):
    process = _FakeSyncWaitProcess()
    connector.runtime_process = process

    code = await connector._wait_for_runtime_process()

    assert code == 0
    assert process.wait_called is True


@pytest.mark.asyncio
async def test_wait_for_runtime_process_supports_async_wait(connector):
    process = _FakeAsyncWaitProcess()
    connector.runtime_process = process

    code = await connector._wait_for_runtime_process()

    assert code == 0
    assert process.wait_called is True

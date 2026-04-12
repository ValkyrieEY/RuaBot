from src.ui import api as api_module


def test_expected_onebot_connectivity_error_detects_common_message():
    err = RuntimeError("Failed to connect to OneBot HTTP API at http://localhost:5700")
    assert api_module._is_expected_onebot_connectivity_error(err) is True


def test_expected_onebot_connectivity_error_ignores_unrelated_error():
    err = ValueError("schema validation failed")
    assert api_module._is_expected_onebot_connectivity_error(err) is False


def test_connectivity_log_rate_limiter(monkeypatch):
    monkeypatch.setattr(api_module, "_onebot_login_info_last_connectivity_log_at", 0.0)

    assert api_module._should_log_onebot_connectivity_issue(now_ts=100.0) is True
    assert api_module._should_log_onebot_connectivity_issue(now_ts=120.0) is False
    assert api_module._should_log_onebot_connectivity_issue(now_ts=161.0) is True

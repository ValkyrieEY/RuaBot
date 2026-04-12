#!/usr/bin/env python3

import asyncio
import sys

RUNTIME_MODE_FLAG = "--runtime-mode"


def _ensure_windows_proactor() -> None:
    if sys.platform == "win32" and sys.version_info >= (3, 13):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def _run_framework_main() -> None:
    _ensure_windows_proactor()
    if sys.platform == "win32" and sys.version_info >= (3, 13):
        print("[启动] 已设置 ProactorEventLoop 策略 (Windows + Python 3.13 兼容)")
    from src.main import main

    main()


def _run_runtime_main() -> None:
    _ensure_windows_proactor()
    from src.plugins.runtime.main import main as runtime_main

    asyncio.run(runtime_main())


if __name__ == "__main__":
    if RUNTIME_MODE_FLAG in sys.argv[1:]:
        _run_runtime_main()
    else:
        _run_framework_main()

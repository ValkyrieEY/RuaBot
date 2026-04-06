#!/usr/bin/env python3

import sys
import asyncio

if sys.platform == 'win32' and sys.version_info >= (3, 13):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[启动] 已设置 ProactorEventLoop 策略 (Windows + Python 3.13 兼容)")

from src.main import main

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""启动脚本 - 确保在 Windows + Python 3.13 上正确设置事件循环策略"""

import sys
import asyncio

# Windows + Python 3.13 兼容性: 在导入任何其他模块之前设置 ProactorEventLoop 策略
if sys.platform == 'win32' and sys.version_info >= (3, 13):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[启动] 已设置 ProactorEventLoop 策略 (Windows + Python 3.13 兼容)")

# 现在导入并运行主程序
from src.main import main

if __name__ == "__main__":
    main()


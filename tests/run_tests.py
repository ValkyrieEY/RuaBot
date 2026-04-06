12#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ruabot 测试套件入口

此脚本提供交互式菜单用于运行各种测试套件。
所有测试按模块组织，可以单独运行或分组运行。
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class TestRunner:
    """Ruabot 交互式测试运行器。"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = Path(__file__).parent
        self.test_modules: Dict[str, Dict[str, str]] = {
            "1": {
                "name": "核心模块测试",
                "description": "测试核心功能，包括应用、事件总线、配置、数据库、存储和日志",
                "path": "tests/test_core/",
                "command": "pytest tests/test_core/ -v --tb=short"
            },
            "2": {
                "name": "AI 模块测试",
                "description": "测试 AI 功能，包括 ai_manager、model_manager、llm_client 和 message_handler",
                "path": "tests/test_ai/",
                "command": "pytest tests/test_ai/ -v --tb=short"
            },
            "3": {
                "name": "协议模块测试",
                "description": "测试协议适配器，包括 OneBot、基础协议和消息处理",
                "path": "tests/test_protocol/",
                "command": "pytest tests/test_protocol/ -v --tb=short"
            },
            "4": {
                "name": "路由模块测试",
                "description": "测试路由功能，包括规则、处理器和消息路由",
                "path": "tests/test_router/",
                "command": "pytest tests/test_router/ -v --tb=short"
            },
            "5": {
                "name": "安全模块测试",
                "description": "测试安全功能，包括认证、权限和访问控制",
                "path": "tests/test_security/",
                "command": "pytest tests/test_security/ -v --tb=short"
            },
            "6": {
                "name": "插件模块测试",
                "description": "测试插件系统，包括拦截器、运行时和插件生命周期",
                "path": "tests/test_plugins/",
                "command": "pytest tests/test_plugins/ -v --tb=short"
            },
            "7": {
                "name": "运行所有测试",
                "description": "按顺序执行所有测试套件",
                "path": "tests/",
                "command": "pytest tests/ -v --tb=short"
            },
            "8": {
                "name": "运行所有测试并生成覆盖率报告",
                "description": "执行所有测试并生成代码覆盖率报告",
                "path": "tests/",
                "command": "pytest tests/ -v --cov=src --cov-report=html --cov-report=term"
            },
            "9": {
                "name": "仅运行失败的测试",
                "description": "仅重新运行上次运行中失败的测试",
                "path": "tests/",
                "command": "pytest tests/ --lf -v --tb=short"
            },
            "10": {
                "name": "列出所有测试",
                "description": "显示所有可用的测试但不运行",
                "path": "tests/",
                "command": "pytest tests/ --collect-only"
            },
            "11": {
                "name": "并行运行测试",
                "description": "使用 pytest-xdist 并行执行测试（更快）",
                "path": "tests/",
                "command": "pytest tests/ -v --tb=short -n auto"
            },
            "12": {
                "name": "运行测试并显示详细输出",
                "description": "执行测试并显示非常详细的输出，包括打印语句",
                "path": "tests/",
                "command": "pytest tests/ -vv --tb=long -s"
            },
            "0": {
                "name": "退出",
                "description": "退出测试运行器",
                "path": None,
                "command": None
            }
        }

        self.quick_tests: Dict[str, Dict[str, str]] = {
            "1": {
                "name": "冒烟测试",
                "description": "快速检查关键功能",
                "command": "pytest tests/ -v -k smoke --tb=short"
            },
            "2": {
                "name": "仅运行单元测试",
                "description": "仅运行单元测试（不包括集成测试）",
                "command": "pytest tests/ -v -m unit --tb=short"
            },
            "3": {
                "name": "仅运行集成测试",
                "description": "仅运行集成测试",
                "command": "pytest tests/ -v -m integration --tb=short"
            },
            "4": {
                "name": "仅运行快速测试",
                "description": "仅运行快速测试（跳过慢速测试）",
                "command": "pytest tests/ -v -m \"not slow\" --tb=short"
            },
            "0": {
                "name": "返回主菜单",
                "description": "返回主测试菜单",
                "command": None
            }
        }

    def print_banner(self):
        """打印测试运行器横幅。"""
        print("\n" + "=" * 70)
        print(" " * 15 + "Ruabot 测试套件")
        print(" " * 12 + "综合测试框架")
        print("=" * 70)
        print()

    def print_menu(self):
        """打印主测试菜单。"""
        print("\n" + "-" * 70)
        print("可用测试套件：")
        print("-" * 70)

        for key, info in self.test_modules.items():
            if key == "0":
                print()
            print(f"  [{key}] {info['name']}")
            print(f"       {info['description']}")

        print("-" * 70)

    def print_quick_menu(self):
        """打印快速测试菜单。"""
        print("\n" + "-" * 70)
        print("快速测试选项：")
        print("-" * 70)

        for key, info in self.quick_tests.items():
            print(f"  [{key}] {info['name']}")
            print(f"       {info['description']}")

        print("-" * 70)

    def print_test_info(self, module_key: str):
        """打印测试模块的详细信息。"""
        if module_key not in self.test_modules:
            print(f"\n错误：无效的测试模块键 '{module_key}'")
            return

        info = self.test_modules[module_key]
        print("\n" + "=" * 70)
        print(f"测试模块：{info['name']}")
        print("=" * 70)
        print(f"\n描述：")
        print(f"  {info['description']}")
        print(f"\n路径：")
        print(f"  {info['path']}")
        print(f"\n命令：")
        print(f"  {info['command']}")
        print(f"\n测试文件：")

        test_path = self.test_dir / info['path'].lstrip('tests/')
        if test_path.exists() and test_path.is_dir():
            test_files = list(test_path.glob("test_*.py"))
            if test_files:
                for test_file in sorted(test_files):
                    print(f"  - {test_file.name}")
            else:
                print("  此目录中未找到测试文件")
        else:
            print("  测试目录不存在")

        print("=" * 70)

    def run_test(self, command: str) -> int:
        """运行测试命令并返回退出码。"""
        print("\n" + "=" * 70)
        print(f"正在运行：{command}")
        print("=" * 70 + "\n")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.project_root,
                check=False
            )
            return result.returncode
        except KeyboardInterrupt:
            print("\n\n测试执行被用户中断")
            return 130
        except Exception as e:
            print(f"\n\n运行测试时出错：{e}")
            return 1

    def check_dependencies(self) -> bool:
        """检查是否安装了所需的依赖项。"""
        print("\n正在检查测试依赖...")

        required_packages = [
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
        ]

        missing_packages = []

        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"  [已安装] {package}")
            except ImportError:
                print(f"  [缺失] {package}")
                missing_packages.append(package)

        if missing_packages:
            print("\n检测到缺失的依赖项：")
            for package in missing_packages:
                print(f"  - {package}")
            print("\n请安装缺失的依赖项：")
            print(f"  pip install {' '.join(missing_packages)}")
            return False

        print("\n所有依赖项已安装。")
        return True

    def main(self):
        """测试运行器的主入口点。"""
        self.print_banner()

        # 检查依赖项
        if not self.check_dependencies():
            print("\n没有必需的依赖项无法继续。")
            return 1

        while True:
            self.print_menu()
            choice = input("\n选择测试套件 (0-12) 或输入 'info <数字>' 查看详情：").strip()

            # 处理 info 命令
            if choice.lower().startswith("info "):
                module_key = choice[5:].strip()
                self.print_test_info(module_key)
                input("\n按 Enter 继续...")
                continue

            # 处理快速测试
            if choice.lower() == "quick" or choice.lower() == "q":
                self.run_quick_menu()
                continue

            # 处理主菜单选择
            if choice == "0":
                print("\n退出测试运行器。再见！")
                break

            if choice in self.test_modules:
                info = self.test_modules[choice]
                if info['command']:
                    exit_code = self.run_test(info['command'])

                    if exit_code == 0:
                        print("\n" + "=" * 70)
                        print("所有测试通过！")
                        print("=" * 70)
                    else:
                        print("\n" + "=" * 70)
                        print(f"测试完成，退出码：{exit_code}")
                        print("=" * 70)

                    input("\n按 Enter 继续...")
            else:
                print(f"\n无效的选择：{choice}")
                print("请输入 0 到 12 之间的数字，或输入 'info <数字>' 查看详情")
                input("按 Enter 继续...")

        return 0

    def run_quick_menu(self):
        """运行快速测试菜单。"""
        while True:
            self.print_quick_menu()
            choice = input("\n选择快速测试选项 (0-4)：").strip()

            if choice == "0":
                break

            if choice in self.quick_tests:
                info = self.quick_tests[choice]
                if info['command']:
                    exit_code = self.run_test(info['command'])

                    if exit_code == 0:
                        print("\n" + "=" * 70)
                        print("测试通过！")
                        print("=" * 70)
                    else:
                        print("\n" + "=" * 70)
                        print(f"测试完成，退出码：{exit_code}")
                        print("=" * 70)

                    input("\n按 Enter 继续...")
            else:
                print(f"\n无效的选择：{choice}")
                input("按 Enter 继续...")


def main():
    """脚本的入口点。"""
    runner = TestRunner()
    try:
        return runner.main()
    except KeyboardInterrupt:
        print("\n\n测试运行器被用户中断")
        return 130
    except Exception as e:
        print(f"\n\n意外错误：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
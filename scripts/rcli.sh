#!/bin/bash

set -euo pipefail

echo "[DEPRECATED] rcli 已弃用。请改用 ruabot-cli（命令: ruabot）。"

if command -v ruabot >/dev/null 2>&1; then
    echo "[INFO] 正在转发到 ruabot $*"
    exec ruabot "$@"
fi

echo "[ERROR] 未找到 ruabot 命令。请先安装新版 CLI："
echo "        npm install -g ruabot-cli"
exit 1

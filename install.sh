#!/bin/bash
################################################################################
# RuaBot CLI 安装脚本（Linux / macOS）
# 目标：
# 1) 仅安装项目隔离的 Node.js 运行时
# 2) 使用该运行时安装新版 ruabot-cli
# 3) 旧版 rcli 维护脚本已弃用
################################################################################

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="${RUABOT_INSTALL_DIR:-$HOME/RuaBot}"
RUNTIME_DIR="$PROJECT_DIR/.runtime"
NODE_VERSION="${RUABOT_NODE_VERSION:-24.12.0}"
NPM_PREFIX="$PROJECT_DIR/.npm-global"
NODE_HOME=""
NODE_BIN=""
NPM_BIN_DIR="$NPM_PREFIX/bin"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

ui_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

detect_platform() {
    local os_name
    local arch_name
    os_name="$(uname -s)"
    arch_name="$(uname -m)"

    case "$os_name" in
        Linux) OS_DIST="linux" ;;
        Darwin) OS_DIST="darwin" ;;
        *)
            log_error "不支持的系统: $os_name（仅支持 Linux/macOS）"
            exit 1
            ;;
    esac

    case "$arch_name" in
        x86_64|amd64) ARCH_DIST="x64" ;;
        arm64|aarch64) ARCH_DIST="arm64" ;;
        *)
            log_error "不支持的架构: $arch_name（支持 x64/arm64）"
            exit 1
            ;;
    esac

    NODE_DIST="${OS_DIST}-${ARCH_DIST}"
    log_info "检测到平台: ${OS_DIST} ${ARCH_DIST}"
}

download_file() {
    local url="$1"
    local dest="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --retry-delay 2 --progress-bar -o "$dest" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget --tries=3 --show-progress -O "$dest" "$url"
    else
        log_error "未找到 curl/wget，请先安装其中之一"
        exit 1
    fi
}

install_isolated_node() {
    mkdir -p "$RUNTIME_DIR"

    local archive="node-v${NODE_VERSION}-${NODE_DIST}.tar.xz"
    local url="https://nodejs.org/dist/v${NODE_VERSION}/${archive}"
    local extract_dir="$RUNTIME_DIR/node-v${NODE_VERSION}-${NODE_DIST}"
    local tmp_archive="/tmp/${archive}"

    if [ -x "$extract_dir/bin/node" ]; then
        log_info "检测到已安装的隔离 Node.js: $extract_dir"
    else
        log_info "下载 Node.js v${NODE_VERSION} ..."
        download_file "$url" "$tmp_archive"

        log_info "解压 Node.js ..."
        tar -xJf "$tmp_archive" -C "$RUNTIME_DIR"
        rm -f "$tmp_archive"
    fi

    NODE_HOME="$extract_dir"
    NODE_BIN="$NODE_HOME/bin"

    if [ ! -x "$NODE_BIN/node" ] || [ ! -x "$NODE_BIN/npm" ]; then
        log_error "Node.js 安装异常，缺少 node/npm 可执行文件"
        exit 1
    fi

    log_success "隔离 Node.js 就绪: $("$NODE_BIN/node" --version)"
    log_success "隔离 npm 就绪: v$("$NODE_BIN/npm" --version)"
}

install_cli() {
    mkdir -p "$NPM_PREFIX"

    log_info "使用隔离 npm 安装 ruabot-cli@latest ..."
    NPM_CONFIG_PREFIX="$NPM_PREFIX" "$NODE_BIN/npm" install -g ruabot-cli@latest

    if [ ! -x "$NPM_BIN_DIR/ruabot" ]; then
        log_error "未找到 ruabot 可执行文件: $NPM_BIN_DIR/ruabot"
        exit 1
    fi

    log_success "ruabot-cli 安装完成: $("$NPM_BIN_DIR/ruabot" --version 2>/dev/null || echo '已安装')"
}

append_path_hint() {
    local shell_rc=""
    local path_line="export PATH=\"$NPM_BIN_DIR:\$PATH\""

    if [ -n "${BASH_VERSION:-}" ]; then
        shell_rc="$HOME/.bashrc"
    elif [ -n "${ZSH_VERSION:-}" ]; then
        shell_rc="$HOME/.zshrc"
    fi

    if [ -n "$shell_rc" ] && [ -f "$shell_rc" ]; then
        if ! grep -q "# RuaBot CLI Path" "$shell_rc"; then
            {
                echo ""
                echo "# RuaBot CLI Path"
                echo "$path_line"
            } >> "$shell_rc"
            log_info "已写入 PATH 到 $shell_rc"
            log_info "请执行: source $shell_rc"
        fi
    fi

    if [[ ":$PATH:" != *":$NPM_BIN_DIR:"* ]]; then
        log_warning "当前 PATH 未包含 $NPM_BIN_DIR"
        log_info "临时生效命令: export PATH=\"$NPM_BIN_DIR:\$PATH\""
    fi
}

write_runtime_env_file() {
    cat > "$PROJECT_DIR/.ruabot-node.env" << EOF
# RuaBot Node runtime metadata
PROJECT_DIR="$PROJECT_DIR"
NODE_VERSION="$NODE_VERSION"
NODE_HOME="$NODE_HOME"
NPM_PREFIX="$NPM_PREFIX"
INSTALL_DATE="$(date +%Y-%m-%d\ %H:%M:%S)"
EOF
    log_success "已写入运行时信息: $PROJECT_DIR/.ruabot-node.env"
}

main() {
    ui_header "RuaBot CLI 安装"

    log_info "安装目录: $PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"

    detect_platform
    install_isolated_node
    install_cli
    append_path_hint
    write_runtime_env_file

    echo ""
    log_success "安装完成"
    echo ""
    echo -e "${CYAN}后续说明:${NC}"
    echo -e "  1) 旧版 ${YELLOW}rcli${NC} 维护脚本已弃用"
    echo -e "  2) 请改用 ${YELLOW}ruabot${NC} 管理框架"
    echo -e "  3) 首次使用可执行: ${YELLOW}ruabot framework install --path \"$PROJECT_DIR\"${NC}"
    echo ""
    echo -e "${CYAN}常用命令:${NC}"
    echo -e "  ${YELLOW}ruabot help${NC}"
    echo -e "  ${YELLOW}ruabot framework list${NC}"
    echo -e "  ${YELLOW}ruabot framework install --path /your/path/RuaBot${NC}"
    echo ""
}

main "$@"

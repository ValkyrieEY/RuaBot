#!/bin/bash
################################################################################
# RuaBot 一键安装脚本
# 仓库: github.com/ValkyrieEY/RuaBot
# 用法: bash <(curl -fsSL https://raw.githubusercontent.com/ValkyrieEY/RuaBot/main/install.sh)
################################################################################

# 不立即退出，先显示错误
set -o pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
REPO_URL="https://github.com/ValkyrieEY/RuaBot.git"
INSTALL_DIR="$HOME/RuaBot"
PYTHON_VERSION="3.13"
NODE_VERSION="24.12.0"

# 日志函数
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

# 检测操作系统
detect_os() {
    log_info "检测操作系统类型..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$ID
            OS_VERSION=$VERSION_ID
            log_info "检测到操作系统: $OS $OS_VERSION"
        else
            OS="linux"
            log_warning "无法读取 /etc/os-release，使用默认 Linux 配置"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        log_info "检测到操作系统: macOS"
    else
        OS="linux"
        log_warning "未知操作系统类型 ($OSTYPE)，使用 Linux 配置"
    fi
    
    return 0
}

# 检查并安装 Git
check_and_install_git() {
    log_info "检查 Git 是否已安装..."
    if command -v git &> /dev/null; then
        log_success "Git 已安装: $(git --version)"
        return 0
    fi

    log_warning "Git 未安装，正在自动安装..."
    
    case "$OS" in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y git
            ;;
        centos|rhel|fedora)
            sudo yum install -y git
            ;;
        macos)
            if command -v brew &> /dev/null; then
                brew install git
            else
                log_error "请先安装 Homebrew 或手动安装 Git"
                exit 1
            fi
            ;;
        *)
            log_error "不支持的操作系统，请手动安装 Git"
            exit 1
            ;;
    esac

    if command -v git &> /dev/null; then
        log_success "Git 安装成功"
    else
        log_error "Git 安装失败"
        exit 1
    fi
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."
    
    case "$OS" in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y build-essential libssl-dev zlib1g-dev \
                libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
                libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
                libffi-dev liblzma-dev
            ;;
        centos|rhel|fedora)
            sudo yum groupinstall -y "Development Tools"
            sudo yum install -y gcc zlib-devel bzip2 bzip2-devel readline-devel \
                sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel
            ;;
        macos)
            if ! command -v brew &> /dev/null; then
                log_warning "安装 Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install openssl readline sqlite3 xz zlib
            ;;
        *)
            log_warning "未知操作系统，跳过依赖安装"
            ;;
    esac
    
    log_success "系统依赖安装完成"
}

# 克隆仓库（带重试机制）
clone_with_retry() {
    local repo_url=$1
    local target_dir=$2
    local retry_count=0
    local max_retries=5
    local clone_success=false
    
    # 配置 Git 以处理 TLS 问题
    git config --global http.sslVerify true 2>/dev/null || true
    git config --global http.postBuffer 524288000 2>/dev/null || true
    
    while [ $retry_count -lt $max_retries ] && [ "$clone_success" = false ]; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -gt 1 ]; then
            log_info "第 $retry_count 次尝试克隆仓库（共 $max_retries 次）..."
            sleep 3
        fi
        
        log_info "正在克隆仓库..."
        if git clone "$repo_url" "$target_dir" 2>&1 | while IFS= read -r line; do
            if [[ "$line" =~ (Cloning|remote:|Receiving|Resolving|Checking out) ]]; then
                echo -e "${BLUE}[INFO]${NC} $line"
            elif [[ "$line" =~ (fatal|error|Error|ERROR) ]]; then
                echo -e "${YELLOW}[WARN]${NC} $line"
            fi
        done && [ -d "$target_dir/.git" ]; then
            clone_success=true
            return 0
        else
            # 清理失败的克隆
            rm -rf "$target_dir" 2>/dev/null || true
            
            if [ $retry_count -lt $max_retries ]; then
                log_warning "克隆失败，将在 3 秒后自动重试..."
            else
                log_error "克隆失败（已重试 $max_retries 次）"
                log_info "可能的原因："
                log_info "  1. 网络连接问题"
                log_info "  2. GitHub 访问受限"
                log_info "  3. 仓库不存在或无权访问"
                return 1
            fi
        fi
    done
    
    return 0
}

# 克隆仓库
clone_repository() {
    log_info "克隆 RuaBot 仓库..."
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "检测到已存在的安装目录: $INSTALL_DIR"
        echo ""
        echo -e "${YELLOW}发现已存在的安装，请选择操作:${NC}"
        echo -e "  ${GREEN}1${NC}. 删除旧安装并重新安装（推荐，完全干净）"
        echo -e "  ${GREEN}2${NC}. 保留旧安装，更新代码（保留环境和配置）"
        echo -e "  ${RED}0${NC}. 取消安装"
        echo ""
        read -p "请选择 [0-2] (默认: 1): " -n 1 -r choice
        echo ""
        
        case $choice in
            1|"")
                log_info "删除旧安装目录..."
                rm -rf "$INSTALL_DIR"
                log_success "旧安装已删除"
                
                # 克隆仓库（带重试机制）
                clone_with_retry "$REPO_URL" "$INSTALL_DIR" || {
                    log_error "仓库克隆失败，请检查网络连接或 GitHub 访问"
                    exit 1
                }
                ;;
            2)
                log_info "更新现有安装..."
                cd "$INSTALL_DIR" || {
                    log_error "无法进入安装目录"
                    exit 1
                }
                
                # 检查是否是 git 仓库
                if [ -d ".git" ]; then
                    log_info "拉取最新代码..."
                    git fetch origin || {
                        log_error "拉取代码失败"
                        exit 1
                    }
                    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || {
                        log_error "更新代码失败"
                        exit 1
                    }
                    log_success "代码更新完成"
                else
                    log_warning "不是 git 仓库，重新克隆..."
                    cd "$HOME"
                    rm -rf "$INSTALL_DIR"
                    clone_with_retry "$REPO_URL" "$INSTALL_DIR" || {
                        log_error "仓库克隆失败"
                        exit 1
                    }
                fi
                ;;
            0)
                log_info "安装取消"
                exit 0
                ;;
            *)
                log_error "无效的选择，安装取消"
                exit 1
                ;;
        esac
    else
        clone_with_retry "$REPO_URL" "$INSTALL_DIR" || {
            log_error "仓库克隆失败，请检查网络连接或 GitHub 访问"
            exit 1
        }
    fi
    
    # 确保进入安装目录
    cd "$INSTALL_DIR" || {
        log_error "无法进入安装目录: $INSTALL_DIR"
        exit 1
    }
    
    log_success "仓库克隆完成"
}

# 克隆仓库（带重试机制）
clone_with_retry() {
    local repo_url=$1
    local target_dir=$2
    local retry_count=0
    local max_retries=5
    local clone_success=false
    
    # 配置 Git 以处理 TLS 问题
    git config --global http.sslVerify true 2>/dev/null || true
    git config --global http.postBuffer 524288000 2>/dev/null || true
    
    while [ $retry_count -lt $max_retries ] && [ "$clone_success" = false ]; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -gt 1 ]; then
            log_info "第 $retry_count 次尝试克隆仓库（共 $max_retries 次）..."
            sleep 3
        fi
        
        log_info "正在克隆仓库..."
        if git clone "$repo_url" "$target_dir" 2>&1 | while IFS= read -r line; do
            if [[ "$line" =~ (Cloning|remote:|Receiving|Resolving|Checking out) ]]; then
                echo -e "${BLUE}[INFO]${NC} $line"
            elif [[ "$line" =~ (fatal|error|Error|ERROR) ]]; then
                echo -e "${YELLOW}[WARN]${NC} $line"
            fi
        done && [ -d "$target_dir/.git" ]; then
            clone_success=true
            return 0
        else
            # 清理失败的克隆
            rm -rf "$target_dir" 2>/dev/null || true
            
            if [ $retry_count -lt $max_retries ]; then
                log_warning "克隆失败，将在 3 秒后自动重试..."
            else
                log_error "克隆失败（已重试 $max_retries 次）"
                log_info "可能的原因："
                log_info "  1. 网络连接问题"
                log_info "  2. GitHub 访问受限"
                log_info "  3. 仓库不存在或无权访问"
                return 1
            fi
        fi
    done
    
    return 0
}

# 安装 Python (使用 pyenv)
install_python() {
    log_info "安装隔离的 Python 环境..."
    
    local PYENV_DIR="$INSTALL_DIR/.pyenv"
    
    # 安装 pyenv
    if [ ! -d "$PYENV_DIR" ]; then
        log_info "正在安装 pyenv..."
        log_info "下载 pyenv 安装脚本..."
        
        export PYENV_ROOT="$PYENV_DIR"
        export PATH="$PYENV_ROOT/bin:$PATH"
        
        # 下载并安装 pyenv，显示进度
        # 使用重试机制安装 pyenv
        local retry_count=0
        local max_retries=3
        local install_success=false
        
        while [ $retry_count -lt $max_retries ] && [ "$install_success" = false ]; do
            retry_count=$((retry_count + 1))
            if [ $retry_count -gt 1 ]; then
                log_info "第 $retry_count 次尝试安装 pyenv（共 $max_retries 次）..."
                sleep 3
                # 清理失败的安装
                rm -rf "$PYENV_DIR" 2>/dev/null || true
            fi
            
            log_info "下载并安装 pyenv..."
            
            # pyenv.run 返回的是一个脚本，需要执行它
            # 设置 PYENV_ROOT 环境变量，让 pyenv 安装到指定目录
            export PYENV_ROOT="$PYENV_DIR"
            export PATH="$PYENV_ROOT/bin:$PATH"
            
            # 下载并执行 pyenv 安装脚本
            # 注意：pyenv.run 返回的脚本会调用 pyenv-installer
            if curl -# https://pyenv.run 2>&1 | bash 2>&1 | tee /tmp/pyenv_install.log | while IFS= read -r line; do
                if [[ "$line" =~ (Cloning|Installing|Downloading|Building|Installed|Successfully|=>) ]]; then
                    echo -e "${BLUE}[INFO]${NC} $line"
                elif [[ "$line" =~ (error|Error|ERROR|failed|Failed|fatal) ]]; then
                    echo -e "${YELLOW}[WARN]${NC} $line"
                fi
            done && [ -f "$PYENV_DIR/bin/pyenv" ]; then
                install_success=true
            else
                # 等待一下，pyenv 安装可能需要时间
                sleep 2
                
                # 再次检查是否真的失败了
                if [ -f "$PYENV_DIR/bin/pyenv" ]; then
                    install_success=true
                elif [ $retry_count -lt $max_retries ]; then
                    log_warning "pyenv 安装失败，将在 3 秒后自动重试..."
                else
                    log_error "pyenv 安装失败（已重试 $max_retries 次），请检查网络连接"
                    log_info "你可以查看日志: cat /tmp/pyenv_install.log"
                    log_info "或者手动安装: curl https://pyenv.run | PYENV_ROOT=$PYENV_DIR bash"
                    exit 1
                fi
            fi
        done
        
        # 等待一下确保安装完成
        sleep 2
        
        # 配置 pyenv
        export PATH="$PYENV_DIR/bin:$PATH"
        if [ -f "$PYENV_DIR/bin/pyenv" ]; then
            eval "$(pyenv init -)" 2>/dev/null || true
            log_success "pyenv 安装完成"
        else
            log_error "pyenv 安装失败，未找到 pyenv 可执行文件"
            log_info "请检查: ls -la $PYENV_DIR/bin/"
            exit 1
        fi
    else
        log_info "pyenv 已存在，跳过安装"
        export PYENV_ROOT="$PYENV_DIR"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)" 2>/dev/null || true
    fi
    
    # 检查 Python 是否已经安装（如果 pyenv 存在但 Python 未安装）
    if [ -d "$PYENV_DIR/versions/$PYTHON_VERSION" ]; then
        log_info "检测到 Python $PYTHON_VERSION 已安装，跳过编译..."
        pyenv local $PYTHON_VERSION
        log_success "使用已安装的 Python: $(python --version 2>&1)"
    else
        # 安装指定版本的 Python
        log_info "正在安装 Python $PYTHON_VERSION（这可能需要 5-15 分钟，请耐心等待）..."
        log_info "正在下载 Python 源码..."
    
    # 启动后台提示进程
    (
        local count=0
        while true; do
            sleep 10
            count=$((count + 1))
            # 检查 pyenv 或 make 进程是否还在运行
            if ! pgrep -f "pyenv" > /dev/null 2>&1 && ! pgrep -f "make.*python" > /dev/null 2>&1 && ! pgrep -f "gcc.*python" > /dev/null 2>&1; then
                break
            fi
            local minutes=$((count * 10 / 60))
            local seconds=$((count * 10 % 60))
            echo -e "\r${YELLOW}[提示]${NC} 正在编译 Python，已等待 ${minutes}分${seconds}秒，请稍候... (时间: $(date +%H:%M:%S))" >&2
        done
    ) &
    local PROMPT_PID=$!
    
    # 使用 verbose 模式显示更多输出，并添加进度提示
    (
        pyenv install -v $PYTHON_VERSION 2>&1 | while IFS= read -r line; do
            # 停止提示进程
            kill $PROMPT_PID 2>/dev/null || true
            
            # 显示编译和安装命令（让用户知道程序在运行）
            if [[ "$line" =~ ^gcc\ .*-o\ .*\.o ]]; then
                # 这是正常的编译命令，显示为 INFO（让用户知道在编译）
                # 只显示文件名，避免刷屏
                local file=$(echo "$line" | grep -oE '[^/]+\.(c|o)$' | tail -1)
                if [ -n "$file" ]; then
                    echo -ne "\r${BLUE}[INFO]${NC} 正在编译: $file                    "
                fi
            elif [[ "$line" =~ ^/usr/bin/install\ .*-c\ .*-m\ .* ]]; then
                # 这是正常的安装命令，显示为 INFO（让用户知道在安装文件）
                local file=$(echo "$line" | grep -oE '[^/]+\.(h|py|so|a)$' | tail -1)
                if [ -n "$file" ]; then
                    echo -ne "\r${BLUE}[INFO]${NC} 正在安装: $file                    "
                else
                    echo -ne "\r${BLUE}[INFO]${NC} 正在安装文件...                    "
                fi
            elif [[ "$line" =~ (Downloading|Installing|Building|Compiling|Linking|running|configure|make|checking for|creating|WARNING|please run|Successfully|Installed) ]]; then
                echo -e "${BLUE}[INFO]${NC} $line"
            elif [[ "$line" =~ (^[[:space:]]*[0-9]+%) ]]; then
                # 显示百分比进度
                echo -ne "\r${BLUE}[INFO]${NC} $line                    "
            elif [[ "$line" =~ (fatal|error:|Error:|ERROR:|failed:|Failed:|BUILD FAILED) ]]; then
                # 只标记真正的错误（带冒号的错误信息或 BUILD FAILED）
                echo -e "${RED}[ERROR]${NC} $line"
            elif [[ "$line" =~ (completed|done) ]]; then
                echo -e "${GREEN}[SUCCESS]${NC} $line"
            fi
        done
        
        # 确保提示进程停止
        kill $PROMPT_PID 2>/dev/null || true
        echo ""
    ) || {
        # 确保提示进程停止
        kill $PROMPT_PID 2>/dev/null || true
        log_error "Python 安装失败，请检查错误信息"
        exit 1
    }
    
    # 确保提示进程停止
    kill $PROMPT_PID 2>/dev/null || true
    
        pyenv local $PYTHON_VERSION
        
        log_success "Python 安装完成: $(python --version 2>&1)"
    fi
    
    # 创建虚拟环境（如果不存在）
    if [ ! -d "$INSTALL_DIR/venv" ]; then
        log_info "创建 Python 虚拟环境..."
        python -m venv "$INSTALL_DIR/venv"
    else
        log_info "检测到 Python 虚拟环境已存在，跳过创建..."
    fi
    source "$INSTALL_DIR/venv/bin/activate"
    
    # 升级 pip（带自动重试机制）
    log_info "升级 pip、setuptools 和 wheel..."
    local retry_count=0
    local max_retries=5
    local install_success=false
    
    while [ $retry_count -lt $max_retries ] && [ "$install_success" = false ]; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -gt 1 ]; then
            log_info "第 $retry_count 次尝试升级 pip（共 $max_retries 次）..."
            sleep 3
        fi
        
        if pip install --upgrade pip setuptools wheel 2>&1 | tee /tmp/pip_upgrade.log | grep -E "(Successfully|Requirement already satisfied|already up-to-date)" > /dev/null 2>&1; then
            install_success=true
            log_success "pip 升级成功"
        else
            if [ $retry_count -lt $max_retries ]; then
                log_warning "pip 升级失败，将在 3 秒后自动重试..."
            else
                log_warning "pip 升级失败（已重试 $max_retries 次），但将继续安装"
                log_info "你可以稍后手动运行: pip install --upgrade pip setuptools wheel"
            fi
        fi
    done
    
    log_success "Python 虚拟环境创建完成"
}

# 安装 Node.js (使用 nvm)
install_nodejs() {
    log_info "安装隔离的 Node.js 环境..."
    
    local NVM_DIR="$INSTALL_DIR/.nvm"
    
    # 安装 nvm（带重试机制）
    if [ ! -d "$NVM_DIR" ]; then
        log_info "正在安装 nvm..."
        log_info "下载 nvm 安装脚本..."
        
        # 先创建目录，否则 nvm 安装脚本会报错
        mkdir -p "$NVM_DIR"
        # 先创建目录，否则 nvm 安装脚本会报错
        mkdir -p "$NVM_DIR"
        export NVM_DIR="$NVM_DIR"
        
        local retry_count=0
        local max_retries=3
        local install_success=false
        
        while [ $retry_count -lt $max_retries ] && [ "$install_success" = false ]; do
            retry_count=$((retry_count + 1))
            if [ $retry_count -gt 1 ]; then
                log_info "第 $retry_count 次尝试安装 nvm（共 $max_retries 次）..."
                sleep 3
                # 清理失败的安装，但保留目录
                rm -rf "$NVM_DIR"/* 2>/dev/null || true
                mkdir -p "$NVM_DIR"
            fi
            
            log_info "下载并安装 nvm..."
            # 下载并执行 nvm 安装脚本
            if curl -# -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh 2>&1 | bash 2>&1 | tee /tmp/nvm_install.log | while IFS= read -r line; do
                if [[ "$line" =~ (Cloning|Installing|Downloading|=>|=> nvm) ]]; then
                    echo -e "${BLUE}[INFO]${NC} $line"
                elif [[ "$line" =~ (error|Error|ERROR|failed|Failed|fatal) ]]; then
                    echo -e "${YELLOW}[WARN]${NC} $line"
                fi
            done && [ -s "$NVM_DIR/nvm.sh" ]; then
                install_success=true
            else
                # 等待一下，nvm 安装可能需要时间
                sleep 2
                
                # 再次检查是否真的失败了
                if [ -s "$NVM_DIR/nvm.sh" ]; then
                    install_success=true
                elif [ $retry_count -lt $max_retries ]; then
                    log_warning "nvm 安装失败，将在 3 秒后自动重试..."
                else
                    log_error "nvm 安装失败（已重试 $max_retries 次），请检查网络连接"
                    log_info "你可以查看日志: cat /tmp/nvm_install.log"
                    log_info "或者手动安装: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | NVM_DIR=$NVM_DIR bash"
                    exit 1
                fi
            fi
        done
        
        # 等待一下确保安装完成
        sleep 2
        
        # 加载 nvm
        if [ -s "$NVM_DIR/nvm.sh" ]; then
            \. "$NVM_DIR/nvm.sh"
            log_success "nvm 安装完成"
        else
            log_error "nvm 安装失败，未找到 nvm.sh"
            log_info "请检查: ls -la $NVM_DIR/"
            exit 1
        fi
    else
        log_info "nvm 已存在，跳过安装"
        export NVM_DIR="$NVM_DIR"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    
    # 检查 Node.js 是否已经安装（智能跳过）
    if [ -d "$NVM_DIR/versions/node/v$NODE_VERSION" ]; then
        log_info "检测到 Node.js v$NODE_VERSION 已安装，跳过安装..."
        nvm use $NODE_VERSION
        log_success "使用已安装的 Node.js: $(node --version 2>&1)"
        log_success "npm 版本: $(npm --version 2>&1)"
    else
        # 安装指定版本的 Node.js
        log_info "正在安装 Node.js $NODE_VERSION（这可能需要几分钟，请耐心等待）..."
        log_info "正在下载 Node.js 源码..."
    
    # 启动后台提示进程
    (
        local count=0
        while true; do
            sleep 8
            count=$((count + 1))
            # 检查 nvm 或 node 相关进程是否还在运行
            if ! pgrep -f "nvm" > /dev/null 2>&1 && ! pgrep -f "node.*install" > /dev/null 2>&1; then
                break
            fi
            local minutes=$((count * 8 / 60))
            local seconds=$((count * 8 % 60))
            echo -e "\r${YELLOW}[提示]${NC} 正在安装 Node.js，已等待 ${minutes}分${seconds}秒，请稍候... (时间: $(date +%H:%M:%S))" >&2
        done
    ) &
    local PROMPT_PID=$!
    
    # 显示 nvm 安装进度
    (
        nvm install $NODE_VERSION 2>&1 | while IFS= read -r line; do
            # 停止提示进程
            kill $PROMPT_PID 2>/dev/null || true
            
            # 显示关键步骤
            if [[ "$line" =~ (Downloading|Installing|Extracting|Computing|Creating|Linking|Building) ]]; then
                echo -e "${BLUE}[INFO]${NC} $line"
            elif [[ "$line" =~ ([0-9]+%) ]]; then
                # 显示百分比进度
                echo -ne "\r${BLUE}[INFO]${NC} $line                    "
            elif [[ "$line" =~ (error|Error|ERROR|failed|Failed) ]]; then
                echo -e "${RED}[ERROR]${NC} $line"
            fi
        done
        
        # 确保提示进程停止
        kill $PROMPT_PID 2>/dev/null || true
        echo ""
    ) || {
        # 确保提示进程停止
        kill $PROMPT_PID 2>/dev/null || true
        log_error "Node.js 安装失败，请检查错误信息"
        exit 1
    }
    
        # 确保提示进程停止
        kill $PROMPT_PID 2>/dev/null || true
        
        nvm use $NODE_VERSION
        
        log_success "Node.js 安装完成: $(node --version 2>&1)"
        log_success "npm 版本: $(npm --version 2>&1)"
    fi
}

# 安装项目依赖
install_dependencies() {
    log_info "安装项目依赖..."
    
    cd "$INSTALL_DIR"
    
    # 激活 Python 虚拟环境
    source "$INSTALL_DIR/venv/bin/activate"
    
    # 安装 Python 依赖（带自动重试机制）
    if [ -f "requirements.txt" ]; then
        log_info "正在安装 Python 依赖（这可能需要几分钟）..."
        local retry_count=0
        local max_retries=5
        local install_success=false
        
        while [ $retry_count -lt $max_retries ] && [ "$install_success" = false ]; do
            retry_count=$((retry_count + 1))
            if [ $retry_count -gt 1 ]; then
                echo ""
                log_info "第 $retry_count 次尝试安装 Python 依赖（共 $max_retries 次）..."
                sleep 5
            fi
            
            if pip install -r requirements.txt 2>&1 | while IFS= read -r line; do
                if [[ "$line" =~ (Collecting|Installing|Downloading|Building|Successfully|Requirement already satisfied|already installed) ]]; then
                    echo -e "${BLUE}[INFO]${NC} $line"
                elif [[ "$line" =~ (error|Error|ERROR|failed|Failed|ConnectionReset|Connection broken|Connection reset|timeout|TIMEOUT) ]]; then
                    echo -e "${YELLOW}[WARN]${NC} $line"
                fi
            done && [ ${PIPESTATUS[0]} -eq 0 ]; then
                install_success=true
                echo ""
                log_success "Python 依赖安装完成"
            else
                if [ $retry_count -lt $max_retries ]; then
                    echo ""
                    log_warning "Python 依赖安装失败，将在 5 秒后自动重试..."
                else
                    echo ""
                    log_error "Python 依赖安装失败（已重试 $max_retries 次）"
                    log_info "你可以稍后手动运行: pip install -r requirements.txt"
                    log_info "或者使用国内镜像: pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
                fi
            fi
        done
    else
        log_warning "未找到 requirements.txt，跳过 Python 依赖安装"
    fi
    
    # 加载 nvm 并安装 Node.js 依赖
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use $NODE_VERSION
    
    if [ -f "package.json" ]; then
        log_info "正在安装 Node.js 依赖（这可能需要几分钟）..."
        local retry_count=0
        local max_retries=5
        local install_success=false
        
        while [ $retry_count -lt $max_retries ] && [ "$install_success" = false ]; do
            retry_count=$((retry_count + 1))
            if [ $retry_count -gt 1 ]; then
                echo ""
                log_info "第 $retry_count 次尝试安装 Node.js 依赖（共 $max_retries 次）..."
                sleep 5
            fi
            
            if npm install 2>&1 | while IFS= read -r line; do
                if [[ "$line" =~ (npm|added|changed|removed|up to date|Installing|Downloading|packages|audited) ]]; then
                    echo -e "${BLUE}[INFO]${NC} $line"
                elif [[ "$line" =~ (error|Error|ERROR|failed|Failed|WARN|ECONNRESET|timeout|TIMEOUT) ]]; then
                    echo -e "${YELLOW}[WARN]${NC} $line"
                fi
            done && [ ${PIPESTATUS[0]} -eq 0 ]; then
                install_success=true
                echo ""
                log_success "Node.js 依赖安装完成"
            else
                if [ $retry_count -lt $max_retries ]; then
                    echo ""
                    log_warning "Node.js 依赖安装失败，将在 5 秒后自动重试..."
                else
                    echo ""
                    log_error "Node.js 依赖安装失败（已重试 $max_retries 次）"
                    log_info "你可以稍后手动运行: npm install"
                    log_info "或者使用国内镜像: npm install --registry=https://registry.npmmirror.com"
                fi
            fi
        done
    else
        log_warning "未找到 package.json，跳过 Node.js 依赖安装"
    fi
}

# 创建配置文件
create_config() {
    log_info "创建配置文件..."
    
    cat > "$INSTALL_DIR/.ruabot.conf" << EOF
# RuaBot 配置文件
INSTALL_DIR="$INSTALL_DIR"
PYTHON_VERSION="$PYTHON_VERSION"
NODE_VERSION="$NODE_VERSION"
INSTALL_DATE="$(date +%Y-%m-%d\ %H:%M:%S)"
EOF
    
    log_success "配置文件创建完成"
}

# 初始化 config.toml 配置
init_config_toml() {
    log_info "初始化 config.toml 配置..."
    
    cd "$INSTALL_DIR"
    
    # 检查 config.toml 是否存在
    if [ ! -f "config.toml" ]; then
        log_warning "config.toml 不存在，将创建默认配置"
        # 如果不存在，从模板复制（如果有的话）
        if [ -f "config.toml.example" ]; then
            cp config.toml.example config.toml
        fi
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        配置初始化${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    
    # 设置 WebUI 管理账号
    echo -e "${YELLOW}设置 WebUI 管理账号${NC}"
    read -p "请输入管理员用户名 [默认: admin]: " webui_username
    webui_username=${webui_username:-admin}
    
    read -sp "请输入管理员密码 [默认: admin123]: " webui_password
    echo ""
    webui_password=${webui_password:-admin123}
    
    # 设置 WebUI 端口
    echo ""
    echo -e "${YELLOW}设置 WebUI 后台端口${NC}"
    read -p "请输入 WebUI 端口 [默认: 8000]: " webui_port
    webui_port=${webui_port:-8000}
    
    # 验证端口是否被占用
    if command -v lsof &> /dev/null || command -v netstat &> /dev/null; then
        local port_in_use=false
        if command -v lsof &> /dev/null; then
            if lsof -i :$webui_port &> /dev/null; then
                port_in_use=true
            fi
        elif command -v netstat &> /dev/null; then
            if netstat -tuln 2>/dev/null | grep -q ":$webui_port "; then
                port_in_use=true
            fi
        fi
        
        if [ "$port_in_use" = true ]; then
            log_warning "端口 $webui_port 已被占用，请确保这是您想要使用的端口"
            read -p "是否继续使用端口 $webui_port? (Y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Nn]$ ]]; then
                read -p "请输入新的端口号: " webui_port
            fi
        fi
    fi
    
    # 设置服务器主机
    echo ""
    echo -e "${YELLOW}设置服务器配置${NC}"
    read -p "请输入服务器主机地址 [默认: 0.0.0.0]: " server_host
    server_host=${server_host:-0.0.0.0}
    
    # 询问是否启用调试模式
    echo ""
    read -p "是否启用调试模式? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        debug_mode="true"
        log_level="DEBUG"
    else
        debug_mode="false"
        log_level="INFO"
    fi
    
    # 更新 config.toml
    log_info "正在更新 config.toml..."
    
    # 使用 Python 或 sed 来更新配置
    if command -v python3 &> /dev/null; then
        python3 << EOF
import re
import sys

config_file = "$INSTALL_DIR/config.toml"

try:
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 更新 WebUI 配置
    content = re.sub(r'username\s*=\s*"[^"]*"', f'username = "$webui_username"', content)
    content = re.sub(r'password\s*=\s*"[^"]*"', f'password = "$webui_password"', content)
    
    # 更新服务器端口
    content = re.sub(r'port\s*=\s*\d+', f'port = $webui_port', content)
    content = re.sub(r'host\s*=\s*"[^"]*"', f'host = "$server_host"', content)
    
    # 更新调试模式
    content = re.sub(r'debug\s*=\s*(true|false)', f'debug = $debug_mode', content)
    content = re.sub(r'level\s*=\s*"[^"]*"', f'level = "$log_level"', content)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ config.toml 更新成功")
except Exception as e:
    print(f"✗ config.toml 更新失败: {e}")
    sys.exit(1)
EOF
    else
        # 使用 sed 更新配置（简单替换）
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/username = \".*\"/username = \"$webui_username\"/" config.toml 2>/dev/null || true
            sed -i '' "s/password = \".*\"/password = \"$webui_password\"/" config.toml 2>/dev/null || true
            sed -i '' "s/port = [0-9]*/port = $webui_port/" config.toml 2>/dev/null || true
            sed -i '' "s/host = \".*\"/host = \"$server_host\"/" config.toml 2>/dev/null || true
            sed -i '' "s/debug = .*/debug = $debug_mode/" config.toml 2>/dev/null || true
            sed -i '' "s/level = \".*\"/level = \"$log_level\"/" config.toml 2>/dev/null || true
        else
            sed -i "s/username = \".*\"/username = \"$webui_username\"/" config.toml 2>/dev/null || true
            sed -i "s/password = \".*\"/password = \"$webui_password\"/" config.toml 2>/dev/null || true
            sed -i "s/port = [0-9]*/port = $webui_port/" config.toml 2>/dev/null || true
            sed -i "s/host = \".*\"/host = \"$server_host\"/" config.toml 2>/dev/null || true
            sed -i "s/debug = .*/debug = $debug_mode/" config.toml 2>/dev/null || true
            sed -i "s/level = \".*\"/level = \"$log_level\"/" config.toml 2>/dev/null || true
        fi
    fi
    
    log_success "配置初始化完成"
    echo ""
    echo -e "${GREEN}配置摘要:${NC}"
    echo -e "  WebUI 用户名: ${BLUE}$webui_username${NC}"
    echo -e "  WebUI 密码: ${BLUE}******${NC}"
    echo -e "  WebUI 端口: ${BLUE}$webui_port${NC}"
    echo -e "  服务器主机: ${BLUE}$server_host${NC}"
    echo -e "  调试模式: ${BLUE}$debug_mode${NC}"
    echo ""
    log_info "您可以在 $INSTALL_DIR/config.toml 中修改这些配置"
}

# 安装 CLI 工具
install_cli() {
    log_info "安装 rcli 命令行工具..."
    
    # 复制 CLI 脚本到 bin 目录
    sudo cp "$INSTALL_DIR/scripts/rcli.sh" /usr/local/bin/rcli
    sudo chmod +x /usr/local/bin/rcli
    
    log_success "rcli 命令行工具安装完成"
    
    # 检查 /usr/local/bin 是否在 PATH 中
    if [[ ":$PATH:" != *":/usr/local/bin:"* ]]; then
        log_warning "/usr/local/bin 不在 PATH 中，正在添加到 shell 配置..."
        local SHELL_RC=""
        if [ -n "$BASH_VERSION" ]; then
            SHELL_RC="$HOME/.bashrc"
        elif [ -n "$ZSH_VERSION" ]; then
            SHELL_RC="$HOME/.zshrc"
        fi
        
        if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
            if ! grep -q "# RuaBot CLI" "$SHELL_RC"; then
                echo "" >> "$SHELL_RC"
                echo "# RuaBot CLI" >> "$SHELL_RC"
                echo "export PATH=\"/usr/local/bin:\$PATH\"" >> "$SHELL_RC"
                log_info "已添加到 $SHELL_RC，请运行: source $SHELL_RC"
            fi
        fi
    else
        log_info "rcli 已安装，可以在任意位置使用 'rcli' 命令"
        log_info "如果当前终端无法使用，请运行: source ~/.bashrc 或重新打开终端"
    fi
}

# 检查文件完整性
check_integrity() {
    log_info "检查文件完整性..."
    
    local required_files=(
        "scripts/rcli.sh"
        ".ruabot.conf"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$INSTALL_DIR/$file" ]; then
            log_warning "缺少文件: $file"
        fi
    done
    
    log_success "文件完整性检查完成"
}

# 显示进度
show_progress() {
    local current=$1
    local total=$2
    local step_name=$3
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r${BLUE}[%d/%d]${NC} ${YELLOW}%s${NC} [${GREEN}%s${NC}${BLUE}%s${NC}] %d%%" \
        "$current" "$total" "$step_name" \
        "$(printf '%*s' $filled | tr ' ' '#')" \
        "$(printf '%*s' $empty | tr ' ' '-')" \
        "$percent"
}

# 主安装流程
main() {
    echo ""
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   RuaBot 一键安装脚本${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    
    # 检查脚本是否完整
    if [ ! -f "$0" ]; then
        log_error "无法找到脚本文件"
        exit 1
    fi
    
    # 检查文件格式（Windows 换行符问题）
    if file "$0" | grep -q "CRLF"; then
        log_warning "检测到 Windows 换行符，正在转换..."
        sed -i 's/\r$//' "$0"
        log_info "已转换为 Unix 格式，请重新运行脚本"
        exit 0
    fi
    
    # 调试信息
    if [ "${DEBUG:-0}" = "1" ]; then
        log_info "调试模式已启用"
        set -x
    fi
    
    local total_steps=11
    local current_step=0
    
    ((current_step++))
    show_progress $current_step $total_steps "检测操作系统..."
    detect_os || {
        log_error "操作系统检测失败"
        exit 1
    }
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "检查并安装 Git..."
    check_and_install_git || {
        log_error "Git 检查/安装失败"
        exit 1
    }
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "安装系统依赖..."
    install_system_dependencies
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "克隆仓库..."
    clone_repository
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "安装 Python 环境..."
    install_python
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "安装 Node.js 环境..."
    install_nodejs
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "安装项目依赖..."
    install_dependencies
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "创建配置文件..."
    create_config
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "初始化配置..."
    init_config_toml
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "安装 CLI 工具..."
    install_cli
    echo ""
    
    ((current_step++))
    show_progress $current_step $total_steps "检查文件完整性..."
    check_integrity
    echo ""
    
    printf "\r${GREEN}[完成]${NC} ${GREEN}安装完成！${NC}                                    \n"
    
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}   安装完成！${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "安装路径: ${BLUE}$INSTALL_DIR${NC}"
    echo -e "使用命令: ${YELLOW}rcli${NC}"
    echo ""
    echo "请运行以下命令使 rcli 生效："
    echo -e "${YELLOW}source ~/.bashrc${NC}  # 或 source ~/.zshrc"
    echo ""
    echo "快速开始："
    echo -e "  ${YELLOW}rcli${NC}          - 打开交互式管理界面"
    echo -e "  ${YELLOW}rcli start${NC}    - 启动 RuaBot"
    echo -e "  ${YELLOW}rcli status${NC}   - 查看运行状态"
    echo ""
}

# 执行主函数
main


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
            if (
                curl -# https://pyenv.run 2>&1 | tee /tmp/pyenv_install.log | while IFS= read -r line; do
                    if [[ "$line" =~ (Cloning|Installing|Downloading|Building) ]]; then
                        echo -e "${BLUE}[INFO]${NC} $line"
                    fi
                done
            ) && [ -f "$PYENV_DIR/bin/pyenv" ]; then
                install_success=true
            else
                if [ $retry_count -lt $max_retries ]; then
                    log_warning "pyenv 安装失败，将在 3 秒后自动重试..."
                else
                    log_error "pyenv 安装失败（已重试 $max_retries 次），请检查网络连接"
                    log_info "你可以查看日志: cat /tmp/pyenv_install.log"
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
            
            # 显示关键步骤
            if [[ "$line" =~ (Downloading|Installing|Building|Compiling|Linking|running|configure|make) ]]; then
                echo -e "${BLUE}[INFO]${NC} $line"
            elif [[ "$line" =~ (^[[:space:]]*[0-9]+%) ]]; then
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
        log_error "Python 安装失败，请检查错误信息"
        exit 1
    }
    
    # 确保提示进程停止
    kill $PROMPT_PID 2>/dev/null || true
    
    pyenv local $PYTHON_VERSION
    
    log_success "Python 安装完成: $(python --version 2>&1)"
    
    # 创建虚拟环境
    log_info "创建 Python 虚拟环境..."
    python -m venv "$INSTALL_DIR/venv"
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
    
    # 安装 nvm
    if [ ! -d "$NVM_DIR" ]; then
        log_info "正在安装 nvm..."
        log_info "下载 nvm 安装脚本..."
        
        export NVM_DIR="$NVM_DIR"
        
        # 下载并安装 nvm，显示进度
        (
            curl -# -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh 2>&1 | bash 2>&1 | while IFS= read -r line; do
                if [[ "$line" =~ (Cloning|Installing|Downloading|=>) ]]; then
                    echo -e "${BLUE}[INFO]${NC} $line"
                fi
            done
        ) || {
            log_error "nvm 安装失败，请检查网络连接"
            exit 1
        }
        
        # 等待一下确保安装完成
        sleep 2
        
        # 加载 nvm
        if [ -s "$NVM_DIR/nvm.sh" ]; then
            \. "$NVM_DIR/nvm.sh"
            log_success "nvm 安装完成"
        else
            log_error "nvm 安装失败，未找到 nvm.sh"
            exit 1
        fi
    else
        log_info "nvm 已存在，跳过安装"
        export NVM_DIR="$NVM_DIR"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    
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
INSTALL_DIR=$INSTALL_DIR
PYTHON_VERSION=$PYTHON_VERSION
NODE_VERSION=$NODE_VERSION
INSTALL_DATE=$(date +%Y-%m-%d\ %H:%M:%S)
EOF
    
    log_success "配置文件创建完成"
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
    
    local total_steps=10
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


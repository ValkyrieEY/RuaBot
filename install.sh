#!/bin/bash
################################################################################
# RuaBot 一键安装脚本
# 仓库: github.com/ValkyrieEY/RuaBot
# 用法: bash <(curl -fsSL https://raw.githubusercontent.com/ValkyrieEY/RuaBot/main/install.sh)
################################################################################

set -e

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
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$ID
            OS_VERSION=$VERSION_ID
        else
            OS="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    log_info "检测到操作系统: $OS"
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

# 克隆仓库
clone_repository() {
    log_info "克隆 RuaBot 仓库..."
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "检测到已存在的安装目录: $INSTALL_DIR"
        read -p "是否删除并重新安装? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            log_error "安装取消"
            exit 1
        fi
    fi
    
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    log_success "仓库克隆完成"
}

# 安装 Python (使用 pyenv)
install_python() {
    log_info "安装隔离的 Python 环境..."
    
    local PYENV_DIR="$INSTALL_DIR/.pyenv"
    
    # 安装 pyenv
    if [ ! -d "$PYENV_DIR" ]; then
        log_info "安装 pyenv..."
        export PYENV_ROOT="$PYENV_DIR"
        export PATH="$PYENV_ROOT/bin:$PATH"
        
        curl https://pyenv.run | bash
        
        # 配置 pyenv
        export PATH="$PYENV_DIR/bin:$PATH"
        eval "$(pyenv init -)"
    else
        export PYENV_ROOT="$PYENV_DIR"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    fi
    
    # 安装指定版本的 Python
    log_info "安装 Python $PYTHON_VERSION..."
    pyenv install -s $PYTHON_VERSION
    pyenv local $PYTHON_VERSION
    
    log_success "Python 安装完成: $(python --version)"
    
    # 创建虚拟环境
    log_info "创建 Python 虚拟环境..."
    python -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    
    # 升级 pip
    pip install --upgrade pip setuptools wheel
    
    log_success "Python 虚拟环境创建完成"
}

# 安装 Node.js (使用 nvm)
install_nodejs() {
    log_info "安装隔离的 Node.js 环境..."
    
    local NVM_DIR="$INSTALL_DIR/.nvm"
    
    # 安装 nvm
    if [ ! -d "$NVM_DIR" ]; then
        log_info "安装 nvm..."
        export NVM_DIR="$NVM_DIR"
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        
        # 加载 nvm
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    else
        export NVM_DIR="$NVM_DIR"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    
    # 安装指定版本的 Node.js
    log_info "安装 Node.js $NODE_VERSION..."
    nvm install $NODE_VERSION
    nvm use $NODE_VERSION
    
    log_success "Node.js 安装完成: $(node --version)"
    log_success "npm 版本: $(npm --version)"
}

# 安装项目依赖
install_dependencies() {
    log_info "安装项目依赖..."
    
    cd "$INSTALL_DIR"
    
    # 激活 Python 虚拟环境
    source "$INSTALL_DIR/venv/bin/activate"
    
    # 安装 Python 依赖
    if [ -f "requirements.txt" ]; then
        log_info "安装 Python 依赖..."
        pip install -r requirements.txt
        log_success "Python 依赖安装完成"
    fi
    
    # 加载 nvm 并安装 Node.js 依赖
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use $NODE_VERSION
    
    if [ -f "package.json" ]; then
        log_info "安装 Node.js 依赖..."
        npm install
        log_success "Node.js 依赖安装完成"
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

# 主安装流程
main() {
    echo ""
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   RuaBot 一键安装脚本${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    
    detect_os
    check_and_install_git
    install_system_dependencies
    clone_repository
    install_python
    install_nodejs
    install_dependencies
    create_config
    install_cli
    check_integrity
    
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


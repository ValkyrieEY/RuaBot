#!/bin/bash
################################################################################
# RuaBot CLI 管理工具
# 用法: rcli [command]
################################################################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# 读取配置
if [ -f "$HOME/RuaBot/.ruabot.conf" ]; then
    source "$HOME/RuaBot/.ruabot.conf"
else
    INSTALL_DIR="$HOME/RuaBot"
fi

# 检查安装
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}错误: RuaBot 未安装${NC}"
    echo "请先运行安装脚本: bash <(curl -fsSL https://raw.githubusercontent.com/ValkyrieEY/RuaBot/main/install.sh)"
    exit 1
fi

# PID 文件
PID_FILE="$INSTALL_DIR/.ruabot.pid"
LOG_FILE="$INSTALL_DIR/logs/ruabot.log"

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

# 显示 Logo
show_logo() {
    echo -e "${CYAN}"
    cat << "EOF"
╔══════════════════════════════════════╗
║          RuaBot Manager              ║
║        命令行管理工具 v0.1.0         ║
╚══════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# 显示主菜单
show_menu() {
    show_logo
    echo -e "${YELLOW}请选择操作:${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC}. 启动框架"
    echo -e "  ${GREEN}2${NC}. 停止服务"
    echo -e "  ${GREEN}3${NC}. 重启服务"
    echo -e "  ${GREEN}4${NC}. 查看状态"
    echo -e "  ${GREEN}5${NC}. 查看日志"
    echo -e "  ${GREEN}6${NC}. 检测文件完整性"
    echo -e "  ${GREEN}7${NC}. 更新框架"
    echo -e "  ${GREEN}8${NC}. 配置系统服务"
    echo -e "  ${GREEN}9${NC}. 环境检查"
    echo -e "  ${GREEN}10${NC}. 环境信息"
    echo -e "  ${GREEN}11${NC}. 卸载框架"
    echo -e "  ${GREEN}12${NC}. 重新安装框架"
    echo -e "  ${GREEN}13${NC}. 更新 rcli 脚本"
    echo -e "  ${GREEN}14${NC}. 安装 AI 模块"
    echo -e "  ${GREEN}15${NC}. 卸载 AI 模块"
    echo -e "  ${GREEN}16${NC}. 安装 WebUI"
    echo -e "  ${GREEN}17${NC}. 卸载 WebUI"
    echo -e "  ${GREEN}18${NC}. 系统维护"
    echo -e "  ${RED}0${NC}. 退出"
    echo ""
    echo -ne "${YELLOW}请输入选项 [0-18]:${NC} "
}

# 启动服务
start_service() {
    log_info "正在启动 RuaBot..."
    
    if [ -f "$PID_FILE" ]; then
        local PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_warning "RuaBot 已经在运行中 (PID: $PID)"
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi
    
    cd "$INSTALL_DIR"
    
    # 激活 Python 环境
    source "$INSTALL_DIR/venv/bin/activate"
    
    # 加载 Node.js 环境
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    # 创建日志目录
    mkdir -p "$INSTALL_DIR/logs"
    
    # 启动主程序 (根据实际项目调整启动命令)
    if [ -f "start.sh" ]; then
        log_info "使用 start.sh 启动..."
        chmod +x start.sh
        nohup bash start.sh > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        log_success "RuaBot 启动成功 (PID: $(cat $PID_FILE))"
    elif [ -f "main.py" ]; then
        nohup python main.py > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        log_success "RuaBot 启动成功 (PID: $(cat $PID_FILE))"
    elif [ -f "index.js" ]; then
        nohup node index.js > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        log_success "RuaBot 启动成功 (PID: $(cat $PID_FILE))"
    elif [ -f "package.json" ]; then
        nohup npm start > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        log_success "RuaBot 启动成功 (PID: $(cat $PID_FILE))"
    else
        log_error "找不到启动文件 (start.sh, main.py 或 index.js)"
        return 1
    fi
    
    sleep 2
    
    # 检查进程是否还在运行
    if [ -f "$PID_FILE" ]; then
        local PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_success "服务运行正常"
        else
            log_error "服务启动失败，请查看日志: $LOG_FILE"
            rm -f "$PID_FILE"
            return 1
        fi
    fi
}

# 停止服务
stop_service() {
    log_info "正在停止 RuaBot..."
    
    if [ ! -f "$PID_FILE" ]; then
        log_warning "RuaBot 未运行"
        return 0
    fi
    
    local PID=$(cat "$PID_FILE")
    
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID"
        
        # 等待进程结束
        local count=0
        while ps -p "$PID" > /dev/null 2>&1 && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        if ps -p "$PID" > /dev/null 2>&1; then
            log_warning "进程未正常结束，强制终止..."
            kill -9 "$PID"
        fi
        
        log_success "RuaBot 已停止"
    else
        log_warning "进程不存在 (PID: $PID)"
    fi
    
    rm -f "$PID_FILE"
}

# 重启服务
restart_service() {
    log_info "正在重启 RuaBot..."
    stop_service
    sleep 2
    start_service
}

# 查看状态
check_status() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        RuaBot 运行状态${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    
    if [ -f "$PID_FILE" ]; then
        local PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "状态: ${GREEN}运行中${NC}"
            echo -e "PID: ${YELLOW}$PID${NC}"
            echo -e "运行时间: ${YELLOW}$(ps -p $PID -o etime= | tr -d ' ')${NC}"
            echo -e "内存使用: ${YELLOW}$(ps -p $PID -o rss= | awk '{printf "%.2f MB", $1/1024}')${NC}"
            echo -e "CPU 使用: ${YELLOW}$(ps -p $PID -o %cpu= | tr -d ' ')%${NC}"
        else
            echo -e "状态: ${RED}已停止${NC} (PID 文件存在但进程不存在)"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "状态: ${RED}未运行${NC}"
    fi
    
    echo ""
    echo -e "安装路径: ${BLUE}$INSTALL_DIR${NC}"
    
    if [ -f "$INSTALL_DIR/.ruabot.conf" ]; then
        source "$INSTALL_DIR/.ruabot.conf"
        echo -e "Python 版本: ${BLUE}$PYTHON_VERSION${NC}"
        echo -e "Node.js 版本: ${BLUE}$NODE_VERSION${NC}"
        echo -e "安装日期: ${BLUE}$INSTALL_DATE${NC}"
    fi
    
    echo ""
}

# 查看日志
view_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        log_warning "日志文件不存在: $LOG_FILE"
        return 1
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        最近 50 行日志${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    
    tail -n 50 "$LOG_FILE"
    
    echo ""
    echo -e "${YELLOW}完整日志文件: $LOG_FILE${NC}"
    echo -e "${YELLOW}使用 'tail -f $LOG_FILE' 实时查看日志${NC}"
    echo ""
}

# 检测文件完整性
check_integrity() {
    log_info "检查文件完整性..."
    echo ""
    
    local missing_files=0
    local required_files=(
        "scripts/rcli.sh"
        ".ruabot.conf"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$INSTALL_DIR/$file" ]; then
            echo -e "${GREEN}[OK]${NC} $file"
        else
            echo -e "${RED}[FAIL]${NC} $file ${RED}(缺失)${NC}"
            missing_files=$((missing_files + 1))
        fi
    done
    
    # 检查虚拟环境
    if [ -d "$INSTALL_DIR/venv" ]; then
        echo -e "${GREEN}[OK]${NC} Python 虚拟环境"
    else
        echo -e "${RED}[FAIL]${NC} Python 虚拟环境 ${RED}(缺失)${NC}"
        missing_files=$((missing_files + 1))
    fi
    
    # 检查 NVM
    if [ -d "$INSTALL_DIR/.nvm" ]; then
        echo -e "${GREEN}[OK]${NC} Node.js 环境 (nvm)"
    else
        echo -e "${RED}[FAIL]${NC} Node.js 环境 ${RED}(缺失)${NC}"
        missing_files=$((missing_files + 1))
    fi
    
    # 检查 Python 依赖
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        echo -e "${GREEN}[OK]${NC} requirements.txt"
    else
        echo -e "${YELLOW}[WARN]${NC} requirements.txt ${YELLOW}(不存在)${NC}"
    fi
    
    # 检查 Node.js 依赖
    if [ -f "$INSTALL_DIR/package.json" ]; then
        echo -e "${GREEN}[OK]${NC} package.json"
    else
        echo -e "${YELLOW}[WARN]${NC} package.json ${YELLOW}(不存在)${NC}"
    fi
    
    echo ""
    
    if [ $missing_files -eq 0 ]; then
        log_success "文件完整性检查通过"
    else
        log_warning "发现 $missing_files 个缺失文件"
        echo -e "${YELLOW}建议重新安装框架${NC}"
    fi
    
    echo ""
}

# 重新安装框架（完全重新安装，不保留用户数据）
reinstall_framework() {
    log_info "正在重新安装 RuaBot..."
    
    # 停止服务
    if [ -f "$PID_FILE" ]; then
        log_info "停止运行中的服务..."
        stop_service
    fi
    
    cd "$INSTALL_DIR"
    
    # 备份配置
    if [ -f ".ruabot.conf" ]; then
        cp .ruabot.conf .ruabot.conf.bak
        log_info "已备份配置文件"
    fi
    
    # 拉取最新代码
    log_info "拉取最新代码..."
    git fetch origin
    git reset --hard origin/main
    
    # 恢复配置
    if [ -f ".ruabot.conf.bak" ]; then
        mv .ruabot.conf.bak .ruabot.conf
    fi
    
    # 激活环境
    source "$INSTALL_DIR/venv/bin/activate"
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    # 更新依赖
    if [ -f "requirements.txt" ]; then
        log_info "更新 Python 依赖..."
        pip install --upgrade -r requirements.txt
    fi
    
    if [ -f "package.json" ]; then
        log_info "更新 Node.js 依赖..."
        npm install
    fi
    
    log_success "重新安装完成"
    
    echo ""
    read -p "是否立即启动服务? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        start_service
    fi
}

# 更新 rcli 脚本
update_script() {
    log_info "正在更新 rcli 脚本..."
    
    # 确定脚本路径（优先使用系统路径，否则使用安装目录中的脚本）
    local SCRIPT_PATH="/usr/local/bin/rcli"
    local INSTALL_SCRIPT_PATH="$INSTALL_DIR/scripts/rcli.sh"
    
    # 检查哪个脚本存在
    if [ ! -f "$SCRIPT_PATH" ] && [ ! -f "$INSTALL_SCRIPT_PATH" ]; then
        log_error "rcli 脚本未找到"
        return 1
    fi
    
    # 确定要更新的脚本路径
    if [ -f "$SCRIPT_PATH" ]; then
        local TARGET_PATH="$SCRIPT_PATH"
        local USE_SUDO=true
    else
        local TARGET_PATH="$INSTALL_SCRIPT_PATH"
        local USE_SUDO=false
    fi
    
    local BACKUP_PATH="$INSTALL_DIR/.rcli_backup_$(date +%Y%m%d_%H%M%S).sh"
    
    # 备份当前脚本
    log_info "备份当前脚本..."
    if [ "$USE_SUDO" = true ]; then
        sudo cp "$TARGET_PATH" "$BACKUP_PATH"
    else
        cp "$TARGET_PATH" "$BACKUP_PATH"
    fi
    log_success "已备份到: $BACKUP_PATH"
    
    # 从 GitHub 下载最新版本
    log_info "从 GitHub 下载最新版本..."
    local GITHUB_URL="https://raw.githubusercontent.com/ValkyrieEY/RuaBot/main/scripts/rcli.sh"
    local TEMP_SCRIPT="/tmp/rcli_new.sh"
    
    if command -v curl &> /dev/null; then
        if curl -fsSL "$GITHUB_URL" -o "$TEMP_SCRIPT"; then
            log_success "下载成功"
        else
            log_error "下载失败，请检查网络连接"
            rm -f "$TEMP_SCRIPT"
            return 1
        fi
    elif command -v wget &> /dev/null; then
        if wget -q "$GITHUB_URL" -O "$TEMP_SCRIPT"; then
            log_success "下载成功"
        else
            log_error "下载失败，请检查网络连接"
            rm -f "$TEMP_SCRIPT"
            return 1
        fi
    else
        log_error "未找到 curl 或 wget，无法下载"
        return 1
    fi
    
    # 验证下载的脚本
    if [ ! -f "$TEMP_SCRIPT" ] || [ ! -s "$TEMP_SCRIPT" ]; then
        log_error "下载的脚本文件无效"
        rm -f "$TEMP_SCRIPT"
        return 1
    fi
    
    # 检查脚本是否包含有效的 bash 脚本
    if ! head -n 1 "$TEMP_SCRIPT" | grep -q "#!/bin/bash"; then
        log_error "下载的文件不是有效的 bash 脚本"
        rm -f "$TEMP_SCRIPT"
        return 1
    fi
    
    # 替换脚本
    log_info "安装新版本..."
    if [ "$USE_SUDO" = true ]; then
        if sudo cp "$TEMP_SCRIPT" "$TARGET_PATH" && sudo chmod +x "$TARGET_PATH"; then
            log_success "rcli 脚本更新成功"
            rm -f "$TEMP_SCRIPT"
            
            # 询问是否删除备份
            echo ""
            read -p "是否删除备份文件 $BACKUP_PATH? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f "$BACKUP_PATH"
                log_info "备份文件已删除"
            else
                log_info "备份文件保留在: $BACKUP_PATH"
            fi
            
            echo ""
            log_info "更新完成！请重新运行 rcli 命令以使用新版本。"
            return 0
        else
            log_error "安装失败，正在恢复备份..."
            sudo cp "$BACKUP_PATH" "$TARGET_PATH"
            sudo chmod +x "$TARGET_PATH"
            rm -f "$TEMP_SCRIPT"
            return 1
        fi
    else
        if cp "$TEMP_SCRIPT" "$TARGET_PATH" && chmod +x "$TARGET_PATH"; then
            log_success "rcli 脚本更新成功"
            rm -f "$TEMP_SCRIPT"
            
            # 询问是否删除备份
            echo ""
            read -p "是否删除备份文件 $BACKUP_PATH? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f "$BACKUP_PATH"
                log_info "备份文件已删除"
            else
                log_info "备份文件保留在: $BACKUP_PATH"
            fi
            
            echo ""
            log_info "更新完成！请重新运行 rcli 命令以使用新版本。"
            return 0
        else
            log_error "安装失败，正在恢复备份..."
            cp "$BACKUP_PATH" "$TARGET_PATH"
            chmod +x "$TARGET_PATH"
            rm -f "$TEMP_SCRIPT"
            return 1
        fi
    fi
}

# 安装 AI 模块
install_ai() {
    log_info "正在安装 AI 模块..."
    
    cd "$INSTALL_DIR"
    
    # 检查是否已安装
    if [ -d "src/ai" ]; then
        log_warning "AI 模块已存在"
        read -p "是否重新安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "取消安装"
            return 0
        fi
        log_info "备份现有 AI 模块..."
        mv src/ai "src/ai_backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    fi
    
    # 检查是否为 git 仓库
    if [ -d ".git" ]; then
        log_info "使用 git 下载 AI 模块..."
        
        # 使用 git sparse-checkout 只下载 src/ai 目录
        git fetch origin main 2>/dev/null || git fetch origin master 2>/dev/null || true
        
        # 创建临时目录
        TEMP_DIR=$(mktemp -d)
        cd "$TEMP_DIR"
        
        # 克隆仓库（浅克隆）
        if git clone --depth 1 --filter=blob:none --sparse https://github.com/ValkyrieEY/RuaBot.git . 2>/dev/null; then
            git sparse-checkout set src/ai
            git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
            
            # 复制 AI 目录
            if [ -d "src/ai" ]; then
                cp -r src/ai "$INSTALL_DIR/src/"
                log_success "AI 模块安装成功"
                cd "$INSTALL_DIR"
                rm -rf "$TEMP_DIR"
                return 0
            fi
        fi
        
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
    fi
    
    # 如果 git 方法失败，使用下载 ZIP 的方式
    log_info "从 GitHub 下载 AI 模块..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    if command -v curl &> /dev/null; then
        curl -fsSL "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/main.zip" -o repo.zip || \
        curl -fsSL "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/master.zip" -o repo.zip
    elif command -v wget &> /dev/null; then
        wget -q "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/main.zip" -O repo.zip || \
        wget -q "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/master.zip" -O repo.zip
    else
        log_error "未找到 curl 或 wget，无法下载"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    fi
    
    if [ ! -f "repo.zip" ]; then
        log_error "下载失败"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    fi
    
    # 解压并提取 AI 目录
    unzip -q repo.zip 2>/dev/null || {
        log_error "解压失败，请检查是否安装了 unzip"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    }
    
    # 查找并复制 AI 目录
    if [ -d "RuaBot-main/src/ai" ]; then
        cp -r RuaBot-main/src/ai "$INSTALL_DIR/src/"
        log_success "AI 模块安装成功"
    elif [ -d "RuaBot-master/src/ai" ]; then
        cp -r RuaBot-master/src/ai "$INSTALL_DIR/src/"
        log_success "AI 模块安装成功"
    else
        log_error "未找到 AI 模块目录"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    fi
    
    cd "$INSTALL_DIR"
    rm -rf "$TEMP_DIR"
    
    log_success "AI 模块安装完成"
    echo ""
    log_info "请重启框架以使 AI 模块生效"
}

# 卸载 AI 模块
uninstall_ai() {
    log_info "正在卸载 AI 模块..."
    
    cd "$INSTALL_DIR"
    
    if [ ! -d "src/ai" ]; then
        log_warning "AI 模块未安装"
        return 0
    fi
    
    # 确认卸载
    echo ""
    read -p "确定要卸载 AI 模块吗? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消卸载"
        return 0
    fi
    
    # 备份（可选）
    BACKUP_DIR="$INSTALL_DIR/.ai_backup_$(date +%Y%m%d_%H%M%S)"
    read -p "是否备份 AI 模块到 $BACKUP_DIR? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        cp -r src/ai "$BACKUP_DIR"
        log_info "已备份到: $BACKUP_DIR"
    fi
    
    # 删除 AI 目录
    rm -rf src/ai
    log_success "AI 模块已卸载"
    
    # 清理 __pycache__
    find src -type d -name "__pycache__" -path "*/ai/*" -exec rm -rf {} + 2>/dev/null || true
    
    echo ""
    log_info "请重启框架以使更改生效"
}

# 安装 WebUI
install_webui() {
    log_info "正在安装 WebUI..."
    
    cd "$INSTALL_DIR"
    
    # 检查是否已安装
    if [ -d "webui" ]; then
        log_warning "WebUI 已存在"
        read -p "是否重新安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "取消安装"
            return 0
        fi
        log_info "备份现有 WebUI..."
        mv webui "webui_backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    fi
    
    # 检查 Node.js
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    if ! command -v node &> /dev/null; then
        log_error "未找到 Node.js，请先安装 Node.js"
        return 1
    fi
    
    log_info "从 GitHub 下载 WebUI..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    if command -v curl &> /dev/null; then
        curl -fsSL "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/main.zip" -o repo.zip || \
        curl -fsSL "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/master.zip" -o repo.zip
    elif command -v wget &> /dev/null; then
        wget -q "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/main.zip" -O repo.zip || \
        wget -q "https://github.com/ValkyrieEY/RuaBot/archive/refs/heads/master.zip" -O repo.zip
    else
        log_error "未找到 curl 或 wget，无法下载"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    fi
    
    if [ ! -f "repo.zip" ]; then
        log_error "下载失败"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    fi
    
    # 解压并提取 webui 目录
    unzip -q repo.zip 2>/dev/null || {
        log_error "解压失败，请检查是否安装了 unzip"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    }
    
    # 查找并复制 webui 目录
    if [ -d "RuaBot-main/webui" ]; then
        cp -r RuaBot-main/webui "$INSTALL_DIR/"
        WEBUI_SOURCE="RuaBot-main"
    elif [ -d "RuaBot-master/webui" ]; then
        cp -r RuaBot-master/webui "$INSTALL_DIR/"
        WEBUI_SOURCE="RuaBot-master"
    else
        log_error "未找到 WebUI 目录"
        cd "$INSTALL_DIR"
        rm -rf "$TEMP_DIR"
        return 1
    fi
    
    cd "$INSTALL_DIR"
    rm -rf "$TEMP_DIR"
    
    # 安装 Node.js 依赖
    cd "$INSTALL_DIR/webui"
    log_info "安装 WebUI 依赖..."
    if npm install; then
        log_success "WebUI 依赖安装成功"
    else
        log_error "WebUI 依赖安装失败"
        return 1
    fi
    
    # 构建 WebUI 到 src/ui/static（必需，框架需要这个目录）
    log_info "构建 WebUI 到 src/ui/static..."
    if npm run build 2>/dev/null; then
        if [ -d "../src/ui/static" ] && [ -f "../src/ui/static/index.html" ]; then
            log_success "WebUI 构建成功，输出到: src/ui/static"
        else
            log_warning "构建命令执行完成，但未找到输出文件"
        fi
    else
        log_error "WebUI 构建失败"
        log_warning "框架需要 src/ui/static 目录中的构建文件才能运行 WebUI"
        return 1
    fi
    
    cd "$INSTALL_DIR"
    log_success "WebUI 安装完成"
    echo ""
    log_info "构建输出位置: src/ui/static (框架实际使用的文件)"
    log_info "源码位置: webui (可选，用于开发)"
    echo ""
    log_info "请重启框架以使 WebUI 生效"
}

# 卸载 WebUI
uninstall_webui() {
    log_info "正在卸载 WebUI..."
    
    cd "$INSTALL_DIR"
    
    # 检查构建输出目录（实际使用的目录）
    local STATIC_DIR="src/ui/static"
    local WEBUI_SOURCE_DIR="webui"
    
    if [ ! -d "$STATIC_DIR" ] && [ ! -d "$WEBUI_SOURCE_DIR" ]; then
        log_warning "WebUI 未安装"
        return 0
    fi
    
    # 确认卸载
    echo ""
    echo -e "${YELLOW}将删除以下内容:${NC}"
    if [ -d "$STATIC_DIR" ]; then
        echo "  - $STATIC_DIR (构建输出，框架实际使用的文件)"
    fi
    if [ -d "$WEBUI_SOURCE_DIR" ]; then
        echo "  - $WEBUI_SOURCE_DIR (源码目录，用于开发)"
    fi
    echo ""
    read -p "确定要卸载 WebUI 吗? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消卸载"
        return 0
    fi
    
    # 备份（可选）
    BACKUP_DIR="$INSTALL_DIR/.webui_backup_$(date +%Y%m%d_%H%M%S)"
    read -p "是否备份 WebUI 到 $BACKUP_DIR? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        mkdir -p "$BACKUP_DIR"
        if [ -d "$STATIC_DIR" ]; then
            cp -r "$STATIC_DIR" "$BACKUP_DIR/static"
            log_info "已备份构建输出"
        fi
        if [ -d "$WEBUI_SOURCE_DIR" ]; then
            cp -r "$WEBUI_SOURCE_DIR" "$BACKUP_DIR/webui"
            log_info "已备份源码目录"
        fi
        log_info "备份位置: $BACKUP_DIR"
    fi
    
    # 删除构建输出目录（主要）
    if [ -d "$STATIC_DIR" ]; then
        rm -rf "$STATIC_DIR"
        log_success "已删除构建输出目录: $STATIC_DIR"
    fi
    
    # 询问是否删除源码目录
    if [ -d "$WEBUI_SOURCE_DIR" ]; then
        read -p "是否同时删除源码目录 $WEBUI_SOURCE_DIR? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$WEBUI_SOURCE_DIR"
            log_success "已删除源码目录: $WEBUI_SOURCE_DIR"
        else
            log_info "保留源码目录: $WEBUI_SOURCE_DIR"
        fi
    fi
    
    log_success "WebUI 已卸载"
    
    echo ""
    log_info "请重启框架以使更改生效"
}

# 系统维护
system_maintenance() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        系统维护工具${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}请选择维护操作:${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC}. 清理缓存文件"
    echo -e "  ${GREEN}2${NC}. 清理临时文件"
    echo -e "  ${GREEN}3${NC}. 清理日志文件"
    echo -e "  ${GREEN}4${NC}. 清理所有（缓存+临时+日志）"
    echo -e "  ${GREEN}5${NC}. 查看磁盘使用情况"
    echo -e "  ${GREEN}6${NC}. 数据库优化"
    echo -e "  ${RED}0${NC}. 返回主菜单"
    echo ""
    echo -ne "${YELLOW}请输入选项 [0-6]:${NC} "
    read -r choice
    echo ""
    
    case $choice in
        1)
            cleanup_cache
            ;;
        2)
            cleanup_temp
            ;;
        3)
            cleanup_logs
            ;;
        4)
            cleanup_all
            ;;
        5)
            show_disk_usage
            ;;
        6)
            optimize_database
            ;;
        0)
            return 0
            ;;
        *)
            log_error "无效的选项"
            ;;
    esac
    
    echo ""
    read -p "按回车键继续..."
}

# 清理缓存文件
cleanup_cache() {
    log_info "正在清理缓存文件..."
    
    cd "$INSTALL_DIR"
    local cleaned=0
    local total_size=0
    
    # 清理图片缓存
    if [ -d "data/image_cache" ]; then
        local size=$(du -sk "data/image_cache" 2>/dev/null | cut -f1)
        if [ -n "$size" ] && [ "$size" -gt 0 ]; then
            rm -rf data/image_cache/*
            total_size=$((total_size + size))
            cleaned=1
            log_success "已清理图片缓存: $(numfmt --to=iec-i --suffix=B $((size * 1024)) 2>/dev/null || echo "${size}KB")"
        fi
    fi
    
    # 清理 Python 缓存
    if [ -d "src" ]; then
        local pycache_count=$(find src -type d -name "__pycache__" 2>/dev/null | wc -l)
        if [ "$pycache_count" -gt 0 ]; then
            local size=$(find src -type d -name "__pycache__" -exec du -sk {} + 2>/dev/null | awk '{sum+=$1} END {print sum+0}')
            find src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
            if [ -n "$size" ] && [ "$size" -gt 0 ]; then
                total_size=$((total_size + size))
                cleaned=1
                log_success "已清理 Python 缓存 ($pycache_count 个目录): $(numfmt --to=iec-i --suffix=B $((size * 1024)) 2>/dev/null || echo "${size}KB")"
            fi
        fi
    fi
    
    # 清理 Node.js 缓存
    if [ -d "webui/node_modules/.cache" ]; then
        local size=$(du -sk "webui/node_modules/.cache" 2>/dev/null | cut -f1)
        if [ -n "$size" ] && [ "$size" -gt 0 ]; then
            rm -rf webui/node_modules/.cache/*
            total_size=$((total_size + size))
            cleaned=1
            log_success "已清理 Node.js 缓存: $(numfmt --to=iec-i --suffix=B $((size * 1024)) 2>/dev/null || echo "${size}KB")"
        fi
    fi
    
    if [ $cleaned -eq 0 ]; then
        log_info "没有需要清理的缓存文件"
    else
        log_success "缓存清理完成，共释放: $(numfmt --to=iec-i --suffix=B $((total_size * 1024)) 2>/dev/null || echo "${total_size}KB")"
    fi
}

# 清理临时文件
cleanup_temp() {
    log_info "正在清理临时文件..."
    
    cd "$INSTALL_DIR"
    local cleaned=0
    local total_size=0
    
    # 清理 data/temp
    if [ -d "data/temp" ]; then
        local size=$(du -sk "data/temp" 2>/dev/null | cut -f1)
        if [ -n "$size" ] && [ "$size" -gt 0 ]; then
            find data/temp -type f -mtime +7 -delete 2>/dev/null
            local remaining=$(find data/temp -type f 2>/dev/null | wc -l)
            if [ "$remaining" -eq 0 ]; then
                rm -rf data/temp/*
            fi
            total_size=$((total_size + size))
            cleaned=1
            log_success "已清理临时文件: $(numfmt --to=iec-i --suffix=B $((size * 1024)) 2>/dev/null || echo "${size}KB")"
        fi
    fi
    
    # 清理插件临时文件
    if [ -d "plugins" ]; then
        local temp_dirs=$(find plugins -type d -name "temp" 2>/dev/null)
        for temp_dir in $temp_dirs; do
            if [ -d "$temp_dir" ]; then
                local size=$(du -sk "$temp_dir" 2>/dev/null | cut -f1)
                if [ -n "$size" ] && [ "$size" -gt 0 ]; then
                    find "$temp_dir" -type f -mtime +7 -delete 2>/dev/null
                    total_size=$((total_size + size))
                    cleaned=1
                fi
            fi
        done
        if [ $cleaned -eq 1 ]; then
            log_success "已清理插件临时文件"
        fi
    fi
    
    # 清理系统临时文件
    rm -rf /tmp/ruabot* 2>/dev/null || true
    rm -rf /tmp/xqnext* 2>/dev/null || true
    
    if [ $cleaned -eq 0 ]; then
        log_info "没有需要清理的临时文件"
    else
        log_success "临时文件清理完成，共释放: $(numfmt --to=iec-i --suffix=B $((total_size * 1024)) 2>/dev/null || echo "${total_size}KB")"
    fi
}

# 清理日志文件
cleanup_logs() {
    log_info "正在清理日志文件..."
    
    cd "$INSTALL_DIR"
    local cleaned=0
    local total_size=0
    
    if [ -d "logs" ]; then
        # 保留最近 7 天的日志，删除更早的
        local old_logs=$(find logs -type f -name "*.log*" -mtime +7 2>/dev/null)
        if [ -n "$old_logs" ]; then
            for log_file in $old_logs; do
                if [ -f "$log_file" ]; then
                    local size=$(du -sk "$log_file" 2>/dev/null | cut -f1)
                    rm -f "$log_file"
                    if [ -n "$size" ]; then
                        total_size=$((total_size + size))
                        cleaned=1
                    fi
                fi
            done
        fi
        
        # 清理过大的日志文件（超过 100MB）
        local large_logs=$(find logs -type f -name "*.log" -size +100M 2>/dev/null)
        if [ -n "$large_logs" ]; then
            for log_file in $large_logs; do
                local size=$(du -sk "$log_file" 2>/dev/null | cut -f1)
                > "$log_file"  # 清空文件内容
                if [ -n "$size" ]; then
                    total_size=$((total_size + size))
                    cleaned=1
                fi
            done
            log_success "已清空过大的日志文件"
        fi
    fi
    
    if [ $cleaned -eq 0 ]; then
        log_info "没有需要清理的日志文件"
    else
        log_success "日志清理完成，共释放: $(numfmt --to=iec-i --suffix=B $((total_size * 1024)) 2>/dev/null || echo "${total_size}KB")"
    fi
}

# 清理所有
cleanup_all() {
    echo ""
    read -p "确定要清理所有缓存、临时文件和旧日志吗? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消清理"
        return 0
    fi
    
    cleanup_cache
    cleanup_temp
    cleanup_logs
    
    log_success "系统清理完成"
}

# 查看磁盘使用情况
show_disk_usage() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        磁盘使用情况${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    
    cd "$INSTALL_DIR"
    
    echo -e "${YELLOW}目录大小:${NC}"
    echo ""
    
    if [ -d "data" ]; then
        local size=$(du -sh data 2>/dev/null | cut -f1)
        echo -e "  data:        ${BLUE}$size${NC}"
    fi
    
    if [ -d "plugins" ]; then
        local size=$(du -sh plugins 2>/dev/null | cut -f1)
        echo -e "  plugins:     ${BLUE}$size${NC}"
    fi
    
    if [ -d "logs" ]; then
        local size=$(du -sh logs 2>/dev/null | cut -f1)
        echo -e "  logs:        ${BLUE}$size${NC}"
    fi
    
    if [ -d "webui" ]; then
        local size=$(du -sh webui 2>/dev/null | cut -f1)
        echo -e "  webui:       ${BLUE}$size${NC}"
    fi
    
    if [ -d "src" ]; then
        local size=$(du -sh src 2>/dev/null | cut -f1)
        echo -e "  src:         ${BLUE}$size${NC}"
    fi
    
    local total_size=$(du -sh . 2>/dev/null | cut -f1)
    echo ""
    echo -e "  总计:        ${GREEN}$total_size${NC}"
    echo ""
    
    # 显示数据库大小
    if [ -d "data" ]; then
        echo -e "${YELLOW}数据库文件:${NC}"
        echo ""
        for db in data/*.db; do
            if [ -f "$db" ]; then
                local size=$(du -sh "$db" 2>/dev/null | cut -f1)
                local name=$(basename "$db")
                echo -e "  $name: ${BLUE}$size${NC}"
            fi
        done
        echo ""
    fi
}

# 数据库优化
optimize_database() {
    log_info "正在优化数据库..."
    
    cd "$INSTALL_DIR"
    
    if [ ! -d "data" ]; then
        log_warning "data 目录不存在"
        return 1
    fi
    
    # 检查是否有 SQLite 数据库
    local db_files=$(find data -name "*.db" -type f 2>/dev/null)
    if [ -z "$db_files" ]; then
        log_warning "未找到数据库文件"
        return 0
    fi
    
    # 激活 Python 环境
    source "$INSTALL_DIR/venv/bin/activate" 2>/dev/null || true
    
    for db_file in $db_files; do
        local db_name=$(basename "$db_file")
        log_info "优化数据库: $db_name"
        
        # 使用 Python 的 sqlite3 进行 VACUUM
        python3 << EOF 2>/dev/null || true
import sqlite3
import sys
try:
    conn = sqlite3.connect('$db_file')
    conn.execute('VACUUM')
    conn.close()
    print("✓ $db_name 优化完成")
except Exception as e:
    print(f"✗ $db_name 优化失败: {e}")
    sys.exit(1)
EOF
    done
    
    log_success "数据库优化完成"
}

# 更新框架（保留用户数据：data、plugins、config.toml）
update_framework() {
    log_info "正在更新 RuaBot（保留用户数据）..."
    
    # 停止服务
    if [ -f "$PID_FILE" ]; then
        log_info "停止运行中的服务..."
        stop_service
    fi
    
    cd "$INSTALL_DIR"
    
    # 备份用户数据
    log_info "备份用户数据..."
    BACKUP_DIR="$INSTALL_DIR/.update_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份 data 目录
    if [ -d "data" ]; then
        log_info "备份 data 目录..."
        cp -r data "$BACKUP_DIR/data"
    fi
    
    # 备份 plugins 目录
    if [ -d "plugins" ]; then
        log_info "备份 plugins 目录..."
        cp -r plugins "$BACKUP_DIR/plugins"
    fi
    
    # 备份 config.toml
    if [ -f "config.toml" ]; then
        log_info "备份 config.toml..."
        cp config.toml "$BACKUP_DIR/config.toml"
    fi
    
    # 备份 .ruabot.conf
    if [ -f ".ruabot.conf" ]; then
        cp .ruabot.conf "$BACKUP_DIR/.ruabot.conf"
    fi
    
    log_success "用户数据已备份到: $BACKUP_DIR"
    
    # 拉取最新代码
    log_info "拉取最新代码..."
    git fetch origin
    git reset --hard origin/main
    
    # 恢复用户数据
    log_info "恢复用户数据..."
    
    if [ -d "$BACKUP_DIR/data" ]; then
        if [ -d "data" ]; then
            # 合并 data 目录，保留新文件
            rsync -a "$BACKUP_DIR/data/" "data/" 2>/dev/null || cp -r "$BACKUP_DIR/data/"* "data/" 2>/dev/null
        else
            cp -r "$BACKUP_DIR/data" .
        fi
        log_info "已恢复 data 目录"
    fi
    
    if [ -d "$BACKUP_DIR/plugins" ]; then
        if [ -d "plugins" ]; then
            # 合并 plugins 目录，保留新文件
            rsync -a "$BACKUP_DIR/plugins/" "plugins/" 2>/dev/null || cp -r "$BACKUP_DIR/plugins/"* "plugins/" 2>/dev/null
        else
            cp -r "$BACKUP_DIR/plugins" .
        fi
        log_info "已恢复 plugins 目录"
    fi
    
    if [ -f "$BACKUP_DIR/config.toml" ]; then
        cp "$BACKUP_DIR/config.toml" config.toml
        log_info "已恢复 config.toml"
    fi
    
    if [ -f "$BACKUP_DIR/.ruabot.conf" ]; then
        cp "$BACKUP_DIR/.ruabot.conf" .ruabot.conf
    fi
    
    # 激活环境
    source "$INSTALL_DIR/venv/bin/activate"
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    # 更新依赖
    if [ -f "requirements.txt" ]; then
        log_info "更新 Python 依赖..."
        pip install --upgrade -r requirements.txt
    fi
    
    if [ -f "package.json" ]; then
        log_info "更新 Node.js 依赖..."
        npm install
    fi
    
    log_success "更新完成（用户数据已保留）"
    
    # 询问是否删除备份
    echo ""
    read -p "是否删除备份目录 $BACKUP_DIR? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$BACKUP_DIR"
        log_info "备份目录已删除"
    else
        log_info "备份目录保留在: $BACKUP_DIR"
    fi
    
    echo ""
    read -p "是否立即启动服务? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        start_service
    fi
}

# 卸载框架
uninstall_framework() {
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║          警告: 卸载 RuaBot                      ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}此操作将:${NC}"
    echo "  • 停止所有运行中的 RuaBot 进程"
    echo "  • 删除安装目录: $INSTALL_DIR"
    echo "  • 删除 Python 虚拟环境"
    echo "  • 删除 Node.js 环境 (nvm)"
    echo "  • 删除 rcli 命令行工具"
    echo "  • 清理环境变量配置"
    echo ""
    echo -e "${RED}所有数据将被永久删除！${NC}"
    echo ""
    
    # 确认卸载
    read -p "确定要卸载 RuaBot 吗? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消卸载"
        return 0
    fi
    
    echo ""
    log_info "开始卸载..."
    echo ""
    
    # 停止服务
    if [ -f "$PID_FILE" ]; then
        log_info "检查运行中的服务..."
        local PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_info "停止 RuaBot 服务 (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
            
            # 等待进程结束
            local count=0
            while ps -p "$PID" > /dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            if ps -p "$PID" > /dev/null 2>&1; then
                log_warning "强制终止进程..."
                kill -9 "$PID" 2>/dev/null || true
            fi
            
            log_success "服务已停止"
        fi
        rm -f "$PID_FILE"
    else
        log_info "没有运行中的服务"
    fi
    
    # 备份配置和数据（可选）
    log_info "是否备份配置和数据?"
    read -p "输入备份路径 (留空跳过): " backup_path
    
    if [ -n "$backup_path" ]; then
        mkdir -p "$backup_path"
        
        # 备份配置文件
        if [ -f "$INSTALL_DIR/.ruabot.conf" ]; then
            cp "$INSTALL_DIR/.ruabot.conf" "$backup_path/"
            log_success "配置文件已备份"
        fi
        
        # 备份数据目录 (如果存在)
        if [ -d "$INSTALL_DIR/data" ]; then
            cp -r "$INSTALL_DIR/data" "$backup_path/"
            log_success "数据已备份到: $backup_path"
        fi
        
        # 备份日志
        if [ -d "$INSTALL_DIR/logs" ]; then
            cp -r "$INSTALL_DIR/logs" "$backup_path/"
            log_success "日志已备份"
        fi
    else
        log_info "跳过备份"
    fi
    
    # 删除 CLI 工具
    log_info "删除 rcli 命令行工具..."
    if [ -f "/usr/local/bin/rcli" ]; then
        sudo rm -f /usr/local/bin/rcli
        log_success "rcli 已删除"
    else
        log_info "rcli 不存在"
    fi
    
    # 清理环境变量
    log_info "清理环境变量配置..."
    local cleaned=0
    
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc" ]; then
            # 备份原文件
            cp "$rc" "$rc.bak.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
            
            # 删除 RuaBot 相关行
            if grep -q "RuaBot" "$rc" 2>/dev/null; then
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    sed -i '' '/# RuaBot/d' "$rc"
                    sed -i '' '/RuaBot/d' "$rc"
                else
                    sed -i '/# RuaBot/d' "$rc"
                    sed -i '/RuaBot/d' "$rc"
                fi
                cleaned=1
                log_success "已清理: $rc"
            fi
        fi
    done
    
    if [ $cleaned -eq 0 ]; then
        log_info "无需清理环境变量"
    fi
    
    # 删除安装目录
    log_info "删除安装目录..."
    if [ -d "$INSTALL_DIR" ]; then
        local size=$(du -sh "$INSTALL_DIR" 2>/dev/null | cut -f1)
        log_info "安装目录大小: $size"
        rm -rf "$INSTALL_DIR"
        log_success "安装目录已删除: $INSTALL_DIR"
    else
        log_warning "安装目录不存在: $INSTALL_DIR"
    fi
    
    # 清理残留文件
    log_info "清理残留文件..."
    rm -rf /tmp/ruabot* 2>/dev/null || true
    rm -rf /var/log/ruabot* 2>/dev/null || true
    log_success "残留文件已清理"
    
    # 显示卸载结果
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║          RuaBot 已成功卸载                     ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}感谢使用 RuaBot!${NC}"
    echo ""
    echo "如需重新安装，请运行:"
    echo -e "${BLUE}bash <(curl -fsSL https://raw.githubusercontent.com/ValkyrieEY/RuaBot/main/install.sh)${NC}"
    echo ""
    echo -e "${YELLOW}请重新加载 shell 配置:${NC}"
    echo -e "${BLUE}source ~/.bashrc${NC}  # 或 source ~/.zshrc"
    echo ""
    
    exit 0
}

# 配置系统服务
setup_service() {
    log_info "配置 RuaBot 为系统服务..."
    
    # 检查是否有 systemd
    if ! command -v systemctl &> /dev/null; then
        log_error "系统不支持 systemd"
        return 1
    fi
    
    local SERVICE_NAME="ruabot"
    local SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    
    # 确定启动命令
    local START_CMD=""
    if [ -f "$INSTALL_DIR/start.sh" ]; then
        START_CMD="/bin/bash $INSTALL_DIR/start.sh"
    elif [ -f "$INSTALL_DIR/main.py" ]; then
        START_CMD="$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py"
    elif [ -f "$INSTALL_DIR/index.js" ]; then
        START_CMD="/bin/bash -c 'export NVM_DIR=\"$INSTALL_DIR/.nvm\"; [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\"; node $INSTALL_DIR/index.js'"
    else
        log_error "找不到启动文件 (start.sh, main.py 或 index.js)"
        return 1
    fi
    
    # 获取 Node.js 版本路径
    export NVM_DIR="$INSTALL_DIR/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    local NODE_PATH=$(which node 2>/dev/null || echo "$INSTALL_DIR/.nvm/versions/node/v24.12.0/bin")
    
    # 创建 systemd 服务文件
    log_info "创建 systemd 服务配置..."
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=RuaBot Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$START_CMD
Restart=on-failure
RestartSec=10
StandardOutput=append:$INSTALL_DIR/logs/ruabot.log
StandardError=append:$INSTALL_DIR/logs/ruabot.log

# 环境变量
Environment="PATH=$INSTALL_DIR/venv/bin:$NODE_PATH:/usr/local/bin:/usr/bin:/bin"
Environment="NVM_DIR=$INSTALL_DIR/.nvm"
Environment="VIRTUAL_ENV=$INSTALL_DIR/venv"

[Install]
WantedBy=multi-user.target
EOF
    
    log_success "服务文件已创建: $SERVICE_FILE"
    
    # 重新加载 systemd
    log_info "重新加载 systemd..."
    sudo systemctl daemon-reload
    
    # 启用服务
    log_info "启用服务..."
    sudo systemctl enable $SERVICE_NAME
    
    log_success "RuaBot 服务配置完成"
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   RuaBot 服务配置成功！v0.1.0           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "服务管理命令："
    echo -e "  ${YELLOW}sudo systemctl start $SERVICE_NAME${NC}    - 启动服务"
    echo -e "  ${YELLOW}sudo systemctl stop $SERVICE_NAME${NC}     - 停止服务"
    echo -e "  ${YELLOW}sudo systemctl restart $SERVICE_NAME${NC}  - 重启服务"
    echo -e "  ${YELLOW}sudo systemctl status $SERVICE_NAME${NC}   - 查看状态"
    echo -e "  ${YELLOW}sudo systemctl enable $SERVICE_NAME${NC}   - 开机自启"
    echo -e "  ${YELLOW}sudo systemctl disable $SERVICE_NAME${NC}  - 取消自启"
    echo ""
    echo "查看日志："
    echo -e "  ${YELLOW}journalctl -u $SERVICE_NAME -f${NC}        - 实时日志"
    echo -e "  ${YELLOW}journalctl -u $SERVICE_NAME -n 50${NC}     - 最近50行"
    echo ""
    
    read -p "是否现在启动服务? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo systemctl start $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME
    fi
}

# 环境检查
check_requirements() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        RuaBot 环境检查工具${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    
    local passed=0
    local failed=0
    local warnings=0
    
    # 检查操作系统
    echo -e "${YELLOW}[1] 检查操作系统...${NC}"
    if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "    ${GREEN}[OK]${NC} 支持的操作系统: $OSTYPE"
        ((passed++))
    else
        echo -e "    ${RED}[FAIL]${NC} 不支持的操作系统: $OSTYPE"
        ((failed++))
    fi
    
    # 检查 curl 或 wget
    echo -e "${YELLOW}[2] 检查下载工具...${NC}"
    if command -v curl &> /dev/null; then
        echo -e "    ${GREEN}[OK]${NC} curl 已安装: $(curl --version | head -n1)"
        ((passed++))
    elif command -v wget &> /dev/null; then
        echo -e "    ${GREEN}[OK]${NC} wget 已安装: $(wget --version | head -n1)"
        ((passed++))
    else
        echo -e "    ${RED}[FAIL]${NC} 未找到 curl 或 wget"
        ((failed++))
    fi
    
    # 检查网络连接
    echo -e "${YELLOW}[3] 检查网络连接...${NC}"
    if ping -c 1 github.com &> /dev/null 2>&1 || ping -c 1 8.8.8.8 &> /dev/null 2>&1; then
        echo -e "    ${GREEN}[OK]${NC} 网络连接正常"
        ((passed++))
    else
        echo -e "    ${YELLOW}[WARN]${NC} 网络连接可能有问题"
        ((warnings++))
    fi
    
    # 检查磁盘空间
    echo -e "${YELLOW}[4] 检查磁盘空间...${NC}"
    if command -v df &> /dev/null; then
        local available=$(df -h "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')
        if [ -n "$available" ]; then
            echo -e "    ${GREEN}[OK]${NC} 可用空间: $available"
            ((passed++))
        else
            echo -e "    ${YELLOW}[WARN]${NC} 无法检测磁盘空间"
            ((warnings++))
        fi
    else
        echo -e "    ${YELLOW}[WARN]${NC} 无法检测磁盘空间"
        ((warnings++))
    fi
    
    # 检查内存
    echo -e "${YELLOW}[5] 检查内存...${NC}"
    if command -v free &> /dev/null; then
        local total_mem=$(free -m 2>/dev/null | awk 'NR==2 {print $2}')
        if [ -n "$total_mem" ]; then
            echo -e "    ${GREEN}[OK]${NC} 总内存: ${total_mem}MB"
            if [ "$total_mem" -lt 1024 ] 2>/dev/null; then
                echo -e "    ${YELLOW}[WARN]${NC} 建议至少有 1GB 内存"
                ((warnings++))
            else
                ((passed++))
            fi
        else
            echo -e "    ${YELLOW}[WARN]${NC} 无法检测内存"
            ((warnings++))
        fi
    else
        echo -e "    ${YELLOW}[WARN]${NC} 无法检测内存"
        ((warnings++))
    fi
    
    # 检查 Git
    echo -e "${YELLOW}[6] 检查 Git...${NC}"
    if command -v git &> /dev/null; then
        echo -e "    ${GREEN}[OK]${NC} Git 已安装: $(git --version)"
        ((passed++))
    else
        echo -e "    ${YELLOW}[WARN]${NC} Git 未安装 (将自动安装)"
        ((warnings++))
    fi
    
    # 检查编译工具
    echo -e "${YELLOW}[7] 检查编译工具...${NC}"
    if command -v gcc &> /dev/null || command -v clang &> /dev/null; then
        echo -e "    ${GREEN}[OK]${NC} 编译工具已安装"
        ((passed++))
    else
        echo -e "    ${YELLOW}[WARN]${NC} 编译工具未安装 (将自动安装)"
        ((warnings++))
    fi
    
    # 检查 sudo 权限
    echo -e "${YELLOW}[8] 检查管理员权限...${NC}"
    if sudo -n true 2>/dev/null; then
        echo -e "    ${GREEN}[OK]${NC} 有 sudo 权限"
        ((passed++))
    else
        echo -e "    ${YELLOW}[WARN]${NC} 可能需要输入 sudo 密码"
        ((warnings++))
    fi
    
    # 检查 RuaBot 安装
    echo -e "${YELLOW}[9] 检查 RuaBot 安装...${NC}"
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "    ${GREEN}[OK]${NC} RuaBot 已安装: $INSTALL_DIR"
        ((passed++))
    else
        echo -e "    ${RED}[FAIL]${NC} RuaBot 未安装"
        ((failed++))
    fi
    
    # 显示结果
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}  检查结果${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "通过: ${GREEN}$passed${NC}"
    echo -e "警告: ${YELLOW}$warnings${NC}"
    echo -e "失败: ${RED}$failed${NC}"
    echo ""
    
    if [ $failed -eq 0 ]; then
        log_success "系统满足要求！"
    else
        log_warning "发现 $failed 个问题，请先解决"
    fi
    
    echo ""
}

# 显示环境信息
show_environment() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${CYAN}        环境信息${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    
    echo -e "${YELLOW}系统信息:${NC}"
    echo -e "  操作系统: $(uname -s)"
    echo -e "  内核版本: $(uname -r)"
    echo -e "  架构: $(uname -m)"
    echo ""
    
    echo -e "${YELLOW}RuaBot 信息:${NC}"
    echo -e "  安装路径: $INSTALL_DIR"
    
    if [ -f "$INSTALL_DIR/.ruabot.conf" ]; then
        source "$INSTALL_DIR/.ruabot.conf"
        echo -e "  Python 版本: $PYTHON_VERSION"
        echo -e "  Node.js 版本: $NODE_VERSION"
        echo -e "  安装日期: $INSTALL_DATE"
    fi
    echo ""
    
    echo -e "${YELLOW}Python 环境:${NC}"
    if [ -f "$INSTALL_DIR/venv/bin/python" ]; then
        source "$INSTALL_DIR/venv/bin/activate"
        echo -e "  Python: $("$INSTALL_DIR/venv/bin/python" --version)"
        echo -e "  Pip: $("$INSTALL_DIR/venv/bin/pip" --version | cut -d' ' -f1-2)"
        deactivate
    else
        echo -e "  ${RED}虚拟环境未找到${NC}"
    fi
    echo ""
    
    echo -e "${YELLOW}Node.js 环境:${NC}"
    export NVM_DIR="$INSTALL_DIR/.nvm"
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        \. "$NVM_DIR/nvm.sh"
        echo -e "  Node.js: $(node --version 2>/dev/null || echo '未安装')"
        echo -e "  npm: $(npm --version 2>/dev/null || echo '未安装')"
    else
        echo -e "  ${RED}NVM 未找到${NC}"
    fi
    echo ""
    
    echo -e "${YELLOW}磁盘使用:${NC}"
    if [ -d "$INSTALL_DIR" ]; then
        local size=$(du -sh "$INSTALL_DIR" 2>/dev/null | cut -f1)
        echo -e "  安装目录大小: $size"
    fi
    echo ""
}

# 交互式菜单
interactive_menu() {
    while true; do
        show_menu
        read -r choice
        echo ""
        
        case $choice in
            1)
                start_service
                ;;
            2)
                stop_service
                ;;
            3)
                restart_service
                ;;
            4)
                check_status
                ;;
            5)
                view_logs
                ;;
            6)
                check_integrity
                ;;
            7)
                update_framework
                ;;
            8)
                setup_service
                ;;
            9)
                check_requirements
                ;;
            10)
                show_environment
                ;;
            11)
                uninstall_framework
                ;;
            12)
                reinstall_framework
                ;;
            13)
                update_script
                ;;
            14)
                install_ai
                ;;
            15)
                uninstall_ai
                ;;
            16)
                install_webui
                ;;
            17)
                uninstall_webui
                ;;
            18)
                system_maintenance
                ;;
            0)
                log_info "退出 RuaBot Manager"
                exit 0
                ;;
            *)
                log_error "无效的选项，请重新选择"
                ;;
        esac
        
        echo ""
        read -p "按回车键继续..."
        clear
    done
}

# 命令行模式
handle_command() {
    case "$1" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            check_status
            ;;
        logs)
            view_logs
            ;;
        check)
            check_integrity
            ;;
        update)
            update_framework
            ;;
        reinstall)
            reinstall_framework
            ;;
        update-script)
            update_script
            ;;
        install-ai)
            install_ai
            ;;
        uninstall-ai)
            uninstall_ai
            ;;
        install-webui)
            install_webui
            ;;
        uninstall-webui)
            uninstall_webui
            ;;
        maintenance|clean)
            system_maintenance
            ;;
        service|setup-service)
            setup_service
            ;;
        check-req|check-requirements)
            check_requirements
            ;;
        uninstall)
            uninstall_framework
            ;;
        env|info)
            show_environment
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 显示帮助
show_help() {
    show_logo
    echo -e "${YELLOW}用法:${NC}"
    echo "  rcli                  - 打开交互式菜单"
    echo "  rcli <command>        - 执行指定命令"
    echo ""
    echo -e "${YELLOW}可用命令:${NC}"
    echo "  start                 - 启动 RuaBot"
    echo "  stop                  - 停止 RuaBot"
    echo "  restart               - 重启 RuaBot"
    echo "  status                - 查看运行状态"
    echo "  logs                  - 查看日志"
    echo "  check                 - 检查文件完整性"
    echo "  update                - 更新框架（保留用户数据：data、plugins、config.toml）"
    echo "  reinstall             - 重新安装框架（不保留数据，完全重新安装）"
    echo "  update-script         - 更新 rcli 脚本本身"
    echo "  install-ai            - 安装 AI 模块"
    echo "  uninstall-ai          - 卸载 AI 模块"
    echo "  install-webui          - 安装 WebUI"
    echo "  uninstall-webui        - 卸载 WebUI"
    echo "  maintenance, clean     - 系统维护（清理缓存、临时文件、日志）"
    echo "  service, setup-service - 配置系统服务"
    echo "  check-req, check-requirements - 环境检查"
    echo "  uninstall             - 卸载框架"
    echo "  env, info             - 显示环境信息"
    echo "  help                  - 显示此帮助信息"
    echo ""
}

# 主函数
main() {
    if [ $# -eq 0 ]; then
        # 无参数，进入交互式菜单
        clear
        interactive_menu
    else
        # 有参数，执行命令
        handle_command "$1"
    fi
}

# 执行主函数
main "$@"


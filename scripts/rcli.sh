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
    echo -e "  ${RED}0${NC}. 退出"
    echo ""
    echo -ne "${YELLOW}请输入选项 [0-11]:${NC} "
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

# 更新框架
update_framework() {
    log_info "正在更新 RuaBot..."
    
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
    
    log_success "更新完成"
    
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
    echo "  update                - 更新框架"
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


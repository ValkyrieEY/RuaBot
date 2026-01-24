#!/bin/bash
# XQNEXT Framework 状态检查脚本

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "XQNEXT Framework 状态检查"
echo "========================================${NC}"
echo ""

# 检查 docker compose 命令
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# 1. 容器状态
echo -e "${YELLOW}📦 容器状态:${NC}"
if $COMPOSE_CMD ps 2>/dev/null | grep -q "xqnext"; then
    $COMPOSE_CMD ps
    echo ""
    
    # 检查容器是否运行
    if $COMPOSE_CMD ps | grep "xqnext" | grep -q "Up"; then
        echo -e "${GREEN}✓ 容器正在运行${NC}"
    else
        echo -e "${RED}✗ 容器未运行${NC}"
    fi
else
    echo -e "${RED}✗ 未找到容器${NC}"
fi
echo ""

# 2. 健康检查
echo -e "${YELLOW}🏥 健康检查:${NC}"
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8000/health)
    echo -e "${GREEN}✓ 服务健康 - $HEALTH${NC}"
else
    echo -e "${RED}✗ 健康检查失败${NC}"
fi
echo ""

# 3. 端口监听
echo -e "${YELLOW}🔌 端口监听:${NC}"
if command -v netstat &> /dev/null; then
    if netstat -tuln 2>/dev/null | grep -q ":8000"; then
        echo -e "${GREEN}✓ 端口 8000 (WebUI/API) 正在监听${NC}"
    else
        echo -e "${RED}✗ 端口 8000 未监听${NC}"
    fi
    
    if netstat -tuln 2>/dev/null | grep -q ":8080"; then
        echo -e "${GREEN}✓ 端口 8080 (OneBot) 正在监听${NC}"
    else
        echo -e "${YELLOW}⚠ 端口 8080 未监听${NC}"
    fi
elif command -v ss &> /dev/null; then
    if ss -tuln 2>/dev/null | grep -q ":8000"; then
        echo -e "${GREEN}✓ 端口 8000 (WebUI/API) 正在监听${NC}"
    else
        echo -e "${RED}✗ 端口 8000 未监听${NC}"
    fi
    
    if ss -tuln 2>/dev/null | grep -q ":8080"; then
        echo -e "${GREEN}✓ 端口 8080 (OneBot) 正在监听${NC}"
    else
        echo -e "${YELLOW}⚠ 端口 8080 未监听${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 无法检查端口（缺少 netstat 或 ss 命令）${NC}"
fi
echo ""

# 4. 资源使用
echo -e "${YELLOW}📊 资源使用:${NC}"
if docker stats --no-stream xqnext-framework 2>/dev/null; then
    echo ""
else
    echo -e "${YELLOW}⚠ 无法获取资源使用情况${NC}"
fi

# 5. 数据目录
echo -e "${YELLOW}💾 数据目录:${NC}"
if [ -d "../data" ]; then
    DATA_DIR="../data"
elif [ -d "data" ]; then
    DATA_DIR="data"
else
    DATA_DIR=""
fi

if [ -n "$DATA_DIR" ]; then
    echo "  目录: $DATA_DIR"
    echo "  大小: $(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)"
    echo "  文件:"
    ls -lh "$DATA_DIR" 2>/dev/null | grep -v "^total" | awk '{print "    " $9 " (" $5 ")"}'
    echo -e "${GREEN}✓ 数据目录正常${NC}"
else
    echo -e "${RED}✗ 未找到数据目录${NC}"
fi
echo ""

# 6. 日志目录
echo -e "${YELLOW}📝 日志目录:${NC}"
if [ -d "../logs" ]; then
    LOGS_DIR="../logs"
elif [ -d "logs" ]; then
    LOGS_DIR="logs"
else
    LOGS_DIR=""
fi

if [ -n "$LOGS_DIR" ]; then
    echo "  目录: $LOGS_DIR"
    echo "  大小: $(du -sh "$LOGS_DIR" 2>/dev/null | cut -f1)"
    if [ -f "$LOGS_DIR/onebot_framework.log" ]; then
        LOG_SIZE=$(du -h "$LOGS_DIR/onebot_framework.log" 2>/dev/null | cut -f1)
        LOG_LINES=$(wc -l < "$LOGS_DIR/onebot_framework.log" 2>/dev/null)
        echo "  主日志: onebot_framework.log (${LOG_SIZE}, ${LOG_LINES} 行)"
        echo -e "${GREEN}✓ 日志目录正常${NC}"
    else
        echo -e "${YELLOW}⚠ 未找到主日志文件${NC}"
    fi
else
    echo -e "${RED}✗ 未找到日志目录${NC}"
fi
echo ""

# 7. 最近的日志错误
echo -e "${YELLOW}🐛 最近的错误日志:${NC}"
if [ -n "$LOGS_DIR" ] && [ -f "$LOGS_DIR/onebot_framework.log" ]; then
    ERROR_COUNT=$(grep -i "error\|exception\|critical" "$LOGS_DIR/onebot_framework.log" 2>/dev/null | tail -10 | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${RED}  发现 $ERROR_COUNT 条错误:${NC}"
        grep -i "error\|exception\|critical" "$LOGS_DIR/onebot_framework.log" 2>/dev/null | tail -3 | while read -r line; do
            echo "    $line"
        done
    else
        echo -e "${GREEN}✓ 无错误日志${NC}"
    fi
elif $COMPOSE_CMD ps 2>/dev/null | grep -q "xqnext"; then
    ERROR_COUNT=$($COMPOSE_CMD logs --tail=100 xqnext 2>/dev/null | grep -i "error\|exception\|critical" | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${RED}  发现 $ERROR_COUNT 条错误:${NC}"
        $COMPOSE_CMD logs --tail=100 xqnext 2>/dev/null | grep -i "error\|exception\|critical" | tail -3 | while read -r line; do
            echo "    $line"
        done
    else
        echo -e "${GREEN}✓ 无错误日志${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 无法检查日志${NC}"
fi
echo ""

# 8. OneBot 连接状态
echo -e "${YELLOW}🤖 OneBot 连接:${NC}"
if [ -n "$LOGS_DIR" ] && [ -f "$LOGS_DIR/onebot_framework.log" ]; then
    if grep -q "WebSocket 连接成功\|Connected to OneBot" "$LOGS_DIR/onebot_framework.log" 2>/dev/null; then
        echo -e "${GREEN}✓ OneBot 已连接${NC}"
    else
        echo -e "${YELLOW}⚠ 未检测到 OneBot 连接${NC}"
    fi
elif $COMPOSE_CMD ps 2>/dev/null | grep -q "xqnext"; then
    if $COMPOSE_CMD logs --tail=100 xqnext 2>/dev/null | grep -q "WebSocket 连接成功\|Connected to OneBot"; then
        echo -e "${GREEN}✓ OneBot 已连接${NC}"
    else
        echo -e "${YELLOW}⚠ 未检测到 OneBot 连接${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 无法检查 OneBot 状态${NC}"
fi
echo ""

# 9. 磁盘空间
echo -e "${YELLOW}💿 磁盘空间:${NC}"
if command -v df &> /dev/null; then
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    DISK_AVAIL=$(df -h . | awk 'NR==2 {print $4}')
    echo "  可用空间: $DISK_AVAIL"
    echo "  使用率: $DISK_USAGE%"
    
    if [ "$DISK_USAGE" -gt 90 ]; then
        echo -e "${RED}✗ 磁盘空间不足！${NC}"
    elif [ "$DISK_USAGE" -gt 80 ]; then
        echo -e "${YELLOW}⚠ 磁盘空间偏低${NC}"
    else
        echo -e "${GREEN}✓ 磁盘空间充足${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 无法检查磁盘空间${NC}"
fi
echo ""

# 10. Docker 镜像
echo -e "${YELLOW}🐳 Docker 镜像:${NC}"
if docker images | grep -q "xqnext-framework"; then
    docker images | grep "xqnext-framework" | awk '{print "  " $1 ":" $2 " (" $7 " " $8 " ago)"}'
    echo -e "${GREEN}✓ Docker 镜像存在${NC}"
else
    echo -e "${RED}✗ 未找到 xqnext-framework 镜像${NC}"
fi
echo ""

# 总结
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}📋 检查完成${NC}"
echo ""
echo -e "${YELLOW}快速操作:${NC}"
echo "  查看实时日志: $COMPOSE_CMD logs -f xqnext"
echo "  重启服务: $COMPOSE_CMD restart xqnext"
echo "  进入容器: $COMPOSE_CMD exec xqnext bash"
echo "  查看详细状态: $COMPOSE_CMD ps -a"
echo ""


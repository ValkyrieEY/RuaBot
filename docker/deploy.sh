#!/bin/bash
# XQNEXT Framework 一键部署脚本

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "  ___  ____   ___  _   _  _____  _____ _____ "
echo " |_ _||  _ \ / _ \| \ | || ____||_   _||_  _|"
echo "  | | | | | | | | |  \| ||  _|    | |   | |  "
echo "  | | | |_| | |_| | |\  || |___   | |   | |  "
echo " |___||____/ \___/|_| \_||_____|  |_|   |_|  "
echo ""
echo -e "${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}XQNEXT Framework 一键部署${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Docker
echo -e "${YELLOW}[1/7] 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未安装 Docker${NC}"
    echo "请访问 https://docs.docker.com/get-docker/ 安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: 未安装 Docker Compose${NC}"
    echo "请访问 https://docs.docker.com/compose/install/ 安装 Docker Compose"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境正常${NC}"
echo "  Docker 版本: $(docker --version)"
echo "  Docker Compose 版本: $(docker-compose --version)"

# 检查环境变量文件
echo ""
echo -e "${YELLOW}[2/7] 检查环境变量配置...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}未找到 .env 文件，从模板创建...${NC}"
    if [ -f "env.example" ]; then
        cp env.example .env
        echo -e "${GREEN}✓ 已创建 .env 文件${NC}"
        echo -e "${YELLOW}请编辑 .env 文件配置必要的参数，然后重新运行此脚本${NC}"
        echo "  主要配置项："
        echo "  - SECRET_KEY: 修改为随机字符串"
        echo "  - WEB_UI_PASSWORD: 修改默认密码"
        echo "  - ONEBOT_WS_URL: OneBot WebSocket 地址"
        echo "  - OPENAI_API_KEY: OpenAI API Key（如果使用 AI）"
        exit 0
    else
        echo -e "${RED}错误: 未找到 env.example 模板文件${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ 找到环境变量配置${NC}"
fi

# 检查配置文件
echo ""
echo -e "${YELLOW}[3/7] 检查配置文件...${NC}"
if [ ! -f "../config.toml" ]; then
    echo -e "${RED}错误: 未找到 config.toml 文件${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 配置文件正常${NC}"

# 创建必要的目录
echo ""
echo -e "${YELLOW}[4/7] 创建数据目录...${NC}"
mkdir -p ../data ../logs ../backups
echo -e "${GREEN}✓ 目录创建完成${NC}"

# 构建镜像
echo ""
echo -e "${YELLOW}[5/7] 构建 Docker 镜像...${NC}"
docker-compose build
echo -e "${GREEN}✓ 镜像构建完成${NC}"

# 启动服务
echo ""
echo -e "${YELLOW}[6/7] 启动服务...${NC}"
docker-compose up -d
echo -e "${GREEN}✓ 服务启动成功${NC}"

# 等待服务就绪
echo ""
echo -e "${YELLOW}[7/7] 等待服务就绪...${NC}"
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ 服务运行正常${NC}"
else
    echo -e "${RED}警告: 服务可能未正常启动${NC}"
    echo "请检查日志: docker-compose logs -f xqnext"
fi

# 显示访问信息
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}访问信息:${NC}"
echo "  WebUI: http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
echo "  健康检查: http://localhost:8000/health"
echo ""
echo -e "${BLUE}默认登录凭据:${NC}"
echo "  用户名: admin"
echo "  密码: (查看 .env 文件中的 WEB_UI_PASSWORD)"
echo ""
echo -e "${BLUE}常用命令:${NC}"
echo "  查看日志: docker-compose logs -f xqnext"
echo "  停止服务: docker-compose stop"
echo "  重启服务: docker-compose restart"
echo "  进入容器: docker-compose exec xqnext bash"
echo ""
echo -e "${BLUE}备份和恢复:${NC}"
echo "  备份数据: ./backup.sh"
echo "  恢复数据: ./restore.sh <backup-file>"
echo ""
echo -e "${GREEN}========================================${NC}"


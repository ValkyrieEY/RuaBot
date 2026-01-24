#!/bin/bash
# XQNEXT Framework 镜像导出脚本
# 用于创建分发包

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
IMAGE_NAME="xqnext-framework"
IMAGE_TAG="0.0.2"
OUTPUT_DIR="../dist"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}"
echo "========================================${NC}"
echo -e "${BLUE}XQNEXT Framework 镜像导出工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查镜像是否存在
echo -e "${YELLOW}[1/6] 检查 Docker 镜像...${NC}"
if ! docker images | grep -q "$IMAGE_NAME"; then
    echo -e "${RED}错误: 未找到镜像 $IMAGE_NAME${NC}"
    echo "请先构建镜像: docker compose build"
    exit 1
fi
echo -e "${GREEN}✓ 找到镜像 $IMAGE_NAME:$IMAGE_TAG${NC}"

# 显示镜像信息
IMAGE_SIZE=$(docker images $IMAGE_NAME:$IMAGE_TAG --format "{{.Size}}")
echo "  镜像大小: $IMAGE_SIZE"
echo ""

# 创建输出目录
echo -e "${YELLOW}[2/6] 创建输出目录...${NC}"
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}✓ 输出目录: $OUTPUT_DIR${NC}"
echo ""

# 导出镜像
echo -e "${YELLOW}[3/6] 导出 Docker 镜像...${NC}"
echo "  这可能需要几分钟，请稍候..."
EXPORT_FILE="$OUTPUT_DIR/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"
docker save $IMAGE_NAME:$IMAGE_TAG | gzip > "$EXPORT_FILE"
echo -e "${GREEN}✓ 镜像已导出${NC}"

# 显示导出文件信息
EXPORT_SIZE=$(du -h "$EXPORT_FILE" | cut -f1)
echo "  文件: $EXPORT_FILE"
echo "  大小: $EXPORT_SIZE"
echo ""

# 复制必要的配置文件
echo -e "${YELLOW}[4/6] 复制配置文件...${NC}"
DIST_CONFIG_DIR="$OUTPUT_DIR/config"
mkdir -p "$DIST_CONFIG_DIR"

cp docker-compose.yml "$DIST_CONFIG_DIR/"
cp env.example "$DIST_CONFIG_DIR/"
cp ../config.toml "$DIST_CONFIG_DIR/"
cp deploy.sh "$DIST_CONFIG_DIR/"
cp backup.sh "$DIST_CONFIG_DIR/"
cp restore.sh "$DIST_CONFIG_DIR/"
cp quick-deploy.sh "$DIST_CONFIG_DIR/"
cp check-status.sh "$DIST_CONFIG_DIR/"

# 添加执行权限
chmod +x "$DIST_CONFIG_DIR"/*.sh

echo -e "${GREEN}✓ 配置文件已复制${NC}"
echo ""

# 创建 README
echo -e "${YELLOW}[5/6] 创建部署说明...${NC}"
cat > "$DIST_CONFIG_DIR/README.txt" <<EOF
==========================================
XQNEXT Framework 部署包
==========================================

版本: $IMAGE_TAG
构建时间: $(date '+%Y-%m-%d %H:%M:%S')
镜像大小: $IMAGE_SIZE
打包大小: $EXPORT_SIZE

==========================================
快速部署步骤
==========================================

1. 加载 Docker 镜像
   docker load < ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz

2. 准备配置文件
   cd config
   cp env.example .env
   nano .env  # 修改必要的配置

3. 创建数据目录
   mkdir -p data logs plugins

4. 启动服务
   docker compose up -d

5. 访问服务
   WebUI: http://localhost:8000
   用户名: admin
   密码: (查看 .env 中的 WEB_UI_PASSWORD)

==========================================
一键部署
==========================================

Linux/macOS:
   cd config
   chmod +x quick-deploy.sh
   ./quick-deploy.sh

Windows:
   使用 Docker Desktop
   在 config 目录下双击 quick-deploy.bat

==========================================
必须配置的参数
==========================================

1. SECRET_KEY - 应用密钥（必须修改）
   生成方法: openssl rand -hex 32

2. WEB_UI_PASSWORD - WebUI 登录密码（必须修改）

3. ONEBOT_WS_URL - OneBot WebSocket 地址
   示例: ws://your-onebot-host:3001

4. ONEBOT_ACCESS_TOKEN - OneBot 访问令牌（如果需要）

5. OPENAI_API_KEY - OpenAI API Key（如果使用 AI 功能）

==========================================
常用命令
==========================================

查看日志:
  docker compose logs -f xqnext

查看状态:
  docker compose ps
  ./check-status.sh

停止服务:
  docker compose stop

重启服务:
  docker compose restart

备份数据:
  ./backup.sh

恢复数据:
  ./restore.sh <backup-file>

==========================================
目录结构
==========================================

xqnext-distribution/
├── xqnext-framework-${IMAGE_TAG}.tar.gz  # Docker 镜像
└── config/                                # 配置文件
    ├── docker-compose.yml                # Docker Compose 配置
    ├── env.example                       # 环境变量模板
    ├── config.toml                       # 应用配置文件
    ├── deploy.sh                         # 完整部署脚本
    ├── quick-deploy.sh                   # 快速部署脚本
    ├── backup.sh                         # 备份脚本
    ├── restore.sh                        # 恢复脚本
    ├── check-status.sh                   # 状态检查脚本
    └── README.txt                        # 本文件

==========================================
故障排查
==========================================

1. 容器无法启动
   - 查看日志: docker compose logs xqnext
   - 检查端口占用: netstat -tuln | grep 8000
   - 检查配置文件: cat .env

2. 无法连接 OneBot
   - 检查 WebSocket 地址是否正确
   - 测试网络连接: ping onebot-host
   - 查看连接日志: docker compose logs xqnext | grep -i onebot

3. WebUI 无法访问
   - 检查容器状态: docker compose ps
   - 检查健康状态: curl http://localhost:8000/health
   - 检查防火墙: sudo ufw status

==========================================
获取支持
==========================================

详细文档: 查看 DEPLOYMENT_GUIDE.md
GitHub: https://github.com/your-repo/xqnext
Issue: https://github.com/your-repo/xqnext/issues

==========================================
EOF

echo -e "${GREEN}✓ 部署说明已创建${NC}"
echo ""

# 创建最终的分发包
echo -e "${YELLOW}[6/6] 创建分发包...${NC}"
cd "$OUTPUT_DIR"
DIST_PACKAGE="xqnext-distribution-${IMAGE_TAG}-${TIMESTAMP}.tar.gz"
tar czf "$DIST_PACKAGE" \
    "${IMAGE_NAME}-${IMAGE_TAG}.tar.gz" \
    config/

DIST_SIZE=$(du -h "$DIST_PACKAGE" | cut -f1)
echo -e "${GREEN}✓ 分发包已创建${NC}"
echo "  文件: $OUTPUT_DIR/$DIST_PACKAGE"
echo "  大小: $DIST_SIZE"
echo ""

# 显示摘要
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 导出完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📦 分发包信息:${NC}"
echo "  位置: $OUTPUT_DIR/$DIST_PACKAGE"
echo "  大小: $DIST_SIZE"
echo "  包含:"
echo "    - Docker 镜像 ($EXPORT_SIZE)"
echo "    - 配置文件和脚本"
echo "    - 部署说明文档"
echo ""
echo -e "${BLUE}📝 使用方法:${NC}"
echo "  1. 将分发包传输到目标服务器"
echo "  2. 解压: tar xzf $DIST_PACKAGE"
echo "  3. 进入目录: cd xqnext-distribution-${IMAGE_TAG}-*"
echo "  4. 查看 README: cat config/README.txt"
echo "  5. 执行部署: cd config && ./quick-deploy.sh"
echo ""
echo -e "${BLUE}🔒 安全提醒:${NC}"
echo "  - 务必修改默认密码和密钥"
echo "  - 妥善保管 .env 配置文件"
echo "  - 定期备份数据"
echo ""
echo -e "${GREEN}========================================${NC}"


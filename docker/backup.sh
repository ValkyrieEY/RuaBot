#!/bin/bash
# XQNEXT Framework 备份脚本

set -e

# 配置
BACKUP_DIR="../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="xqnext-backup-${TIMESTAMP}.tar.gz"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}XQNEXT Framework 备份工具${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

echo -e "${YELLOW}[1/4] 停止服务...${NC}"
docker-compose stop xqnext

echo -e "${YELLOW}[2/4] 备份数据...${NC}"
tar czf "${BACKUP_DIR}/${BACKUP_FILE}" \
    -C .. \
    data/ \
    plugins/ \
    config.toml \
    2>/dev/null || true

echo -e "${YELLOW}[3/4] 启动服务...${NC}"
docker-compose start xqnext

echo -e "${YELLOW}[4/4] 清理旧备份（保留最近5个）...${NC}"
cd "${BACKUP_DIR}"
ls -t xqnext-backup-*.tar.gz | tail -n +6 | xargs -r rm

echo ""
echo -e "${GREEN}✓ 备份完成！${NC}"
echo -e "备份文件: ${BACKUP_DIR}/${BACKUP_FILE}"
echo -e "文件大小: $(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)"
echo ""
echo -e "${GREEN}========================================${NC}"


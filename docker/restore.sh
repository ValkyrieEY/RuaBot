#!/bin/bash
# XQNEXT Framework 恢复脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}XQNEXT Framework 恢复工具${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查参数
if [ -z "$1" ]; then
    echo -e "${RED}错误: 请指定备份文件${NC}"
    echo "用法: $0 <backup-file.tar.gz>"
    echo ""
    echo "可用的备份文件:"
    ls -lh ../backups/xqnext-backup-*.tar.gz 2>/dev/null || echo "  (没有找到备份文件)"
    exit 1
fi

BACKUP_FILE="$1"

# 检查备份文件是否存在
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}错误: 备份文件不存在: ${BACKUP_FILE}${NC}"
    exit 1
fi

# 确认操作
echo -e "${YELLOW}警告: 此操作将覆盖现有数据！${NC}"
echo -e "备份文件: ${BACKUP_FILE}"
echo -e "文件大小: $(du -h "${BACKUP_FILE}" | cut -f1)"
echo ""
read -p "确认要恢复吗? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}已取消${NC}"
    exit 0
fi

echo -e "${YELLOW}[1/4] 停止服务...${NC}"
docker-compose stop xqnext

echo -e "${YELLOW}[2/4] 备份当前数据...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
tar czf "../backups/pre-restore-${TIMESTAMP}.tar.gz" \
    -C .. \
    data/ \
    plugins/ \
    config.toml \
    2>/dev/null || true

echo -e "${YELLOW}[3/4] 恢复数据...${NC}"
tar xzf "${BACKUP_FILE}" -C ..

echo -e "${YELLOW}[4/4] 启动服务...${NC}"
docker-compose start xqnext

echo ""
echo -e "${GREEN}✓ 恢复完成！${NC}"
echo -e "当前数据已备份到: ../backups/pre-restore-${TIMESTAMP}.tar.gz"
echo ""
echo -e "${GREEN}========================================${NC}"


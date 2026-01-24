# XQNEXT Framework 分发部署完整指南

## 📋 目录

1. [Docker 配置检查](#docker-配置检查)
2. [部署准备](#部署准备)
3. [本地部署](#本地部署)
4. [生产环境部署](#生产环境部署)
5. [分发部署方案](#分发部署方案)
6. [常见问题解决](#常见问题解决)

---

## 🔍 Docker 配置检查

### 当前配置状态

✅ **已完成的配置：**

1. ✅ **Dockerfile** - 多阶段构建配置
   - 前端构建阶段（Node.js 20 Alpine）
   - Python 依赖构建阶段（Python 3.11）
   - 最终运行时镜像（包含字体支持）

2. ✅ **docker-compose.yml** - 生产环境配置
   - 端口映射：8000（WebUI/API）、8080（OneBot WebSocket）
   - 数据持久化：data、logs、plugins 目录
   - 健康检查和资源限制
   - 可选服务：PostgreSQL、Redis、Prometheus、Grafana

3. ✅ **环境变量配置** - env.example
   - 基本配置（环境、日志级别）
   - 安全配置（密钥、登录凭据）
   - OneBot 配置
   - AI 配置（可选）

4. ✅ **部署脚本**
   - `deploy.sh` - 一键部署脚本
   - `backup.sh` - 数据备份脚本
   - `restore.sh` - 数据恢复脚本

5. ✅ **开发环境配置** - docker-compose.dev.yml
   - 热重载支持
   - 源代码挂载

---

## 🎯 部署准备

### 系统要求

**最低配置：**
- CPU: 2 核心
- 内存: 2GB RAM
- 磁盘: 5GB 可用空间
- 操作系统: Linux, macOS, Windows (WSL2)

**推荐配置：**
- CPU: 4 核心
- 内存: 4GB RAM
- 磁盘: 20GB 可用空间（用于日志和数据库）

### 安装 Docker

**Linux (Ubuntu/Debian):**
```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 启动 Docker 服务
sudo systemctl enable docker
sudo systemctl start docker

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

**Windows:**
1. 下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 启用 WSL2 后端
3. 重启计算机

**macOS:**
1. 下载并安装 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
2. 启动 Docker Desktop

### 验证安装

```bash
# 检查 Docker 版本
docker --version
# 输出示例: Docker version 24.0.7, build afdd53b

# 检查 Docker Compose 版本
docker compose version
# 输出示例: Docker Compose version v2.23.0

# 测试 Docker 运行
docker run hello-world
```

---

## 💻 本地部署

### 方法 1: 使用一键部署脚本（推荐）

```bash
# 1. 克隆或解压项目
cd XQNEXT

# 2. 进入 docker 目录
cd docker

# 3. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

脚本会自动：
- ✅ 检查 Docker 环境
- ✅ 创建 .env 配置文件
- ✅ 创建必要的目录
- ✅ 构建 Docker 镜像
- ✅ 启动服务
- ✅ 显示访问信息

### 方法 2: 手动部署

```bash
# 1. 进入 docker 目录
cd docker

# 2. 创建环境变量文件
cp env.example .env

# 3. 编辑 .env 文件（重要！）
nano .env
# 或者使用其他编辑器
code .env

# 4. 创建必要的目录
mkdir -p ../data ../logs ../backups

# 5. 构建镜像
docker compose build

# 6. 启动服务
docker compose up -d

# 7. 查看日志
docker compose logs -f xqnext

# 8. 检查服务状态
docker compose ps
```

### 必须修改的配置项

编辑 `.env` 文件，修改以下重要配置：

```bash
# 1. 安全配置（必须修改！）
SECRET_KEY=your-random-secret-key-here  # 使用随机字符串
WEB_UI_PASSWORD=your-secure-password    # 修改默认密码

# 2. OneBot 配置
ONEBOT_WS_URL=ws://host.docker.internal:3001  # 替换为你的 OneBot WebSocket 地址
ONEBOT_ACCESS_TOKEN=your-token-here           # 如果你的 OneBot 需要 token

# 3. AI 配置（如果使用 AI 功能）
OPENAI_API_KEY=sk-your-openai-api-key
```

### 访问服务

部署成功后，访问：

- **WebUI 管理界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

默认登录凭据：
- 用户名: `admin`
- 密码: `.env` 文件中的 `WEB_UI_PASSWORD`

---

## 🚀 生产环境部署

### 1. 服务器准备

```bash
# 1. 更新系统
sudo apt-get update && sudo apt-get upgrade -y

# 2. 安装 Docker（如果未安装）
curl -fsSL https://get.docker.com | sh

# 3. 安装 Docker Compose
sudo apt-get install docker-compose-plugin

# 4. 配置防火墙
sudo ufw allow 8000/tcp  # WebUI/API
sudo ufw allow 8080/tcp  # OneBot WebSocket
sudo ufw enable
```

### 2. 安全加固

**A. 修改默认配置**

```bash
# 生成随机密钥
SECRET_KEY=$(openssl rand -hex 32)
echo "SECRET_KEY=$SECRET_KEY" >> .env

# 修改默认密码
read -sp "输入新的 WebUI 密码: " password
echo "WEB_UI_PASSWORD=$password" >> .env
```

**B. 限制网络访问**

编辑 `docker-compose.yml`，修改端口映射：

```yaml
ports:
  # 只在本地监听（如果使用 Nginx 反向代理）
  - "127.0.0.1:8000:8000"
  - "127.0.0.1:8080:8080"
```

**C. 使用 HTTPS（推荐）**

使用 Nginx 作为反向代理并配置 SSL：

```bash
# 安装 Nginx
sudo apt-get install nginx certbot python3-certbot-nginx

# 获取 SSL 证书
sudo certbot --nginx -d your-domain.com

# Nginx 配置示例
sudo nano /etc/nginx/sites-available/xqnext
```

Nginx 配置文件内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /onebot/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. 启用数据库和缓存（大规模部署）

编辑 `docker-compose.yml`，取消以下服务的注释：

```yaml
# PostgreSQL 数据库
postgres:
  image: postgres:15-alpine
  # ...

# Redis 缓存
redis:
  image: redis:7-alpine
  # ...
```

然后修改 `.env`：

```bash
DATABASE_URL=postgresql+asyncpg://xqnext:xqnext123@postgres:5432/xqnext
POSTGRES_PASSWORD=your-secure-password
```

### 4. 启用监控（可选）

取消 Prometheus 和 Grafana 的注释：

```bash
# 启动监控服务
docker compose up -d prometheus grafana

# 访问 Grafana
# URL: http://localhost:3000
# 默认用户名/密码: admin/admin
```

### 5. 设置自动备份

添加 cron 任务：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨 2 点备份）
0 2 * * * cd /path/to/XQNEXT/docker && ./backup.sh >> /var/log/xqnext-backup.log 2>&1

# 每周清理旧备份（保留最近 30 天）
0 3 * * 0 find /path/to/XQNEXT/backups -name "*.tar.gz" -mtime +30 -delete
```

---

## 📦 分发部署方案

### 方案 1: Docker 镜像分发（推荐）

适合：内网部署、多台服务器部署

**步骤 1: 构建并保存镜像**

```bash
# 1. 构建镜像
cd docker
docker compose build

# 2. 保存镜像为 tar 文件
docker save xqnext-framework:0.0.2 | gzip > xqnext-framework-0.0.2.tar.gz

# 3. 查看镜像大小
ls -lh xqnext-framework-0.0.2.tar.gz
```

**步骤 2: 准备分发包**

创建分发包目录结构：

```bash
# 创建分发目录
mkdir -p xqnext-distribution
cd xqnext-distribution

# 复制必要文件
cp ../docker/docker-compose.yml ./
cp ../docker/env.example ./
cp ../docker/deploy.sh ./
cp ../docker/backup.sh ./
cp ../docker/restore.sh ./
cp ../config.toml ./
cp ../xqnext-framework-0.0.2.tar.gz ./

# 创建 README
cat > README.txt <<EOF
XQNEXT Framework 部署包

部署步骤：
1. 安装 Docker 和 Docker Compose
2. 加载镜像: docker load < xqnext-framework-0.0.2.tar.gz
3. 配置环境: cp env.example .env && nano .env
4. 创建目录: mkdir -p data logs plugins
5. 启动服务: docker compose up -d
6. 访问: http://localhost:8000

详细文档：https://your-docs-url.com
EOF

# 打包
cd ..
tar czf xqnext-distribution.tar.gz xqnext-distribution/
```

**步骤 3: 在目标服务器部署**

```bash
# 1. 解压分发包
tar xzf xqnext-distribution.tar.gz
cd xqnext-distribution

# 2. 加载 Docker 镜像
docker load < xqnext-framework-0.0.2.tar.gz

# 3. 配置环境变量
cp env.example .env
nano .env  # 修改必要的配置

# 4. 创建数据目录
mkdir -p data logs plugins

# 5. 启动服务
docker compose up -d

# 6. 查看日志
docker compose logs -f
```

### 方案 2: Docker Registry 分发

适合：持续部署、多环境部署

**步骤 1: 推送到 Docker Registry**

```bash
# 1. 登录 Docker Hub（或私有 Registry）
docker login

# 2. 标记镜像
docker tag xqnext-framework:0.0.2 yourusername/xqnext-framework:0.0.2
docker tag xqnext-framework:0.0.2 yourusername/xqnext-framework:latest

# 3. 推送镜像
docker push yourusername/xqnext-framework:0.0.2
docker push yourusername/xqnext-framework:latest
```

**步骤 2: 修改 docker-compose.yml**

```yaml
services:
  xqnext:
    image: yourusername/xqnext-framework:0.0.2  # 使用远程镜像
    # 删除 build 配置
    # ...
```

**步骤 3: 在目标服务器部署**

```bash
# 1. 准备配置文件
mkdir xqnext-deployment
cd xqnext-deployment

# 下载 docker-compose.yml 和 env.example
wget https://your-repo/docker-compose.yml
wget https://your-repo/env.example

# 2. 配置环境
cp env.example .env
nano .env

# 3. 创建目录
mkdir -p data logs plugins

# 4. 启动服务（会自动拉取镜像）
docker compose pull
docker compose up -d
```

### 方案 3: 完整源码部署

适合：需要自定义修改、开发环境

**步骤 1: 准备源码包**

```bash
# 1. 打包源码（排除不必要的文件）
cd XQNEXT
tar --exclude='node_modules' \
    --exclude='.git' \
    --exclude='data' \
    --exclude='logs' \
    --exclude='*.db' \
    --exclude='__pycache__' \
    -czf xqnext-source-0.0.2.tar.gz .
```

**步骤 2: 在目标服务器部署**

```bash
# 1. 解压源码
tar xzf xqnext-source-0.0.2.tar.gz -C xqnext
cd xqnext

# 2. 进入 docker 目录
cd docker

# 3. 运行一键部署脚本
chmod +x deploy.sh
./deploy.sh
```

### 方案 4: 自动化部署（使用脚本）

创建一键部署脚本 `auto-deploy.sh`：

```bash
#!/bin/bash
# XQNEXT 自动部署脚本

set -e

REPO_URL="https://github.com/your-repo/xqnext.git"
BRANCH="main"
INSTALL_DIR="/opt/xqnext"

echo "开始自动部署 XQNEXT Framework..."

# 1. 安装 Docker（如果未安装）
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 2. 安装 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "安装 Docker Compose..."
    apt-get update
    apt-get install -y docker-compose-plugin
fi

# 3. 克隆或更新代码
if [ -d "$INSTALL_DIR" ]; then
    echo "更新现有代码..."
    cd $INSTALL_DIR
    git pull origin $BRANCH
else
    echo "克隆代码..."
    git clone -b $BRANCH $REPO_URL $INSTALL_DIR
    cd $INSTALL_DIR
fi

# 4. 配置环境变量
cd docker
if [ ! -f .env ]; then
    echo "创建环境变量文件..."
    cp env.example .env
    
    # 生成随机密钥
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/change-this-to-a-random-secret-key/$SECRET_KEY/" .env
    
    echo "请编辑 .env 文件配置必要的参数，然后重新运行此脚本"
    exit 0
fi

# 5. 创建目录
mkdir -p ../data ../logs ../backups

# 6. 构建并启动
echo "构建 Docker 镜像..."
docker compose build

echo "启动服务..."
docker compose up -d

# 7. 等待服务就绪
echo "等待服务启动..."
sleep 10

# 8. 检查健康状态
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ 部署成功！"
    echo "访问: http://localhost:8000"
else
    echo "✗ 服务可能未正常启动，请检查日志："
    echo "docker compose logs -f xqnext"
fi
```

使用方法：

```bash
# 在目标服务器上运行
wget https://your-repo/auto-deploy.sh
chmod +x auto-deploy.sh
sudo ./auto-deploy.sh
```

---

## 🔧 常见问题解决

### 1. 容器无法启动

**问题**: 运行 `docker compose up -d` 后容器立即退出

**解决方法**:

```bash
# 查看详细日志
docker compose logs xqnext

# 常见原因：
# - config.toml 文件格式错误
# - 环境变量配置错误
# - 端口被占用

# 检查端口占用
sudo lsof -i :8000
sudo lsof -i :8080

# 停止占用端口的进程或修改 .env 中的端口配置
```

### 2. 无法连接 OneBot

**问题**: 日志显示 WebSocket 连接失败

**解决方法**:

```bash
# 1. 检查 OneBot 服务是否运行
# 2. 检查 .env 中的 ONEBOT_WS_URL 配置

# 如果 OneBot 运行在宿主机：
# Linux/Mac: ws://host.docker.internal:3001
# Windows: ws://host.docker.internal:3001

# 如果 OneBot 运行在其他服务器：
# ONEBOT_WS_URL=ws://服务器IP:端口

# 3. 检查防火墙设置
sudo ufw allow 3001/tcp

# 4. 测试网络连接
docker compose exec xqnext ping host.docker.internal
```

### 3. 数据丢失

**问题**: 容器重启后数据丢失

**解决方法**:

```bash
# 检查数据卷挂载
docker compose config | grep volumes

# 确保 docker-compose.yml 中正确配置了卷挂载：
volumes:
  - ../data:/app/data
  - ../logs:/app/logs
  - ../plugins:/app/plugins

# 恢复备份
./restore.sh backups/xqnext-backup-20240101.tar.gz
```

### 4. 镜像构建失败

**问题**: `docker compose build` 失败

**解决方法**:

```bash
# 1. 清理 Docker 缓存
docker system prune -a

# 2. 检查网络连接（需要下载依赖）
ping pypi.org
ping registry.npmjs.org

# 3. 使用国内镜像（如果在中国）
# 修改 Dockerfile，添加镜像源：

# For pip:
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# For npm:
RUN npm config set registry https://registry.npmmirror.com

# 4. 重新构建（不使用缓存）
docker compose build --no-cache
```

### 5. 内存不足

**问题**: 容器运行缓慢或被 OOM Kill

**解决方法**:

```bash
# 1. 查看资源使用情况
docker stats xqnext-framework

# 2. 调整 docker-compose.yml 中的资源限制
deploy:
  resources:
    limits:
      cpus: '4'        # 增加 CPU 限制
      memory: 4G       # 增加内存限制

# 3. 清理日志
find ../logs -name "*.log" -size +100M -delete

# 4. 优化数据库
docker compose exec xqnext sqlite3 data/framework.db "VACUUM;"
```

### 6. WebUI 无法访问

**问题**: 浏览器无法打开 http://localhost:8000

**解决方法**:

```bash
# 1. 检查容器状态
docker compose ps

# 2. 检查端口映射
docker compose port xqnext 8000

# 3. 检查防火墙
sudo ufw status
sudo ufw allow 8000/tcp

# 4. 测试本地访问
curl http://localhost:8000/health

# 5. 查看详细日志
docker compose logs -f xqnext | grep -i error
```

### 7. 插件无法加载

**问题**: 插件目录中的插件无法被识别

**解决方法**:

```bash
# 1. 检查插件目录挂载
docker compose exec xqnext ls -la /app/plugins/

# 2. 检查插件配置文件
docker compose exec xqnext cat /app/plugins/your_plugin/plugin.json

# 3. 查看插件加载日志
docker compose logs xqnext | grep -i plugin

# 4. 手动重新加载插件
docker compose restart xqnext
```

### 8. 更新到新版本

**问题**: 如何升级到新版本

**解决方法**:

```bash
# 1. 备份数据
./backup.sh

# 2. 停止服务
docker compose stop

# 3. 拉取新代码（源码部署）
git pull origin main

# 或加载新镜像（镜像部署）
docker load < xqnext-framework-0.0.3.tar.gz

# 4. 重新构建
docker compose build --no-cache

# 5. 启动新版本
docker compose up -d

# 6. 查看日志确认无错误
docker compose logs -f xqnext

# 7. 如果有问题，回滚
docker compose down
./restore.sh backups/xqnext-backup-latest.tar.gz
docker compose up -d
```

---

## 📊 监控和维护

### 日常检查

```bash
# 1. 检查服务状态
docker compose ps

# 2. 查看资源使用
docker stats xqnext-framework

# 3. 检查日志（最后 100 行）
docker compose logs --tail=100 xqnext

# 4. 检查磁盘空间
df -h

# 5. 检查健康状态
curl http://localhost:8000/health
```

### 性能优化

```bash
# 1. 清理 Docker 缓存
docker system prune -a --volumes

# 2. 清理旧日志
find ../logs -name "*.log" -mtime +7 -delete

# 3. 优化数据库
docker compose exec xqnext sqlite3 data/framework.db "VACUUM;"

# 4. 重启服务（释放内存）
docker compose restart xqnext
```

### 定期维护

建议每周执行：

```bash
#!/bin/bash
# 维护脚本 maintenance.sh

# 1. 备份数据
./backup.sh

# 2. 清理旧备份（保留最近 30 天）
find ../backups -name "*.tar.gz" -mtime +30 -delete

# 3. 清理日志
find ../logs -name "*.log" -mtime +7 -delete

# 4. 优化数据库
docker compose exec xqnext sqlite3 data/framework.db "VACUUM;"

# 5. 清理 Docker 缓存
docker system prune -f

# 6. 重启服务
docker compose restart xqnext

echo "维护完成"
```

---

## 📞 获取支持

如果遇到问题：

1. 查看 [常见问题解决](#常见问题解决) 章节
2. 查看 [详细文档](../docs/README.md)
3. 提交 GitHub Issue: https://github.com/your-repo/issues
4. 加入社区讨论: https://community.your-domain.com

---

## 📝 附录

### A. 完整的 .env 配置示例

```bash
# ===========================================
# XQNEXT Framework 生产环境配置
# ===========================================

# 基本配置
ENVIRONMENT=production
LOG_LEVEL=INFO

# 端口配置
API_PORT=8000
ONEBOT_PORT=8080

# 安全配置（必须修改！）
SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
WEB_UI_USERNAME=admin
WEB_UI_PASSWORD=YourSecurePassword123!

# OneBot 配置
ONEBOT_WS_URL=ws://host.docker.internal:3001
ONEBOT_ACCESS_TOKEN=your-token-here

# AI 配置（可选）
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

# 数据库配置（使用 PostgreSQL 时）
# DATABASE_URL=postgresql+asyncpg://xqnext:xqnext123@postgres:5432/xqnext
# POSTGRES_PASSWORD=YourPostgresPassword123!

# 时区
TZ=Asia/Shanghai
```

### B. 快速命令参考

```bash
# 服务管理
docker compose up -d              # 启动服务
docker compose stop               # 停止服务
docker compose restart            # 重启服务
docker compose down               # 停止并删除容器
docker compose ps                 # 查看服务状态
docker compose logs -f xqnext     # 查看实时日志

# 数据管理
./backup.sh                       # 备份数据
./restore.sh <backup-file>        # 恢复数据
docker volume ls                  # 查看数据卷

# 容器管理
docker compose exec xqnext bash   # 进入容器
docker stats xqnext-framework     # 查看资源使用
docker compose build --no-cache   # 重新构建镜像

# 清理
docker system prune -a            # 清理 Docker 缓存
docker volume prune               # 清理未使用的数据卷
```

### C. 目录结构说明

```
XQNEXT/
├── docker/                    # Docker 配置目录
│   ├── Dockerfile            # Docker 镜像构建文件
│   ├── docker-compose.yml    # 生产环境配置
│   ├── docker-compose.dev.yml # 开发环境配置
│   ├── .dockerignore         # Docker 忽略文件
│   ├── env.example           # 环境变量模板
│   ├── deploy.sh             # 一键部署脚本
│   ├── backup.sh             # 备份脚本
│   ├── restore.sh            # 恢复脚本
│   └── README.md             # Docker 使用说明
├── data/                     # 数据目录（持久化）
│   ├── framework.db          # 框架数据库
│   └── RuaBot.db            # AI 数据库
├── logs/                     # 日志目录（持久化）
│   └── onebot_framework.log # 主日志文件
├── plugins/                  # 插件目录（持久化）
├── config.toml               # 主配置文件
└── src/                      # 源代码目录
```

---

**文档版本**: 1.0.0  
**最后更新**: 2024-01-24  
**维护者**: XQNEXT Team


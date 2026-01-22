# XQNEXT Framework Docker 部署指南

## 📦 快速开始

### 1. 准备环境

确保已安装：
- Docker >= 20.10
- Docker Compose >= 2.0

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，修改必要的配置
nano .env
```

**重要配置项：**
- `SECRET_KEY`: 修改为随机字符串
- `WEB_UI_PASSWORD`: 修改默认密码
- `ONEBOT_WS_URL`: 配置 OneBot 实现的 WebSocket 地址
- `OPENAI_API_KEY`: 如果使用 AI 功能

### 3. 构建和启动

```bash
# 进入 docker 目录
cd docker

# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f xqnext

# 查看服务状态
docker-compose ps
```

### 4. 访问服务

- **WebUI**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

默认登录凭据：
- 用户名：`admin`
- 密码：`admin123`（请在 `.env` 中修改）

## 🔧 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 停止并删除容器
docker-compose down

# 停止并删除容器和数据卷
docker-compose down -v

# 查看日志
docker-compose logs -f [服务名]

# 进入容器
docker-compose exec xqnext bash

# 查看资源使用
docker stats xqnext-framework
```

### 镜像管理

```bash
# 构建镜像（不使用缓存）
docker-compose build --no-cache

# 拉取最新镜像
docker-compose pull

# 查看镜像
docker images | grep xqnext

# 删除旧镜像
docker image prune -a
```

### 数据管理

```bash
# 备份数据
docker run --rm -v xqnext_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/xqnext-backup-$(date +%Y%m%d).tar.gz /data

# 恢复数据
docker run --rm -v xqnext_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/xqnext-backup-20240101.tar.gz -C /

# 查看数据卷
docker volume ls | grep xqnext

# 删除数据卷（谨慎使用！）
docker volume rm xqnext_data
```

## 📁 目录结构

```
docker/
├── Dockerfile              # 多阶段构建 Dockerfile
├── docker-compose.yml      # 生产环境配置
├── .dockerignore          # 忽略文件列表
├── .env.example           # 环境变量模板
└── README.md              # 本文件

../data/                   # 数据目录（挂载）
├── framework.db          # 框架数据库
├── RuaBot.db            # AI 学习数据库
└── config/              # 其他配置文件

../logs/                  # 日志目录（挂载）
└── onebot_framework.log # 主日志文件

../plugins/              # 插件目录（挂载）
├── kawaii_status/
├── so_good/
└── like_plugin/
```

## 🚀 高级配置

### 1. 使用 PostgreSQL（大规模部署）

在 `docker-compose.yml` 中取消 `postgres` 服务的注释：

```yaml
services:
  postgres:
    # ... 取消注释
```

然后修改配置：

```bash
# .env 文件
DATABASE_URL=postgresql+asyncpg://xqnext:xqnext123@postgres:5432/xqnext
POSTGRES_PASSWORD=your-secure-password
```

### 2. 使用 Redis 缓存

```yaml
services:
  redis:
    # ... 取消注释
```

### 3. 添加监控（Prometheus + Grafana）

```bash
# 取消 prometheus 和 grafana 服务的注释
docker-compose up -d prometheus grafana

# 访问 Prometheus: http://localhost:9090
# 访问 Grafana: http://localhost:3000
```

### 4. 自定义资源限制

编辑 `docker-compose.yml`：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'          # 限制 CPU
      memory: 4G         # 限制内存
    reservations:
      cpus: '1'          # 预留 CPU
      memory: 1G         # 预留内存
```

## 🔐 安全建议

1. **修改默认密码**
   ```bash
   # 在 .env 中修改
   WEB_UI_PASSWORD=your-strong-password-here
   SECRET_KEY=$(openssl rand -hex 32)
   ```

2. **使用 HTTPS**
   ```bash
   # 使用 nginx 或 traefik 作为反向代理
   # 配置 SSL 证书
   ```

3. **限制网络访问**
   ```yaml
   # 只在本地监听
   ports:
     - "127.0.0.1:8000:8000"
   ```

4. **定期备份**
   ```bash
   # 设置 cron 任务
   0 2 * * * cd /path/to/docker && ./backup.sh
   ```

## 📊 性能优化

### 1. 调整 Workers 数量

修改 `config.toml`:
```toml
[server]
workers = 4  # 根据 CPU 核心数调整
```

### 2. 启用 Gzip 压缩

```toml
[server]
gzip_enabled = true
gzip_level = 6
```

### 3. 配置缓存

```toml
[cache]
enabled = true
backend = "redis"  # 或 "memory"
redis_url = "redis://redis:6379/0"
```

## 🐛 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs --tail=100 xqnext

# 检查容器状态
docker-compose ps

# 检查健康检查
docker inspect xqnext-framework | grep -A 20 Health
```

### 连接 OneBot 失败

```bash
# 检查网络连接
docker-compose exec xqnext ping host.docker.internal

# 检查 OneBot 配置
docker-compose exec xqnext cat /app/config.toml | grep onebot
```

### 数据库错误

```bash
# 检查数据库文件
docker-compose exec xqnext ls -lh /app/data/

# 备份并重建数据库
docker-compose exec xqnext python -c "from src.core.database import DatabaseManager; import asyncio; asyncio.run(DatabaseManager().initialize())"
```

### 插件无法加载

```bash
# 检查插件目录
docker-compose exec xqnext ls -la /app/plugins/

# 查看插件日志
docker-compose exec xqnext grep "plugin" /app/logs/onebot_framework.log
```

## 📝 更新和维护

### 更新到新版本

```bash
# 1. 停止服务
docker-compose stop

# 2. 备份数据
./backup.sh

# 3. 拉取最新代码
git pull origin main

# 4. 重新构建镜像
docker-compose build --no-cache

# 5. 启动服务
docker-compose up -d

# 6. 检查日志
docker-compose logs -f xqnext
```

### 清理旧数据

```bash
# 清理日志（保留最近 7 天）
find ../logs -name "*.log" -mtime +7 -delete

# 清理 Docker 缓存
docker system prune -a --volumes -f
```

## 🆘 获取帮助

- GitHub Issues: https://github.com/your-repo/issues
- 文档: https://docs.your-domain.com
- 社区: https://community.your-domain.com

## 📄 许可证

MIT License


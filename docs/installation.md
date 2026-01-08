# 安装与配置

## 环境要求

### 系统要求

- **操作系统**: Windows 10+, Linux, macOS
- **Python**: Python 3.13 或更高版本
- **内存**: 建议 2GB 以上
- **磁盘空间**: 建议 500MB 以上

### Python 环境

确保已安装 Python 3.10 或更高版本：

```bash
python --version
```

如果未安装 Python，请访问 [Python 官网](https://www.python.org/) 下载安装。

### 依赖服务

- **OneBot 实现**: 需要连接一个 OneBot v11 协议的实现（如 go-cqhttp）
- **数据库**: SQLite（已包含，无需额外安装）

## 安装步骤

### 1. 获取项目

#### 从 Git 仓库克隆

```bash
git clone <repository-url>
cd RuaBot_v0.0.1
```

#### 或下载源码包

下载并解压源码包到目标目录。

### 2. 安装 Python 依赖

#### 使用 pip 安装

```bash
pip install -r requirements.txt
```

#### 使用虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 安装前端依赖（可选）

如果需要开发或修改 Web UI：

```bash
cd webui
npm install
```

### 4. 配置项目

#### 编辑配置文件

编辑项目根目录下的 `config.toml` 文件：

```toml
[app]
name = "RuaBot"
version = "0.0.1"
environment = "development"
debug = false

[server]
host = "0.0.0.0"
port = 8000

[onebot]
version = "v11"
connection_type = "ws_reverse"
ws_reverse_host = "0.0.0.0"
ws_reverse_port = 8080
ws_reverse_path = "/onebot/v11/ws"

[database]
url = "sqlite+aiosqlite:///./data/onebot_framework.db"

[web_ui]
enabled = true
username = "admin"
password = "admin123"
```

#### 配置说明

**服务器配置**
- `host`: Web 服务器监听地址
- `port`: Web 服务器端口

**OneBot 配置**
- `connection_type`: 连接类型（`ws_reverse` 或 `ws_forward`）
- `ws_reverse_host`: WebSocket 反向连接监听地址
- `ws_reverse_port`: WebSocket 反向连接端口
- `ws_reverse_path`: WebSocket 反向连接路径

**数据库配置**
- `url`: 数据库连接 URL（SQLite 无需修改）

**Web UI 配置**
- `enabled`: 是否启用 Web UI
- `username`: Web UI 登录用户名
- `password`: Web UI 登录密码

### 5. 初始化数据库

数据库会在首次启动时自动创建，无需手动初始化。

### 6. 启动服务

#### Windows

```bash
start.bat
```

或直接运行：

```bash
python src/main.py
```

#### Linux/macOS

```bash
chmod +x start.sh
./start.sh
```

或直接运行：

```bash
python src/main.py
```

### 7. 验证安装

启动成功后，访问以下地址验证：

- **Web UI**: http://localhost:8000/
- **API 文档**: http://localhost:8000/docs
- **默认登录**: admin / admin123

## 配置详解

### 应用配置

```toml
[app]
name = "RuaBot"              # 应用名称
version = "0.0.1"             # 应用版本
environment = "development"   # 运行环境 (development/production)
debug = false                 # 调试模式
log_level = "INFO"           # 日志级别
```

### 服务器配置

```toml
[server]
host = "0.0.0.0"             # 监听地址 (0.0.0.0 表示所有接口)
port = 8000                   # 监听端口
```

### OneBot 配置

#### WebSocket 反向连接（推荐）

```toml
[onebot]
version = "v11"
connection_type = "ws_reverse"
ws_reverse_host = "0.0.0.0"
ws_reverse_port = 8080
ws_reverse_path = "/onebot/v11/ws"
access_token = ""             # 访问令牌（可选）
secret = ""                   # 签名密钥（可选）
```

#### WebSocket 正向连接

```toml
[onebot]
version = "v11"
connection_type = "ws_forward"
ws_url = "ws://127.0.0.1:5700"
access_token = ""
```

#### HTTP 连接

```toml
[onebot]
version = "v11"
connection_type = "http"
http_url = "http://localhost:5700"
access_token = ""
```

### 数据库配置

```toml
[database]
url = "sqlite+aiosqlite:///./data/onebot_framework.db"
```

SQLite 数据库文件会自动创建在 `data` 目录下。

### 安全配置

```toml
[security]
secret_key = "your-secret-key-change-this-in-production"
access_token_expire_minutes = 30
```

**重要**: 生产环境请修改 `secret_key` 为随机字符串。

### 插件配置

```toml
[plugins]
dir = "./plugins"            # 插件目录
auto_load = true             # 自动加载插件
```

### Web UI 配置

```toml
[web_ui]
enabled = true               # 启用 Web UI
username = "admin"           # 登录用户名
password = "admin123"        # 登录密码
```

### AI 配置

```toml
[ai]
thread_pool_enabled = true   # 启用线程池
thread_pool_workers = 5      # 线程池工作线程数
```

### 腾讯云配置（可选）

如果需要使用腾讯云 TTS 功能：

```toml
[tencent_cloud]
secret_id = "your-secret-id"
secret_key = "your-secret-key"
```

## 环境变量配置

除了配置文件，还可以通过环境变量进行配置：

```bash
# 服务器配置
export HOST=0.0.0.0
export PORT=8000

# OneBot 配置
export ONEBOT_CONNECTION_TYPE=ws_reverse
export ONEBOT_WS_REVERSE_PORT=8080

# 数据库配置
export DATABASE_URL=sqlite+aiosqlite:///./data/onebot_framework.db

# 安全配置
export SECRET_KEY=your-secret-key

# Web UI 配置
export WEB_UI_USERNAME=admin
export WEB_UI_PASSWORD=admin123
```

环境变量会覆盖配置文件中的对应设置。

## Docker 部署（可选）

### 使用 Docker Compose

项目提供了 Docker 支持，可以使用 Docker Compose 快速部署：

```bash
cd docker
docker-compose up -d
```

### 构建 Docker 镜像

```bash
cd docker
docker build -t ruabot:latest .
```

### 运行 Docker 容器

```bash
docker run -d \
  -p 8000:8000 \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.toml:/app/config.toml \
  ruabot:latest
```

## 常见问题

### 1. 端口被占用

如果启动时提示端口被占用，可以：

- 修改 `config.toml` 中的端口号
- 或关闭占用端口的程序

### 2. 数据库连接失败

- 确保 `data` 目录存在且有写权限
- 检查数据库文件路径是否正确

### 3. OneBot 连接失败

- 检查 OneBot 实现是否正常运行
- 检查连接配置是否正确
- 检查防火墙设置

### 4. 插件加载失败

- 检查插件目录是否存在
- 检查插件配置文件是否正确
- 查看日志文件获取详细错误信息

### 5. Web UI 无法访问

- 检查 Web UI 是否启用
- 检查端口是否正确
- 检查防火墙设置

### 6. 依赖安装失败

- 确保 Python 版本符合要求
- 尝试使用国内镜像源：
  ```bash
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

## 更新升级

### 更新代码

```bash
git pull
```

### 更新依赖

```bash
pip install -r requirements.txt --upgrade
```

### 数据库迁移

数据库结构变更时会自动迁移，无需手动操作。

## 卸载

### 停止服务

停止运行中的服务。

### 删除文件

删除项目目录即可。

### 清理数据（可选）

如需完全清理，删除以下目录：

- `data/` - 数据目录
- `logs/` - 日志目录
- `plugins/` - 插件目录（如果不需要保留插件）

## 生产环境部署建议

### 1. 使用进程管理

推荐使用 systemd (Linux) 或 supervisor 管理进程：

```ini
[program:ruabot]
command=/path/to/venv/bin/python /path/to/src/main.py
directory=/path/to/RuaBot_v0.0.1
autostart=true
autorestart=true
user=ruabot
```

### 2. 使用反向代理

推荐使用 Nginx 作为反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 配置 HTTPS

使用 Let's Encrypt 配置 HTTPS：

```bash
certbot --nginx -d your-domain.com
```

### 4. 安全加固

- 修改默认密码
- 配置防火墙
- 限制访问 IP
- 定期更新依赖

### 5. 监控和日志

- 配置日志轮转
- 设置监控告警
- 定期备份数据


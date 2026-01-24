# Installation and Configuration

{ [Chinese](installation_CN.md) | English }

## System Requirements

### System

- **OS**: Windows 10+, Linux, macOS
- **Python**: Python 3.13 or higher
- **Memory**: 2GB+ recommended
- **Disk**: 500MB+ recommended

### Python Environment

Ensure Python 3.10 or higher is installed:

```bash
python --version
```

If not installed, visit [Python Official Site](https://www.python.org/) to download and install.

### Dependent Services

- **OneBot Implementation**: Requires connecting to a OneBot v11 protocol implementation (e.g., go-cqhttp)
- **Database**: SQLite (included, no extra installation required)

## Installation Steps

### 1. Get the Project

#### Clone from Git

```bash
git clone <repository-url>
cd RuaBot_v0.0.1
```

#### Or Download Source Code

Download and extract the source code to the target directory.

### 2. Install Python Dependencies

#### Using pip

```bash
pip install -r requirements.txt
```

#### Using Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies (Optional)

If you need to develop or modify the Web UI:

```bash
cd webui
npm install
```

### 4. Configure Project

#### Edit Configuration File

Edit `config.toml` in the project root directory:

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

#### Configuration Description

**Server Config**
- `host`: Web server listening address
- `port`: Web server port

**OneBot Config**
- `connection_type`: Connection type (`ws_reverse` or `ws_forward`)
- `ws_reverse_host`: WebSocket reverse connection listening address
- `ws_reverse_port`: WebSocket reverse connection port
- `ws_reverse_path`: WebSocket reverse connection path

**Database Config**
- `url`: Database connection URL (SQLite usually needs no modification)

**Web UI Config**
- `enabled`: Whether to enable Web UI
- `username`: Web UI login username
- `password`: Web UI login password

### 5. Initialize Database

The database will be automatically created on the first startup, no manual initialization required.

### 6. Start Service

#### Windows

```bash
start.bat
```

Or run directly:

```bash
python src/main.py
```

#### Linux/macOS

```bash
chmod +x start.sh
./start.sh
```

Or run directly:

```bash
python src/main.py
```

### 7. Verify Installation

After successful startup, visit the following addresses to verify:

- **Web UI**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs
- **Default Login**: admin / admin123

## Configuration Details

### App Config

```toml
[app]
name = "RuaBot"              # App name
version = "0.0.1"             # App version
environment = "development"   # Runtime environment (development/production)
debug = false                 # Debug mode
log_level = "INFO"           # Log level
```

### Server Config

```toml
[server]
host = "0.0.0.0"             # Listening address (0.0.0.0 means all interfaces)
port = 8000                   # Listening port
```

### OneBot Config

#### WebSocket Reverse (Recommended)

```toml
[onebot]
version = "v11"
connection_type = "ws_reverse"
ws_reverse_host = "0.0.0.0"
ws_reverse_port = 8080
ws_reverse_path = "/onebot/v11/ws"
access_token = ""             # Access token (optional)
secret = ""                   # Signature secret (optional)
```

#### WebSocket Forward

```toml
[onebot]
version = "v11"
connection_type = "ws_forward"
ws_url = "ws://127.0.0.1:5700"
access_token = ""
```

#### HTTP

```toml
[onebot]
version = "v11"
connection_type = "http"
http_url = "http://localhost:5700"
access_token = ""
```

### Database Config

```toml
[database]
url = "sqlite+aiosqlite:///./data/onebot_framework.db"
```

SQLite database file will be automatically created in the `data` directory.

### Security Config

```toml
[security]
secret_key = "your-secret-key-change-this-in-production"
access_token_expire_minutes = 30
```

**Important**: Change `secret_key` to a random string in production environment.

### Plugin Config

```toml
[plugins]
dir = "./plugins"            # Plugin directory
auto_load = true             # Auto load plugins
```

### Web UI Config

```toml
[web_ui]
enabled = true               # Enable Web UI
username = "admin"           # Login username
password = "admin123"        # Login password
```

### AI Config

```toml
[ai]
thread_pool_enabled = true   # Enable thread pool
thread_pool_workers = 5      # Thread pool workers
```

### Tencent Cloud Config (Optional)

If you need to use Tencent Cloud TTS function:

```toml
[tencent_cloud]
secret_id = "your-secret-id"
secret_key = "your-secret-key"
```

## Environment Variable Configuration

Besides configuration file, you can also configure via environment variables:

```bash
# Server Config
export HOST=0.0.0.0
export PORT=8000

# OneBot Config
export ONEBOT_CONNECTION_TYPE=ws_reverse
export ONEBOT_WS_REVERSE_PORT=8080

# Database Config
export DATABASE_URL=sqlite+aiosqlite:///./data/onebot_framework.db

# Security Config
export SECRET_KEY=your-secret-key

# Web UI Config
export WEB_UI_USERNAME=admin
export WEB_UI_PASSWORD=admin123
```

Environment variables will override corresponding settings in the configuration file.

## Docker Deployment (Optional)

### Using Docker Compose

The project supports Docker, you can use Docker Compose for quick deployment:

```bash
cd docker
docker-compose up -d
```

### Build Docker Image

```bash
cd docker
docker build -t ruabot:latest .
```

### Run Docker Container

```bash
docker run -d \
  -p 8000:8000 \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.toml:/app/config.toml \
  ruabot:latest
```

## FAQ

### 1. Port Occupied

If prompted that the port is occupied during startup, you can:

- Modify port number in `config.toml`
- Or close the program occupying the port

### 2. Database Connection Failed

- Ensure `data` directory exists and is writable
- Check if database file path is correct

### 3. OneBot Connection Failed

- Check if OneBot implementation is running normally
- Check if connection configuration is correct
- Check firewall settings

### 4. Plugin Load Failed

- Check if plugin directory exists
- Check if plugin configuration file is correct
- View log file for detailed error information

### 5. Web UI Inaccessible

- Check if Web UI is enabled
- Check if port is correct
- Check firewall settings

### 6. Dependency Installation Failed

- Ensure Python version meets requirements
- Try using domestic mirror source:
  ```bash
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

## Update & Upgrade

### Update Code

```bash
git pull
```

### Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

### Database Migration

Database structure changes will be automatically migrated, no manual operation required.

## Uninstall

### Stop Service

Stop the running service.

### Delete Files

Delete the project directory.

### Clean Data (Optional)

If you need to completely clean up, delete the following directories:

- `data/` - Data directory
- `logs/` - Log directory
- `plugins/` - Plugin directory (if you don't need to keep plugins)

## Production Deployment Suggestions

### 1. Use Process Management

Recommend using systemd (Linux) or supervisor to manage processes:

```ini
[program:ruabot]
command=/path/to/venv/bin/python /path/to/src/main.py
directory=/path/to/RuaBot_v0.0.1
autostart=true
autorestart=true
user=ruabot
```

### 2. Use Reverse Proxy

Recommend using Nginx as reverse proxy:

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

### 3. Configure HTTPS

Use Let's Encrypt to configure HTTPS:

```bash
certbot --nginx -d your-domain.com
```

### 4. Security Hardening

- Change default password
- Configure firewall
- Restrict access IP
- Regularly update dependencies

### 5. Monitoring and Logs

- Configure log rotation
- Set up monitoring alerts
- Regularly backup data


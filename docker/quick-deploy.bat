@echo off
REM XQNEXT Framework 快速部署脚本 (Windows)

setlocal enabledelayedexpansion

echo ========================================
echo XQNEXT Framework 快速部署 (Windows)
echo ========================================
echo.

REM 检查 Docker
echo [1/6] 检查 Docker 环境...
docker --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未安装 Docker
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo 错误: Docker Compose 不可用
    pause
    exit /b 1
)

echo 成功: Docker 环境正常
echo.

REM 加载镜像
echo [2/6] 检查 Docker 镜像...
if exist "xqnext-framework-0.0.2.tar.gz" (
    echo 找到镜像文件，正在加载...
    docker load -i xqnext-framework-0.0.2.tar.gz
    echo 成功: 镜像加载完成
) else if exist "xqnext-framework.tar.gz" (
    echo 找到镜像文件，正在加载...
    docker load -i xqnext-framework.tar.gz
    echo 成功: 镜像加载完成
) else (
    echo 提示: 未找到镜像文件，将使用本地构建或从仓库拉取
)
echo.

REM 配置环境变量
echo [3/6] 配置环境变量...
if not exist ".env" (
    if exist "env.example" (
        copy env.example .env >nul
        echo 成功: 已创建 .env 文件
        echo.
        echo 重要: 请编辑 .env 文件设置以下配置:
        echo   1. WEB_UI_PASSWORD - WebUI 登录密码
        echo   2. ONEBOT_WS_URL - OneBot WebSocket 地址
        echo   3. ONEBOT_ACCESS_TOKEN - OneBot 访问令牌（如果需要）
        echo   4. OPENAI_API_KEY - OpenAI API Key（如果使用 AI）
        echo.
        pause
    ) else (
        echo 错误: 未找到 env.example 文件
        pause
        exit /b 1
    )
) else (
    echo 成功: 使用现有的 .env 文件
)
echo.

REM 创建目录
echo [4/6] 创建必要的目录...
if exist "..\data" (
    REM 在 docker 子目录中
    if not exist "..\data" mkdir "..\data"
    if not exist "..\logs" mkdir "..\logs"
    if not exist "..\backups" mkdir "..\backups"
    echo 成功: 目录创建完成（在上级目录）
) else (
    REM 在项目根目录
    if not exist "data" mkdir "data"
    if not exist "logs" mkdir "logs"
    if not exist "backups" mkdir "backups"
    echo 成功: 目录创建完成
)
echo.

REM 检查配置文件
echo [5/6] 检查配置文件...
if exist "..\config.toml" (
    echo 成功: 找到配置文件 ..\config.toml
) else if exist "config.toml" (
    echo 成功: 找到配置文件 config.toml
) else (
    echo 错误: 未找到 config.toml 文件
    pause
    exit /b 1
)
echo.

REM 启动服务
echo [6/6] 启动服务...
docker images | findstr "xqnext-framework" >nul
if errorlevel 1 (
    echo 构建并启动镜像...
    docker compose up -d --build
) else (
    echo 使用已加载的镜像启动...
    docker compose up -d
)

if errorlevel 1 (
    echo 错误: 启动失败
    pause
    exit /b 1
)

echo 成功: 服务启动成功
echo.

REM 等待服务就绪
echo 等待服务就绪...
timeout /t 5 /nobreak >nul

REM 检查服务状态
docker compose ps | findstr "Up" >nul
if errorlevel 1 (
    echo 警告: 服务可能未正常启动，请检查日志
) else (
    echo 成功: 服务运行正常
)
echo.

REM 显示访问信息
echo ========================================
echo 部署完成！
echo ========================================
echo.
echo 服务信息:
echo   WebUI 管理界面: http://localhost:8000
echo   API 接口文档: http://localhost:8000/docs
echo   健康检查: http://localhost:8000/health
echo.
echo 登录信息:
echo   用户名: admin
echo   密码: (查看 .env 文件中的 WEB_UI_PASSWORD)
echo.
echo 常用命令:
echo   查看日志: docker compose logs -f xqnext
echo   查看状态: docker compose ps
echo   停止服务: docker compose stop
echo   重启服务: docker compose restart
echo   进入容器: docker compose exec xqnext bash
echo.
echo 数据管理:
echo   备份数据: backup.bat
echo   恢复数据: restore.bat [backup-file]
echo.
echo 提示: 如需详细部署文档，请查看 DEPLOYMENT_GUIDE.md
echo.
echo ========================================
echo.

pause


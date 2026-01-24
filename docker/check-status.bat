@echo off
REM XQNEXT Framework 状态检查脚本 (Windows)

setlocal enabledelayedexpansion

echo ========================================
echo XQNEXT Framework 状态检查 (Windows)
echo ========================================
echo.

REM 1. 容器状态
echo 容器状态:
docker compose ps 2>nul
if errorlevel 1 (
    echo 错误: 未找到容器或 Docker 未运行
) else (
    docker compose ps | findstr "Up" >nul
    if errorlevel 1 (
        echo 警告: 容器未运行
    ) else (
        echo 成功: 容器正在运行
    )
)
echo.

REM 2. 健康检查
echo 健康检查:
curl -f http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo 错误: 健康检查失败
) else (
    curl -s http://localhost:8000/health
    echo.
    echo 成功: 服务健康
)
echo.

REM 3. 端口监听
echo 端口监听:
netstat -an | findstr ":8000.*LISTENING" >nul
if errorlevel 1 (
    echo 警告: 端口 8000 未监听
) else (
    echo 成功: 端口 8000 (WebUI/API) 正在监听
)

netstat -an | findstr ":8080.*LISTENING" >nul
if errorlevel 1 (
    echo 警告: 端口 8080 未监听
) else (
    echo 成功: 端口 8080 (OneBot) 正在监听
)
echo.

REM 4. 数据目录
echo 数据目录:
if exist "..\data" (
    echo   目录: ..\data
    dir "..\data" /b
    echo   成功: 数据目录正常
) else if exist "data" (
    echo   目录: data
    dir "data" /b
    echo   成功: 数据目录正常
) else (
    echo   错误: 未找到数据目录
)
echo.

REM 5. 日志目录
echo 日志目录:
if exist "..\logs" (
    echo   目录: ..\logs
    if exist "..\logs\onebot_framework.log" (
        for %%A in ("..\logs\onebot_framework.log") do echo   主日志: onebot_framework.log (%%~zA bytes)
        echo   成功: 日志目录正常
    ) else (
        echo   警告: 未找到主日志文件
    )
) else if exist "logs" (
    echo   目录: logs
    if exist "logs\onebot_framework.log" (
        for %%A in ("logs\onebot_framework.log") do echo   主日志: onebot_framework.log (%%~zA bytes)
        echo   成功: 日志目录正常
    ) else (
        echo   警告: 未找到主日志文件
    )
) else (
    echo   错误: 未找到日志目录
)
echo.

REM 6. Docker 镜像
echo Docker 镜像:
docker images | findstr "xqnext-framework"
if errorlevel 1 (
    echo 错误: 未找到 xqnext-framework 镜像
) else (
    echo 成功: Docker 镜像存在
)
echo.

REM 7. 磁盘空间
echo 磁盘空间:
for /f "tokens=3" %%a in ('dir /-c ^| findstr "bytes free"') do set FREE=%%a
echo   可用空间: %FREE% bytes
echo.

echo ========================================
echo 检查完成
echo.
echo 快速操作:
echo   查看实时日志: docker compose logs -f xqnext
echo   重启服务: docker compose restart xqnext
echo   进入容器: docker compose exec xqnext bash
echo   查看详细状态: docker compose ps -a
echo.
echo ========================================

pause


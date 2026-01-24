@echo off
REM XQNEXT Framework 备份脚本 (Windows)

setlocal enabledelayedexpansion

REM 配置
set BACKUP_DIR=..\backups
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set DATE=%%c%%a%%b)
for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set TIME=%%a%%b)
set TIMESTAMP=%DATE%_%TIME: =0%
set BACKUP_FILE=xqnext-backup-%TIMESTAMP%.tar.gz

echo ========================================
echo XQNEXT Framework 备份工具 (Windows)
echo ========================================
echo.

REM 创建备份目录
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [1/4] 停止服务...
docker compose stop xqnext
echo.

echo [2/4] 备份数据...
REM 使用 tar 命令（Windows 10 1803+ 自带）
tar -czf "%BACKUP_DIR%\%BACKUP_FILE%" -C .. data plugins config.toml 2>nul
if errorlevel 1 (
    echo 错误: 备份失败
    echo 提示: 请确保 tar 命令可用，或手动复制 data、plugins 目录
    pause
    docker compose start xqnext
    exit /b 1
)
echo.

echo [3/4] 启动服务...
docker compose start xqnext
echo.

echo [4/4] 清理旧备份（保留最近5个）...
REM Windows 下的清理逻辑较复杂，这里简化处理
echo 提示: 请定期手动清理旧备份文件
echo.

echo 成功: 备份完成！
echo 备份文件: %BACKUP_DIR%\%BACKUP_FILE%
for %%A in ("%BACKUP_DIR%\%BACKUP_FILE%") do echo 文件大小: %%~zA bytes
echo.
echo ========================================

pause


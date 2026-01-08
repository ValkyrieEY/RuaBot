@echo off
REM Build script for webui (Windows)

echo Building Vite WebUI...

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
)

REM Clean old build
echo Cleaning old build...
if exist "..\src\ui\static" (
    rmdir /s /q "..\src\ui\static"
)

REM Build the project
echo Building production bundle...
call npm run build

echo Build complete! Output: ..\src\ui\static

REM Check if build succeeded
if exist "..\src\ui\static\index.html" (
    echo ✓ Build successful!
) else (
    echo ✗ Build failed!
    exit /b 1
)

@echo off
chcp 65001 >nul
echo 🚀 PDF批量重命名工具 - WebUI版本
echo ====================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo 📦 安装Python依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo ✅ 启动WebUI服务器...
echo 🌐 请在浏览器中访问: http://localhost:8000
echo 📝 按 Ctrl+C 停止服务器
echo.

python main.py

pause

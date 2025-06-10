#!/bin/bash

echo "🚀 PDF批量重命名工具 - WebUI版本"
echo "===================================="

if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "📦 安装Python依赖..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败"
        exit 1
    fi
fi

echo ""
echo "✅ 启动WebUI服务器..."
echo "🌐 请在浏览器中访问: http://localhost:8000"
echo "📝 按 Ctrl+C 停止服务器"
echo ""

python3 main.py

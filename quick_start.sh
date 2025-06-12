#!/bin/bash

# =============================================================================
# PDF批量重命名工具 - 快速启动脚本
# 简化版本，适合已安装依赖的用户
# =============================================================================

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 图标定义
ROCKET="🚀"
CHECK="✅"
INFO="ℹ️"
GLOBE="🌐"

echo -e "${BLUE}${ROCKET} PDF批量重命名工具 - 快速启动${NC}"
echo -e "${CYAN}正在启动WebUI服务器...${NC}\n"

# 查找Python命令
PYTHON_CMD=""
for cmd in python3 python python3.11 python3.10 python3.9 python3.8; do
    if command -v $cmd &> /dev/null; then
        PYTHON_CMD=$cmd
        break
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "${YELLOW}未找到Python，请先安装Python 3.8+${NC}"
    exit 1
fi

# 检查main.py是否存在
if [[ ! -f "main.py" ]]; then
    echo -e "${YELLOW}未找到main.py文件${NC}"
    exit 1
fi

# 创建必要目录
mkdir -p uploads downloads backup static templates

# 查找可用端口
PORT=8000
while nc -z localhost $PORT 2>/dev/null; do
    PORT=$((PORT + 1))
done

echo -e "${GREEN}${CHECK} 使用Python: $PYTHON_CMD${NC}"
echo -e "${GREEN}${CHECK} 服务端口: $PORT${NC}"
echo -e "${CYAN}${GLOBE} 访问地址: http://localhost:$PORT${NC}"
echo -e "${CYAN}${INFO} 按 Ctrl+C 停止服务器${NC}\n"

# 尝试自动打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2 && open "http://localhost:$PORT" &
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sleep 2 && xdg-open "http://localhost:$PORT" &
fi

# 启动服务器
$PYTHON_CMD main.py --port $PORT 
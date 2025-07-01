#!/bin/bash

# ===================================================================================
# PDF批量重命名工具 - Rocky Linux/RHEL/CentOS/Fedora 专用一键安装脚本
# ===================================================================================

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 开始为Rocky Linux/RHEL系列系统准备环境...${NC}"

# 1. 更新系统并安装必要的开发工具和系统依赖
echo -e "\n${GREEN}第一步：安装系统依赖 (需要sudo权限)...${NC}"
# 新增：启用CRB和EPEL软件源，以提供额外的开发包
echo "  启用CRB(CodeReady Builder)软件源..."
sudo dnf config-manager --set-enabled crb
echo "  安装并启用EPEL(Extra Packages for Enterprise Linux)软件源..."
sudo dnf install -y epel-release
echo "  软件源准备就绪。"

sudo dnf update -y --allowerasing
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y \
    python3-devel \
    python3-pip \
    libjpeg-turbo-devel \
    zlib-devel \
    libtiff-devel \
    freetype-devel \
    lcms2-devel \
    libwebp-devel \
    tcl-devel \
    tk-devel \
    harfbuzz-devel \
    fribidi-devel \
    libraqm-devel \
    libimagequant-devel \
    libxcb-devel \
    git
echo -e "${GREEN}✅ 系统依赖安装完成。${NC}"

# 2. 检查Python和pip版本
echo -e "\n${GREEN}第二步：检查Python环境...${NC}"
if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 或 pip3 未找到，请检查安装。${NC}"
    exit 1
fi
python3 --version
pip3 --version
echo -e "${GREEN}✅ Python环境检查通过。${NC}"

# 3. 创建并激活Python虚拟环境
echo -e "\n${GREEN}第三步：设置Python虚拟环境...${NC}"
VENV_DIR="venv_pdf_renamer"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  创建虚拟环境于: $VENV_DIR"
else
    echo "  虚拟环境已存在。"
fi
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✅ 虚拟环境已激活。${NC}"

# 4. 尝试安装并使用uv进行闪电般快速的依赖安装
echo -e "\n${GREEN}第四步：安装Python依赖...${NC}"
if python3 -m pip install uv --quiet; then
    echo "  🚀 检测到uv，将使用超快速安装。"
    uv pip install --system --requirement requirements.txt
else
    echo "  📦 uv安装失败，将使用pip进行安装。"
    pip3 install -r requirements.txt
fi
echo -e "${GREEN}✅ Python依赖安装完成。${NC}"

# 5. PaddleOCR兼容性修复 (如果脚本存在)
if [ -f "fix-paddleocr.sh" ]; then
    echo -e "\n${GREEN}第五步：应用PaddleOCR兼容性修复...${NC}"
    chmod +x fix-paddleocr.sh
    ./fix-paddleocr.sh
    echo -e "${GREEN}✅ PaddleOCR修复完成。${NC}"
else
    echo -e "\n${YELLOW}⚠️ 未找到fix-paddleocr.sh，跳过此步骤。${NC}"
fi

echo -e "\n${BLUE}=====================================================${NC}"
echo -e "${GREEN}🎉 Rocky Linux环境配置完成！ 🎉${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo ""
echo "您现在可以通过以下两种方式启动应用："
echo ""
echo -e "  1. ${YELLOW}使用启动脚本 (推荐):${NC}"
echo "     chmod +x start.sh"
echo "     ./start.sh"
echo ""
echo -e "  2. ${YELLOW}手动启动:${NC}"
echo "     source $VENV_DIR/bin/activate"
echo "     uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo -e "访问地址: ${GREEN}http://<您的服务器IP>:8000${NC}"
echo "" 
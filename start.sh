#!/bin/bash

# =============================================================================
# PDF批量重命名工具 - 智能启动脚本
# 支持自动环境检测、分步安装和错误恢复
# =============================================================================

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 图标定义
ICON_ROCKET="🚀"
ICON_CHECK="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_PACKAGE="📦"
ICON_GEAR="⚙️"
ICON_FIRE="🔥"
ICON_GLOBE="🌐"

# 日志函数
log_info() {
    echo -e "${CYAN}${ICON_INFO} $1${NC}"
}

log_success() {
    echo -e "${GREEN}${ICON_CHECK} $1${NC}"
}

log_error() {
    echo -e "${RED}${ICON_ERROR} $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}${ICON_WARNING} $1${NC}"
}

log_header() {
    echo -e "\n${PURPLE}===============================================${NC}"
    echo -e "${PURPLE} $1${NC}"
    echo -e "${PURPLE}===============================================${NC}\n"
}

# 打印欢迎信息
print_welcome() {
    clear
    echo -e "${BLUE}"
    echo "  ██████╗ ██████╗ ███████╗    ██████╗ ███████╗███╗   ██╗ █████╗ ███╗   ███╗███████╗██████╗ "
    echo "  ██╔══██╗██╔══██╗██╔════╝    ██╔══██╗██╔════╝████╗  ██║██╔══██╗████╗ ████║██╔════╝██╔══██╗"
    echo "  ██████╔╝██║  ██║█████╗      ██████╔╝█████╗  ██╔██╗ ██║███████║██╔████╔██║█████╗  ██████╔╝"
    echo "  ██╔═══╝ ██║  ██║██╔══╝      ██╔══██╗██╔══╝  ██║╚██╗██║██╔══██║██║╚██╔╝██║██╔══╝  ██╔══██╗"
    echo "  ██║     ██████╔╝██║         ██║  ██║███████╗██║ ╚████║██║  ██║██║ ╚═╝ ██║███████╗██║  ██║"
    echo "  ╚═╝     ╚═════╝ ╚═╝         ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝"
    echo -e "${NC}\n"
    echo -e "${CYAN}${ICON_ROCKET} PDF批量重命名工具 - WebUI版本${NC}"
    echo -e "${CYAN}基于OCR技术的智能PDF文件重命名系统${NC}\n"
}

# 检查Python版本
check_python() {
    log_info "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "未找到Python3，请先安装Python 3.8+"
        log_info "安装方法："
        log_info "  macOS: brew install python"
        log_info "  Ubuntu: sudo apt install python3 python3-pip"
        log_info "  CentOS: sudo yum install python3 python3-pip"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_success "Python版本: $python_version"
    
    # 检查版本是否符合要求
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_success "Python版本符合要求"
    else
        log_error "Python版本过低，需要3.8或更高版本"
        exit 1
    fi
}

# 检查pip并升级
check_and_upgrade_pip() {
    log_info "检查并升级pip..."
    
    if ! python3 -c "import pip" 2>/dev/null; then
        log_error "pip未安装，请先安装pip"
        exit 1
    fi
    
    log_info "升级pip到最新版本..."
    python3 -m pip install --upgrade pip
    log_success "pip升级完成"
}

# 检查并安装系统依赖
check_system_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查Tesseract OCR
    if command -v tesseract &> /dev/null; then
        tesseract_version=$(tesseract --version | head -1)
        log_success "Tesseract已安装: $tesseract_version"
    else
        log_warning "Tesseract OCR未安装"
        log_info "自动安装Tesseract OCR..."
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            if command -v brew &> /dev/null; then
                brew install tesseract tesseract-lang
                log_success "Tesseract OCR安装完成"
            else
                log_error "未找到Homebrew，请手动安装Tesseract或先安装Homebrew"
                log_info "Homebrew安装: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux
            if command -v apt &> /dev/null; then
                sudo apt update
                sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
                log_success "Tesseract OCR安装完成"
            elif command -v yum &> /dev/null; then
                sudo yum install -y tesseract tesseract-langpack-chi_sim
                log_success "Tesseract OCR安装完成"
            else
                log_warning "无法自动安装Tesseract，请手动安装"
            fi
        else
            log_warning "不支持的操作系统，请手动安装Tesseract OCR"
        fi
    fi
}

# 智能安装Python依赖
install_python_dependencies() {
    log_header "安装Python依赖包"
    
    # 检查requirements.txt是否存在
    if [[ ! -f "requirements.txt" ]]; then
        log_error "未找到requirements.txt文件"
        exit 1
    fi
    
    log_info "正在安装Python依赖包..."
    log_info "这可能需要几分钟时间，首次安装会下载OCR模型..."
    
    # 分步安装，避免超时
    log_info "第1步: 安装Web框架依赖..."
    python3 -m pip install fastapi uvicorn jinja2 python-multipart
    
    log_info "第2步: 安装图像处理依赖..."
    python3 -m pip install Pillow opencv-python numpy
    
    log_info "第3步: 安装PDF处理依赖..."
    python3 -m pip install PyMuPDF
    
    log_info "第4步: 安装基础OCR依赖..."
    python3 -m pip install pytesseract
    
    log_info "第5步: 安装科学计算依赖..."
    python3 -m pip install scipy scikit-learn psutil
    
    log_info "第6步: 安装PaddleOCR (主力OCR引擎)..."
    if python3 -m pip install paddlepaddle paddleocr; then
        log_success "PaddleOCR安装成功"
    else
        log_warning "PaddleOCR安装失败，将使用EasyOCR作为主引擎"
    fi
    
    log_info "第7步: 安装EasyOCR (备用OCR引擎)..."
    if python3 -m pip install torch torchvision easyocr; then
        log_success "EasyOCR安装成功"
    else
        log_warning "EasyOCR安装失败"
    fi
    
    log_success "Python依赖安装完成"
}

# 测试关键模块导入
test_imports() {
    log_info "测试关键模块导入..."
    
    modules=("fastapi" "uvicorn" "jinja2" "fitz" "PIL" "cv2" "numpy")
    failed_modules=()
    
    for module in "${modules[@]}"; do
        if python3 -c "import $module" 2>/dev/null; then
            log_success "$module"
        else
            log_error "$module 导入失败"
            failed_modules+=("$module")
        fi
    done
    
    # 测试OCR模块（可选）
    ocr_modules=("easyocr" "paddleocr")
    available_ocr=()
    
    for module in "${ocr_modules[@]}"; do
        if python3 -c "import $module" 2>/dev/null; then
            log_success "$module (OCR引擎)"
            available_ocr+=("$module")
        else
            log_warning "$module OCR引擎不可用"
        fi
    done
    
    if [[ ${#failed_modules[@]} -gt 0 ]]; then
        log_error "以下模块导入失败: ${failed_modules[*]}"
        log_warning "程序可能无法正常运行"
        read -p "是否继续启动? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    if [[ ${#available_ocr[@]} -eq 0 ]]; then
        log_error "没有可用的OCR引擎！"
        log_info "请手动安装OCR引擎："
        log_info "  python3 -m pip install easyocr"
        log_info "  python3 -m pip install paddlepaddle paddleocr"
        exit 1
    fi
    
    log_success "模块测试完成，可用OCR引擎: ${available_ocr[*]}"
}

# 查找可用端口
find_available_port() {
    local start_port=8000
    local max_attempts=10
    
    for ((i=0; i<max_attempts; i++)); do
        local port=$((start_port + i))
        if ! nc -z localhost $port 2>/dev/null; then
            echo $port
            return
        fi
    done
    
    echo $start_port  # 默认返回8000
}

# 启动服务器
start_server() {
    log_header "启动WebUI服务器"
    
    # 查找可用端口
    port=$(find_available_port)
    
    log_success "启动WebUI服务器..."
    log_info "访问地址: http://localhost:$port"
    log_info "按 Ctrl+C 停止服务器"
    log_info ""
    
    # 尝试自动打开浏览器
    if command -v open &> /dev/null; then
        # macOS
        sleep 2 && open "http://localhost:$port" &
    elif command -v xdg-open &> /dev/null; then
        # Linux
        sleep 2 && xdg-open "http://localhost:$port" &
    fi
    
    # 启动服务器
    python3 main.py --port $port
}

# 清理函数
cleanup() {
    log_info "正在清理..."
    # 可以添加清理逻辑
}

# 捕获中断信号
trap cleanup EXIT INT TERM

# 主函数
main() {
    print_welcome
    
    log_header "环境检查"
    check_python
    check_and_upgrade_pip
    check_system_dependencies
    
    # 检查是否需要安装依赖
    if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
        install_python_dependencies
    else
        log_success "Python依赖已安装"
    fi
    
    test_imports
    start_server
}

# 检查是否有命令行参数
if [[ "$1" == "--install-only" ]]; then
    print_welcome
    log_header "仅安装模式"
    check_python
    check_and_upgrade_pip  
    check_system_dependencies
    install_python_dependencies
    test_imports
    log_success "安装完成！运行 './start.sh' 启动服务器"
    exit 0
fi

# 运行主函数
main

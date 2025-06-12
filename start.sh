#!/bin/bash

# =============================================================================
# PDF批量重命名工具 - 智能启动脚本
# 支持自动环境检测、分步安装和错误恢复
# 版本: 2.0
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
ICON_CLEAN="🧹"
ICON_MAGIC="✨"

# 配置变量
DEFAULT_PORT=8000
MAX_PORT_ATTEMPTS=10
PYTHON_MIN_VERSION="3.8"
INSTALL_TIMEOUT=300  # 5分钟超时

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

log_step() {
    echo -e "\n${BLUE}${ICON_GEAR} $1${NC}"
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
    echo -e "${CYAN}${ICON_ROCKET} PDF批量重命名工具 - WebUI版本 v2.0${NC}"
    echo -e "${CYAN}基于AI OCR技术的智能PDF文件重命名系统${NC}"
    echo -e "${CYAN}支持EasyOCR、PaddleOCR、Tesseract多引擎识别${NC}\n"
}

# 检查操作系统
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt &> /dev/null; then
            echo "ubuntu"
        elif command -v yum &> /dev/null; then
            echo "centos"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# 检查Python版本
check_python() {
    log_step "检查Python环境"
    
    # 尝试不同的Python命令
    python_cmd=""
    for cmd in python3 python python3.11 python3.10 python3.9 python3.8; do
        if command -v $cmd &> /dev/null; then
            python_cmd=$cmd
            break
        fi
    done
    
    if [[ -z "$python_cmd" ]]; then
        log_error "未找到Python，请先安装Python ${PYTHON_MIN_VERSION}+"
        log_info "安装方法："
        case $(detect_os) in
            "macOS")
                log_info "  brew install python"
                log_info "  或下载: https://www.python.org/downloads/"
                ;;
            "ubuntu")
                log_info "  sudo apt update && sudo apt install python3 python3-pip"
                ;;
            "centos")
                log_info "  sudo yum install python3 python3-pip"
                ;;
            *)
                log_info "  请访问 https://www.python.org/downloads/ 下载安装"
                ;;
        esac
        exit 1
    fi
    
    # 检查版本
    python_version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_success "Python版本: $python_version (命令: $python_cmd)"
    
    # 版本检查
    if $python_cmd -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_success "Python版本符合要求"
        export PYTHON_CMD=$python_cmd
    else
        log_error "Python版本过低，需要${PYTHON_MIN_VERSION}或更高版本"
        exit 1
    fi
}

# 检查pip并升级
check_and_upgrade_pip() {
    log_step "检查并升级pip"
    
    if ! $PYTHON_CMD -c "import pip" 2>/dev/null; then
        log_error "pip未安装，正在尝试安装..."
        
        # 尝试安装pip
        if command -v curl &> /dev/null; then
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            $PYTHON_CMD get-pip.py
            rm -f get-pip.py
        else
            log_error "请手动安装pip"
            exit 1
        fi
    fi
    
    log_info "升级pip到最新版本..."
    $PYTHON_CMD -m pip install --upgrade pip --timeout 60
    log_success "pip升级完成"
}

# 检查并安装系统依赖
check_system_dependencies() {
    log_step "检查系统依赖"
    
    # 检查Tesseract OCR
    if command -v tesseract &> /dev/null; then
        tesseract_version=$(tesseract --version 2>&1 | head -1)
        log_success "Tesseract已安装: $tesseract_version"
    else
        log_warning "Tesseract OCR未安装，正在自动安装..."
        install_tesseract
    fi
    
    # 检查其他系统工具
    check_system_tools
}

# 安装Tesseract OCR
install_tesseract() {
    case $(detect_os) in
        "macOS")
            if command -v brew &> /dev/null; then
                log_info "使用Homebrew安装Tesseract..."
                brew install tesseract tesseract-lang
                log_success "Tesseract OCR安装完成"
            else
                log_error "未找到Homebrew，请手动安装Tesseract或先安装Homebrew"
                log_info "Homebrew安装: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                return 1
            fi
            ;;
        "ubuntu")
            log_info "使用apt安装Tesseract..."
            sudo apt update
            sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra
            log_success "Tesseract OCR安装完成"
            ;;
        "centos")
            log_info "使用yum安装Tesseract..."
            sudo yum install -y epel-release
            sudo yum install -y tesseract tesseract-langpack-chi_sim
            log_success "Tesseract OCR安装完成"
            ;;
        *)
            log_warning "不支持的操作系统，请手动安装Tesseract OCR"
            log_info "下载地址: https://github.com/tesseract-ocr/tesseract"
            return 1
            ;;
    esac
}

# 检查系统工具
check_system_tools() {
    # 检查网络连接工具
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        log_warning "建议安装curl或wget以获得更好的网络支持"
    fi
    
    # 检查解压工具
    if ! command -v unzip &> /dev/null; then
        log_warning "建议安装unzip工具"
    fi
}

# 创建虚拟环境（可选）
setup_virtual_env() {
    if [[ "$1" == "--venv" ]]; then
        log_step "设置Python虚拟环境"
        
        if [[ ! -d "venv" ]]; then
            log_info "创建虚拟环境..."
            $PYTHON_CMD -m venv venv
        fi
        
        log_info "激活虚拟环境..."
        source venv/bin/activate
        log_success "虚拟环境已激活"
        
        # 更新虚拟环境中的pip
        pip install --upgrade pip
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
    log_info "这可能需要几分钟时间，首次安装会下载AI模型..."
    
    # 设置pip安装参数
    pip_args="--timeout 300 --retries 3"
    
    # 分步安装，避免超时和依赖冲突
    log_info "第1步: 安装Web框架依赖..."
    $PYTHON_CMD -m pip install $pip_args fastapi uvicorn[standard] jinja2 python-multipart
    
    log_info "第2步: 安装图像处理依赖..."
    $PYTHON_CMD -m pip install $pip_args Pillow opencv-python numpy
    
    log_info "第3步: 安装PDF处理依赖..."
    $PYTHON_CMD -m pip install $pip_args PyMuPDF
    
    log_info "第4步: 安装基础OCR依赖..."
    $PYTHON_CMD -m pip install $pip_args pytesseract
    
    log_info "第5步: 安装科学计算依赖..."
    $PYTHON_CMD -m pip install $pip_args scipy scikit-learn psutil
    
    # 可选的重型依赖
    install_optional_ocr_engines
    
    log_info "第6步: 安装辅助工具..."
    $PYTHON_CMD -m pip install $pip_args python-dotenv rich requests aiofiles
    
    log_success "Python依赖安装完成"
}

# 安装可选的OCR引擎
install_optional_ocr_engines() {
    log_info "第5a步: 安装EasyOCR (推荐OCR引擎)..."
    if $PYTHON_CMD -m pip install $pip_args torch torchvision easyocr; then
        log_success "EasyOCR安装成功"
    else
        log_warning "EasyOCR安装失败，将仅使用Tesseract"
    fi
    
    log_info "第5b步: 安装PaddleOCR (高精度OCR引擎，可选)..."
    if $PYTHON_CMD -m pip install $pip_args paddlepaddle paddleocr; then
        log_success "PaddleOCR安装成功"
    else
        log_warning "PaddleOCR安装失败，这是正常的（可选组件）"
    fi
}

# 测试关键模块导入
test_imports() {
    log_step "测试关键模块导入"
    
    # 必需模块
    required_modules=("fastapi" "uvicorn" "jinja2" "fitz" "PIL" "cv2" "numpy")
    failed_modules=()
    
    for module in "${required_modules[@]}"; do
        if $PYTHON_CMD -c "import $module" 2>/dev/null; then
            log_success "$module"
        else
            log_error "$module 导入失败"
            failed_modules+=("$module")
        fi
    done
    
    # 可选OCR模块
    ocr_modules=("easyocr" "paddleocr" "pytesseract")
    available_ocr=()
    
    for module in "${ocr_modules[@]}"; do
        if $PYTHON_CMD -c "import $module" 2>/dev/null; then
            log_success "$module (OCR引擎)"
            available_ocr+=("$module")
        else
            log_warning "$module OCR引擎不可用"
        fi
    done
    
    # 检查结果
    if [[ ${#failed_modules[@]} -gt 0 ]]; then
        log_error "以下必需模块导入失败: ${failed_modules[*]}"
        log_warning "程序可能无法正常运行"
        
        read -p "是否尝试重新安装失败的模块? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            retry_install_failed_modules "${failed_modules[@]}"
        else
            read -p "是否继续启动? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    if [[ ${#available_ocr[@]} -eq 0 ]]; then
        log_error "没有可用的OCR引擎！"
        log_info "请手动安装OCR引擎："
        log_info "  $PYTHON_CMD -m pip install easyocr"
        log_info "  $PYTHON_CMD -m pip install paddlepaddle paddleocr"
        exit 1
    fi
    
    log_success "模块测试完成，可用OCR引擎: ${available_ocr[*]}"
}

# 重试安装失败的模块
retry_install_failed_modules() {
    local modules=("$@")
    log_info "重新安装失败的模块..."
    
    for module in "${modules[@]}"; do
        case $module in
            "fitz")
                $PYTHON_CMD -m pip install --force-reinstall PyMuPDF
                ;;
            "PIL")
                $PYTHON_CMD -m pip install --force-reinstall Pillow
                ;;
            "cv2")
                $PYTHON_CMD -m pip install --force-reinstall opencv-python
                ;;
            *)
                $PYTHON_CMD -m pip install --force-reinstall $module
                ;;
        esac
    done
}

# 查找可用端口
find_available_port() {
    local start_port=${1:-$DEFAULT_PORT}
    local max_attempts=${2:-$MAX_PORT_ATTEMPTS}
    
    for ((i=0; i<max_attempts; i++)); do
        local port=$((start_port + i))
        if ! nc -z localhost $port 2>/dev/null && ! lsof -i :$port >/dev/null 2>&1; then
            echo $port
            return
        fi
    done
    
    # 如果都被占用，尝试随机端口
    echo $((start_port + RANDOM % 1000))
}

# 创建必要的目录
create_directories() {
    log_step "创建必要的目录"
    
    directories=("uploads" "downloads" "backup" "static" "templates")
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_success "创建目录: $dir"
        fi
    done
}

# 检查项目文件完整性
check_project_files() {
    log_step "检查项目文件完整性"
    
    required_files=("main.py" "requirements.txt")
    missing_files=()
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        log_error "缺少必要文件: ${missing_files[*]}"
        exit 1
    fi
    
    log_success "项目文件完整"
}

# 清理临时文件
cleanup_temp_files() {
    log_info "清理临时文件..."
    
    # 清理Python缓存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # 清理临时下载文件
    rm -f get-pip.py 2>/dev/null || true
    
    log_success "临时文件清理完成"
}

# 启动服务器
start_server() {
    log_header "启动WebUI服务器"
    
    # 查找可用端口
    port=$(find_available_port)
    
    log_success "准备启动WebUI服务器..."
    log_info "访问地址: http://localhost:$port"
    log_info "网络访问: http://0.0.0.0:$port"
    log_info "按 Ctrl+C 停止服务器"
    log_info ""
    
    # 尝试自动打开浏览器
    open_browser "http://localhost:$port" &
    
    # 启动服务器
    $PYTHON_CMD main.py --port $port
}

# 打开浏览器
open_browser() {
    local url=$1
    sleep 3  # 等待服务器启动
    
    case $(detect_os) in
        "macOS")
            command -v open &> /dev/null && open "$url"
            ;;
        "ubuntu"|"linux")
            command -v xdg-open &> /dev/null && xdg-open "$url"
            ;;
        "windows")
            command -v start &> /dev/null && start "$url"
            ;;
    esac
}

# 显示帮助信息
show_help() {
    echo "PDF批量重命名工具 - 启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --install-only    仅安装依赖，不启动服务器"
    echo "  --venv           使用Python虚拟环境"
    echo "  --port PORT      指定端口号 (默认: 8000)"
    echo "  --no-browser     不自动打开浏览器"
    echo "  --clean          清理临时文件后退出"
    echo "  --check          仅检查环境，不安装或启动"
    echo "  --help           显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 正常启动"
    echo "  $0 --install-only     # 仅安装依赖"
    echo "  $0 --venv            # 使用虚拟环境"
    echo "  $0 --port 9000       # 使用端口9000"
    echo ""
}

# 清理函数
cleanup() {
    log_info "正在清理..."
    # 可以添加清理逻辑
    cleanup_temp_files
}

# 捕获中断信号
trap cleanup EXIT INT TERM

# 解析命令行参数
parse_arguments() {
    INSTALL_ONLY=false
    USE_VENV=false
    CUSTOM_PORT=""
    NO_BROWSER=false
    CLEAN_ONLY=false
    CHECK_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-only)
                INSTALL_ONLY=true
                shift
                ;;
            --venv)
                USE_VENV=true
                shift
                ;;
            --port)
                CUSTOM_PORT="$2"
                shift 2
                ;;
            --no-browser)
                NO_BROWSER=true
                shift
                ;;
            --clean)
                CLEAN_ONLY=true
                shift
                ;;
            --check)
                CHECK_ONLY=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 主函数
main() {
    print_welcome
    
    # 解析参数
    parse_arguments "$@"
    
    # 仅清理模式
    if [[ "$CLEAN_ONLY" == true ]]; then
        cleanup_temp_files
        log_success "清理完成"
        exit 0
    fi
    
    # 环境检查
    log_header "环境检查"
    check_project_files
    check_python
    check_and_upgrade_pip
    check_system_dependencies
    create_directories
    
    # 仅检查模式
    if [[ "$CHECK_ONLY" == true ]]; then
        log_success "环境检查完成"
        exit 0
    fi
    
    # 设置虚拟环境
    if [[ "$USE_VENV" == true ]]; then
        setup_virtual_env --venv
    fi
    
    # 检查是否需要安装依赖
    if ! $PYTHON_CMD -c "import fastapi, uvicorn" 2>/dev/null; then
        install_python_dependencies
    else
        log_success "Python依赖已安装"
    fi
    
    test_imports
    
    # 仅安装模式
    if [[ "$INSTALL_ONLY" == true ]]; then
        log_success "安装完成！运行 './start.sh' 启动服务器"
        exit 0
    fi
    
    # 设置自定义端口
    if [[ -n "$CUSTOM_PORT" ]]; then
        DEFAULT_PORT=$CUSTOM_PORT
    fi
    
    start_server
}

# 运行主函数
main "$@"

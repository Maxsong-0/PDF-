#!/bin/bash

# =============================================================================
# PDF批量重命名工具 - 智能启动脚本
# 支持自动环境检测、分步安装和错误恢复
# 优化版本：支持自动修复PaddleOCR兼容性问题和图形警告抑制
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
ICON_MAGIC="✨"
ICON_FOLDER="📁"

# 全局变量
VERBOSE_MODE=false
MAX_THREADS=8
USE_SMART_REGION=true
CLEAN_DOWNLOADS=false
INSTALL_ONLY=false
SYSTEM_TYPE=""
ARCH_TYPE=""

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

log_debug() {
    if [[ "$VERBOSE_MODE" == true ]]; then
        echo -e "${BLUE}${ICON_GEAR} DEBUG: $1${NC}"
    fi
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
    echo -e "${CYAN}${ICON_ROCKET} PDF批量重命名工具 - 增强版${NC}"
    echo -e "${CYAN}基于OCR技术的智能PDF文件重命名系统${NC}\n"
}

# 检测系统类型和架构
detect_system() {
    log_info "检测系统环境..."
    
    # 检测操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SYSTEM_TYPE="macOS"
        if [[ $(uname -m) == "arm64" ]]; then
            ARCH_TYPE="Apple Silicon (M1/M2)"
        else
            ARCH_TYPE="Intel"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        SYSTEM_TYPE="Linux"
        if command -v lsb_release &> /dev/null; then
            SYSTEM_TYPE="Linux ($(lsb_release -si))"
        elif [[ -f /etc/os-release ]]; then
            SYSTEM_TYPE="Linux ($(source /etc/os-release && echo $NAME))"
        fi
        ARCH_TYPE=$(uname -m)
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        SYSTEM_TYPE="Windows"
        ARCH_TYPE=$(uname -m)
    else
        SYSTEM_TYPE="Unknown"
        ARCH_TYPE=$(uname -m)
    fi
    
    log_success "系统: $SYSTEM_TYPE ($ARCH_TYPE)"
    log_debug "完整系统信息: $(uname -a)"
}

# 创建必要的目录结构
create_directories() {
    log_info "${ICON_FOLDER} 创建必要目录..."
    
    # 定义需要创建的目录
    directories=(
        "uploads"
        "downloads" 
        "temp"
        "static"
        "templates"
        "backup"
        "logs"
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_success "创建目录: $dir"
        else
            log_debug "目录已存在: $dir"
        fi
    done
    
    # 创建日志文件
    if [[ ! -f "logs/app.log" ]]; then
        touch "logs/app.log"
        log_success "创建日志文件: logs/app.log"
    fi
    
    # 设置目录权限
    chmod 755 uploads downloads temp static templates backup logs 2>/dev/null || true
    
    log_success "目录结构创建完成"
}

# 检查磁盘空间
check_disk_space() {
    log_info "检查磁盘空间..."
    
    # 获取当前目录可用空间（单位：GB）
    if command -v df &> /dev/null; then
        if [[ "$SYSTEM_TYPE" == "macOS" ]]; then
            available_space=$(df -h . | awk 'NR==2{print $4}' | sed 's/G//')
        else
            available_space=$(df -h . | awk 'NR==2{print $4}' | sed 's/G//')
        fi
        
        # 简单检查是否有足够空间（至少1GB）
        if [[ ${available_space%.*} -lt 1 ]] 2>/dev/null; then
            log_warning "磁盘空间不足，建议至少保留1GB空间"
        else
            log_success "磁盘空间充足: ${available_space}可用"
        fi
    else
        log_debug "无法检测磁盘空间"
    fi
}

# 检查Python版本
check_python() {
    log_info "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "未找到Python3，请先安装Python 3.8+"
        log_info "安装方法："
        case "$SYSTEM_TYPE" in
            "macOS")
                log_info "  brew install python"
                ;;
            *"Linux"*)
                log_info "  Ubuntu/Debian: sudo apt install python3 python3-pip"
                log_info "  CentOS/RHEL: sudo yum install python3 python3-pip"
                log_info "  Rocky/AlmaLinux: sudo dnf install python3 python3-pip"
                ;;
            "Windows")
                log_info "  从 https://python.org 下载安装"
                ;;
        esac
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    log_success "Python版本: $python_version"
    
    # 检查版本是否符合要求
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_success "Python版本符合要求"
    else
        log_error "Python版本过低，需要3.8或更高版本"
        exit 1
    fi
    
    # 检查pip
    if python3 -c "import pip" 2>/dev/null; then
        pip_version=$(python3 -m pip --version | awk '{print $2}')
        log_success "pip版本: $pip_version"
    else
        log_error "pip未安装，请先安装pip"
        exit 1
    fi
}

# 检查并安装uv包管理器
check_and_install_uv() {
    log_info "检查包管理器..."
    
    # 检查uv是否可用
    if command -v uv &> /dev/null; then
        uv_version=$(uv --version | awk '{print $2}')
        log_success "uv包管理器可用: $uv_version（超快速安装）"
        return 0
    fi
    
    log_info "尝试安装uv包管理器..."
    
    # 尝试安装uv
    if python3 -m pip install uv --quiet --user; then
        # 将uv添加到PATH
        export PATH="$HOME/.local/bin:$PATH"
        
        if command -v uv &> /dev/null; then
            uv_version=$(uv --version | awk '{print $2}')
            log_success "uv安装成功: $uv_version！将使用超快速安装"
            return 0
        fi
    fi
    
    log_warning "uv安装失败，将使用pip"
    log_info "升级pip到最新版本..."
    python3 -m pip install --upgrade pip --user
    log_success "pip升级完成"
    return 1
}

# 设置PaddlePaddle环境变量（解决MKLDNN等兼容性问题）
setup_paddle_env() {
    log_info "设置优化环境变量..."
    
    # PaddleOCR 优化变量
    export PADDLE_DISABLE_MKLDNN=1                    # 禁用MKLDNN（解决macOS编译问题）
    export PADDLE_DISABLE_CUDA=1                      # 禁用CUDA（使用CPU）
    export PADDLE_CPP_LOG_LEVEL=3                     # 减少日志输出
    export FLAGS_allocator_strategy=auto_growth       # 内存自动增长策略
    export FLAGS_fraction_of_gpu_memory_to_use=0      # 不使用GPU内存
    
    # 性能优化变量
    export NUMEXPR_MAX_THREADS=$MAX_THREADS           # NumExpr线程限制
    export OMP_NUM_THREADS=$MAX_THREADS               # OpenMP线程限制
    export MKL_NUM_THREADS=$MAX_THREADS               # MKL线程限制
    export OPENBLAS_NUM_THREADS=$MAX_THREADS          # OpenBLAS线程限制
    
    # PyTorch优化变量
    export PYTORCH_DISABLE_PIN_MEMORY=1               # 禁用pin_memory（避免警告）
    export CUDA_VISIBLE_DEVICES=""                    # 禁用CUDA设备
    export TORCH_USE_CUDA_DSA=0                       # 禁用CUDA DSA
    
    # 图形界面优化变量
    export PYTHONWARNINGS="ignore::UserWarning"       # 忽略UserWarning
    export WEBKIT_DISABLE_COMPOSITING_MODE=1          # WebKit渲染优化
    export QT_MAC_WANTS_LAYER=1                       # macOS图形渲染优化
    export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu" # 禁用GPU加速（提高稳定性）
    export QT_LOGGING_RULES="qt5ct.debug=false;*.debug=false" # 减少Qt日志
    
    log_success "环境变量设置完成，已优化运行环境"
    log_debug "线程数设置为: $MAX_THREADS"
}

# 获取包管理器命令
get_package_manager() {
    if command -v uv &> /dev/null; then
        echo "uv"
    else
        echo "pip"
    fi
}

# 使用最佳包管理器安装包
install_packages() {
    local packages="$1"
    local description="$2"
    local pm=$(get_package_manager)
    
    log_info "$description"
    
    if [[ "$pm" == "uv" ]]; then
        log_info "🚀 使用uv超快速安装..."
        uv pip install $packages --user
    else
        log_info "📦 使用pip安装..."
        python3 -m pip install $packages --user
    fi
}

# 检查并安装系统依赖
check_system_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查Tesseract OCR
    if command -v tesseract &> /dev/null; then
        tesseract_version=$(tesseract --version 2>&1 | head -1 | awk '{print $2}')
        log_success "Tesseract已安装: $tesseract_version"
    else
        log_warning "Tesseract OCR未安装"
        install_tesseract
    fi
    
    # 检查其他系统依赖
    case "$SYSTEM_TYPE" in
        "macOS")
            log_debug "macOS系统，检查brew依赖..."
            if ! command -v brew &> /dev/null; then
                log_warning "建议安装Homebrew以便管理依赖"
            fi
            ;;
        *"Linux"*)
            log_debug "Linux系统，检查系统依赖..."
            # 检查fontconfig (字体渲染所需)
            if ! command -v fc-list &> /dev/null; then
                log_warning "fontconfig未安装，某些字体渲染功能可能受限"
            fi
            ;;
    esac
}

# 安装Tesseract OCR
install_tesseract() {
    log_info "自动安装Tesseract OCR..."
    
    case "$SYSTEM_TYPE" in
        "macOS")
            if command -v brew &> /dev/null; then
                brew install tesseract tesseract-lang
                log_success "Tesseract OCR安装完成"
            else
                log_error "未找到Homebrew，请手动安装Tesseract或先安装Homebrew"
                log_info "Homebrew安装: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            fi
            ;;
        *"Linux"*)
            if command -v apt &> /dev/null; then
                sudo apt update
                sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
                log_success "Tesseract OCR安装完成"
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y tesseract tesseract-langpack-chi_sim
                log_success "Tesseract OCR安装完成"
            elif command -v yum &> /dev/null; then
                sudo yum install -y tesseract tesseract-langpack-chi_sim
                log_success "Tesseract OCR安装完成"
            else
                log_warning "无法自动安装Tesseract，请手动安装"
            fi
            ;;
        *)
            log_warning "不支持的操作系统，请手动安装Tesseract OCR"
            ;;
    esac
}

# 修复PaddleOCR V3兼容性问题
fix_paddleocr_compatibility() {
    log_info "检查PaddleOCR兼容性..."
    
    # 检查是否已经安装了PaddleOCR
    if ! python3 -c "import paddleocr" &>/dev/null; then
        log_debug "PaddleOCR未安装，跳过兼容性修复"
        return
    fi
    
    # 检查是否已经存在monkey patch文件
    if [[ -f "paddleocr_v3_monkeypatch.py" ]]; then
        log_success "PaddleOCR V3兼容性补丁已存在"
    else
        log_info "创建PaddleOCR V3兼容性补丁..."
        
        # 创建monkey patch文件
        cat > paddleocr_v3_monkeypatch.py << 'EOF'
# PaddleOCR V3.x 兼容性补丁
# 解决MKLDNN相关的错误和API变更问题

import sys
import os
import warnings

# 抑制不必要的警告
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

def apply_paddle_fixes():
    """应用PaddleOCR修复"""
    print("正在应用PaddleOCR兼容性补丁...")
    
    # 设置关键环境变量
    os.environ['PADDLE_DISABLE_MKLDNN'] = '1'  # 禁用MKLDNN，解决macOS下的编译错误
    os.environ['PADDLE_DISABLE_CUDA'] = '1'     # 禁用CUDA，强制使用CPU
    os.environ['PADDLE_CPP_LOG_LEVEL'] = '3'    # 减少日志输出
    
    # Monkey patch MKLDNN相关函数
    try:
        import paddle
        
        # 检查是否需要补丁
        if not hasattr(paddle.fluid.core, 'set_mkldnn_cache_capacity'):
            print("应用MKLDNN缺失函数补丁...")
            
            # 添加缺失的函数
            def set_mkldnn_cache_capacity(capacity):
                # 空函数，只是为了避免API错误
                pass
            
            # 注入函数
            paddle.fluid.core.set_mkldnn_cache_capacity = set_mkldnn_cache_capacity
            print("MKLDNN补丁应用成功!")
    except ImportError:
        print("未找到paddle库，跳过MKLDNN补丁")
    
    # 处理API变化
    try:
        from paddleocr import PaddleOCR
        
        # 保存原始的__init__函数
        original_init = PaddleOCR.__init__
        
        def patched_init(self, **kwargs):
            # 替换已废弃的参数
            if 'use_angle_cls' in kwargs:
                print("转换已弃用的use_angle_cls参数为use_textline_orientation")
                kwargs['use_textline_orientation'] = kwargs.pop('use_angle_cls')
            
            # 移除已弃用的cls参数
            if 'cls' in kwargs:
                kwargs.pop('cls')
            
            # 调用原始初始化
            original_init(self, **kwargs)
        
        # 应用补丁
        PaddleOCR.__init__ = patched_init
        print("PaddleOCR API兼容性补丁应用成功!")
    except ImportError:
        print("未找到paddleocr库，跳过API兼容性补丁")

# 自动应用修复
apply_paddle_fixes()
EOF
        log_success "PaddleOCR V3兼容性补丁创建完成"
    fi
    
    log_debug "PaddleOCR兼容性检查完成"
}

# 智能安装Python依赖
install_python_dependencies() {
    log_header "安装Python依赖包"
    
    # 检查requirements.txt是否存在
    if [[ ! -f "requirements.txt" ]]; then
        log_error "未找到requirements.txt文件"
        exit 1
    fi
    
    local pm=$(get_package_manager)
    
    if [[ "$pm" == "uv" ]]; then
        log_info "🚀 使用uv超快速安装，速度比pip快5-10倍！"
        log_info "这可能需要1-2分钟时间，首次安装会下载OCR模型..."
    else
        log_info "📦 使用pip安装，这可能需要5-10分钟时间..."
        log_info "首次安装会下载OCR模型..."
    fi
    
    # 分步安装，避免超时
    install_packages "fastapi uvicorn[standard] jinja2 python-multipart" "第1步: 安装Web框架依赖..."
    
    install_packages "Pillow opencv-python numpy" "第2步: 安装图像处理依赖..."
    
    install_packages "PyMuPDF" "第3步: 安装PDF处理依赖..."
    
    install_packages "pytesseract" "第4步: 安装基础OCR依赖..."
    
    install_packages "scipy scikit-learn psutil" "第5步: 安装科学计算依赖..."
    
    log_info "第6步: 安装PaddleOCR (主力OCR引擎)..."
    if [[ "$pm" == "uv" ]]; then
        if uv pip install paddlepaddle>=2.4.0 paddleocr>=2.6.0; then
            log_success "PaddleOCR安装成功"
            fix_paddleocr_compatibility
        else
            log_warning "PaddleOCR安装失败，将使用EasyOCR作为主引擎"
        fi
    else
        if python3 -m pip install paddlepaddle>=2.4.0 paddleocr>=2.6.0; then
            log_success "PaddleOCR安装成功"
            fix_paddleocr_compatibility
        else
            log_warning "PaddleOCR安装失败，将使用EasyOCR作为主引擎"
        fi
    fi
    
    log_info "第7步: 安装EasyOCR (备用OCR引擎)..."
    if [[ "$pm" == "uv" ]]; then
        if uv pip install torch torchvision easyocr; then
            log_success "EasyOCR安装成功"
        else
            log_warning "EasyOCR安装失败"
        fi
    else
        if python3 -m pip install torch torchvision easyocr; then
            log_success "EasyOCR安装成功"
        else
            log_warning "EasyOCR安装失败"
        fi
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
    
    # 测试PaddleOCR monkey patch
    if [[ " ${available_ocr[*]} " =~ " paddleocr " ]]; then
        log_info "测试PaddleOCR补丁..."
        # 尝试导入补丁文件
        if python3 -c "import paddleocr_v3_monkeypatch" 2>/dev/null; then
            log_success "PaddleOCR补丁可用"
        else
            log_warning "PaddleOCR补丁不可用，但不影响继续"
        fi
    fi
    
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
        # 使用更可靠的检测方法
        if ! (echo > /dev/tcp/localhost/$port) >/dev/null 2>&1; then
            echo $port
            return
        fi
    done
    
    echo $start_port  # 默认返回8000
}

# 启动服务器
start_server() {
    log_header "启动WebUI服务器"
    
    # 检查PaddleOCR补丁是否需要应用
    if [[ -f "paddleocr_v3_monkeypatch.py" ]]; then
        log_info "应用PaddleOCR兼容性补丁..."
        export PYTHONPATH=".:$PYTHONPATH"
    fi
    
    # 查找可用端口
    port=$(find_available_port)
    
    log_success "启动WebUI服务器..."
    log_info "${ICON_GLOBE} 访问地址: http://localhost:$port"
    log_info "按 Ctrl+C 停止服务器"
    log_info ""
    
    # 添加智能区域识别和优化参数
    local extra_args=""
    if [[ "$USE_SMART_REGION" == true ]]; then
        extra_args="--smart-region"
    fi
    
    # 尝试自动打开浏览器
    if command -v open &> /dev/null; then
        # macOS
        sleep 2 && open "http://localhost:$port" &
    elif command -v xdg-open &> /dev/null; then
        # Linux
        sleep 2 && xdg-open "http://localhost:$port" &
    elif command -v start &> /dev/null; then
        # Windows
        sleep 2 && start "http://localhost:$port" &
    fi
    
    # 启动服务器
    python3 -c "import paddleocr_v3_monkeypatch" 2>/dev/null || true  # 尝试预加载补丁
    python3 main.py --port $port $extra_args
}

# 优化系统缓存
optimize_system() {
    log_info "${ICON_MAGIC} 执行系统优化..."
    
    # 清理Python缓存
    find . -type d -name "__pycache__" -exec rm -rf {} +  2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # 设置线程数
    if command -v nproc &> /dev/null; then
        # 检测CPU核心数并设置合理的线程数
        cpu_count=$(nproc)
        MAX_THREADS=$((cpu_count / 2))
        # 确保至少有2个线程，最多8个
        if [[ $MAX_THREADS -lt 2 ]]; then
            MAX_THREADS=2
        elif [[ $MAX_THREADS -gt 8 ]]; then
            MAX_THREADS=8
        fi
        log_debug "检测到 $cpu_count 个CPU核心，优化线程数为 $MAX_THREADS"
    fi
    
    log_success "系统优化完成"
}

# 清理函数
cleanup() {
    log_info "正在清理..."
    # 可以添加清理逻辑
}

# 捕获中断信号
trap cleanup EXIT INT TERM

# 解析命令行参数
parse_args() {
    # 设置默认值
    VERBOSE_MODE=false
    CLEAN_DOWNLOADS=false
    INSTALL_ONLY=false
    
    # 解析传入的参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-only)
                INSTALL_ONLY=true
                shift
                ;;
            --verbose|-v)
                VERBOSE_MODE=true
                shift
                ;;
            --no-browser)
                export NO_BROWSER=1
                shift
                ;;
            --no-smart-region)
                USE_SMART_REGION=false
                shift
                ;;
            --clean-downloads)
                CLEAN_DOWNLOADS=true
                shift
                ;;
            --threads)
                if [[ $# -lt 2 ]]; then
                    log_error "缺少线程数参数"
                    exit 1
                fi
                MAX_THREADS=$2
                shift 2
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo
                echo "选项:"
                echo "  --install-only        仅安装依赖，不启动服务器"
                echo "  --verbose, -v         显示详细日志"
                echo "  --no-browser          不自动打开浏览器"
                echo "  --no-smart-region     禁用智能区域识别优化"
                echo "  --clean-downloads     启动前清空downloads目录中的所有文件"
                echo "  --threads <num>       设置使用的线程数（默认：自动）"
                echo "  --help, -h            显示此帮助信息"
                exit 0
                ;;
            *)
                # 未知参数，忽略
                shift
                ;;
        esac
    done
    
    log_debug "运行参数: verbose=$VERBOSE_MODE, smart_region=$USE_SMART_REGION, threads=$MAX_THREADS, clean_downloads=$CLEAN_DOWNLOADS, install_only=$INSTALL_ONLY"
}

# 主函数
main() {
    print_welcome
    
    # 基础环境检测
    log_header "系统环境检测"
    detect_system
    check_disk_space
    create_directories
    
    # 如果启用了清理downloads选项，则清理downloads目录
    if [[ "$CLEAN_DOWNLOADS" == true ]]; then
        log_header "清理下载目录"
        log_info "清理downloads目录中的所有文件..."
        
        # 计算PDF文件数量
        pdf_count=$(find downloads -maxdepth 1 -type f -name "*.pdf" 2>/dev/null | wc -l)
        
        # 清理所有PDF文件
        find downloads -maxdepth 1 -type f -name "*.pdf" -delete 2>/dev/null || true
        
        # 清理.DS_Store文件（macOS）
        if [[ "$SYSTEM_TYPE" == "macOS" ]]; then
            find downloads -name ".DS_Store" -delete 2>/dev/null || true
        fi
        
        # 清理其他可能的临时文件
        find downloads -maxdepth 1 -type f \( -name "*.tmp" -o -name "*.temp" -o -name "*.part" \) -delete 2>/dev/null || true
        
        # 确认目录已清空
        current_count=$(find downloads -maxdepth 1 -type f 2>/dev/null | wc -l)
        if [[ $current_count -eq 0 ]]; then
            log_success "已清理 $pdf_count 个PDF文件，downloads目录现已完全清空"
        else
            log_success "已清理 $pdf_count 个PDF文件，downloads目录中还有 $current_count 个其他文件"
        fi
    fi
    
    # 如果是仅安装模式，执行安装流程后退出
    if [[ "$INSTALL_ONLY" == true ]]; then
        log_header "仅安装模式"
        optimize_system
        check_python
        check_and_install_uv
        check_system_dependencies
        install_python_dependencies
        fix_paddleocr_compatibility
        test_imports
        log_success "安装完成！运行 './start.sh' 启动服务器"
        return
    fi
    
    log_header "环境检查与优化"
    optimize_system
    setup_paddle_env
    check_python
    check_and_install_uv
    check_system_dependencies
    
    # 检查是否需要安装依赖
    if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
        install_python_dependencies
    else
        log_success "Python依赖已安装"
        # 检查并确保PaddleOCR兼容性
        fix_paddleocr_compatibility
    fi
    
    test_imports
    start_server
}

# 检查命令行参数
parse_args "$@"

# 运行主函数
main


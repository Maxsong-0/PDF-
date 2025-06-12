#!/usr/bin/env python3
"""
PDF批量重命名工具 - 智能安装脚本
支持多种安装模式和环境检测
版本: 2.0
"""

import subprocess
import sys
import os
import platform
import json
import time
from pathlib import Path

# 颜色定义
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

# 图标定义
class Icons:
    ROCKET = "🚀"
    CHECK = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    PACKAGE = "📦"
    GEAR = "⚙️"
    FIRE = "🔥"
    GLOBE = "🌐"
    MAGIC = "✨"
    CLEAN = "🧹"

def log_info(message):
    print(f"{Colors.CYAN}{Icons.INFO} {message}{Colors.NC}")

def log_success(message):
    print(f"{Colors.GREEN}{Icons.CHECK} {message}{Colors.NC}")

def log_error(message):
    print(f"{Colors.RED}{Icons.ERROR} {message}{Colors.NC}")

def log_warning(message):
    print(f"{Colors.YELLOW}{Icons.WARNING} {message}{Colors.NC}")

def log_header(message):
    print(f"\n{Colors.PURPLE}{'='*50}{Colors.NC}")
    print(f"{Colors.PURPLE} {message}{Colors.NC}")
    print(f"{Colors.PURPLE}{'='*50}{Colors.NC}\n")

def print_welcome():
    """打印欢迎信息"""
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{Colors.BLUE}")
    print("  ██████╗ ██████╗ ███████╗    ██████╗ ███████╗███╗   ██╗ █████╗ ███╗   ███╗███████╗██████╗ ")
    print("  ██╔══██╗██╔══██╗██╔════╝    ██╔══██╗██╔════╝████╗  ██║██╔══██╗████╗ ████║██╔════╝██╔══██╗")
    print("  ██████╔╝██║  ██║█████╗      ██████╔╝█████╗  ██╔██╗ ██║███████║██╔████╔██║█████╗  ██████╔╝")
    print("  ██╔═══╝ ██║  ██║██╔══╝      ██╔══██╗██╔══╝  ██║╚██╗██║██╔══██║██║╚██╔╝██║██╔══╝  ██╔══██╗")
    print("  ██║     ██████╔╝██║         ██║  ██║███████╗██║ ╚████║██║  ██║██║ ╚═╝ ██║███████╗██║  ██║")
    print("  ╚═╝     ╚═════╝ ╚═╝         ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝")
    print(f"{Colors.NC}\n")
    print(f"{Colors.CYAN}{Icons.ROCKET} PDF批量重命名工具 - 智能安装程序 v2.0{Colors.NC}")
    print(f"{Colors.CYAN}基于AI OCR技术的智能PDF文件重命名系统{Colors.NC}\n")

def run_command(command, description, timeout=300):
    """运行命令并显示进度"""
    log_info(f"{description}...")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True,
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        log_success(f"{description}完成")
        return True, result.stdout
    except subprocess.TimeoutExpired:
        log_error(f"{description}超时")
        return False, "超时"
    except subprocess.CalledProcessError as e:
        log_error(f"{description}失败: {e}")
        if e.stderr:
            print(f"错误输出: {e.stderr}")
        return False, e.stderr
    except Exception as e:
        log_error(f"{description}异常: {e}")
        return False, str(e)

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    log_info(f"Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        log_error("需要Python 3.8或更高版本")
        return False
    
    log_success("Python版本符合要求")
    return True

def detect_system():
    """检测系统信息"""
    system_info = {
        'os': platform.system(),
        'arch': platform.machine(),
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}",
        'platform': platform.platform()
    }
    
    log_info(f"操作系统: {system_info['os']} {system_info['arch']}")
    log_info(f"Python版本: {system_info['python_version']}")
    
    return system_info

def detect_gpu():
    """检测GPU支持"""
    try:
        # 尝试导入torch检测GPU
        result = subprocess.run([sys.executable, '-c', 
            'import torch; print(torch.cuda.is_available()); print(torch.cuda.device_count() if torch.cuda.is_available() else 0)'],
            capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            has_gpu = lines[0] == 'True'
            gpu_count = int(lines[1]) if len(lines) > 1 else 0
            
            if has_gpu:
                log_success(f"检测到GPU支持，设备数量: {gpu_count}")
                return True, gpu_count
    except:
        pass
    
    log_info("未检测到GPU支持，将使用CPU模式")
    return False, 0

def check_available_space():
    """检查可用磁盘空间"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free // (1024**3)
        
        log_info(f"可用磁盘空间: {free_gb} GB")
        
        if free_gb < 2:
            log_warning("磁盘空间不足2GB，可能影响模型下载")
            return False
        
        return True
    except Exception as e:
        log_warning(f"无法检查磁盘空间: {e}")
        return True

def install_basic_dependencies():
    """安装基础依赖"""
    log_header("安装基础依赖")
    
    basic_deps = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-multipart>=0.0.6",
        "jinja2>=3.1.0",
        "PyMuPDF>=1.23.0",
        "Pillow>=10.0.0",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "pytesseract>=0.3.10",
        "scipy>=1.7.0",
        "scikit-learn>=1.0.0",
        "psutil>=5.9.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        "requests>=2.28.0",
        "aiofiles>=23.0.0"
    ]
    
    for dep in basic_deps:
        success, _ = run_command(f"pip install {dep}", f"安装 {dep.split('>=')[0]}")
        if not success:
            log_error(f"基础依赖 {dep} 安装失败")
            return False
    
    log_success("基础依赖安装完成")
    return True

def install_easyocr():
    """安装EasyOCR"""
    log_header("安装EasyOCR (推荐OCR引擎)")
    
    # 检查是否已安装
    try:
        import easyocr
        log_success("EasyOCR已安装")
        return True
    except ImportError:
        pass
    
    # 安装PyTorch
    log_info("安装PyTorch...")
    has_gpu, _ = detect_gpu()
    
    if has_gpu:
        torch_cmd = "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118"
    else:
        torch_cmd = "pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu"
    
    success, _ = run_command(torch_cmd, "安装PyTorch", timeout=600)
    if not success:
        log_warning("PyTorch安装失败，尝试默认源")
        success, _ = run_command("pip install torch torchvision", "安装PyTorch(默认源)", timeout=600)
        if not success:
            return False
    
    # 安装EasyOCR
    success, _ = run_command("pip install easyocr>=1.7.0", "安装EasyOCR", timeout=300)
    if not success:
        return False
    
    log_success("EasyOCR安装完成")
    return True

def install_paddleocr():
    """安装PaddleOCR (可选)"""
    log_header("安装PaddleOCR (高精度OCR引擎)")
    
    # 检查是否已安装
    try:
        import paddleocr
        log_success("PaddleOCR已安装")
        return True
    except ImportError:
        pass
    
    # 安装PaddlePaddle
    success, _ = run_command("pip install paddlepaddle>=2.5.0", "安装PaddlePaddle", timeout=600)
    if not success:
        log_warning("PaddlePaddle安装失败")
        return False
    
    # 安装PaddleOCR
    success, _ = run_command("pip install paddleocr>=2.7.0", "安装PaddleOCR", timeout=300)
    if not success:
        log_warning("PaddleOCR安装失败")
        return False
    
    log_success("PaddleOCR安装完成")
    return True

def test_ocr_engines():
    """测试OCR引擎"""
    log_header("测试OCR引擎")
    
    available_engines = []
    
    # 测试Tesseract
    try:
        import pytesseract
        log_success("Tesseract OCR 可用")
        available_engines.append("tesseract")
    except Exception as e:
        log_warning(f"Tesseract OCR 不可用: {e}")
    
    # 测试EasyOCR
    try:
        import easyocr
        # 简单初始化测试
        reader = easyocr.Reader(['en'], gpu=False)
        log_success("EasyOCR 可用")
        available_engines.append("easyocr")
    except Exception as e:
        log_warning(f"EasyOCR 不可用: {e}")
    
    # 测试PaddleOCR
    try:
        import paddleocr
        log_success("PaddleOCR 可用")
        available_engines.append("paddleocr")
    except Exception as e:
        log_warning(f"PaddleOCR 不可用: {e}")
    
    if not available_engines:
        log_error("没有可用的OCR引擎！")
        return False
    
    log_success(f"可用OCR引擎: {', '.join(available_engines)}")
    return True

def test_basic_imports():
    """测试基础模块导入"""
    log_header("测试基础模块")
    
    required_modules = [
        "fastapi", "uvicorn", "jinja2", 
        "fitz", "PIL", "cv2", "numpy",
        "scipy", "sklearn", "psutil"
    ]
    
    failed_modules = []
    
    for module in required_modules:
        try:
            if module == "fitz":
                import fitz
            elif module == "PIL":
                from PIL import Image
            elif module == "cv2":
                import cv2
            elif module == "sklearn":
                import sklearn
            else:
                __import__(module)
            log_success(f"{module} 导入成功")
        except ImportError as e:
            log_error(f"{module} 导入失败: {e}")
            failed_modules.append(module)
    
    if failed_modules:
        log_error(f"以下模块导入失败: {', '.join(failed_modules)}")
        return False
    
    log_success("所有基础模块导入成功")
    return True

def create_directories():
    """创建必要的目录"""
    log_header("创建项目目录")
    
    directories = ["uploads", "downloads", "backup", "static", "templates"]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        log_success(f"创建目录: {directory}")

def save_install_info():
    """保存安装信息"""
    install_info = {
        "install_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "has_gpu": detect_gpu()[0],
        "installed_engines": []
    }
    
    # 检查已安装的OCR引擎
    try:
        import easyocr
        install_info["installed_engines"].append("easyocr")
    except:
        pass
    
    try:
        import paddleocr
        install_info["installed_engines"].append("paddleocr")
    except:
        pass
    
    try:
        import pytesseract
        install_info["installed_engines"].append("tesseract")
    except:
        pass
    
    with open(".install_info.json", "w", encoding="utf-8") as f:
        json.dump(install_info, f, indent=2, ensure_ascii=False)
    
    log_success("安装信息已保存")

def show_install_options():
    """显示安装选项"""
    print(f"{Colors.CYAN}请选择安装模式:{Colors.NC}")
    print("1. 🚀 完整安装 (推荐) - 安装所有OCR引擎")
    print("2. ⚡ 快速安装 - 仅安装基础依赖和EasyOCR")
    print("3. 🔧 自定义安装 - 选择要安装的组件")
    print("4. 📋 仅基础依赖 - 不安装OCR引擎")
    print("5. ❌ 退出安装")
    
    while True:
        try:
            choice = input(f"\n{Colors.YELLOW}请输入选项 (1-5): {Colors.NC}").strip()
            if choice in ['1', '2', '3', '4', '5']:
                return int(choice)
            else:
                print("请输入有效选项 (1-5)")
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}安装已取消{Colors.NC}")
            sys.exit(0)

def custom_install():
    """自定义安装"""
    print(f"{Colors.CYAN}自定义安装选项:{Colors.NC}")
    
    options = {
        'easyocr': input("安装EasyOCR? (推荐) [Y/n]: ").strip().lower() not in ['n', 'no'],
        'paddleocr': input("安装PaddleOCR? (可选，体积较大) [y/N]: ").strip().lower() in ['y', 'yes']
    }
    
    return options

def main():
    """主函数"""
    print_welcome()
    
    # 环境检查
    log_header("环境检查")
    
    if not check_python_version():
        sys.exit(1)
    
    system_info = detect_system()
    check_available_space()
    
    # 显示安装选项
    choice = show_install_options()
    
    if choice == 5:
        log_info("安装已取消")
        sys.exit(0)
    
    # 安装基础依赖
    if not install_basic_dependencies():
        log_error("基础依赖安装失败")
        sys.exit(1)
    
    # 根据选择安装OCR引擎
    if choice == 1:  # 完整安装
        install_easyocr()
        install_paddleocr()
    elif choice == 2:  # 快速安装
        install_easyocr()
    elif choice == 3:  # 自定义安装
        options = custom_install()
        if options['easyocr']:
            install_easyocr()
        if options['paddleocr']:
            install_paddleocr()
    elif choice == 4:  # 仅基础依赖
        log_info("跳过OCR引擎安装")
    
    # 测试安装
    if not test_basic_imports():
        log_error("基础模块测试失败")
        sys.exit(1)
    
    if choice != 4:  # 如果不是仅基础依赖模式
        if not test_ocr_engines():
            log_warning("OCR引擎测试失败，但基础功能可用")
    
    # 创建目录
    create_directories()
    
    # 保存安装信息
    save_install_info()
    
    # 安装完成
    log_header("安装完成")
    log_success("🎉 PDF批量重命名工具安装成功！")
    
    print(f"\n{Colors.CYAN}下一步:{Colors.NC}")
    print("1. 运行 './start.sh' 启动WebUI服务器")
    print("2. 或运行 'python main.py' 直接启动")
    print("3. 在浏览器中访问 http://localhost:8000")
    
    print(f"\n{Colors.CYAN}提示:{Colors.NC}")
    print("- 首次使用OCR功能时会自动下载AI模型")
    print("- 模型文件约100-200MB，请确保网络通畅")
    print("- 如遇问题，请查看README.md获取帮助")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}安装已中断{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        log_error(f"安装过程中出现异常: {e}")
        sys.exit(1)

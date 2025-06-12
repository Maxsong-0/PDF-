#!/usr/bin/env python3
"""
PDF批量重命名工具 - 环境检查脚本
检查系统环境和依赖是否正确安装
"""

import sys
import platform
import subprocess
import importlib
import json
from pathlib import Path

# 颜色定义
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

# 图标定义
class Icons:
    CHECK = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    GEAR = "⚙️"

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
    print(f"{Colors.PURPLE}{'='*50}{Colors.NC}")

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major >= 3 and version.minor >= 8:
        log_success(f"Python版本: {version_str}")
        return True
    else:
        log_error(f"Python版本过低: {version_str} (需要3.8+)")
        return False

def check_system_info():
    """检查系统信息"""
    log_info(f"操作系统: {platform.system()} {platform.release()}")
    log_info(f"架构: {platform.machine()}")
    log_info(f"平台: {platform.platform()}")

def check_disk_space():
    """检查磁盘空间"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free // (1024**3)
        total_gb = total // (1024**3)
        
        log_info(f"磁盘空间: {free_gb}GB 可用 / {total_gb}GB 总计")
        
        if free_gb < 2:
            log_warning("磁盘空间不足2GB，可能影响模型下载")
            return False
        return True
    except Exception as e:
        log_warning(f"无法检查磁盘空间: {e}")
        return True

def check_module(module_name, import_name=None, optional=False):
    """检查模块是否可导入"""
    if import_name is None:
        import_name = module_name
    
    try:
        if import_name == "fitz":
            import fitz
        elif import_name == "PIL":
            from PIL import Image
        elif import_name == "cv2":
            import cv2
        elif import_name == "sklearn":
            import sklearn
        else:
            importlib.import_module(import_name)
        
        # 获取版本信息
        try:
            if import_name == "fitz":
                import fitz
                version = fitz.version[0] if hasattr(fitz, 'version') else "unknown"
            elif import_name == "PIL":
                from PIL import Image
                version = Image.__version__ if hasattr(Image, '__version__') else "unknown"
            elif import_name == "cv2":
                import cv2
                version = cv2.__version__
            elif import_name == "sklearn":
                import sklearn
                version = sklearn.__version__
            else:
                module = importlib.import_module(import_name)
                version = getattr(module, '__version__', 'unknown')
        except:
            version = "unknown"
        
        log_success(f"{module_name}: {version}")
        return True
    except ImportError as e:
        if optional:
            log_warning(f"{module_name}: 未安装 (可选)")
        else:
            log_error(f"{module_name}: 未安装 - {e}")
        return False

def check_required_modules():
    """检查必需模块"""
    log_header("检查必需模块")
    
    required_modules = [
        ("FastAPI", "fastapi"),
        ("Uvicorn", "uvicorn"),
        ("Jinja2", "jinja2"),
        ("PyMuPDF", "fitz"),
        ("Pillow", "PIL"),
        ("OpenCV", "cv2"),
        ("NumPy", "numpy"),
        ("SciPy", "scipy"),
        ("Scikit-learn", "sklearn"),
        ("PSUtil", "psutil"),
        ("Python-multipart", "multipart"),
        ("Requests", "requests"),
        ("AIOFiles", "aiofiles"),
    ]
    
    all_ok = True
    for module_name, import_name in required_modules:
        if not check_module(module_name, import_name):
            all_ok = False
    
    return all_ok

def check_ocr_engines():
    """检查OCR引擎"""
    log_header("检查OCR引擎")
    
    ocr_engines = [
        ("Tesseract", "pytesseract"),
        ("EasyOCR", "easyocr"),
        ("PaddleOCR", "paddleocr"),
    ]
    
    available_engines = []
    for engine_name, import_name in ocr_engines:
        if check_module(engine_name, import_name, optional=True):
            available_engines.append(engine_name)
    
    if not available_engines:
        log_error("没有可用的OCR引擎！")
        return False
    
    log_success(f"可用OCR引擎: {', '.join(available_engines)}")
    return True

def check_optional_modules():
    """检查可选模块"""
    log_header("检查可选模块")
    
    optional_modules = [
        ("Rich", "rich"),
        ("Python-dotenv", "dotenv"),
        ("PyTorch", "torch"),
        ("TorchVision", "torchvision"),
        ("PaddlePaddle", "paddle"),
    ]
    
    for module_name, import_name in optional_modules:
        check_module(module_name, import_name, optional=True)

def check_external_tools():
    """检查外部工具"""
    log_header("检查外部工具")
    
    tools = [
        ("Tesseract OCR", "tesseract"),
        ("Git", "git"),
        ("Curl", "curl"),
        ("Wget", "wget"),
    ]
    
    for tool_name, command in tools:
        try:
            result = subprocess.run([command, "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # 提取版本信息
                version_line = result.stdout.split('\n')[0]
                log_success(f"{tool_name}: {version_line}")
            else:
                log_warning(f"{tool_name}: 未安装或无法访问")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            log_warning(f"{tool_name}: 未安装")
        except Exception as e:
            log_warning(f"{tool_name}: 检查失败 - {e}")

def check_project_files():
    """检查项目文件"""
    log_header("检查项目文件")
    
    required_files = [
        "main.py",
        "requirements.txt",
        "start.sh",
        "README.md"
    ]
    
    optional_files = [
        "pyproject.toml",
        "poetry.lock",
        "install.py",
        "install_easyocr.py",
        "quick_start.sh"
    ]
    
    all_ok = True
    for file in required_files:
        if Path(file).exists():
            log_success(f"必需文件: {file}")
        else:
            log_error(f"缺少必需文件: {file}")
            all_ok = False
    
    for file in optional_files:
        if Path(file).exists():
            log_success(f"可选文件: {file}")
        else:
            log_warning(f"可选文件: {file} (未找到)")
    
    return all_ok

def check_directories():
    """检查目录结构"""
    log_header("检查目录结构")
    
    required_dirs = ["uploads", "downloads", "backup"]
    optional_dirs = ["static", "templates", "__pycache__"]
    
    for directory in required_dirs:
        if Path(directory).exists():
            log_success(f"目录: {directory}")
        else:
            log_warning(f"目录不存在: {directory} (将自动创建)")
            Path(directory).mkdir(exist_ok=True)
            log_success(f"已创建目录: {directory}")
    
    for directory in optional_dirs:
        if Path(directory).exists():
            log_success(f"可选目录: {directory}")

def check_gpu_support():
    """检查GPU支持"""
    log_header("检查GPU支持")
    
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            log_success(f"GPU支持: {gpu_name} (数量: {gpu_count})")
            return True
        else:
            log_info("GPU支持: 未检测到CUDA GPU")
            return False
    except ImportError:
        log_info("GPU支持: PyTorch未安装，无法检测")
        return False

def load_install_info():
    """加载安装信息"""
    try:
        with open(".install_info.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        log_warning(f"读取安装信息失败: {e}")
        return None

def show_install_info():
    """显示安装信息"""
    install_info = load_install_info()
    if install_info:
        log_header("安装信息")
        log_info(f"安装时间: {install_info.get('install_time', 'unknown')}")
        log_info(f"Python版本: {install_info.get('python_version', 'unknown')}")
        log_info(f"平台: {install_info.get('platform', 'unknown')}")
        log_info(f"GPU支持: {'是' if install_info.get('has_gpu', False) else '否'}")
        engines = install_info.get('installed_engines', [])
        if engines:
            log_info(f"已安装OCR引擎: {', '.join(engines)}")

def generate_report():
    """生成检查报告"""
    log_header("环境检查报告")
    
    checks = {
        "Python版本": check_python_version(),
        "必需模块": check_required_modules(),
        "OCR引擎": check_ocr_engines(),
        "项目文件": check_project_files(),
        "目录结构": True,  # 总是成功，因为会自动创建
    }
    
    passed = sum(checks.values())
    total = len(checks)
    
    print(f"\n{Colors.CYAN}检查结果: {passed}/{total} 项通过{Colors.NC}")
    
    if passed == total:
        log_success("🎉 环境检查完全通过！系统已准备就绪")
        print(f"\n{Colors.GREEN}启动建议:{Colors.NC}")
        print("1. 运行 './start.sh' 启动完整服务")
        print("2. 运行 './quick_start.sh' 快速启动")
        print("3. 运行 'python main.py' 直接启动")
    else:
        log_warning("⚠️ 部分检查未通过，可能影响功能")
        print(f"\n{Colors.YELLOW}修复建议:{Colors.NC}")
        print("1. 运行 'python install.py' 重新安装依赖")
        print("2. 运行 './start.sh --install-only' 仅安装依赖")
        print("3. 手动安装缺失的模块")
    
    return passed == total

def main():
    """主函数"""
    print(f"{Colors.BLUE}")
    print("  ██████╗██╗  ██╗███████╗ ██████╗██╗  ██╗    ███████╗███╗   ██╗██╗   ██╗")
    print("  ██╔════╝██║  ██║██╔════╝██╔════╝██║ ██╔╝    ██╔════╝████╗  ██║██║   ██║")
    print("  ██║     ███████║█████╗  ██║     █████╔╝     █████╗  ██╔██╗ ██║██║   ██║")
    print("  ██║     ██╔══██║██╔══╝  ██║     ██╔═██╗     ██╔══╝  ██║╚██╗██║╚██╗ ██╔╝")
    print("  ╚██████╗██║  ██║███████╗╚██████╗██║  ██╗    ███████╗██║ ╚████║ ╚████╔╝ ")
    print("   ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝    ╚══════╝╚═╝  ╚═══╝  ╚═══╝  ")
    print(f"{Colors.NC}\n")
    print(f"{Colors.CYAN}{Icons.GEAR} PDF批量重命名工具 - 环境检查{Colors.NC}\n")
    
    # 显示系统信息
    check_system_info()
    check_disk_space()
    
    # 显示安装信息
    show_install_info()
    
    # 检查各项
    check_directories()
    check_required_modules()
    check_ocr_engines()
    check_optional_modules()
    check_external_tools()
    check_gpu_support()
    
    # 生成报告
    return generate_report()

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}检查已中断{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}{Icons.ERROR} 检查过程中出现异常: {e}{Colors.NC}")
        sys.exit(1) 
#!/usr/bin/env python3
"""
PDF批量重命名工具 - WebUI版本安装脚本
自动检测环境并安装所需依赖
"""

import subprocess
import sys
import platform
import os

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python版本过低: {version.major}.{version.minor}")
        print("请安装Python 3.8或更高版本")
        return False
    
    print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True

def check_pip():
    """检查pip是否可用"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        print("✅ pip可用")
        return True
    except subprocess.CalledProcessError:
        print("❌ pip不可用，请安装pip")
        return False

def install_requirements():
    """安装Python依赖"""
    try:
        print("📦 安装Python依赖包...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Python依赖安装成功")
            return True
        else:
            print(f"❌ 依赖安装失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 安装过程出错: {e}")
        return False

def check_tesseract():
    """检查Tesseract OCR是否安装"""
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Tesseract OCR已安装")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Tesseract OCR未安装")
    system = platform.system()
    
    print("\n请按以下步骤安装Tesseract OCR:")
    if system == "Windows":
        print("1. 访问: https://github.com/UB-Mannheim/tesseract/wiki")
        print("2. 下载并安装Tesseract OCR")
        print("3. 下载中文语言包 chi_sim.traineddata")
        print("4. 将语言包放入Tesseract安装目录的tessdata文件夹")
    elif system == "Darwin":  # macOS
        print("运行命令: brew install tesseract tesseract-lang")
    else:  # Linux
        print("运行命令:")
        print("sudo apt update")
        print("sudo apt install tesseract-ocr tesseract-ocr-chi-sim")
    
    return False

def test_imports():
    """测试关键模块导入"""
    modules = [
        'fastapi',
        'uvicorn', 
        'jinja2',
        'fitz',
        'PIL',
        'pytesseract',
        'cv2',
        'numpy'
    ]
    
    failed_modules = []
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module}")
            failed_modules.append(module)
    
    return len(failed_modules) == 0

def main():
    print("🚀 PDF批量重命名工具 - WebUI版本安装程序")
    print("=" * 50)
    
    if not check_python_version():
        sys.exit(1)
    
    if not check_pip():
        sys.exit(1)
    
    print("\n📦 安装Python依赖...")
    if not install_requirements():
        print("❌ Python依赖安装失败")
        sys.exit(1)
    
    print("\n🧪 测试模块导入...")
    if not test_imports():
        print("⚠️ 部分模块导入失败，可能影响功能")
    
    print("\n🔍 检查Tesseract OCR...")
    tesseract_ok = check_tesseract()
    
    print("\n" + "=" * 50)
    print("🎉 安装检查完成！")
    
    if tesseract_ok:
        print("✅ 所有依赖都已正确安装")
        print("\n🚀 启动方法:")
        print("Windows: 双击 start.bat")
        print("Linux/macOS: bash start.sh")
        print("或直接运行: python main.py")
        print("\n🌐 然后在浏览器访问: http://localhost:8000")
    else:
        print("⚠️ 请先安装Tesseract OCR后再使用")
        print("安装完成后运行: python main.py")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
EasyOCR 安装脚本
自动安装 EasyOCR 和相关依赖
"""

import subprocess
import sys
import os
import platform

def run_command(command, description):
    """运行命令并显示进度"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {description}完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"📋 Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要Python 3.8或更高版本")
        return False
    
    print("✅ Python版本符合要求")
    return True

def detect_gpu():
    """检测GPU支持"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            print(f"🎮 检测到GPU: {gpu_name} (数量: {gpu_count})")
            return True
    except ImportError:
        pass
    
    print("💻 未检测到GPU，将使用CPU模式")
    return False

def install_dependencies():
    """安装依赖"""
    print("\n🚀 开始安装 EasyOCR 和相关依赖...")
    
    # 基础依赖
    dependencies = [
        "torch>=1.13.0",
        "torchvision>=0.14.0", 
        "easyocr>=1.7.0",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0"
    ]
    
    for dep in dependencies:
        if not run_command(f"pip install {dep}", f"安装 {dep}"):
            return False
    
    return True

def test_easyocr():
    """测试EasyOCR安装"""
    print("\n🧪 测试 EasyOCR 安装...")
    
    test_code = """
import easyocr
import numpy as np
from PIL import Image

# 创建测试图像
img = Image.new('RGB', (200, 50), color='white')
img_array = np.array(img)

# 初始化EasyOCR
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
print("✅ EasyOCR 初始化成功")

# 这会下载模型文件（首次使用）
print("📥 正在下载模型文件...")
results = reader.readtext(img_array)
print("✅ EasyOCR 测试完成")
"""
    
    try:
        exec(test_code)
        return True
    except Exception as e:
        print(f"❌ EasyOCR 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🌸 PDF批量重命名工具 - EasyOCR安装脚本")
    print("="*50)
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 检测GPU
    has_gpu = detect_gpu()
    
    # 安装依赖
    if not install_dependencies():
        print("\n❌ 安装失败，请检查网络连接和权限")
        sys.exit(1)
    
    # 测试安装
    if not test_easyocr():
        print("\n❌ EasyOCR 测试失败")
        sys.exit(1)
    
    print("\n🎉 EasyOCR 安装和配置完成！")
    print("\n📝 安装摘要:")
    print("  ✅ EasyOCR 高精度OCR引擎")
    print("  ✅ 中英文识别模型")
    print(f"  ✅ 运行模式: {'GPU加速' if has_gpu else 'CPU模式'}")
    print("\n💡 提示:")
    print("  - 首次使用时会自动下载AI模型")
    print("  - 模型文件约100-200MB，请确保网络通畅")
    print("  - 下载完成后识别速度会显著提升")
    
    print("\n🚀 现在可以启动PDF重命名工具了！")
    print("   python main.py")

if __name__ == "__main__":
    main() 
# PDF批量重命名工具

🚀 基于OCR技术的智能PDF批量重命名工具，支持中文识别和自动角度校正。

## ✨ 核心特性

- 🔥 **双引擎OCR**: EasyOCR + PaddleOCR，识别精度更高
- 🎯 **智能角度校正**: 自动检测和校正PDF旋转角度
- 🎨 **现代化界面**: 美观的Web UI，支持拖拽上传
- 📦 **批量处理**: 支持多文件同时处理
- 🔒 **安全备份**: 自动备份原文件
- 🌐 **跨平台**: 支持Windows、macOS、Linux

## 🚀 快速开始

### 一键启动（推荐）
```bash
# 自动检测环境、安装依赖并启动服务
./start.sh
```

### 分步操作
```bash
# 1. 检查项目状态
./check.sh

# 2. 仅安装依赖（不启动服务）
./start.sh --install-only

# 3. 启动服务
./start.sh

# 4. 清理项目文件
./clean.sh
```

### 手动启动
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

## 📖 使用方法

1. **启动服务**: 运行 `./start.sh` 或 `python main.py`
2. **访问界面**: 打开浏览器访问 http://localhost:8000
3. **上传文件**: 拖拽或选择PDF文件
4. **开始处理**: 点击"开始处理"按钮
5. **下载结果**: 处理完成后下载重命名的文件

## 📋 系统要求

- **Python**: 3.8 或更高版本
- **内存**: 建议 4GB 以上（双OCR引擎）
- **磁盘空间**: 至少 2GB（模型文件）
- **网络**: 首次运行需要下载OCR模型

## 🔧 支持的格式

工具可以识别以下格式的订单号：
- `销货出库单号: SO2024001`
- `出库单号：ABC123`
- `单号: XYZ-456`
- `订单号 DEF789`
- `SO: GHI012`

## 📁 项目结构

```
pdf重命名-基础/
├── main.py                    # 主程序
├── start.sh                   # 启动脚本（推荐使用）
├── check.sh                   # 项目状态检查
├── clean.sh                   # 项目清理脚本
├── requirements.txt           # Python依赖
├── digit_enhancement.py       # 数字识别增强
├── smart_region_ocr.py       # 智能区域识别
├── paddleocr_v3_monkeypatch.py # PaddleOCR兼容性修复
├── templates/                 # Web模板
├── static/                    # 静态资源
├── uploads/                   # 上传文件目录
├── downloads/                 # 下载文件目录
├── backup/                    # 备份文件目录
└── logs/                      # 日志文件目录
```

## 🛠️ 故障排除

### 常见问题

1. **PIL.Image.ANTIALIAS 错误**
   - 已内置兼容性修复，无需手动处理

2. **OCR模型下载失败**
   ```bash
   # 手动重新下载模型
   python -c "import easyocr; easyocr.Reader(['ch_sim', 'en'])"
   python -c "from paddleocr import PaddleOCR; PaddleOCR()"
   ```

3. **端口被占用**
   ```bash
   # 使用其他端口启动
   python main.py --port 8001
   ```

4. **内存不足**
   - 关闭其他应用程序
   - 重启系统释放内存
   - 考虑升级内存

### 环境检查

运行检查脚本查看环境状态：
```bash
./check.sh
```

### 清理项目

清理临时文件和缓存：
```bash
./clean.sh
```

## 📝 更新日志

### v2.0.0
- ✅ 添加PIL兼容性修复
- ✅ 优化项目结构
- ✅ 新增项目管理脚本
- ✅ 改进错误处理
- ✅ 简化安装流程

### v1.x.x
- ✅ 双引擎OCR支持
- ✅ 智能角度校正
- ✅ Web界面优化
- ✅ 批量处理功能

## 📄 许可证

本项目采用 MIT 许可证。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

---

💡 **提示**: 首次运行时，OCR引擎会自动下载模型文件，请保持网络连接。

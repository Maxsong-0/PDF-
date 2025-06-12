# PDF批量重命名工具 - AI高精度版本 v2.0

🤖 基于多引擎AI OCR技术的高精度PDF批量重命名工具，采用现代化Liquid Glass粉色材质设计的Web界面。

## ✨ 核心亮点

- 🤖 **多引擎AI OCR**: 集成EasyOCR、PaddleOCR、Tesseract三大引擎，识别精度高达95%+
- 🎨 **Liquid Glass界面**: 现代化粉色玻璃质感设计，美观易用
- 🔍 **智能多引擎**: EasyOCR主力 + PaddleOCR高精度 + Tesseract备用，确保最佳识别效果
- 🔄 **智能角度检测**: 三种算法综合判断，自动校正任意角度旋转
- 🚀 **性能优化**: 极简模式切换，适配不同设备性能
- 📦 **安全下载**: 多种下载方式，原文件自动备份保护
- ⚡ **智能安装**: 多种安装模式，自动环境检测和依赖管理

## 🚀 功能特点

- ✅ **AI深度学习识别**: EasyOCR引擎，支持中英文混合复杂格式
- ✅ **现代化WebUI界面**: Liquid Glass粉色材质设计，响应式布局
- ✅ **高精度文本识别**: 专门优化销货出库单号识别，支持特殊格式
- ✅ **智能角度检测**: 霍夫线变换+投影分析+形态学操作三重检测
- ✅ **批量处理**: 支持多文件同时上传和处理，智能批次优化
- ✅ **拖拽上传**: 支持拖拽和点击选择PDF文件
- ✅ **实时反馈**: 详细的处理日志和OCR引擎状态显示
- ✅ **多种下载**: 单个下载、批量ZIP、选择性下载
- ✅ **自动备份**: 按日期分类的原文件安全备份
- ✅ **性能模式**: 标准模式/极简模式智能切换
- ✅ **跨平台支持**: 通过浏览器访问，支持Windows、macOS、Linux

## 📦 快速开始

### 🚀 方法一：一键启动（推荐）
```bash
# 克隆项目
git clone <repository-url>
cd pdf-webui-renamer

# 一键启动（自动检测环境并安装依赖）
./start.sh
```

### ⚡ 方法二：快速启动（已安装依赖）
```bash
# 快速启动（适合已安装依赖的用户）
./quick_start.sh
```

### 🔧 方法三：智能安装
```bash
# 智能安装程序（多种安装模式）
python install.py
```

## 📋 详细安装说明

### 🛠️ 安装脚本说明

#### 1. `start.sh` - 完整启动脚本
- ✅ 自动检测Python环境和版本
- ✅ 智能安装系统依赖（Tesseract OCR）
- ✅ 分步安装Python依赖包
- ✅ 测试模块导入和OCR引擎
- ✅ 自动查找可用端口并启动服务
- ✅ 支持多种命令行参数

```bash
# 使用方法
./start.sh                    # 正常启动
./start.sh --install-only     # 仅安装依赖
./start.sh --venv            # 使用虚拟环境
./start.sh --port 9000       # 指定端口
./start.sh --check          # 仅检查环境
./start.sh --clean          # 清理临时文件
./start.sh --help           # 显示帮助
```

#### 2. `install.py` - 智能安装程序
- 🚀 **完整安装**: 安装所有OCR引擎（推荐）
- ⚡ **快速安装**: 仅安装基础依赖和EasyOCR
- 🔧 **自定义安装**: 选择要安装的组件
- 📋 **仅基础依赖**: 不安装OCR引擎
- ✅ 自动检测GPU支持和系统环境
- ✅ 智能错误处理和重试机制

```bash
python install.py
```

#### 3. `check_env.py` - 环境检查工具
- 🔍 检查Python版本和系统信息
- 📦 检查所有依赖模块状态
- 🤖 检查OCR引擎可用性
- 💾 检查磁盘空间和GPU支持
- 📊 生成详细的环境报告

```bash
python check_env.py
```

#### 4. `quick_start.sh` - 快速启动脚本
- ⚡ 适合已安装依赖的用户
- 🔍 自动查找Python命令和可用端口
- 📁 自动创建必要目录
- 🌐 自动打开浏览器

```bash
./quick_start.sh
```

### 🐍 Python环境要求
- **Python版本**: 3.8+ （推荐3.9+）
- **内存要求**: 4GB+ （推荐8GB+）
- **磁盘空间**: 2GB+ （用于AI模型）
- **网络要求**: 首次安装需要下载模型

### 🔧 系统依赖

#### macOS:
```bash
# 使用Homebrew安装Tesseract
brew install tesseract tesseract-lang
```

#### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra
```

#### CentOS/RHEL:
```bash
sudo yum install epel-release
sudo yum install tesseract tesseract-langpack-chi_sim
```

### 📦 依赖管理

#### 使用pip安装:
```bash
pip install -r requirements.txt
```

#### 使用Poetry安装:
```bash
# 安装Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 安装依赖
poetry install

# 安装可选OCR引擎
poetry install --extras "easyocr paddleocr"
```

### 📋 传统安装方法

#### 1. 安装基础依赖
```bash
pip install -r requirements.txt
```

#### 2. 安装EasyOCR AI引擎
```bash
# 安装EasyOCR（推荐，高精度）
pip install easyocr>=1.7.0

# 安装PyTorch（EasyOCR依赖）
pip install torch torchvision
```

#### 3. 安装Tesseract OCR（备用引擎）

##### Windows:
1. 下载并安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
2. 下载中文语言包 `chi_sim.traineddata`
3. 将语言包放入Tesseract安装目录的`tessdata`文件夹

##### macOS:
```bash
brew install tesseract tesseract-lang
```

##### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

### 💡 安装提示
- **首次使用**: EasyOCR会自动下载AI模型（约100-200MB）
- **GPU支持**: 如有NVIDIA GPU，自动启用GPU加速
- **内存需求**: 建议4GB+内存，8GB+最佳
- **网络要求**: 首次安装需要网络下载模型

## 使用方法

### 启动WebUI服务
```bash
python main.py
```

### 访问Web界面
打开浏览器访问: http://localhost:8000

### 使用步骤
1. **上传PDF文件**: 拖拽或点击选择PDF文件
2. **开始处理**: 点击"开始处理"按钮
3. **查看结果**: 查看处理日志和识别结果
4. **下载文件**: 点击"下载重命名文件"获取结果

## 支持的订单号格式
- `销货出库单号: SO2024001`
- `出库单号：ABC123`
- `单号: XYZ-456`
- `订单号 DEF789`
- `SO: GHI012`

## 🔧 技术架构

### 🤖 AI识别引擎
- **EasyOCR**: 深度学习OCR引擎（主要）
  - 支持中英文混合识别
  - GPU/CPU自适应
  - 高精度文本检测和识别
- **Tesseract**: 传统OCR引擎（备用）
  - 多配置优化
  - 特殊字符过滤

### 🚀 后端架构
- **FastAPI**: 现代化异步Python Web框架
- **PyMuPDF**: 高性能PDF文档处理
- **OpenCV**: 图像处理和智能角度检测
- **NumPy**: 数值计算和图像数组处理
- **Pillow**: 图像增强和格式转换
- **PyTorch**: EasyOCR深度学习框架

### 🎨 前端架构
- **HTML5**: 现代化Web标准和拖拽API
- **CSS3**: Liquid Glass粉色材质设计，响应式布局
- **JavaScript**: 交互逻辑、文件处理、状态管理
- **WebAPI**: File API、Fetch API、LocalStorage

## 🔧 故障排除

### 1. EasyOCR相关问题

#### EasyOCR安装失败
```bash
# 重新安装EasyOCR
pip uninstall easyocr
pip install easyocr>=1.7.0

# 安装PyTorch（如果有GPU）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

#### 模型下载失败
```bash
# 手动重新初始化EasyOCR
python -c "import easyocr; reader = easyocr.Reader(['ch_sim', 'en'])"
```

#### GPU内存不足
- 系统会自动切换到CPU模式
- 可以重启应用释放GPU内存
- 考虑使用性能极简模式

### 2. OCR识别精度问题
- ✅ **使用高质量PDF**: 确保文档清晰、分辨率足够
- ✅ **检查文字角度**: 工具会自动检测角度，但过度旋转可能影响识别
- ✅ **查看详细日志**: 观察EasyOCR和Tesseract的识别结果对比
- ✅ **确认格式支持**: 标准格式为4位-12位数字，如`1403-202501030009`

### 3. 性能和内存问题
```bash
# 检查内存使用
python -c "import psutil; print(f'内存使用: {psutil.virtual_memory().percent}%')"

# 使用性能极简模式
# 在界面右下角切换为🌿极简模式
```

### 4. 依赖安装问题
```bash
# 重新安装所有依赖
pip install --upgrade -r requirements.txt

# 检查关键组件
python -c "import easyocr, cv2, fitz; print('✅ 核心依赖正常')"

# 检查Tesseract安装
tesseract --version
```

### 5. 端口和网络问题
```bash
# 检查端口占用
netstat -an | grep 8000

# 修改端口（编辑main.py）
# uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 6. 文件处理问题
- **上传失败**: 检查文件大小（建议<50MB单个文件）
- **下载异常**: 清空浏览器缓存，刷新页面
- **识别失败**: 查看🔧调试下载的详细信息

## 开发说明

### 文件结构
```
pdf_webui_renamer/
├── main.py              # 主程序入口
├── requirements.txt     # Python依赖
├── templates/           # HTML模板
│   └── index.html      # 主页面
├── static/             # 静态资源
├── uploads/            # 上传文件临时目录
└── downloads/          # 处理结果下载目录
```

### 自定义配置
可以在main.py中修改以下配置：
- 支持的文件格式
- OCR识别参数
- 订单号匹配模式
- 服务器端口和地址

## 许可证
本项目仅供学习和个人使用。

## 🆘 技术支持

### 📋 问题检查清单
在报告问题前，请检查：

#### 🔧 环境要求
- ✅ Python版本 >= 3.8（推荐3.9+）
- ✅ 可用内存 >= 4GB（推荐8GB+）
- ✅ 可用磁盘空间 >= 2GB（模型文件）

#### 🤖 AI引擎状态
```bash
# 检查EasyOCR安装
python -c "import easyocr; print('✅ EasyOCR可用')"

# 检查GPU支持
python -c "import torch; print(f'GPU可用: {torch.cuda.is_available()}')"

# 检查Tesseract备用引擎
tesseract --version
```

#### 📁 文件要求
- ✅ PDF文件大小 < 50MB
- ✅ 文档包含清晰的文字内容
- ✅ 销货出库单号格式标准（如：1403-202501030009）
- ✅ 文字未过度旋转或扭曲

#### 🌐 网络环境
- ✅ 首次使用需要网络连接下载AI模型
- ✅ 防火墙允许Python访问互联网
- ✅ 代理设置正确（如果使用）

### 🔍 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 识别精度低 | 文档质量差 | 使用高质量扫描件，确保文字清晰 |
| 启动慢 | 首次下载模型 | 耐心等待AI模型下载完成 |
| 内存不足 | 设备配置低 | 使用🌿极简模式，关闭其他程序 |
| GPU错误 | 驱动问题 | 自动切换CPU模式，更新GPU驱动 |

### 📧 获取帮助
如问题仍未解决，请提供：
1. 🐍 Python版本：`python --version`
2. 💾 系统信息：操作系统和版本
3. 📝 错误日志：完整的错误信息
4. 🔧 调试信息：点击🔧调试下载按钮获取的诊断报告

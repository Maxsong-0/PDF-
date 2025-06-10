
# 📄 PDF 销货出库单号自动识别与重命名工具

本项目基于 [EasyOCR](https://github.com/JaidedAI/EasyOCR) 和 `pdf2image` 实现了对 PDF 文件中的销货出库单号的自动识别与重命名，支持批量处理文件夹中的多个 PDF，并可输出中间图像以便调试。

---

## 🔧 功能特点

- ✅ 支持批量处理 `pdf_input/` 文件夹下的所有 PDF
- ✅ 自动识别销货出库单号（如 `0310-20240515` 格式）
- ✅ 将 PDF 重命名并保存至 `pdf_output/`
- ✅ 自动图像旋转优化识别准确率
- ✅ 可选输出识别过程中的中间图像（调试用）
- ✅ 命令行实时显示处理进度与识别状态

---

## 📁 文件夹结构

```
project/
├── pdf_input/           # 原始PDF文件放入此文件夹
├── pdf_output/          # 输出的PDF文件（按单号命名）
├── debug_output/        # 可选调试图像输出
├── ocr_rename.py        # 主程序脚本
└── README.md            # 项目说明文件
```

---

## 🚀 快速开始

### 1️⃣ 克隆项目

```bash
git clone https://github.com/your-username/pdf-invoice-ocr.git
cd pdf-invoice-ocr
```

### 2️⃣ 安装依赖

确保你使用的是 **Python 3.8+**

```bash
pip install -r requirements.txt
```

如果你没有 `requirements.txt`，可手动安装：

```bash
pip install easyocr opencv-python pdf2image
```

---

### 3️⃣ 安装 Poppler（Windows 用户）

> 本项目依赖 Poppler 来将 PDF 转换为图像

- 下载地址：https://github.com/oschwartz10612/poppler-windows/releases
- 解压后，将 `bin` 目录路径复制
- 修改 `ocr_rename.py` 中的 `POPPLER_PATH` 为你的本地路径，例如：

```python
POPPLER_PATH = r"D:\poppler-24.08.0\Library\bin"
```

---

### 4️⃣ 使用说明

将你需要处理的 PDF 文件放入 `pdf_input/` 文件夹：

```bash
python ocr_rename.py
```

运行后程序将：

- 自动读取所有 PDF
- 提取并识别出库单号
- 按单号重命名 PDF 并保存到 `pdf_output/` 文件夹
- 如果启用了调试选项，将输出中间图像至 `debug_output/`

---

## ⚙️ 参数配置

你可以在 `ocr_rename.py` 中修改以下参数：

```python
SAVE_DEBUG_IMAGES = True   # 是否保存中间图像
POPPLER_PATH = r"..."      # Poppler 安装路径
```

---

## 📦 示例输出

```
pdf_input/
├── 未命名文档1.pdf
├── 未命名文档2.pdf

↓ 运行后将变为：

pdf_output/
├── 0310-20240512.pdf
├── 0311-20240515.pdf

debug_output/（可选）
├── 文档1_original.jpg
├── 文档1_rotated_90.jpg
...
```

---

## 📜 License

MIT License

---

## 🙋‍♂️ 联系

如有任何问题或建议，欢迎提交 [Issue](https://github.com/your-username/pdf-invoice-ocr/issues) 或 Pull Request。

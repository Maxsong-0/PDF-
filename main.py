#!/usr/bin/env python3
# type: ignore
"""
PDF批量重命名工具 - WebUI版本
支持OCR识别销货出库单号，包含旋转检测功能
"""

import os
import re
import io
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict, Any
import logging
import glob
import time
import uuid

# 设置环境变量解决各种警告和兼容性问题
os.environ['NUMEXPR_MAX_THREADS'] = '8'
os.environ['OMP_NUM_THREADS'] = '8'
# PaddlePaddle环境变量（解决MKLDNN编译问题）
os.environ['PADDLE_DISABLE_MKLDNN'] = '1'        # 禁用MKLDNN（解决macOS编译问题）
os.environ['PADDLE_DISABLE_CUDA'] = '1'         # 禁用CUDA（使用CPU）
os.environ['PADDLE_CPP_LOG_LEVEL'] = '3'        # 减少日志输出
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'  # 内存自动增长策略
os.environ['FLAGS_fraction_of_gpu_memory_to_use'] = '0'  # 不使用GPU内存

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
import uvicorn

# 类型注解
try:
    import fitz  # PyMuPDF
    from PIL import Image, ImageEnhance
    import cv2
    import numpy as np
    import easyocr  # type: ignore
    from paddleocr import PaddleOCR  # type: ignore
    
    # 类型提示
    FitzType = type(fitz)
    ImageType = type(Image)
    CV2Type = type(cv2)
    NPType = type(np)
    ImageEnhanceType = type(ImageEnhance)
    EasyOCRType = type(easyocr)
    PaddleOCRType = type(PaddleOCR)
except ImportError:
    # 如果导入失败，使用Any类型
    FitzType = Any
    ImageType = Any
    CV2Type = Any
    NPType = Any
    ImageEnhanceType = Any
    EasyOCRType = Any
    PaddleOCRType = Any

def lazy_import_ocr():
    """延迟导入OCR相关库以减少启动内存"""
    global fitz, Image, cv2, np, ImageEnhance, easyocr, paddleocr
    try:
        import fitz  # PyMuPDF
        from PIL import Image, ImageEnhance
        
        # PIL兼容性补丁 - 处理Pillow 10.0.0+中ANTIALIAS被移除的问题
        if not hasattr(Image, 'ANTIALIAS'):
            Image.ANTIALIAS = Image.Resampling.LANCZOS
            Image.NEAREST = Image.Resampling.NEAREST
            Image.BILINEAR = Image.Resampling.BILINEAR
            Image.BICUBIC = Image.Resampling.BICUBIC
            Image.BOX = Image.Resampling.BOX
            Image.HAMMING = Image.Resampling.HAMMING
            Image.LANCZOS = Image.Resampling.LANCZOS
        
        import cv2
        import numpy as np
        import easyocr  # 快速初识别引擎  # type: ignore
        from paddleocr import PaddleOCR  # 精确确认引擎  # type: ignore
        paddleocr = PaddleOCR
        return True
    except ImportError as e:
        logger.error(f"OCR库导入失败: {e}")
        logger.info("请安装依赖库:")
        logger.info("pip install easyocr paddlepaddle paddleocr")
        return False

# 初始化全局变量
fitz = None
Image = None
cv2 = None
np = None
ImageEnhance = None
easyocr = None
paddleocr = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF批量重命名工具", description="基于OCR识别的PDF批量重命名工具")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加全局变量来存储文件名映射关系
filename_mapping: Dict[str, str] = {}  # 重命名后文件名 -> 原始文件名

# 全局变量存储临时ZIP文件信息
temp_zip_files = {}

def clean_original_filename_files():
    """清理downloads目录中的原始文件名格式文件（时间戳开头的文件）"""
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        return 0

    cleaned_count = 0
    try:
        # 识别原始文件名格式的文件（以时间戳开头，格式如：20250213165300083_xxxx.pdf）
        import re
        original_pattern = re.compile(r'^\d{17}_\d{4}.*\.pdf$')  # 匹配 20250213165300083_0022.pdf 格式

        for pdf_file in downloads_dir.glob("*.pdf"):
            # 检查是否是原始文件名格式
            if original_pattern.match(pdf_file.name):
                try:
                    os.remove(pdf_file)
                    cleaned_count += 1
                    logger.info(f"清理原始文件名格式文件: {pdf_file.name}")
                except Exception as e:
                    logger.warning(f"清理文件失败 {pdf_file.name}: {e}")

    except Exception as e:
        logger.error(f"清理原始文件名格式文件时出错: {e}")

    if cleaned_count > 0:
        logger.info(f"✅ 自动清理了 {cleaned_count} 个原始文件名格式文件")

    return cleaned_count

def clean_debug_files():
    """专门清理调试文件的函数"""
    current_dir = Path(".")
    debug_cleaned_count = 0

    # 扩展的调试文件模式
    debug_patterns = [
        "debug_*.png",      # 调试PNG图片
        "debug_*.jpg",      # 调试JPG图片
        "temp_*.png",       # 临时PNG文件
        "temp_*.jpg",       # 临时JPG文件
        "temp_*.zip",       # 临时ZIP文件
        "rotated_*.png",    # 旋转测试图片
        "processed_*.png",  # 处理后图片
        "enhanced_*.png",   # 增强图片
        "original_*.png",   # 原始图片
        "test_*.png",       # 测试图片
        "digit_*.png",      # 数字测试图片
        "roi_*.png",        # ROI测试图片
        "*.debug.png",      # .debug后缀的图片
    ]

    try:
        for pattern in debug_patterns:
            for debug_file in current_dir.glob(pattern):
                try:
                    os.remove(debug_file)
                    debug_cleaned_count += 1
                    logger.debug(f"清理调试文件: {debug_file.name}")
                except Exception as e:
                    logger.warning(f"清理调试文件失败 {debug_file.name}: {e}")
    except Exception as e:
        logger.error(f"清理调试文件时出错: {e}")

    if debug_cleaned_count > 0:
        logger.info(f"🗑️ 专门清理了 {debug_cleaned_count} 个调试文件")

    return debug_cleaned_count

def clean_all_downloads():
    """清理downloads目录中的所有PDF文件和调试文件（每次新识别前清理上次结果）"""
    downloads_dir = Path("downloads")
    current_dir = Path(".")

    cleaned_count = 0
    debug_cleaned_count = 0

    # 清理downloads目录中的PDF文件
    if downloads_dir.exists():
        try:
            for pdf_file in downloads_dir.glob("*.pdf"):
                try:
                    os.remove(pdf_file)
                    cleaned_count += 1
                    logger.info(f"清理上次处理文件: {pdf_file.name}")
                except Exception as e:
                    logger.warning(f"清理文件失败 {pdf_file.name}: {e}")
        except Exception as e:
            logger.error(f"清理downloads目录时出错: {e}")

    # 清理当前目录中的调试文件
    debug_patterns = [
        "debug_*.png",      # 调试PNG图片
        "debug_*.jpg",      # 调试JPG图片
        "temp_*.png",       # 临时PNG文件
        "temp_*.jpg",       # 临时JPG文件
        "temp_*.zip",       # 临时ZIP文件
        "rotated_*.png",    # 旋转测试图片
        "processed_*.png",  # 处理后图片
        "enhanced_*.png",   # 增强图片
        "original_*.png",   # 原始图片
    ]

    try:
        for pattern in debug_patterns:
            for debug_file in current_dir.glob(pattern):
                try:
                    os.remove(debug_file)
                    debug_cleaned_count += 1
                    logger.debug(f"清理调试文件: {debug_file.name}")
                except Exception as e:
                    logger.warning(f"清理调试文件失败 {debug_file.name}: {e}")
    except Exception as e:
        logger.error(f"清理调试文件时出错: {e}")

    total_cleaned = cleaned_count + debug_cleaned_count

    if cleaned_count > 0:
        logger.info(f"🧹 清理了 {cleaned_count} 个上次处理的文件")
    if debug_cleaned_count > 0:
        logger.info(f"🗑️ 清理了 {debug_cleaned_count} 个调试文件")

    return total_cleaned

def get_template_directory():
    """自动检测模板目录的正确路径"""
    # 获取当前脚本的目录
    script_dir = Path(__file__).parent.absolute()

    # 可能的模板目录位置
    possible_paths = [
        script_dir / "templates",  # 同级目录
        Path.cwd() / "templates",  # 当前工作目录
        script_dir.parent / "templates",  # 上级目录
    ]

    for template_path in possible_paths:
        if template_path.exists() and (template_path / "index.html").exists():
            logger.info(f"找到模板目录: {template_path}")
            return str(template_path)

    # 如果都找不到，创建默认目录
    default_path = script_dir / "templates"
    default_path.mkdir(exist_ok=True)
    logger.warning(f"未找到现有模板目录，创建默认目录: {default_path}")
    return str(default_path)

def get_static_directory():
    """自动检测静态文件目录的正确路径"""
    script_dir = Path(__file__).parent.absolute()

    possible_paths = [
        script_dir / "static",
        Path.cwd() / "static",
        script_dir.parent / "static",
    ]

    for static_path in possible_paths:
        if static_path.exists():
            logger.info(f"找到静态文件目录: {static_path}")
            return str(static_path)

    # 如果都找不到，创建默认目录
    default_path = script_dir / "static"
    default_path.mkdir(exist_ok=True)
    logger.info(f"创建静态文件目录: {default_path}")
    return str(default_path)

# 创建必要的目录
script_dir = Path(__file__).parent.absolute()
for dir_name in ["uploads", "backup", "downloads"]:
    dir_path = script_dir / dir_name
    dir_path.mkdir(exist_ok=True)

# 获取正确的模板和静态文件目录
template_dir = get_template_directory()
static_dir = get_static_directory()

templates = Jinja2Templates(directory=template_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class PDFProcessor:
    def __init__(self):
        # EasyOCR 读取器（延迟初始化）
        self._easyocr_reader = None
        self._easyocr_initialized = False

        # PaddleOCR 读取器（延迟初始化）
        self._paddleocr_reader = None
        self._paddleocr_initialized = False

        # OCR常见错误矫正字典（数字容易错误识别）
        self.ocr_correction_map = {
            '8': '0',  # 8容易被误识别为0
            '0': '8',  # 0容易被误识别为8
            '6': '5',  # 6容易被误识别为5
            '5': '6',  # 5容易被误识别为6
            '1': 'I',  # 数字1和字母I的混淆
            'I': '1',  # 字母I和数字1的混淆
            'O': '0',  # 字母O和数字0的混淆
            '0': 'O',  # 数字0和字母O的混淆
            'Z': '2',  # Z和2的混淆
            '2': 'Z',  # 2和Z的混淆
        }

        # 快递单号特征模式（需要排除的）
        self.express_patterns = [
            r'[A-Z]{2}[0-9]{10,15}',  # 如YT1234567890123（圆通）
            r'[0-9]{12,15}',  # 纯12-15位数字快递单号
            r'JD[0-9]{13,18}',  # 京东快递
            r'SF[0-9]{12}',  # 顺丰速运
            r'YTO[0-9]{10,13}',  # 圆通速递
            r'ZTO[0-9]{12}',  # 中通快递
            r'STO[0-9]{12}',  # 申通快递
            r'YD[0-9]{13}',  # 韵达快递
            r'HTKY[0-9]{10}',  # 百世汇通
            r'[0-9]{13}',  # 13位纯数字（常见快递格式）
        ]

        # 销货出库单号的精确识别模式（按置信度排序）
        self.patterns = [
            # 超高置信度：包含明确标识的完整格式
            r'销货出库单号[：:\s]*([0-9]{4}[-_][0-9]{12})',  # 严格4-12位格式
            r'销货出库单号[：:\s]*([0-9]{4}[-_][0-9]{10,15})',  # 中文+4位数字-10到15位数字
            r'出库单号[：:\s]*([0-9]{4}[-_][0-9]{12})',  # 出库单号+严格格式

            # 高置信度：标准****-************格式（你的主要格式）
            r'(?<![A-Za-z0-9])([0-9]{4}[-_][0-9]{12})(?![A-Za-z0-9])',  # 严格4位-12位数字
            r'(?<![A-Za-z0-9])([0-9]{4}[-_][0-9]{10,15})(?![A-Za-z0-9])',  # 4位数字-10到15位数字

            # 中高置信度：包含关键词的格式
            r'单号[：:\s]*([0-9]{4}[-_][0-9]{12})',  # "单号"+严格格式
            r'编号[：:\s]*([0-9]{4}[-_][0-9]{12})',  # "编号"+严格格式
            r'出库[：:\s]*([0-9]{4}[-_][0-9]{12})',  # "出库"+严格格式

            # 中置信度：特定前缀（排除快递公司前缀）
            r'(?<![A-Za-z0-9])([13579][0-9]{3}[-_][0-9]{12})(?![A-Za-z0-9])',  # 奇数开头4位-12位
            r'(?<![A-Za-z0-9])([1][4][0-9]{2}[-_][0-9]{12})(?![A-Za-z0-9])',  # 14开头的格式

            # 容错模式：OCR可能的错误识别（增强版）
            r'销[货买贷][出人山][库单里][单里号][：:\s]*([0-9]{4}[-_][0-9]{10,15})',  # OCR容错
            r'[销锗][货贷买][出山人][库里单][单里号]号[：:\s]*([0-9]{4}[-_][0-9]{10,15})',  # 更多OCR容错

            # 增强宽松格式：适应更多OCR识别结果
            r'(?<![A-Za-z0-9])([0-9]{4}[－—\-_]\s*[0-9]{8,20})(?![A-Za-z0-9])',  # 支持各种横线符号和空格
            r'(?<![A-Za-z0-9])([0-9]{3,5}[-_][0-9]{8,20})(?![A-Za-z0-9])',  # 3-5位-8-20位数字
            r'(?<![A-Za-z0-9])([0-9]{4}\s+[0-9]{10,15})(?![A-Za-z0-9])',  # 空格分隔的格式

            # 调试模式：超宽松匹配（用于调试）
            r'(?<![A-Za-z])([0-9]{4}[^A-Za-z0-9\u4e00-\u9fff]*[0-9]{8,})',  # 4位数字+任意分隔符+8位以上数字
            r'([0-9]{12,20})',  # 直接匹配12-20位连续数字
        ]

        # 需要排除的常见单词和无效模式（大幅扩展）
        self.excluded_words = {
            # 基本排除词
            'document', 'order', 'sales', 'number', 'date', 'customer',
            'address', 'phone', 'email', 'total', 'amount', 'price',
            'quantity', 'description', 'product', 'service', 'company',
            'invoice', 'receipt', 'payment', 'balance', 'account',

            # 快递公司相关
            'express', 'delivery', 'courier', 'shipping', 'tracking',
            'jd', 'sf', 'yto', 'zto', 'sto', 'yd', 'htky',

            # 无效数字序列
            '0000000000000000', '1111111111111111', '2222222222222222',
            '3333333333333333', '4444444444444444', '5555555555555555',
            '6666666666666666', '7777777777777777', '8888888888888888',
            '9999999999999999',

            # 无效字母序列
            'abcdefghijklmnop', 'qrstuvwxyz', 'xxxxxxxxxxxxxxxxx',
        }

        # 增强验证规则（支持1410等新前缀）
        self.validation_rules = {
            'min_digits': 4,  # 降低数字要求便于调试
            'min_length': 6,  # 降低最小长度要求
            'max_length': 30,  # 增加最大长度
            'required_separator': ['-', '_', '－', '—', ' '],  # 支持更多分隔符类型
            'min_separator_count': 0,  # 不强制要求分隔符（便于调试）
            'sales_order_prefixes': ['1403', '1404', '1405', '1410', '1411', '1412'],  # 扩展销货单号前缀
            'invalid_patterns': [
                r'^[0]+$',  # 全零
                r'^[1]+$',  # 全一
                r'^(.)\1{8,}$',  # 重复字符超过8次
                r'^[A-Z]{2}[0-9]{10,15}$',  # 快递单号格式
                r'^JD[0-9]+$',  # 京东快递
                r'^SF[0-9]+$',  # 顺丰快递
                r'^YTO[0-9]+$',  # 圆通快递
                r'^ZTO[0-9]+$',  # 中通快递
                r'^STO[0-9]+$',  # 申通快递
            ]
        }

    def extract_order_number(self, pdf_path: str) -> Tuple[Optional[str], str]:
        """从PDF中提取销货出库单号，返回(订单号, 处理日志)"""
        log_messages = []

        if not lazy_import_ocr():
            return None, "❌ OCR库导入失败，请确保已安装所有依赖"

        try:
            # 检查文件是否存在
            if not os.path.exists(pdf_path):
                return None, "❌ 文件不存在"

            if fitz is None:
                return None, "❌ PyMuPDF库未正确导入"

            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                page_text = page.get_text()
                text += page_text
            doc.close()

            log_messages.append("✅ PDF文件读取成功")

            # 先尝试直接文本提取
            order_number = self.find_order_number_in_text(text)
            if order_number:
                log_messages.append(f"✅ 直接文本提取成功: {order_number}")
                return order_number, "\n".join(log_messages)

            log_messages.append("⚠️ 直接文本提取失败，开始OCR处理...")

            # 使用OCR处理
            ocr_result, ocr_logs = self.extract_with_ocr(pdf_path)
            log_messages.extend(ocr_logs)

            return ocr_result, "\n".join(log_messages)

        except Exception as e:
            error_msg = f"❌ 处理失败: {str(e)}"
            log_messages.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None, "\n".join(log_messages)

    def find_order_number_in_text(self, text: str) -> Optional[str]:
        """在文本中查找销货出库单号 - 高精度版本（增强OCR矫正）"""
        try:
            candidates = []

            # 1. 获取OCR矫正后的多个文本版本
            text_variants = self._apply_ocr_correction(text)
            logger.info(f"OCR矫正生成{len(text_variants)}个文本变体")

            # 2. 对每个文本变体进行模式匹配
            for variant_index, text_variant in enumerate(text_variants):
                variant_label = "原文" if variant_index == 0 else f"矫正{variant_index}"

                # 遍历所有模式，按优先级收集候选项
                for pattern_index, pattern in enumerate(self.patterns):
                    matches = re.finditer(pattern, text_variant, re.IGNORECASE)
                    for match in matches:
                        result = match.group(1).strip()
                        if self._validate_order_number(result):
                            # 计算综合置信度
                            base_confidence = len(self.patterns) - pattern_index
                            # 原文匹配置信度更高
                            variant_bonus = 1.0 if variant_index == 0 else 0.8
                            final_confidence = base_confidence * variant_bonus

                            candidates.append({
                                'number': result,
                                'confidence': final_confidence,
                                'pattern_index': pattern_index,
                                'variant': variant_label,
                                'variant_index': variant_index
                            })

                            logger.info(f"候选订单号: {result} (模式{pattern_index}, {variant_label}, 置信度{final_confidence:.2f})")

            if not candidates:
                logger.info("未找到有效的销货出库单号候选")
                return None

            # 3. 按置信度排序，返回最佳候选项
            candidates.sort(key=lambda x: (-x['confidence'], x['pattern_index'], x['variant_index']))

            # 4. 去重，优先选择原文识别的结果
            unique_numbers = {}
            for candidate in candidates:
                number = candidate['number']
                if number not in unique_numbers:
                    unique_numbers[number] = candidate
                else:
                    # 如果是原文识别的，替换矫正文本的结果
                    if candidate['variant_index'] == 0 and unique_numbers[number]['variant_index'] > 0:
                        unique_numbers[number] = candidate

            final_candidates = list(unique_numbers.values())
            final_candidates.sort(key=lambda x: (-x['confidence'], x['pattern_index'], x['variant_index']))

            best_candidate = final_candidates[0]

            logger.info(f"最终选择: {best_candidate['number']} (来源: {best_candidate['variant']}, 置信度: {best_candidate['confidence']:.2f})")
            logger.info(f"总计找到{len(candidates)}个候选项，去重后{len(final_candidates)}个")

            return best_candidate['number']

        except Exception as e:
            logger.error(f"文本查找失败: {e}")
            return None

    def _apply_ocr_correction(self, text: str) -> List[str]:
        """应用OCR常见错误矫正，生成多个候选文本"""
        original = text
        corrected_variants = [original]

        # 尝试常见的数字矫正
        for wrong, correct in self.ocr_correction_map.items():
            if wrong in text:
                variant = text.replace(wrong, correct)
                if variant != original and variant not in corrected_variants:
                    corrected_variants.append(variant)

        return corrected_variants

    def _is_express_number(self, candidate: str) -> bool:
        """检查是否是快递单号"""
        # 检查快递单号特征模式
        for pattern in self.express_patterns:
            if re.match(pattern, candidate):
                logger.info(f"识别为快递单号（格式匹配）: {candidate}")
                return True

        # 检查快递公司前缀
        express_prefixes = ['JD', 'SF', 'YTO', 'ZTO', 'STO', 'YD', 'HTKY', 'EMS', 'YZPY', 'YUNDA']
        for prefix in express_prefixes:
            if candidate.upper().startswith(prefix):
                logger.info(f"识别为快递单号（前缀匹配）: {candidate}")
                return True

        # 特殊格式检查：纯数字且长度为快递常用长度
        if candidate.isdigit():
            if len(candidate) in [13, 15, 18]:  # 快递单号常用长度
                logger.info(f"识别为快递单号（长度特征）: {candidate}")
                return True

        return False

    def _validate_order_number(self, candidate: str) -> bool:
        """验证候选订单号是否有效（调试期间宽松版本）"""
        if not candidate:
            return False

        # 基本长度检查
        rules = self.validation_rules
        if len(candidate) < rules['min_length'] or len(candidate) > rules['max_length']:
            logger.debug(f"长度不符合要求: {candidate} (长度: {len(candidate)})")
            return False

        # 排除常见无效词汇
        if candidate.lower() in self.excluded_words:
            logger.debug(f"在排除词汇中: {candidate}")
            return False

        # 快递单号排除检查
        if self._is_express_number(candidate):
            logger.debug(f"识别为快递单号: {candidate}")
            return False

        # 检查是否包含足够的数字
        digit_count = sum(1 for c in candidate if c.isdigit())
        if digit_count < rules['min_digits']:
            logger.debug(f"数字数量不足: {candidate} (数字: {digit_count}, 要求: {rules['min_digits']})")
            return False

        # 检查必需的分隔符（如果要求的话）
        if rules.get('min_separator_count', 0) > 0:
            separator_count = sum(1 for sep in rules['required_separator'] if sep in candidate)
            if separator_count < rules.get('min_separator_count', 0):
                logger.debug(f"分隔符数量不足: {candidate}")
                return False

        # 检查无效模式
        for invalid_pattern in rules['invalid_patterns']:
            if re.match(invalid_pattern, candidate):
                logger.debug(f"匹配无效模式: {candidate}")
                return False

        # 销货出库单号特征检查
        # 1. 检查是否符合销货单号格式 (XXXX-XXXXXXXXXXXX)
        separators = ['-', '_', '－', '—', ' ']
        for sep in separators:
            if sep in candidate:
                parts = candidate.split(sep)
                if len(parts) >= 2:
                    first_part = parts[0].strip()
                    second_part = parts[1].strip()

                    # 第一部分应该是3-5位数字，第二部分应该是6-20位数字（放宽要求）
                    if (first_part.isdigit() and 3 <= len(first_part) <= 5 and
                        second_part.isdigit() and 6 <= len(second_part) <= 20):

                        # 检查是否以销货单号常见前缀开头
                        sales_prefixes = rules.get('sales_order_prefixes', [])
                        if sales_prefixes and any(first_part.startswith(prefix) for prefix in sales_prefixes):
                            logger.debug(f"销货单号前缀匹配: {candidate}")
                            return True

                        # 或者符合一般格式要求
                        if len(first_part) == 4 and len(second_part) >= 8:
                            logger.debug(f"符合一般格式: {candidate}")
                            return True
                break

        # 检查纯数字格式（12-20位）
        if candidate.isdigit() and 12 <= len(candidate) <= 20:
            logger.debug(f"纯数字格式通过: {candidate}")
            return True

        # 调试期间：对包含足够数字的候选放宽要求
        if digit_count >= 8:  # 如果包含8个以上数字，可能是有效的
            # 避免过于简单的模式
            if len(set(candidate)) >= 3:  # 至少3种不同字符
                # 检查数字字母比例是否合理
                alpha_count = sum(1 for c in candidate if c.isalpha())
                # 销货单号主要应该是数字和分隔符，允许少量字母
                if alpha_count <= len(candidate) * 0.3:  # 字母不超过30%
                    logger.debug(f"宽松模式通过: {candidate} (数字: {digit_count}, 字符种类: {len(set(candidate))})")
                    return True

        logger.debug(f"验证失败: {candidate} (数字: {digit_count}, 长度: {len(candidate)})")
        return False

    def _validate_strict_format(self, candidate: str) -> bool:
        """严格验证订单号格式：必须是4位-12位格式"""
        try:
            if not candidate:
                return False

            # 清理候选号码
            clean_candidate = re.sub(r'[^\w-]', '', candidate).strip()

            # 严格格式检查：4位-12位
            strict_pattern = r'^(\d{4})[-_](\d{12})$'
            match = re.match(strict_pattern, clean_candidate)

            if not match:
                logger.debug(f"格式不符合4位-12位要求: {candidate}")
                return False

            prefix, suffix = match.groups()

            # 检查前缀是否为有效的销货单号前缀
            valid_prefixes = ['1403', '1404', '1405', '1410', '1411', '1412']
            if prefix not in valid_prefixes:
                logger.debug(f"前缀无效: {prefix}，有效前缀: {valid_prefixes}")
                return False

            # 检查后缀是否全为数字
            if not suffix.isdigit():
                logger.debug(f"后缀包含非数字字符: {suffix}")
                return False

            logger.debug(f"✅ 严格格式验证通过: {clean_candidate}")
            return True

        except Exception as e:
            logger.error(f"严格格式验证失败: {e}")
            return False

    def find_all_order_candidates(self, text: str) -> list:
        """找到文本中所有潜在的订单号候选"""
        candidates = []
        strict_candidates = []  # 符合严格格式的候选

        # 遍历所有模式，按优先级收集候选项
        for pattern_index, pattern in enumerate(self.patterns):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                result = match.group(1).strip()
                if self._validate_order_number(result):
                    base_confidence = len(self.patterns) - pattern_index

                    # 检查是否符合严格格式（4位-12位）
                    if self._validate_strict_format(result):
                        # 严格格式的候选给予更高的置信度
                        strict_candidates.append({
                            'number': result,
                            'confidence': base_confidence + 100,  # 严格格式额外加分
                            'pattern_index': pattern_index,
                            'format_type': 'strict'
                        })

                    # 也记录为普通候选（兼容性）
                    candidates.append({
                        'number': result,
                        'confidence': base_confidence,
                        'pattern_index': pattern_index,
                        'format_type': 'loose'
                    })

        # 如果有严格格式的候选，优先返回它们
        if strict_candidates:
            strict_candidates.sort(key=lambda x: (-x['confidence'], x['pattern_index']))
            logger.debug(f"🎯 找到 {len(strict_candidates)} 个严格格式候选")
            return strict_candidates

        # 否则返回普通候选
        candidates.sort(key=lambda x: (-x['confidence'], x['pattern_index']))
        logger.debug(f"⚠️ 未找到严格格式候选，返回 {len(candidates)} 个普通候选")
        return candidates

    def _compare_ocr_results(self, easyocr_results: list, paddleocr_results: list, log_messages: list) -> Optional[dict]:
        """比较两个OCR引擎的结果，选择最佳候选"""
        all_candidates = []

        # 收集EasyOCR候选
        for result in easyocr_results:
            for candidate in result['candidates']:
                all_candidates.append({
                    'text': result['text'],
                    'method': f"EasyOCR初识别 ({result['info']})",
                    'number': candidate['number'],
                    'confidence': candidate['confidence'],
                    'source': 'easyocr'
                })

        # 收集PaddleOCR候选
        for result in paddleocr_results:
            for candidate in result['candidates']:
                all_candidates.append({
                    'text': result['text'],
                    'method': f"PaddleOCR精确确认 ({result['info']})",
                    'number': candidate['number'],
                    'confidence': candidate['confidence'],
                    'source': 'paddleocr'
                })

        if not all_candidates:
            return None

        # 智能选择策略（PaddleOCR主力策略）
        # 1. 优先使用PaddleOCR结果（数字识别更准确）
        paddleocr_candidates = [c for c in all_candidates if c['source'] == 'paddleocr']
        if paddleocr_candidates:
            best = max(paddleocr_candidates, key=lambda x: x['confidence'])
            log_messages.append(f"🔥 PaddleOCR主力识别: {best['number']} (置信度: {best['confidence']})")
            return best

        # 2. 如果PaddleOCR失败，检查EasyOCR和PaddleOCR的共同结果
        easyocr_numbers = {c['number'] for c in all_candidates if c['source'] == 'easyocr'}
        paddleocr_numbers = {c['number'] for c in all_candidates if c['source'] == 'paddleocr'}
        common_numbers = easyocr_numbers & paddleocr_numbers

        if common_numbers:
            # 选择共同识别的最高置信度结果
            common_candidates = [c for c in all_candidates if c['number'] in common_numbers]
            best = max(common_candidates, key=lambda x: x['confidence'])
            log_messages.append(f"🎯 双引擎确认相同结果: {best['number']} (置信度: {best['confidence']})")
            return best

        # 3. 最后回退到EasyOCR结果（仅作备用）
        easyocr_candidates = [c for c in all_candidates if c['source'] == 'easyocr']
        if easyocr_candidates:
            best = max(easyocr_candidates, key=lambda x: x['confidence'])
            log_messages.append(f"⚡ 回退EasyOCR结果: {best['number']} (置信度: {best['confidence']})")
            return best

        return None

    def _get_easyocr_reader(self):
        """获取EasyOCR读取器（延迟初始化）"""
        if not self._easyocr_initialized:
            try:
                if not lazy_import_ocr():
                    return None

                logger.info("🚀 初始化 EasyOCR 快速识别引擎（首次使用需要下载模型，请稍候...）")
                # 支持中文和英文，GPU加速（如果可用）
                if easyocr is not None:
                    self._easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=True)
                    self._easyocr_initialized = True
                    logger.info("✅ EasyOCR 快速识别引擎初始化完成")

            except Exception as e:
                logger.warning(f"EasyOCR GPU模式初始化失败，尝试CPU模式: {e}")
                try:
                    # 尝试仅CPU模式
                    if easyocr is not None:
                        self._easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                        self._easyocr_initialized = True
                        logger.info("✅ EasyOCR CPU模式初始化完成")
                except Exception as e2:
                    logger.error(f"EasyOCR CPU模式也失败: {e2}")
                    self._easyocr_reader = None
                    self._easyocr_initialized = True

        return self._easyocr_reader

    def _get_paddleocr_reader(self):
        """获取PaddleOCR读取器（延迟初始化）"""
        if not self._paddleocr_initialized:
            try:
                if not lazy_import_ocr():
                    return None

                logger.info("🔥 初始化 PaddleOCR 精确确认引擎（首次使用需要下载模型，请稍候...）")
                
                # 使用修复后的PaddleOCR配置 (兼容PaddleOCR 2.7.3)
                from paddleocr_v3_monkeypatch import get_paddle_ocr3_monkeypatch
                fix = get_paddle_ocr3_monkeypatch()
                
                if fix.is_available():
                    self._paddleocr_reader = fix
                    self._paddleocr_initialized = True
                    logger.info("✅ PaddleOCR精确确认引擎初始化完成（使用兼容性修复）")
                else:
                    logger.error("❌ PaddleOCR 兼容性修复失败")
                    self._paddleocr_reader = None
                    self._paddleocr_initialized = True

            except Exception as e:
                logger.error(f"PaddleOCR初始化完全失败: {e}")
                self._paddleocr_reader = None
                self._paddleocr_initialized = True

        return self._paddleocr_reader

    def _extract_text_with_easyocr(self, image) -> tuple:
        """使用EasyOCR提取文本"""
        try:
            reader = self._get_easyocr_reader()
            if reader is None:
                return None, "EasyOCR初始化失败"

            # 转换PIL图像为numpy数组
            if hasattr(image, 'convert') and cv2 is not None and np is not None:
                # PIL图像
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            else:
                # 已经是numpy数组
                cv_image = image

            # EasyOCR识别
            logger.info("⚡ 使用 EasyOCR 进行快速初识别...")
            results = reader.readtext(cv_image, detail=1, paragraph=False)

            # 合并所有识别的文本
            text_parts = []
            confidence_scores = []

            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # 过滤低置信度文本
                    text_parts.append(text)
                    confidence_scores.append(confidence)

            full_text = ' '.join(text_parts)
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

            info = f"识别到{len(text_parts)}个文本块，平均置信度:{avg_confidence:.2f}"
            logger.info(f"EasyOCR快速识别结果: {info}")

            return full_text, info

        except Exception as e:
            logger.error(f"EasyOCR识别失败: {e}")
            return None, f"EasyOCR识别失败: {str(e)}"

    def _extract_text_with_paddleocr(self, image) -> tuple:
        """使用PaddleOCR提取文本"""
        try:
            reader = self._get_paddleocr_reader()
            if reader is None:
                return None, "PaddleOCR初始化失败"

            # 保存图像为临时文件，因为新的适配器需要文件路径
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
                
                # 转换并保存图像
                if hasattr(image, 'save'):
                    # PIL图像
                    image.save(temp_path)
                else:
                    # numpy数组
                    if Image is not None:
                        pil_image = Image.fromarray(image)
                        pil_image.save(temp_path)
                    else:
                        return None, "无法保存临时图像文件"

            try:
                # PaddleOCR识别
                logger.info("🔥 使用 PaddleOCR 3.0.1 进行精确确认...")
                
                # 使用新的适配器进行OCR识别
                results = reader.predict_to_old_format(temp_path)

                # 解析结果（已经是旧格式）
                text_parts = []
                confidence_scores = []

                if results and results[0]:  # results[0]是第一页的结果
                    for line in results[0]:
                        if len(line) >= 2:
                            text = line[1][0]  # 提取文本
                            confidence = line[1][1]  # 提取置信度

                            if confidence > 0.3:  # 过滤低置信度文本
                                text_parts.append(text)
                                confidence_scores.append(confidence)

                full_text = ' '.join(text_parts)
                avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

                info = f"识别到{len(text_parts)}个文本块，平均置信度:{avg_confidence:.2f}"
                logger.info(f"PaddleOCR 3.0.1精确确认结果: {info}")

                return full_text, info
                
            finally:
                # 清理临时文件
                try:
                    import os
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"清理临时文件失败: {cleanup_error}")

        except Exception as e:
            logger.error(f"PaddleOCR识别失败: {e}")
            return None, f"PaddleOCR识别失败: {str(e)}"

    def _enhance_image_for_ocr(self, image):
        """专门为OCR优化的图像增强处理（基于测试结果优化）"""
        try:
            # 转换为灰度
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image

            # 对比度增强（基于测试结果，1.8倍效果好）
            if ImageEnhance is not None:
                enhancer = ImageEnhance.Contrast(gray)
                enhanced = enhancer.enhance(1.8)
            else:
                enhanced = gray

            # 转换为OpenCV格式
            if np is not None and cv2 is not None:
                cv_image = np.array(enhanced)

                # 高斯模糊去噪（轻微去噪）
                blurred = cv2.GaussianBlur(cv_image, (1, 1), 0)

                # OTSU二值化（测试证明效果最好）
                _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # 轻微的形态学操作清理噪声
                kernel = np.ones((1, 1), np.uint8)
                cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

                logger.debug(f"应用优化的OCR图像增强处理")

                if Image is not None:
                    return Image.fromarray(cleaned)

            return enhanced

        except Exception as e:
            logger.warning(f"图像增强失败，使用原图: {e}")
            return image

    def _enhance_for_digit_recognition(self, image):
        """专门针对数字识别的图像增强"""
        try:
            if np is None or cv2 is None:
                logger.warning("numpy或cv2未导入，跳过数字识别增强")
                return image

            # 转换为灰度
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image

            cv_image = np.array(gray)

            # 1. 高斯模糊去噪
            denoised = cv2.GaussianBlur(cv_image, (1, 1), 0)

            # 2. 直方图均衡化增强对比度
            equalized = cv2.equalizeHist(denoised)

            # 3. 双边滤波保持边缘的同时去噪
            bilateral = cv2.bilateralFilter(equalized, 9, 75, 75)

            # 4. 多级阈值处理
            # OTSU自动阈值
            _, otsu = cv2.threshold(bilateral, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # 5. 形态学开运算去除小噪声
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            opening = cv2.morphologyEx(otsu, cv2.MORPH_OPEN, kernel)

            # 6. 膨胀操作增强数字笔画
            kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            final = cv2.dilate(opening, kernel_dilate, iterations=1)

            if Image is not None:
                return Image.fromarray(final)
            return image

        except Exception as e:
            logger.warning(f"数字识别增强失败: {e}")
            return image

    def detect_text_orientation(self, image) -> float:
        """精细的文本方向检测，返回精确角度（小数）"""
        try:
            if cv2 is None or np is None:
                logger.warning("cv2或numpy未导入，跳过方向检测")
                return 0.0

            # 首先检查是否有必要的依赖
            try:
                import scipy  # type: ignore
                import sklearn  # type: ignore
                use_advanced_detection = True
            except ImportError as import_error:
                logger.warning(f"高级角度检测依赖缺失: {import_error}，将使用基础检测")
                use_advanced_detection = False

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            if use_advanced_detection:
                # 使用新的精细检测方法
                try:
                    # 方法1: 精细霍夫线变换角度检测
                    angle1, confidence1, method1_info = self._detect_precise_angle_by_hough(gray)
                    logger.debug(f"精细霍夫线检测: {angle1:.2f}° (置信度: {confidence1:.3f}) - {method1_info}")

                    # 方法2: 基于主成分分析的角度检测
                    angle2, confidence2, method2_info = self._detect_angle_by_pca(gray)
                    logger.debug(f"PCA检测: {angle2:.2f}° (置信度: {confidence2:.3f}) - {method2_info}")

                    # 方法3: 基于边缘方向的角度检测
                    angle3, confidence3, method3_info = self._detect_angle_by_edge_direction(gray)
                    logger.debug(f"边缘方向检测: {angle3:.2f}° (置信度: {confidence3:.3f}) - {method3_info}")

                    # 加权平均，置信度高的方法权重更大
                    angles = [angle1, angle2, angle3]
                    confidences = [confidence1, confidence2, confidence3]
                    methods_info = [method1_info, method2_info, method3_info]

                    # 过滤掉置信度过低的结果
                    valid_results = [(angle, conf, info) for angle, conf, info in zip(angles, confidences, methods_info) if conf > 0.1]

                    if valid_results:
                        # 加权平均计算最终角度
                        total_weight = sum(conf for _, conf, _ in valid_results)
                        if total_weight > 0:
                            weighted_angle = sum(angle * conf for angle, conf, _ in valid_results) / total_weight

                            # 记录详细的检测信息
                            logger.debug(f"角度检测详情: 霍夫线={angle1:.2f}°(置信度{confidence1:.3f}), PCA={angle2:.2f}°(置信度{confidence2:.3f}), 边缘={angle3:.2f}°(置信度{confidence3:.3f})")
                            logger.debug(f"加权平均角度: {weighted_angle:.2f}°")

                            # 对角度进行合理性检查和修正
                            final_angle = self._normalize_detected_angle(weighted_angle)
                            logger.debug(f"最终标准化角度: {final_angle:.2f}°")

                            return final_angle

                except Exception as detection_error:
                    logger.warning(f"精细角度检测失败: {detection_error}，回退到基础检测")
                    use_advanced_detection = False

            if not use_advanced_detection:
                # 回退到基础角度检测
                logger.info("使用基础角度检测方法")
                return self._basic_angle_detection(gray)

            return 0.0

        except Exception as e:
            logger.warning(f"文本方向检测失败: {e}")
            return 0.0

    def _basic_angle_detection(self, gray) -> float:
        """基础角度检测方法（回退方案）"""
        try:
            if cv2 is None or np is None:
                return 0.0

            # 简单的霍夫线检测
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)

            if lines is not None and len(lines) > 5:
                angles = []
                for line in lines:
                    rho, theta = line[0]
                    angle_deg = np.degrees(theta) - 90
                    if angle_deg > 45:
                        angle_deg -= 90
                    elif angle_deg < -45:
                        angle_deg += 90
                    angles.append(angle_deg)

                # 使用中位数作为代表角度
                import statistics
                median_angle = statistics.median(angles)
                logger.debug(f"基础检测角度: {median_angle:.2f}°")
                return median_angle

            return 0.0

        except Exception as e:
            logger.warning(f"基础角度检测失败: {e}")
            return 0.0

    def _detect_precise_angle_by_hough(self, gray) -> tuple:
        """使用精细霍夫线变换检测角度"""
        try:
            if cv2 is None or np is None:
                return 0.0, 0.0, "cv2或numpy未导入"

            # 多级预处理以增强线条检测
            # 1. 高斯模糊去噪
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)

            # 2. 自适应阈值二值化
            binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 15, 10)

            # 3. 形态学操作增强线条
            kernel_horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
            kernel_vertical = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))

            # 分别增强水平和垂直线条
            enhanced_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_horizontal)
            enhanced_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_vertical)
            enhanced = cv2.bitwise_or(enhanced_h, enhanced_v)

            # 4. 边缘检测
            edges = cv2.Canny(enhanced, 30, 100, apertureSize=3)

            # 5. 精细霍夫线变换（更高的角度分辨率）
            lines = cv2.HoughLines(edges, 1, np.pi/360, threshold=30)  # 0.5度精度

            if lines is not None and len(lines) >= 5:
                angle_data = []

                for line in lines:
                    rho, theta = line[0]
                    # 将theta转换为角度，范围[-90, 90]
                    angle_deg = np.degrees(theta) - 90

                    # 标准化角度到[-45, 45]范围
                    if angle_deg > 45:
                        angle_deg -= 90
                    elif angle_deg < -45:
                        angle_deg += 90

                    angle_data.append(angle_deg)

                if angle_data:
                    # 使用直方图分析找到主导角度
                    hist, bin_edges = np.histogram(angle_data, bins=180, range=(-45, 45))

                    # 平滑直方图
                    try:
                        from scipy import ndimage
                        smoothed_hist = ndimage.gaussian_filter1d(hist.astype(float), sigma=1.0)
                    except ImportError:
                        # 如果没有scipy，使用简单的移动平均
                        smoothed_hist = hist.astype(float)
                        for i in range(1, len(smoothed_hist)-1):
                            smoothed_hist[i] = (hist[i-1] + hist[i] + hist[i+1]) / 3.0

                    # 找到峰值
                    peak_idx = np.argmax(smoothed_hist)
                    peak_angle = bin_edges[peak_idx] + (bin_edges[1] - bin_edges[0]) / 2
                    peak_strength = smoothed_hist[peak_idx]

                    # 计算置信度
                    total_strength = np.sum(smoothed_hist)
                    confidence = peak_strength / total_strength if total_strength > 0 else 0

                    # 使用重心法进一步精细化角度
                    window_size = 5
                    start_idx = max(0, peak_idx - window_size)
                    end_idx = min(len(smoothed_hist), peak_idx + window_size + 1)

                    weights = smoothed_hist[start_idx:end_idx]
                    angles = bin_edges[start_idx:end_idx] + (bin_edges[1] - bin_edges[0]) / 2

                    if np.sum(weights) > 0:
                        refined_angle = np.average(angles, weights=weights)
                    else:
                        refined_angle = peak_angle

                    info = f"检测到{len(lines)}条线，主导角度{refined_angle:.2f}°，置信度{confidence:.3f}"

                    return refined_angle, confidence, info

            return 0.0, 0.0, f"检测到{len(lines) if lines is not None else 0}条线，不足以判断"

        except Exception as e:
            logger.warning(f"精细霍夫线变换角度检测失败: {e}")
            return 0.0, 0.0, f"检测失败: {str(e)}"

    def _detect_angle_by_pca(self, gray) -> tuple:
        """使用主成分分析检测文本方向"""
        try:
            # 二值化
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # 找到所有前景像素点
            coords = np.column_stack(np.where(binary > 0))

            if len(coords) < 100:  # 需要足够的点进行PCA
                return 0.0, 0.0, "前景像素点不足"

            # 随机采样减少计算量
            if len(coords) > 10000:
                indices = np.random.choice(len(coords), 10000, replace=False)
                coords = coords[indices]

            # 执行PCA
            try:
                from sklearn.decomposition import PCA
                pca = PCA(n_components=2)
                pca.fit(coords)
            except ImportError:
                return 0.0, 0.0, "sklearn未安装，无法使用PCA检测"

            # 获取主成分方向
            principal_component = pca.components_[0]

            # 计算角度
            angle_rad = np.arctan2(principal_component[1], principal_component[0])
            angle_deg = np.degrees(angle_rad)

            # 标准化角度到[-45, 45]范围
            if angle_deg > 45:
                angle_deg -= 90
            elif angle_deg < -45:
                angle_deg += 90

            # 计算置信度（基于方差比）
            explained_variance_ratio = pca.explained_variance_ratio_
            confidence = explained_variance_ratio[0] - explained_variance_ratio[1]
            confidence = max(0, min(1, confidence))  # 限制在[0,1]范围

            info = f"PCA分析{len(coords)}个点，第一主成分解释{explained_variance_ratio[0]:.3f}方差"

            return angle_deg, confidence, info

        except Exception as e:
            logger.warning(f"PCA角度检测失败: {e}")
            return 0.0, 0.0, f"PCA检测失败: {str(e)}"

    def _detect_angle_by_edge_direction(self, gray) -> tuple:
        """基于边缘方向的角度检测"""
        try:
            # Sobel梯度计算
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

            # 计算梯度幅值和方向
            magnitude = np.sqrt(grad_x**2 + grad_y**2)
            direction = np.arctan2(grad_y, grad_x)

            # 只保留强边缘
            threshold = np.percentile(magnitude, 85)
            strong_edges = magnitude > threshold

            if np.sum(strong_edges) < 100:
                return 0.0, 0.0, "强边缘点不足"

            # 获取强边缘的方向
            strong_directions = direction[strong_edges]

            # 将方向转换为角度（度）
            angles_deg = np.degrees(strong_directions)

            # 将角度映射到文本方向（垂直于边缘方向）
            text_angles = angles_deg + 90

            # 标准化到[-45, 45]范围
            text_angles = text_angles % 180
            text_angles[text_angles > 90] -= 180
            text_angles[text_angles > 45] -= 90
            text_angles[text_angles < -45] += 90

            # 使用直方图找到主导方向
            hist, bin_edges = np.histogram(text_angles, bins=180, range=(-45, 45))

            # 平滑直方图
            try:
                from scipy import ndimage
                smoothed_hist = ndimage.gaussian_filter1d(hist.astype(float), sigma=1.0)
            except ImportError:
                # 如果没有scipy，使用简单的移动平均
                smoothed_hist = hist.astype(float)
                for i in range(1, len(smoothed_hist)-1):
                    smoothed_hist[i] = (hist[i-1] + hist[i] + hist[i+1]) / 3.0

            # 找到峰值
            peak_idx = np.argmax(smoothed_hist)
            peak_angle = bin_edges[peak_idx] + (bin_edges[1] - bin_edges[0]) / 2
            peak_strength = smoothed_hist[peak_idx]

            # 计算置信度
            total_strength = np.sum(smoothed_hist)
            confidence = peak_strength / total_strength if total_strength > 0 else 0

            info = f"分析{np.sum(strong_edges)}个强边缘点，主导方向{peak_angle:.2f}°"

            return peak_angle, confidence, info

        except Exception as e:
            logger.warning(f"边缘方向角度检测失败: {e}")
            return 0.0, 0.0, f"边缘检测失败: {str(e)}"

    def _normalize_detected_angle(self, angle: float) -> float:
        """标准化检测到的角度"""
        try:
            # 限制角度在合理范围内
            angle = angle % 360

            # 转换到[-180, 180]范围
            if angle > 180:
                angle -= 360

            # 对于文档扫描，通常倾斜角度不会超过±45度
            # 如果角度太大，可能是检测错误
            if abs(angle) > 45:
                # 可能是90度的倍数 + 小角度
                if angle > 45 and angle < 135:
                    angle = 90 + (angle - 90)
                elif angle > 135 or angle < -135:
                    angle = 180 + (angle - 180) if angle > 0 else 180 + (angle + 180)
                elif angle < -45 and angle > -135:
                    angle = -90 + (angle + 90)

            # 最终限制在[-45, 45]范围，对于OCR来说这是合理的
            if angle > 45:
                angle = 45
            elif angle < -45:
                angle = -45

            return angle

        except Exception as e:
            logger.warning(f"角度标准化失败: {e}")
            return 0.0

    def _generate_angle_sequence(self, detected_angle: float) -> list:
        """生成智能的角度尝试序列"""
        try:
            angles_to_try = []

            # 1. 优先尝试检测到的精确角度
            if abs(detected_angle) > 0.1:  # 只有当检测角度有意义时才加入
                angles_to_try.append(detected_angle)

            # 2. 添加检测角度的精细调整
            if abs(detected_angle) > 0.5:
                # 对于较大的检测角度，尝试±0.5°的微调
                for delta in [-0.5, 0.5, -1.0, 1.0]:
                    adjusted_angle = detected_angle + delta
                    if abs(adjusted_angle) <= 45:  # 保持在合理范围内
                        angles_to_try.append(adjusted_angle)

            # 3. 总是包含0度（正常方向）
            if 0.0 not in angles_to_try:
                angles_to_try.append(0.0)

            # 4. 检查是否接近常见旋转角度
            common_angles = [90, 180, 270, -90, -180]
            for common_angle in common_angles:
                diff = abs(detected_angle - common_angle)
                if diff < 45:  # 如果检测角度接近某个常见角度
                    # 添加该常见角度及其微调
                    if common_angle not in angles_to_try:
                        angles_to_try.append(common_angle)

                    # 为常见角度添加精细调整
                    for delta in [-2, -1, -0.5, 0.5, 1, 2]:
                        adjusted = common_angle + delta
                        if adjusted not in angles_to_try and abs(adjusted) <= 180:
                            angles_to_try.append(adjusted)

            # 5. 添加其他可能的旋转角度（如果还没有包含）
            standard_angles = [0, 90, 180, 270, -90, -180]
            for angle in standard_angles:
                if angle not in angles_to_try:
                    angles_to_try.append(angle)

            # 6. 如果检测角度很小，添加一些小角度的系统性尝试
            if abs(detected_angle) < 5:
                small_angles = [-3, -2, -1, -0.5, 0.5, 1, 2, 3]
                for small_angle in small_angles:
                    if small_angle not in angles_to_try:
                        angles_to_try.append(small_angle)

            # 7. 去重并排序（保持检测角度优先）
            # 按与检测角度的接近程度排序
            def angle_priority(angle):
                if abs(angle - detected_angle) < 0.1:
                    return 0  # 检测角度本身最高优先级
                elif abs(angle) < 0.1:
                    return 1  # 0度次优先级
                else:
                    return abs(angle - detected_angle)  # 其他按接近程度排序

            # 去重
            unique_angles = []
            for angle in angles_to_try:
                # 检查是否已存在相近的角度
                is_duplicate = False
                for existing in unique_angles:
                    if abs(angle - existing) < 0.1:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique_angles.append(angle)

            # 排序
            unique_angles.sort(key=angle_priority)

            # 限制尝试次数（避免过度计算）
            max_attempts = 12
            final_angles = unique_angles[:max_attempts]

            return final_angles

        except Exception as e:
            logger.warning(f"生成角度序列失败: {e}")
            # 回退到基本序列
            return [0, detected_angle, 90, 270, 180] if abs(detected_angle) > 0.1 else [0, 90, 270, 180]

    def rotate_image(self, image, angle):
        """安全地旋转图像"""
        try:
            if angle == 0:
                return image

            # 获取图像尺寸
            height, width = image.shape[:2]
            center = (width // 2, height // 2)

            # 创建旋转矩阵
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

            # 计算新的边界框尺寸
            cos_val = np.abs(rotation_matrix[0, 0])
            sin_val = np.abs(rotation_matrix[0, 1])
            new_width = int((height * sin_val) + (width * cos_val))
            new_height = int((height * cos_val) + (width * sin_val))

            # 调整旋转矩阵的平移部分
            rotation_matrix[0, 2] += (new_width / 2) - center[0]
            rotation_matrix[1, 2] += (new_height / 2) - center[1]

            # 执行旋转
            rotated = cv2.warpAffine(image, rotation_matrix, (new_width, new_height),
                                   flags=cv2.INTER_CUBIC,
                                   borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(255, 255, 255))

            return rotated

        except Exception as e:
            logger.warning(f"图像旋转失败: {e}")
            return image

    def extract_with_ocr(self, pdf_path: str) -> Tuple[Optional[str], List[str]]:
        """使用OCR从PDF中提取文本并查找销货出库单号，包含改进的旋转检测"""
        log_messages = []

        if not lazy_import_ocr():
            return None, ["❌ OCR库导入失败"]

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]
                log_messages.append(f"📄 处理第{page_num + 1}页")

                # 提高分辨率以改善OCR效果
                mat = fitz.Matrix(2.0, 2.0)  # 200 DPI
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                pix = None

                # 转换为PIL图像
                pil_image = Image.open(io.BytesIO(img_data))

                # 限制图像大小以节省内存
                max_size = 1500
                if max(pil_image.size) > max_size:
                    ratio = max_size / max(pil_image.size)
                    new_size = tuple(int(dim * ratio) for dim in pil_image.size)
                    pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

                # 确保图像是RGB模式
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                # 转换为OpenCV格式
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

                # 精细角度检测
                detected_angle = self.detect_text_orientation(cv_image)
                log_messages.append(f"🔍 精细角度检测结果: {detected_angle:.2f}°")

                # 生成智能角度尝试序列，优先考虑大角度旋转
                angles_to_try = self._generate_angle_sequence(detected_angle)

                # 根据测试结果，优先尝试270°和90°（这些PDF可能需要大角度旋转）
                priority_angles = [270, 90, 0, 180]

                # 将优先角度放在前面，然后是检测到的精细角度
                final_angles = []
                for angle in priority_angles:
                    if angle not in final_angles:
                        final_angles.append(angle)

                # 添加检测到的精细角度
                for angle in angles_to_try:
                    if angle not in final_angles:
                        final_angles.append(angle)

                angles_to_try = final_angles
                log_messages.append(f"📐 角度尝试序列: {[f'{a:.1f}°' for a in angles_to_try[:8]]}...")

                # 如果检测角度较小，提前尝试精细校正
                if abs(detected_angle) < 0.5:
                    log_messages.append("💡 检测到微小倾斜，将重点尝试精细校正")

                for angle in angles_to_try:
                    try:
                        # 旋转图像
                        if angle != 0:
                            rotated_cv = self.rotate_image(cv_image, angle)
                            rotated_pil = Image.fromarray(cv2.cvtColor(rotated_cv, cv2.COLOR_BGR2RGB))
                        else:
                            rotated_pil = pil_image

                        # 智能区域识别优先策略
                        try:
                            from smart_region_ocr import smart_ocr

                            # 先尝试智能区域识别
                            smart_result, smart_logs = smart_ocr.smart_extract_order_number(rotated_pil)

                            # 添加智能识别日志
                            log_messages.extend(smart_logs)

                            if smart_result:
                                # 智能区域识别成功，验证结果
                                candidates = self.find_all_order_candidates(smart_result)
                                if candidates:
                                    best_candidate = candidates[0]
                                    order_number = best_candidate['number']
                                    log_messages.append(f"🎯 智能区域识别成功: {order_number} (置信度: {best_candidate['confidence']})")
                                    doc.close()
                                    return order_number, log_messages
                                else:
                                    log_messages.append(f"⚠️ 智能区域识别结果验证失败: {smart_result}")

                        except ImportError:
                            log_messages.append("⚠️ 智能区域识别模块未加载，使用传统方法")
                        except Exception as smart_error:
                            log_messages.append(f"⚠️ 智能区域识别失败: {smart_error}")

                        # 如果智能识别失败，回退到传统方法
                        log_messages.append("🔄 回退到传统全图OCR识别")

                        # 多层图像增强处理
                        enhanced_image = self._enhance_image_for_ocr(rotated_pil)

                        # PaddleOCR主力策略：PaddleOCR优先 + EasyOCR备用
                        easyocr_results = []
                        paddleocr_results = []
                        final_text = ""
                        ocr_method_used = ""

                        # 第一步：PaddleOCR主力识别
                        log_messages.append(f"🔥 第一步：PaddleOCR主力识别 (角度: {angle:.1f}°)...")
                        paddleocr_text, paddleocr_info = self._extract_text_with_paddleocr(enhanced_image)

                        paddleocr_found_candidates = False
                        if paddleocr_text and paddleocr_text.strip():
                            # 添加详细的OCR文本调试信息
                            log_messages.append(f"🔍 PaddleOCR识别文本: {paddleocr_text[:200]}...")

                            # 检查是否包含潜在的订单号候选
                            potential_orders = self.find_all_order_candidates(paddleocr_text)
                            if potential_orders:
                                paddleocr_results.append({
                                    'text': paddleocr_text,
                                    'info': paddleocr_info,
                                    'candidates': potential_orders
                                })
                                paddleocr_found_candidates = True
                                log_messages.append(f"✅ PaddleOCR找到{len(potential_orders)}个候选: {[c['number'] for c in potential_orders[:3]]}")

                                # PaddleOCR成功，直接使用结果
                                final_text = paddleocr_text
                                ocr_method_used = f"PaddleOCR主力识别 ({paddleocr_info})"
                            else:
                                # 显示为什么没有找到候选的详细信息
                                log_messages.append(f"⚠️ PaddleOCR识别到文本但无有效候选")
                                log_messages.append(f"📝 PaddleOCR完整文本: {paddleocr_text}")

                                # 检查是否包含关键词
                                keywords = ['销货', '出库', '单号', '订单', '编号']
                                found_keywords = [kw for kw in keywords if kw in paddleocr_text]
                                if found_keywords:
                                    log_messages.append(f"💡 PaddleOCR发现关键词: {found_keywords}")

                                # 检查是否包含数字模式
                                import re
                                number_patterns = re.findall(r'\d{3,}[-_]?\d*', paddleocr_text)
                                if number_patterns:
                                    log_messages.append(f"🔢 PaddleOCR发现数字模式: {number_patterns[:5]}")
                        else:
                            log_messages.append(f"⚠️ PaddleOCR未识别到有效文本")

                        # 第二步：如果PaddleOCR失败，使用EasyOCR备用
                        if not paddleocr_found_candidates:
                            log_messages.append(f"⚡ 第二步：PaddleOCR无候选，EasyOCR备用识别...")
                            easyocr_text, easyocr_info = self._extract_text_with_easyocr(enhanced_image)

                            if easyocr_text and easyocr_text.strip():
                                # 添加EasyOCR的调试信息
                                log_messages.append(f"🔍 EasyOCR备用识别文本: {easyocr_text[:200]}...")

                                # 检查EasyOCR的候选
                                easyocr_candidates = self.find_all_order_candidates(easyocr_text)
                                if easyocr_candidates:
                                    easyocr_results.append({
                                        'text': easyocr_text,
                                        'info': easyocr_info,
                                        'candidates': easyocr_candidates
                                    })
                                    final_text = easyocr_text
                                    ocr_method_used = f"EasyOCR备用识别 ({easyocr_info})"
                                    log_messages.append(f"✅ EasyOCR找到{len(easyocr_candidates)}个候选: {[c['number'] for c in easyocr_candidates[:3]]}")
                                else:
                                    final_text = easyocr_text
                                    ocr_method_used = f"EasyOCR备用识别 ({easyocr_info})"
                                    log_messages.append(f"⚠️ EasyOCR识别到文本但无有效候选")
                                    log_messages.append(f"📝 EasyOCR完整文本: {easyocr_text}")

                                    # 检查是否包含关键词
                                    keywords = ['销货', '出库', '单号', '订单', '编号']
                                    found_keywords = [kw for kw in keywords if kw in easyocr_text]
                                    if found_keywords:
                                        log_messages.append(f"💡 EasyOCR发现关键词: {found_keywords}")

                                    # 检查是否包含数字模式
                                    import re
                                    number_patterns = re.findall(r'\d{3,}[-_]?\d*', easyocr_text)
                                    if number_patterns:
                                        log_messages.append(f"🔢 EasyOCR发现数字模式: {number_patterns[:5]}")
                            else:
                                log_messages.append(f"❌ PaddleOCR和EasyOCR均未识别到有效文本")
                        else:
                            log_messages.append(f"🎯 PaddleOCR主力识别成功，跳过EasyOCR备用")

                        text = final_text

                        if text.strip():
                            # 应用数字错误纠正
                            corrected_text = text
                            try:
                                from digit_enhancement import digit_enhancer
                                corrected_text = digit_enhancer.correct_common_digit_errors(text)
                                if corrected_text != text:
                                    log_messages.append(f"🔧 应用数字纠正: {repr(text[:100])} -> {repr(corrected_text[:100])}")
                            except ImportError:
                                log_messages.append("⚠️ 数字增强模块未加载")
                            except Exception as correction_error:
                                log_messages.append(f"⚠️ 数字纠正失败: {correction_error}")

                            log_messages.append(f"📝 使用{ocr_method_used}识别文本片段: {corrected_text[:150]}...")

                            # 查找销货出库单号（使用纠正后的文本）
                            candidates = self.find_all_order_candidates(corrected_text)
                            if candidates:
                                best_candidate = candidates[0]  # 已按置信度排序
                                order_number = best_candidate['number']

                                # 检查是否为严格格式（4位-12位）
                                if self._validate_strict_format(order_number):
                                    log_messages.append(f"✅ 找到标准格式销货出库单号: {order_number} (使用{ocr_method_used}，置信度: {best_candidate['confidence']})")
                                    doc.close()
                                    return order_number, log_messages
                                else:
                                    # 非严格格式，记录但继续尝试其他角度
                                    log_messages.append(f"⚠️ 找到非标准格式订单号: {order_number} (不符合4位-12位格式，继续尝试其他角度)")
                                    # 可以选择在最后回退到这个结果
                                    if not hasattr(self, '_fallback_candidate'):
                                        self._fallback_candidate = (order_number, log_messages.copy())
                        else:
                            log_messages.append(f"⚠️ 角度{angle:.1f}°所有OCR方法都未识别到文本")

                    except Exception as e:
                        log_messages.append(f"⚠️ 角度{angle:.1f}°处理失败: {str(e)}")
                        continue

            doc.close()

            # 如果没有找到严格格式，但有非标准格式的候选，作为最后的回退
            if hasattr(self, '_fallback_candidate'):
                fallback_number, fallback_logs = self._fallback_candidate
                delattr(self, '_fallback_candidate')  # 清理临时属性
                log_messages.append(f"🔄 回退到非标准格式结果: {fallback_number} (格式不完全符合4位-12位要求)")
                return fallback_number, log_messages

            log_messages.append("❌ 所有页面和角度都未找到销货出库单号")
            return None, log_messages

        except Exception as e:
            error_msg = f"❌ OCR处理失败: {str(e)}"
            log_messages.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None, log_messages

    def clean_filename(self, order_number: str) -> str:
        """清理文件名，移除特殊字符"""
        try:
            # 移除文件名中的非法字符
            cleaned = re.sub(r'[<>:"/\\|?*]', '_', order_number)
            # 移除首尾空格
            cleaned = cleaned.strip()
            # 确保不为空
            if not cleaned:
                cleaned = "unknown_order"
            return cleaned
        except Exception as e:
            logger.error(f"文件名清理失败: {e}")
            return "unknown_order"

processor = PDFProcessor()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico")
async def favicon():
    """提供favicon.ico，避免404错误"""
    # 返回一个简单的SVG图标
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" fill="#ff6b9d"/>
        <text x="50" y="65" text-anchor="middle" font-size="60" fill="white">📄</text>
    </svg>"""

    from fastapi.responses import Response
    return Response(content=svg_content, media_type="image/svg+xml")

def create_backup(file_path: str, original_filename: str) -> str:
    """创建文件备份"""
    try:
        from datetime import datetime
        import shutil

        # 创建日期文件夹
        today = datetime.now().strftime("%Y-%m-%d")
        backup_dir = Path(f"backup/{today}")
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 生成备份文件路径
        backup_path = backup_dir / original_filename

        # 如果备份文件已存在，添加时间戳
        if backup_path.exists():
            timestamp = datetime.now().strftime("%H%M%S")
            name_part = backup_path.stem
            ext_part = backup_path.suffix
            backup_path = backup_dir / f"{name_part}_{timestamp}{ext_part}"

        # 复制文件到备份目录
        shutil.copy2(file_path, backup_path)

        logger.info(f"📂 备份创建成功: {backup_path}")
        return str(backup_path)

    except Exception as e:
        logger.error(f"备份创建失败: {e}")
        raise

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), enableBackup: str = "true"):
    """上传文件并提取销货出库单号进行重命名"""
    global filename_mapping

    # 开始处理前清理downloads文件夹中的所有文件
    cleaned_count = clean_all_downloads()
    if cleaned_count > 0:
        logger.info(f"🧹 处理开始前清理了 {cleaned_count} 个文件（包括上次处理的文件和调试文件）")
    else:
        logger.info("🧹 downloads文件夹为空，无需清理")

    # 记录处理开始时downloads目录状态
    downloads_dir = Path("downloads")
    if downloads_dir.exists():
        existing_files = list(downloads_dir.glob("*.pdf"))
        logger.info(f"📊 批次处理开始 - downloads目录现有文件: {len(existing_files)}个")
        for existing_file in existing_files:
            logger.info(f"  已存在: {existing_file.name}")
    else:
        logger.info(f"📊 批次处理开始 - downloads目录不存在")

    if not files:
        raise HTTPException(status_code=400, detail="没有上传文件")

    processor = PDFProcessor()
    results = []
    processed_count = 0
    backup_enabled = enableBackup.lower() == "true"

    logger.info(f"处理模式: {'启用备份' if backup_enabled else '禁用备份'}")

    for file in files:
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            results.append({
                "filename": file.filename or "unknown",
                "success": False,
                "message": "❌ 不是PDF文件"
            })
            continue

        upload_path = None
        try:
            # 处理文件名，去除路径信息（文件夹上传时的路径）
            clean_filename = os.path.basename(file.filename) if file.filename else "unknown.pdf"

            # 保存上传的文件到uploads根目录
            upload_path = f"uploads/{clean_filename}"

            # 如果文件已存在，添加时间戳避免冲突
            if os.path.exists(upload_path):
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_part = os.path.splitext(clean_filename)[0]
                ext_part = os.path.splitext(clean_filename)[1]
                upload_path = f"uploads/{name_part}_{timestamp}{ext_part}"

            with open(upload_path, "wb") as buffer:
                content = await file.read()
                if not content:
                    raise ValueError("文件内容为空")
                buffer.write(content)

            logger.info(f"开始处理文件: {file.filename} -> {clean_filename}")

            # 处理PDF文件
            order_number, log = processor.extract_order_number(upload_path)

            if order_number:
                # 清理文件名
                clean_order = processor.clean_filename(order_number)
                new_filename = f"{clean_order}.pdf"

                # 根据备份模式决定是否创建备份
                backup_path = "未启用备份"
                if backup_enabled:
                    # 使用原始文件名进行备份，保持文件夹结构信息
                    backup_filename = file.filename if file.filename else clean_filename
                    backup_path = create_backup(upload_path, backup_filename)

                # 处理重名文件 - 确保downloads目录存在
                os.makedirs("downloads", exist_ok=True)
                counter = 1
                base_name = clean_order
                final_filename = new_filename

                # 加强文件名冲突检测 - 查找整个downloads目录，不仅检查文件存在性还考虑处理队列中的其他文件
                existing_downloads = set(os.path.basename(f) for f in glob.glob("downloads/*.pdf"))
                in_process_names = set()  # 跟踪当前批次中已使用的文件名

                # 检查results中是否已有相同文件名（在当前批次中）
                for result in results:
                    if result.get("new_filename"):
                        in_process_names.add(result["new_filename"])

                logger.info(f"文件名检查 - 基础名称: {base_name}, 初始文件名: {final_filename}")
                logger.info(f"已存在的下载文件: {len(existing_downloads)}个, 当前批次中已使用名称: {len(in_process_names)}个")

                # 确保文件名不冲突
                while final_filename in existing_downloads or final_filename in in_process_names:
                    counter += 1
                    final_filename = f"{base_name}_{counter}.pdf"
                    logger.info(f"文件名冲突，尝试新名称: {final_filename}")

                # 存储文件名映射关系 - 重命名后到原始文件名的映射
                original_filename = os.path.basename(upload_path)
                filename_mapping[final_filename] = original_filename

                # 创建重命名副本到downloads文件夹 - 增强文件操作稳定性
                download_path = f"downloads/{final_filename}"
                try:
                    import shutil
                    import time

                    # 确保downloads目录存在且可写
                    downloads_dir = Path("downloads")
                    downloads_dir.mkdir(exist_ok=True)

                    # 多次尝试文件复制，提高成功率
                    copy_success = False
                    max_copy_attempts = 3

                    for attempt in range(max_copy_attempts):
                        try:
                            # 复制文件前额外检查
                            if not os.path.exists(upload_path) or os.path.getsize(upload_path) == 0:
                                raise Exception(f"源文件无效或大小为0: {upload_path}")

                            # 复制前检查目标是否已存在（双重检查）
                            if os.path.exists(download_path):
                                logger.warning(f"目标文件已存在，将被覆盖: {download_path}")
                                # 添加额外的安全保障 - 重命名已存在的文件而不是覆盖
                                backup_filename = f"{download_path}.bak.{int(time.time())}"
                                os.rename(download_path, backup_filename)
                                logger.info(f"已存在的文件已备份为: {backup_filename}")

                            # 复制文件
                            shutil.copy2(upload_path, download_path)

                            # 验证文件完整性
                            if os.path.exists(download_path) and os.path.getsize(download_path) > 0:
                                # 额外验证：检查文件大小是否一致
                                if os.path.getsize(upload_path) == os.path.getsize(download_path):
                                    # 文件内容验证
                                    with open(upload_path, "rb") as src_file:
                                        src_data = src_file.read(1024)  # 读取前1KB做完整性验证
                                    with open(download_path, "rb") as dst_file:
                                        dst_data = dst_file.read(1024)

                                    if src_data == dst_data:
                                        copy_success = True
                                        logger.info(f"文件已成功保存到下载目录: {download_path} (尝试{attempt+1}/{max_copy_attempts})")

                                        # 额外检查文件是否真实存在（防止NFS缓存等问题）
                                        time.sleep(0.1)  # 短暂等待文件系统同步
                                        if os.path.exists(download_path):
                                            logger.info(f"文件确认存在: {download_path}, 大小: {os.path.getsize(download_path)}字节")
                                        else:
                                            raise Exception("文件系统同步后文件不存在")

                                        break
                                    else:
                                        raise Exception("文件内容验证失败，可能复制不完整")
                                else:
                                    raise Exception("文件大小不一致，可能复制不完整")
                            else:
                                raise Exception("文件复制后不存在或大小为0")

                        except Exception as attempt_error:
                            logger.warning(f"文件复制尝试{attempt+1}失败: {attempt_error}")
                            # 清理可能的不完整文件
                            if os.path.exists(download_path):
                                try:
                                    os.remove(download_path)
                                    logger.info(f"已清理不完整文件: {download_path}")
                                except:
                                    logger.warning(f"清理不完整文件失败: {download_path}")

                            if attempt < max_copy_attempts - 1:
                                time.sleep(0.5 * (attempt + 1))  # 递增等待时间后重试
                                logger.info(f"将在{0.5 * (attempt + 1)}秒后重试")
                            else:
                                raise attempt_error

                    if not copy_success:
                        raise Exception(f"经过{max_copy_attempts}次尝试，文件复制仍然失败")

                    # 安全删除uploads中的临时文件
                    if os.path.exists(upload_path):
                        try:
                            os.remove(upload_path)
                            logger.info(f"临时文件已删除: {upload_path}")
                        except Exception as del_error:
                            logger.warning(f"删除临时文件失败（但不影响主流程）: {del_error}")

                except Exception as copy_error:
                    logger.error(f"文件操作失败: {copy_error}")
                    # 尝试清理可能的不完整文件
                    if os.path.exists(download_path):
                        try:
                            os.remove(download_path)
                        except:
                            pass
                    raise Exception(f"保存文件失败: {copy_error}")

                results.append({
                    "filename": file.filename,
                    "success": True,
                    "message": f"✅ 文件处理成功: {file.filename} → {final_filename}",
                    "new_filename": final_filename,
                    "backup_path": backup_path,
                    "order_number": order_number,
                    "log": log,
                    "download_ready": True
                })

                logger.info(f"文件处理成功: {file.filename} -> {final_filename}")
                processed_count += 1

            else:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": "❌ 未找到销货出库单号",
                    "log": log
                })

                logger.warning(f"未找到销货出库单号: {file.filename}")

        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            results.append({
                "filename": file.filename or "unknown",
                "success": False,
                "message": f"❌ {error_msg}",
                "log": f"系统错误: {str(e)}"
            })
            logger.error(f"文件处理失败 {file.filename}: {error_msg}", exc_info=True)

        finally:
            # 清理uploads中的临时文件
            if upload_path and os.path.exists(upload_path) and upload_path.startswith("uploads/"):
                try:
                    os.remove(upload_path)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")

            # 强制垃圾回收
            import gc
            gc.collect()

    logger.info(f"批量处理完成，成功处理 {processed_count} 个文件")

    # 记录处理结束时downloads目录状态
    if downloads_dir.exists():
        final_files = list(downloads_dir.glob("*.pdf"))
        logger.info(f"📊 批次处理结束 - downloads目录现有文件: {len(final_files)}个")
        for final_file in final_files:
            logger.info(f"  最终存在: {final_file.name}")
    else:
        logger.info(f"📊 批次处理结束 - downloads目录不存在")

    # 生成处理信息
    process_info = None
    if processed_count > 0:
        from datetime import datetime
        download_info = f"📥 处理完成，{processed_count} 个文件可供下载"
        if backup_enabled:
            backup_info = f"备份保存在: backup/{datetime.now().strftime('%Y-%m-%d')}/"
            process_info = f"{download_info}，{backup_info}"
        else:
            process_info = download_info

    return JSONResponse({
        "results": results,
        "processed_count": processed_count,
        "total_count": len(files),
        "process_info": process_info,
        "download_available": processed_count > 0
    })

@app.get("/backup-info")
async def get_backup_info():
    """获取备份信息"""
    try:
        backup_root = Path("backup")
        if not backup_root.exists():
            return JSONResponse({
                "backup_folders": [],
                "total_backups": 0,
                "message": "暂无备份文件"
            })

        backup_folders = []
        total_backups = 0

        # 获取所有日期文件夹
        for date_folder in sorted(backup_root.iterdir(), reverse=True):
            if date_folder.is_dir():
                pdf_files = list(date_folder.glob("*.pdf"))
                if pdf_files:
                    backup_folders.append({
                        "date": date_folder.name,
                        "file_count": len(pdf_files),
                        "files": [f.name for f in pdf_files]
                    })
                    total_backups += len(pdf_files)

        return JSONResponse({
            "backup_folders": backup_folders,
            "total_backups": total_backups,
            "message": f"共有 {len(backup_folders)} 天的备份，总计 {total_backups} 个文件"
        })

    except Exception as e:
        logger.error(f"获取备份信息失败: {e}")
        return JSONResponse({
            "backup_folders": [],
            "total_backups": 0,
            "message": f"获取备份信息失败: {str(e)}"
        })

@app.get("/download-list")
async def get_download_list():
    """获取可下载文件列表"""
    downloads_dir = Path("downloads")
    files = []

    try:
        if downloads_dir.exists():
            pdf_files = list(downloads_dir.glob("*.pdf"))

            # 查找所有下载文件，优先使用重命名后文件名
            renamed_files = []
            for file in pdf_files:
                # 检查此文件是否是重命名后的文件（通过检查命名模式）
                if "-" in file.stem and file.stem.count("-") == 1:
                    renamed_files.append(file.name)
                else:
                    # 对于原始文件名格式，查找是否有对应的重命名映射
                    found = False
                    for renamed, original in filename_mapping.items():
                        if file.name == original:
                            renamed_files.append(renamed)
                            found = True
                            break
                    if not found:
                        # 如果没有映射关系，直接使用原始文件名
                        renamed_files.append(file.name)

            files = renamed_files
            logger.info(f"下载目录检查: 找到 {len(files)} 个PDF文件")

            # 详细日志
            for file in files:
                logger.info(f"  - {file}")
        else:
            logger.warning("下载目录不存在")

        return JSONResponse({
            "files": files,
            "count": len(files),
            "message": f"找到 {len(files)} 个可下载文件",
            "downloads_dir": str(downloads_dir),
            "dir_exists": downloads_dir.exists()
        })
    except Exception as e:
        logger.error(f"获取下载列表失败: {e}")
        return JSONResponse({
            "files": [],
            "count": 0,
            "message": f"获取文件列表失败: {str(e)}",
            "error": str(e)
        })

@app.get("/download/{filename}")
async def download_single_file(filename: str):
    """下载单个文件"""
    try:
        downloads_dir = Path("downloads")

        # 检查是否需要文件名映射
        actual_filename = filename
        mapped_original = None

        # 尝试从映射中查找对应的原始文件名
        if filename in filename_mapping:
            mapped_original = filename_mapping[filename]
            logger.info(f"文件名映射: {filename} -> {mapped_original}")

        # 先尝试直接查找重命名后的文件
        file_path = downloads_dir / filename
        if not file_path.exists() and mapped_original:
            # 如果重命名后的文件不存在，尝试查找原始文件
            file_path = downloads_dir / mapped_original
            actual_filename = mapped_original
            logger.info(f"使用原始文件名路径: {file_path}")

        # 如果还是找不到，尝试查找可能匹配的文件
        if not file_path.exists():
            logger.info(f"尝试查找匹配的文件，原始名称: {filename}")
            # 尝试找到含有相似命名的文件
            matching_files = []

            for potential_file in downloads_dir.glob("*.pdf"):
                # 1. 尝试原始文件名中包含订单号的部分
                if "-" in filename:
                    order_number = filename.split("-")[1].replace(".pdf", "")
                    if order_number in potential_file.name:
                        matching_files.append(potential_file)
                        logger.info(f"找到订单号匹配文件: {potential_file.name} (包含 {order_number})")

                # 2. 尝试匹配前缀部分
                if filename.startswith(potential_file.stem[:5]):
                    matching_files.append(potential_file)
                    logger.info(f"找到前缀匹配文件: {potential_file.name}")

            # 如果有匹配的文件，使用第一个
            if matching_files:
                file_path = matching_files[0]
                actual_filename = file_path.name
                logger.info(f"使用最佳匹配文件: {file_path}")

        # 详细日志记录
        logger.info(f"请求下载文件: {filename} -> 实际文件名: {actual_filename}")
        logger.info(f"寻找路径: {file_path}")

        # 安全性检查：确保文件名不包含路径遍历攻击
        if ".." in filename or "/" in filename or "\\" in filename:
            logger.warning(f"下载请求包含无效的文件名: {filename}")
            raise HTTPException(status_code=400, detail="无效的文件名 (包含非法字符)")

        # 检查文件是否存在
        if not downloads_dir.exists():
            logger.warning(f"下载目录不存在: {downloads_dir}")
            raise HTTPException(
                status_code=404,
                detail=f"下载目录不存在，请先处理文件或使用修复功能"
            )

        if not file_path.exists():
            logger.warning(f"请求的文件不存在: {file_path}")

            # 查找所有可用文件
            available_files = list(downloads_dir.glob("*.pdf"))
            available_names = [f.name for f in available_files]

            detail_msg = f"文件 '{filename}' 不存在"
            if available_files:
                detail_msg += f"。可用文件: {', '.join(available_names[:5])}"
                if len(available_names) > 5:
                    detail_msg += f" 等共 {len(available_names)} 个文件"

            raise HTTPException(status_code=404, detail=detail_msg)

        if not file_path.is_file():
            logger.warning(f"路径存在但不是文件: {file_path}")
            raise HTTPException(status_code=404, detail=f"'{filename}' 不是一个文件")

        # 检查文件类型
        if not file_path.name.lower().endswith('.pdf'):
            logger.warning(f"请求下载非PDF文件: {file_path.name}")
            raise HTTPException(status_code=400, detail="只支持下载PDF文件")

        # 检查文件大小
        file_size = file_path.stat().st_size
        if file_size == 0:
            logger.warning(f"文件大小为0: {file_path}")
            raise HTTPException(status_code=400, detail="文件大小为0，可能已损坏")

        logger.info(f"单个文件下载成功: {filename} -> {file_path.name}, 大小: {file_size} 字节")

        # 设置响应头确保浏览器直接下载而不是预览
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }

        # 返回实际找到的文件，但保持用户请求的下载文件名
        # 强制浏览器下载而不是预览，使用正确的头部信息
        headers.update({
            "Content-Type": "application/octet-stream",  # 使用通用二进制流类型强制下载
            "X-Content-Type-Options": "nosniff"          # 防止浏览器猜测内容类型
        })
        return FileResponse(
            file_path,
            filename=filename,  # 使用用户请求的文件名作为下载名称
            media_type="application/octet-stream",  # 优先使用通用类型强制下载
            headers=headers
        )

    except HTTPException:
        # 继续抛出HTTP异常
        raise
    except Exception as e:
        # 捕获其他异常并记录
        logger.error(f"下载文件时发生未预期错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载文件时发生错误: {str(e)}")

@app.post("/download-all")
async def download_all():
    """批量下载所有重命名文件（ZIP格式）- 兼容旧接口，重定向到新的ZIP创建方式"""
    try:
        # 直接调用新的ZIP创建接口
        return await create_zip_all()
    except Exception as e:
        logger.error(f"ZIP下载失败，回退到直接响应: {e}")
        # 如果新方式失败，回退到原来的直接响应方式
        downloads_dir = Path("downloads")
        if not downloads_dir.exists() or not list(downloads_dir.glob("*.pdf")):
            raise HTTPException(status_code=404, detail="没有可下载的文件")

        pdf_files = list(downloads_dir.glob("*.pdf"))
        
        from datetime import datetime
        zip_filename = f"renamed_pdfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = f"temp_{zip_filename}"

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for pdf_file in pdf_files:
                    zipf.write(pdf_file, pdf_file.name)

            zip_size = os.path.getsize(zip_path)

            def cleanup_zip():
                try:
                    os.remove(zip_path)
                except:
                    pass

            headers = {
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Content-Type": "application/zip",
                "Content-Length": str(zip_size),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Accept-Ranges": "bytes"
            }

            return FileResponse(
                zip_path,
                filename=zip_filename,
                media_type="application/zip",
                headers=headers,
                background=BackgroundTask(cleanup_zip)
            )

        except Exception as e2:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise HTTPException(status_code=500, detail=f"创建下载文件失败: {str(e2)}")

@app.post("/download-selected")
async def download_selected(filenames: List[str]):
    """选择性下载指定文件（ZIP格式）- 兼容旧接口，重定向到新的ZIP创建方式"""
    try:
        # 直接调用新的ZIP创建接口
        return await create_zip_selected(filenames)
    except Exception as e:
        logger.error(f"选择性ZIP下载失败，回退到直接响应: {e}")
        # 回退到原来的方式（保持兼容性）
        if not filenames:
            raise HTTPException(status_code=400, detail="没有选择文件")

        downloads_dir = Path("downloads")
        existing_files = []
        for filename in filenames:
            file_path = downloads_dir / filename
            if file_path.exists() and file_path.suffix.lower() == '.pdf':
                existing_files.append(file_path)

        if not existing_files:
            raise HTTPException(status_code=404, detail="选择的文件都不存在")

        from datetime import datetime
        zip_filename = f"selected_pdfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = f"temp_{zip_filename}"

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for pdf_file in existing_files:
                    zipf.write(pdf_file, pdf_file.name)

            zip_size = os.path.getsize(zip_path)

            def cleanup_zip():
                try:
                    os.remove(zip_path)
                except:
                    pass

            headers = {
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Content-Type": "application/zip",
                "Content-Length": str(zip_size),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Accept-Ranges": "bytes"
            }

            return FileResponse(
                zip_path,
                filename=zip_filename,
                media_type="application/zip",
                headers=headers,
                background=BackgroundTask(cleanup_zip)
            )

        except Exception as e2:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise HTTPException(status_code=500, detail=f"创建下载文件失败: {str(e2)}")

@app.post("/download-direct-all")
async def download_direct_all():
    """批量直接下载所有PDF文件（不打包）- 返回文件列表供前端逐个下载"""
    downloads_dir = Path("downloads")

    if not downloads_dir.exists() or not list(downloads_dir.glob("*.pdf")):
        raise HTTPException(status_code=404, detail="没有可下载的文件")

    pdf_files = list(downloads_dir.glob("*.pdf"))
    
    # 返回文件信息列表
    file_list = []
    total_size = 0
    
    for pdf_file in pdf_files:
        file_size = pdf_file.stat().st_size
        total_size += file_size
        file_list.append({
            "filename": pdf_file.name,
            "size": file_size,
            "size_mb": round(file_size / 1024 / 1024, 2),
            "download_url": f"/download/{pdf_file.name}"
        })
    
    logger.info(f"准备批量直接下载: {len(pdf_files)} 个文件, 总大小: {round(total_size / 1024 / 1024, 2)}MB")
    
    return JSONResponse({
        "success": True,
        "files": file_list,
        "total_files": len(pdf_files),
        "total_size": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2)
    })

@app.post("/download-direct-selected")
async def download_direct_selected(filenames: List[str]):
    """批量直接下载选定的PDF文件（不打包）- 返回文件列表供前端逐个下载"""
    if not filenames:
        raise HTTPException(status_code=400, detail="没有选择文件")

    downloads_dir = Path("downloads")

    # 验证文件是否存在
    existing_files = []
    for filename in filenames:
        file_path = downloads_dir / filename
        if file_path.exists() and file_path.suffix.lower() == '.pdf':
            existing_files.append(file_path)

    if not existing_files:
        raise HTTPException(status_code=404, detail="选择的文件都不存在")

    # 返回文件信息列表
    file_list = []
    total_size = 0
    
    for pdf_file in existing_files:
        file_size = pdf_file.stat().st_size
        total_size += file_size
        file_list.append({
            "filename": pdf_file.name,
            "size": file_size,
            "size_mb": round(file_size / 1024 / 1024, 2),
            "download_url": f"/download/{pdf_file.name}"
        })
    
    logger.info(f"准备批量直接下载选定文件: {len(existing_files)} 个文件, 总大小: {round(total_size / 1024 / 1024, 2)}MB")
    
    return JSONResponse({
        "success": True,
        "files": file_list,
        "total_files": len(existing_files),
        "total_size": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2)
    })

@app.get("/debug-downloads")
async def debug_downloads():
    """调试下载目录 - 详细信息"""
    downloads_dir = Path("downloads")

    try:
        debug_info = {
            "downloads_dir": str(downloads_dir.absolute()),
            "dir_exists": downloads_dir.exists(),
            "is_directory": downloads_dir.is_dir() if downloads_dir.exists() else False,
            "permissions": oct(downloads_dir.stat().st_mode)[-3:] if downloads_dir.exists() else "N/A",
            "all_files": [],
            "pdf_files": [],
            "file_sizes": {},
            "total_files": 0,
            "total_size": 0
        }

        if downloads_dir.exists():
            # 获取所有文件
            all_files = list(downloads_dir.iterdir())
            debug_info["all_files"] = [f.name for f in all_files if f.is_file()]

            # 获取PDF文件
            pdf_files = list(downloads_dir.glob("*.pdf"))
            debug_info["pdf_files"] = [f.name for f in pdf_files]

            # 文件大小信息
            for file in pdf_files:
                size = file.stat().st_size
                debug_info["file_sizes"][file.name] = {
                    "size_bytes": size,
                    "size_mb": round(size / 1024 / 1024, 2),
                    "modified": file.stat().st_mtime
                }
                debug_info["total_size"] += size

            debug_info["total_files"] = len(pdf_files)

        logger.info(f"调试下载目录: {debug_info}")
        return JSONResponse(debug_info)

    except Exception as e:
        logger.error(f"调试下载目录失败: {e}")
        return JSONResponse({
            "error": str(e),
            "downloads_dir": str(downloads_dir),
            "dir_exists": False
        })

@app.post("/auto-fix")
async def auto_fix_uploads():
    """自动修复：将uploads中遗留的处理好的PDF文件移动到downloads目录，并从备份目录恢复缺失文件"""
    uploads_dir = Path("uploads")
    downloads_dir = Path("downloads")
    backup_dir = Path("backup")

    # 确保downloads目录存在
    downloads_dir.mkdir(exist_ok=True)

    fixed_count = 0
    backup_files_added = 0
    results = []

    # 第一步：检查uploads中的文件
    if uploads_dir.exists():
        pdf_files = list(uploads_dir.glob("*.pdf"))

        for file in pdf_files:
            try:
                # 检查文件名是否是处理后的格式（包含-的销货单号）
                if "-" in file.stem and (file.stem.count("-") == 1):
                    # 这是一个处理后的文件，应该移动到downloads
                    destination = downloads_dir / file.name

                    # 处理重名情况
                    counter = 1
                    original_stem = file.stem
                    original_suffix = file.suffix
                    while destination.exists():
                        new_name = f"{original_stem}_{counter}{original_suffix}"
                        destination = downloads_dir / new_name
                        counter += 1

                    # 移动文件
                    import shutil
                    shutil.copy2(str(file), str(destination))

                    fixed_count += 1
                    results.append({
                        "original": file.name,
                        "moved_to": destination.name,
                        "success": True
                    })
                    logger.info(f"自动修复: {file.name} -> {destination.name}")

                else:
                    # 保留未处理的文件
                    results.append({
                        "original": file.name,
                        "moved_to": None,
                        "success": False,
                        "reason": "非处理后文件，保留在uploads"
                    })

            except Exception as e:
                results.append({
                    "original": file.name,
                    "moved_to": None,
                    "success": False,
                    "reason": f"移动失败: {str(e)}"
                })
                logger.error(f"自动修复失败 {file.name}: {e}")

    # 第二步：从备份目录复制文件到downloads
    backup_date_dirs = []
    if backup_dir.exists():
        backup_date_dirs = [d for d in backup_dir.iterdir() if d.is_dir()]
        # 按日期倒序排列，确保使用最新的备份
        backup_date_dirs.sort(reverse=True)

    for date_dir in backup_date_dirs:
        logger.info(f"检查备份目录: {date_dir}")
        backup_files = list(date_dir.glob("*.pdf"))

        for backup_file in backup_files:
            try:
                # 尝试从原始文件恢复处理后文件
                if "-" in backup_file.stem and backup_file.stem.count("-") == 1:
                    # 这是一个处理后的文件名格式 (如1403-20250110...)
                    destination = downloads_dir / backup_file.name

                    if not destination.exists():
                        import shutil
                        shutil.copy2(str(backup_file), str(destination))
                        backup_files_added += 1
                        results.append({
                            "original": backup_file.name,
                            "moved_to": backup_file.name,
                            "success": True,
                            "source": "backup-direct-processed"
                        })
                        logger.info(f"从备份恢复处理后文件: {backup_file.name}")
            except Exception as e:
                logger.error(f"从备份恢复失败 {backup_file.name}: {e}")

    # 第三步：如果还是没有文件，从备份复制重命名格式的PDF文件（排除原始文件名格式）
    if backup_files_added == 0 and fixed_count == 0 and backup_date_dirs:
        latest_backup = backup_date_dirs[0]
        logger.info(f"尝试从最新备份目录复制重命名文件: {latest_backup}")

        import re
        # 只复制重命名格式的文件（包含-或_的销货单号格式）
        renamed_pattern = re.compile(r'^[0-9]{4}[-_][0-9]{8,}.*\.pdf$')
        original_pattern = re.compile(r'^\d{17}_\d{4}.*\.pdf$')  # 排除原始文件名格式

        for backup_file in latest_backup.glob("*.pdf"):
            try:
                # 检查是否是重命名格式的文件，排除原始文件名格式
                if (renamed_pattern.match(backup_file.name) and
                    not original_pattern.match(backup_file.name)):

                    destination = downloads_dir / backup_file.name
                    if not destination.exists():
                        import shutil
                        shutil.copy2(str(backup_file), str(destination))
                        backup_files_added += 1
                        results.append({
                            "original": backup_file.name,
                            "moved_to": backup_file.name,
                            "success": True,
                            "source": "backup-renamed-only"
                        })
                        logger.info(f"从备份复制重命名文件: {backup_file.name}")
                    else:
                        logger.info(f"跳过已存在的文件: {backup_file.name}")
                else:
                    logger.debug(f"跳过原始文件名格式: {backup_file.name}")
            except Exception as e:
                logger.error(f"从备份复制失败 {backup_file.name}: {e}")

    total_fixed = fixed_count + backup_files_added

    # 自动修复完成后清理任何残留的原始文件名格式文件（备份恢复可能产生）
    auto_cleaned_count = clean_original_filename_files()
    if auto_cleaned_count > 0:
        logger.info(f"🧹 自动修复后清理了 {auto_cleaned_count} 个原始文件名格式文件")

    message = f"✅ 自动修复完成，共处理 {total_fixed} 个文件"
    if fixed_count > 0:
        message += f"（从uploads修复: {fixed_count}个）"
    if backup_files_added > 0:
        message += f"（从备份恢复: {backup_files_added}个）"
    if auto_cleaned_count > 0:
        message += f"（清理原始文件: {auto_cleaned_count}个）"

    logger.info(message)

    return JSONResponse({
        "message": message,
        "fixed_count": fixed_count,
        "backup_files_added": backup_files_added,
        "cleaned_count": auto_cleaned_count,
        "total_fixed": total_fixed,
        "details": results
    })

@app.post("/clear")
async def clear_downloads():
    """清理下载文件"""
    global filename_mapping

    # 使用统一的清理函数
    cleared_count = clean_all_downloads()

    # 清空文件名映射关系
    filename_mapping.clear()

    logger.info(f"手动清理了 {cleared_count} 个下载文件")
    return JSONResponse({"message": f"✅ 已清理 {cleared_count} 个下载文件"})

@app.post("/clear-debug")
async def clear_debug():
    """专门清理调试文件"""
    debug_cleared_count = clean_debug_files()

    message = f"✅ 已清理 {debug_cleared_count} 个调试文件" if debug_cleared_count > 0 else "✅ 没有调试文件需要清理"
    logger.info(f"手动清理了 {debug_cleared_count} 个调试文件")
    return JSONResponse({"message": message, "cleared_count": debug_cleared_count})

@app.post("/selective-backup")
async def selective_backup(files: List[UploadFile] = File(...)):
    """选择性备份功能"""
    if not files:
        raise HTTPException(status_code=400, detail="没有上传文件")

    results = []
    backup_count = 0

    for file in files:
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            results.append({
                "filename": file.filename or "unknown",
                "success": False,
                "message": "❌ 不是PDF文件"
            })
            continue

        try:
            # 处理文件名，去除路径信息
            clean_filename = os.path.basename(file.filename) if file.filename else "unknown.pdf"

            # 临时保存文件
            temp_path = f"temp_{clean_filename}"
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                if not content:
                    raise ValueError("文件内容为空")
                buffer.write(content)

            # 创建备份，使用原始文件名保持文件夹结构信息
            backup_filename = file.filename if file.filename else clean_filename
            backup_path = create_backup(temp_path, backup_filename)

            # 删除临时文件
            os.remove(temp_path)

            results.append({
                "filename": file.filename,
                "success": True,
                "message": "✅ 备份成功",
                "backup_path": backup_path
            })
            backup_count += 1

        except Exception as e:
            # 清理临时文件
            clean_filename = os.path.basename(file.filename) if file.filename else "unknown.pdf"
            temp_path = f"temp_{clean_filename}"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

            results.append({
                "filename": file.filename or "unknown",
                "success": False,
                "message": f"❌ 备份失败: {str(e)}"
            })

    logger.info(f"选择性备份完成，成功备份 {backup_count} 个文件")

    return JSONResponse({
        "results": results,
        "backup_count": backup_count,
        "total_count": len(files),
        "message": f"✅ 选择性备份完成，成功备份 {backup_count}/{len(files)} 个文件"
    })

@app.post("/clear-backup")
async def clear_backup(date: Optional[str] = None):
    """清理备份文件"""
    try:
        backup_root = Path("backup")
        cleared_count = 0

        if not backup_root.exists():
            return JSONResponse({"message": "⚠️ 备份目录不存在"})

        if date:
            # 清理指定日期的备份
            date_folder = backup_root / date
            if date_folder.exists():
                for file in date_folder.glob("*.pdf"):
                    try:
                        os.remove(file)
                        cleared_count += 1
                    except Exception as e:
                        logger.warning(f"清理备份文件失败 {file}: {e}")

                # 如果文件夹为空，删除文件夹
                try:
                    if not any(date_folder.iterdir()):
                        date_folder.rmdir()
                except:
                    pass

                logger.info(f"清理了 {date} 的 {cleared_count} 个备份文件")
                return JSONResponse({"message": f"✅ 已清理 {date} 的 {cleared_count} 个备份文件"})
            else:
                return JSONResponse({"message": f"⚠️ 日期 {date} 的备份不存在"})
        else:
            # 清理所有备份
            for date_folder in backup_root.iterdir():
                if date_folder.is_dir():
                    for file in date_folder.glob("*.pdf"):
                        try:
                            os.remove(file)
                            cleared_count += 1
                        except Exception as e:
                            logger.warning(f"清理备份文件失败 {file}: {e}")

                    # 删除空文件夹
                    try:
                        if not any(date_folder.iterdir()):
                            date_folder.rmdir()
                    except:
                        pass

            logger.info(f"清理了所有 {cleared_count} 个备份文件")
            return JSONResponse({"message": f"✅ 已清理所有 {cleared_count} 个备份文件"})

    except Exception as e:
        logger.error(f"清理备份失败: {e}")
        return JSONResponse({"message": f"❌ 清理备份失败: {str(e)}"})

def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """查找可用端口"""
    import socket

    for port in range(start_port, start_port + max_attempts):
        try:
            # 尝试绑定端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                logger.info(f"✅ 找到可用端口: {port}")
                return port
        except OSError:
            logger.debug(f"端口 {port} 已被占用")
            continue

    # 如果所有端口都被占用，返回一个随机端口
    import random
    random_port = random.randint(8010, 8999)
    logger.warning(f"⚠️ 前{max_attempts}个端口都被占用，尝试随机端口: {random_port}")
    return random_port

def start_server():
    """启动服务器"""
    logger.info("🚀 启动PDF批量重命名工具...")

    # 启动时清理调试文件
    debug_cleaned = clean_debug_files()
    if debug_cleaned > 0:
        logger.info(f"🗑️ 启动时清理了 {debug_cleaned} 个调试文件")

    # 查找可用端口
    available_port = find_available_port()

    try:
        logger.info(f"🌐 服务将在以下地址启动:")
        logger.info(f"   - 本地访问: http://localhost:{available_port}")
        logger.info(f"   - 网络访问: http://0.0.0.0:{available_port}")
        logger.info("=" * 50)

        uvicorn.run(app, host="0.0.0.0", port=available_port)

    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")

        # 尝试备用端口
        logger.info("🔄 尝试备用端口...")
        backup_port = find_available_port(9000, 5)

        try:
            logger.info(f"🌐 使用备用端口: {backup_port}")
            uvicorn.run(app, host="0.0.0.0", port=backup_port)
        except Exception as backup_e:
            logger.error(f"❌ 备用端口启动也失败: {backup_e}")
            logger.error("💡 请手动指定端口号或检查网络配置")

@app.post("/create-zip-all")
async def create_zip_all():
    """创建所有文件的ZIP包并返回下载链接"""
    downloads_dir = Path("downloads")

    if not downloads_dir.exists() or not list(downloads_dir.glob("*.pdf")):
        raise HTTPException(status_code=404, detail="没有可下载的文件")

    pdf_files = list(downloads_dir.glob("*.pdf"))
    
    # 创建ZIP文件
    from datetime import datetime
    import uuid
    
    zip_id = str(uuid.uuid4())
    zip_filename = f"renamed_pdfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = Path("temp") / f"zip_{zip_id}.zip"
    
    # 确保temp目录存在
    zip_path.parent.mkdir(exist_ok=True)

    try:
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            for pdf_file in pdf_files:
                zipf.write(pdf_file, pdf_file.name)

        # 获取ZIP文件信息
        zip_size = zip_path.stat().st_size
        zip_size_mb = round(zip_size / 1024 / 1024, 2)

        # 存储ZIP文件信息（30分钟后自动清理）
        import time
        temp_zip_files[zip_id] = {
            "filename": zip_filename,
            "path": str(zip_path),
            "size": zip_size,
            "size_mb": zip_size_mb,
            "created_at": time.time(),
            "file_count": len(pdf_files)
        }

        logger.info(f"创建批量下载ZIP: {zip_filename}, 包含 {len(pdf_files)} 个文件, 大小: {zip_size_mb}MB")

        return JSONResponse({
            "success": True,
            "zip_id": zip_id,
            "filename": zip_filename,
            "download_url": f"/download-zip/{zip_id}",
            "size": zip_size,
            "size_mb": zip_size_mb,
            "file_count": len(pdf_files)
        })

    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        if zip_path.exists():
            zip_path.unlink()
        raise HTTPException(status_code=500, detail=f"创建下载文件失败: {str(e)}")

@app.post("/create-zip-selected")
async def create_zip_selected(filenames: List[str]):
    """创建选定文件的ZIP包并返回下载链接"""
    if not filenames:
        raise HTTPException(status_code=400, detail="没有选择文件")

    downloads_dir = Path("downloads")

    # 验证文件是否存在
    existing_files = []
    for filename in filenames:
        file_path = downloads_dir / filename
        if file_path.exists() and file_path.suffix.lower() == '.pdf':
            existing_files.append(file_path)

    if not existing_files:
        raise HTTPException(status_code=404, detail="选择的文件都不存在")

    # 创建ZIP文件
    from datetime import datetime
    import uuid
    
    zip_id = str(uuid.uuid4())
    zip_filename = f"selected_pdfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = Path("temp") / f"zip_{zip_id}.zip"
    
    # 确保temp目录存在
    zip_path.parent.mkdir(exist_ok=True)

    try:
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            for pdf_file in existing_files:
                zipf.write(pdf_file, pdf_file.name)

        # 获取ZIP文件信息
        zip_size = zip_path.stat().st_size
        zip_size_mb = round(zip_size / 1024 / 1024, 2)

        # 存储ZIP文件信息
        import time
        temp_zip_files[zip_id] = {
            "filename": zip_filename,
            "path": str(zip_path),
            "size": zip_size,
            "size_mb": zip_size_mb,
            "created_at": time.time(),
            "file_count": len(existing_files)
        }

        logger.info(f"创建选择性下载ZIP: {zip_filename}, 包含 {len(existing_files)} 个文件, 大小: {zip_size_mb}MB")

        return JSONResponse({
            "success": True,
            "zip_id": zip_id,
            "filename": zip_filename,
            "download_url": f"/download-zip/{zip_id}",
            "size": zip_size,
            "size_mb": zip_size_mb,
            "file_count": len(existing_files)
        })

    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        if zip_path.exists():
            zip_path.unlink()
        raise HTTPException(status_code=500, detail=f"创建下载文件失败: {str(e)}")

@app.get("/download-zip/{zip_id}")
async def download_zip_file(zip_id: str):
    """下载指定的ZIP文件"""
    if zip_id not in temp_zip_files:
        raise HTTPException(status_code=404, detail="ZIP文件不存在或已过期")
    
    zip_info = temp_zip_files[zip_id]
    zip_path = Path(zip_info["path"])
    
    if not zip_path.exists():
        # 清理过期记录
        del temp_zip_files[zip_id]
        raise HTTPException(status_code=404, detail="ZIP文件已被清理")
    
    # 检查文件是否过期（30分钟）
    import time
    if time.time() - zip_info["created_at"] > 1800:  # 30分钟
        # 清理过期文件
        try:
            zip_path.unlink()
            del temp_zip_files[zip_id]
        except:
            pass
        raise HTTPException(status_code=404, detail="ZIP文件已过期")
    
    def cleanup_zip():
        try:
            # 延迟清理，给下载足够时间
            import threading
            import time
            def delayed_cleanup():
                time.sleep(60)  # 1分钟后清理
                try:
                    if zip_path.exists():
                        zip_path.unlink()
                    if zip_id in temp_zip_files:
                        del temp_zip_files[zip_id]
                    logger.debug(f"清理临时ZIP文件: {zip_path}")
                except:
                    pass
            
            thread = threading.Thread(target=delayed_cleanup)
            thread.daemon = True
            thread.start()
        except:
            pass

    # 设置下载响应头
    headers = {
        "Content-Disposition": f'attachment; filename="{zip_info["filename"]}"',
        "Content-Type": "application/zip",
        "Content-Length": str(zip_info["size"]),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Accept-Ranges": "bytes"
    }

    return FileResponse(
        str(zip_path),
        filename=zip_info["filename"],
        media_type="application/zip",
        headers=headers,
        background=BackgroundTask(cleanup_zip)
    )

if __name__ == "__main__":
    start_server()

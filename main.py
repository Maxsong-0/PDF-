#!/usr/bin/env python3
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
from typing import List, Optional, Tuple
import logging
import glob
import time

# 设置环境变量解决NumExpr警告
os.environ['NUMEXPR_MAX_THREADS'] = '8'
os.environ['OMP_NUM_THREADS'] = '8'

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

def lazy_import_ocr():
    """延迟导入OCR相关库以减少启动内存"""
    global fitz, Image, pytesseract, cv2, np, ImageEnhance, easyocr
    try:
        import fitz  # PyMuPDF
        from PIL import Image, ImageEnhance
        import pytesseract
        import cv2
        import numpy as np
        import easyocr  # 新增高精度OCR引擎
        return True
    except ImportError as e:
        logger.error(f"OCR库导入失败: {e}")
        logger.info("请安装 EasyOCR: pip install easyocr")
        return False

fitz = None
Image = None
pytesseract = None
cv2 = None
np = None
ImageEnhance = None
easyocr = None

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
filename_mapping = {}  # 重命名后文件名 -> 原始文件名

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

def clean_all_downloads():
    """清理downloads目录中的所有PDF文件（每次新识别前清理上次结果）"""
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        return 0
    
    cleaned_count = 0
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
    
    if cleaned_count > 0:
        logger.info(f"🧹 清理了 {cleaned_count} 个上次处理的文件")
    
    return cleaned_count

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("backup", exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

class PDFProcessor:
    def __init__(self):
        # EasyOCR 读取器（延迟初始化）
        self._easyocr_reader = None
        self._easyocr_initialized = False
        
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
            
            # 低优先级：宽松格式（严格过滤）
            r'(?<![A-Za-z0-9])([0-9]{3,5}[-_][0-9]{8,20})(?![A-Za-z0-9])',  # 3-5位-8-20位数字
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
        
        # 增强验证规则
        self.validation_rules = {
            'min_digits': 6,  # 至少包含6个数字（提高要求）
            'min_length': 8,  # 最小长度（提高要求）
            'max_length': 25,  # 最大长度
            'required_separator': ['-', '_'],  # 必须包含的分隔符
            'min_separator_count': 1,  # 至少需要1个分隔符
            'sales_order_prefixes': ['1403', '1404', '1405'],  # 销货单号常见前缀
            'invalid_patterns': [
                r'^[0]+$',  # 全零
                r'^[1]+$',  # 全一
                r'^(.)\1+$',  # 重复字符
                r'^[A-Z]{2}[0-9]{10,15}$',  # 快递单号格式
                r'^[0-9]{13}$',  # 13位纯数字（快递常用）
                r'^[0-9]{15}$',  # 15位纯数字（快递常用）
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
    
    def _apply_ocr_correction(self, text: str) -> str:
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
        """验证候选订单号是否有效（增强版）"""
        if not candidate:
            return False
        
        # 基本长度检查
        rules = self.validation_rules
        if len(candidate) < rules['min_length'] or len(candidate) > rules['max_length']:
            return False
        
        # 排除常见无效词汇
        if candidate.lower() in self.excluded_words:
            return False
        
        # 快递单号排除检查
        if self._is_express_number(candidate):
            return False
        
        # 检查是否包含足够的数字
        digit_count = sum(1 for c in candidate if c.isdigit())
        if digit_count < rules['min_digits']:
            return False
        
        # 检查必需的分隔符
        separator_count = sum(1 for sep in rules['required_separator'] if sep in candidate)
        if separator_count < rules.get('min_separator_count', 0):
            return False
        
        # 检查无效模式
        for invalid_pattern in rules['invalid_patterns']:
            if re.match(invalid_pattern, candidate):
                return False
        
        # 销货出库单号特征检查
        # 1. 检查是否符合销货单号格式 (XXXX-XXXXXXXXXXXX)
        if '-' in candidate or '_' in candidate:
            parts = re.split(r'[-_]', candidate)
            if len(parts) >= 2:
                first_part = parts[0]
                second_part = parts[1]
                
                # 第一部分应该是3-5位数字，第二部分应该是8-15位数字
                if (first_part.isdigit() and 3 <= len(first_part) <= 5 and
                    second_part.isdigit() and 8 <= len(second_part) <= 15):
                    
                    # 检查是否以销货单号常见前缀开头
                    sales_prefixes = rules.get('sales_order_prefixes', [])
                    if sales_prefixes and any(first_part.startswith(prefix) for prefix in sales_prefixes):
                        logger.info(f"销货单号前缀匹配: {candidate}")
                        return True
                    
                    # 或者符合一般格式要求
                    if len(first_part) == 4 and len(second_part) >= 10:
                        return True
        
        # 额外的质量检查
        # 1. 避免过于简单的模式
        if len(set(candidate)) < 4:  # 字符种类太少（提高要求）
            return False
        
        # 2. 检查数字字母比例是否合理
        alpha_count = sum(1 for c in candidate if c.isalpha())
        special_count = sum(1 for c in candidate if not c.isalnum())
        
        # 销货单号主要应该是数字和分隔符
        if alpha_count > len(candidate) * 0.2:  # 字母不应超过20%
            return False
        
        # 如果是纯数字但太短，拒绝
        if alpha_count == 0 and special_count == 0 and len(candidate) < 10:
            return False
        
        return True
    
    def find_all_order_candidates(self, text: str) -> list:
        """找到文本中所有潜在的订单号候选"""
        candidates = []
        
        # 遍历所有模式，按优先级收集候选项
        for pattern_index, pattern in enumerate(self.patterns):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                result = match.group(1).strip()
                if self._validate_order_number(result):
                    # 记录候选项及其置信度（模式索引越小置信度越高）
                    candidates.append({
                        'number': result,
                        'confidence': len(self.patterns) - pattern_index,  # 置信度分数
                        'pattern_index': pattern_index
                    })
        
        # 按置信度排序
        candidates.sort(key=lambda x: (-x['confidence'], x['pattern_index']))
        return candidates
    
    def _compare_ocr_results(self, tesseract_results: list, easyocr_results: list, log_messages: list) -> dict:
        """比较两个OCR引擎的结果，选择最佳候选"""
        all_candidates = []
        
        # 收集Tesseract候选
        for result in tesseract_results:
            for candidate in result['candidates']:
                all_candidates.append({
                    'text': result['text'],
                    'method': f"Tesseract配置{result['config']}",
                    'number': candidate['number'],
                    'confidence': candidate['confidence'],
                    'source': 'tesseract'
                })
        
        # 收集EasyOCR候选
        for result in easyocr_results:
            for candidate in result['candidates']:
                all_candidates.append({
                    'text': result['text'],
                    'method': f"EasyOCR验证 ({result['info']})",
                    'number': candidate['number'],
                    'confidence': candidate['confidence'],
                    'source': 'easyocr'
                })
        
        if not all_candidates:
            return None
        
        # 智能选择策略
        # 1. 如果EasyOCR和Tesseract都找到相同的订单号，优先选择
        easyocr_numbers = {c['number'] for c in all_candidates if c['source'] == 'easyocr'}
        tesseract_numbers = {c['number'] for c in all_candidates if c['source'] == 'tesseract'}
        common_numbers = easyocr_numbers & tesseract_numbers
        
        if common_numbers:
            # 选择共同识别的最高置信度结果
            common_candidates = [c for c in all_candidates if c['number'] in common_numbers]
            best = max(common_candidates, key=lambda x: x['confidence'])
            log_messages.append(f"🎯 双引擎确认相同结果: {best['number']} (置信度: {best['confidence']})")
            return best
        
        # 2. EasyOCR结果优先（精度更高）
        easyocr_candidates = [c for c in all_candidates if c['source'] == 'easyocr']
        if easyocr_candidates:
            best = max(easyocr_candidates, key=lambda x: x['confidence'])
            log_messages.append(f"🤖 选择EasyOCR最佳结果: {best['number']} (置信度: {best['confidence']})")
            return best
        
        # 3. 回退到Tesseract最佳结果
        tesseract_candidates = [c for c in all_candidates if c['source'] == 'tesseract']
        if tesseract_candidates:
            best = max(tesseract_candidates, key=lambda x: x['confidence'])
            log_messages.append(f"⚡ 选择Tesseract最佳结果: {best['number']} (置信度: {best['confidence']})")
            return best
        
        return None
    
    def _get_easyocr_reader(self):
        """获取EasyOCR读取器（延迟初始化）"""
        if not self._easyocr_initialized:
            try:
                if not lazy_import_ocr():
                    return None
                
                logger.info("🚀 初始化 EasyOCR 引擎（首次使用需要下载模型，请稍候...）")
                # 支持中文和英文，GPU加速（如果可用）
                self._easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=True)
                self._easyocr_initialized = True
                logger.info("✅ EasyOCR 引擎初始化完成")
                
            except Exception as e:
                logger.warning(f"EasyOCR 初始化失败，将使用 Tesseract: {e}")
                try:
                    # 尝试仅CPU模式
                    self._easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                    self._easyocr_initialized = True
                    logger.info("✅ EasyOCR CPU模式初始化完成")
                except Exception as e2:
                    logger.error(f"EasyOCR CPU模式也失败: {e2}")
                    self._easyocr_reader = None
                    self._easyocr_initialized = True
        
        return self._easyocr_reader
    
    def _extract_text_with_easyocr(self, image) -> tuple:
        """使用EasyOCR提取文本"""
        try:
            reader = self._get_easyocr_reader()
            if reader is None:
                return None, "EasyOCR初始化失败"
            
            # 转换PIL图像为numpy数组
            if hasattr(image, 'convert'):
                # PIL图像
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            else:
                # 已经是numpy数组
                cv_image = image
            
            # EasyOCR识别
            logger.info("🔍 使用 EasyOCR 进行高精度识别...")
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
            logger.info(f"EasyOCR识别结果: {info}")
            
            return full_text, info
            
        except Exception as e:
            logger.error(f"EasyOCR识别失败: {e}")
            return None, f"EasyOCR识别失败: {str(e)}"
    
    def _enhance_image_for_ocr(self, image):
        """专门为OCR优化的图像增强处理（数字识别优化版）"""
        try:
            # 1. 首先创建多个预处理版本
            enhanced_versions = []
            
            # 版本1：标准增强
            enhanced = image.copy()
            
            # 对比度增强（针对数字识别优化）
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(1.6)  # 提高对比度
            
            # 清晰度增强
            enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = enhancer.enhance(1.5)  # 提高清晰度
            
            # 亮度微调
            enhancer = ImageEnhance.Brightness(enhanced)
            enhanced = enhancer.enhance(1.05)
            
            enhanced_versions.append(('标准增强', enhanced))
            
            # 版本2：高对比度二值化（适合数字识别）
            if enhanced.mode != 'L':
                gray = enhanced.convert('L')
            else:
                gray = enhanced
            
            import numpy as np
            cv_image = np.array(gray)
            
            # 高斯模糊去噪
            cv_image = cv2.GaussianBlur(cv_image, (1, 1), 0)
            
            # 多种二值化方法
            # 方法1: OTSU自适应阈值
            _, binary1 = cv2.threshold(cv_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            enhanced_versions.append(('OTSU二值化', Image.fromarray(binary1)))
            
            # 方法2: 自适应阈值（高斯）
            binary2 = cv2.adaptiveThreshold(cv_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)
            enhanced_versions.append(('自适应阈值', Image.fromarray(binary2)))
            
            # 方法3: 针对数字优化的形态学处理
            kernel = np.ones((1, 1), np.uint8)
            binary3 = cv2.morphologyEx(binary1, cv2.MORPH_CLOSE, kernel)
            
            # 额外的数字分离处理
            # 膨胀操作，有助于分离粘连的数字
            kernel_dilate = np.ones((2, 2), np.uint8)
            binary3 = cv2.dilate(binary3, kernel_dilate, iterations=1)
            # 然后腐蚀回原大小
            binary3 = cv2.erode(binary3, kernel_dilate, iterations=1)
            
            enhanced_versions.append(('形态学优化', Image.fromarray(binary3)))
            
            # 版本4: 反色处理（有时对OCR有帮助）
            inverted = cv2.bitwise_not(binary1)
            enhanced_versions.append(('反色处理', Image.fromarray(inverted)))
            
            # 选择最佳版本（这里返回标准增强版，但保留其他版本用于调试）
            logger.debug(f"生成{len(enhanced_versions)}个图像处理版本")
            
            # 返回OTSU二值化版本，通常对数字识别效果最好
            return enhanced_versions[1][1]  # OTSU二值化版本
            
        except Exception as e:
            logger.warning(f"图像增强失败，使用原图: {e}")
            return image
    
    def _enhance_for_digit_recognition(self, image):
        """专门针对数字识别的图像增强"""
        try:
            import numpy as np
            
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
            
            return Image.fromarray(final)
            
        except Exception as e:
            logger.warning(f"数字识别增强失败: {e}")
            return image
    
    def detect_text_orientation(self, image) -> int:
        """多方法结合的文本方向检测，返回标准角度：0, 90, 180, 270"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 方法1: 基于霍夫线变换的角度检测
            angle1, method1_info = self._detect_angle_by_hough_lines(gray)
            logger.debug(f"霍夫线检测: {angle1}° - {method1_info}")
            
            # 方法2: 基于投影的角度检测
            angle2, method2_info = self._detect_angle_by_projection(gray)
            logger.debug(f"投影法检测: {angle2}° - {method2_info}")
            
            # 方法3: 基于形态学操作的角度检测
            angle3, method3_info = self._detect_angle_by_morphology(gray)
            logger.debug(f"形态学检测: {angle3}° - {method3_info}")
            
            # 综合判断最可能的角度
            angles = [angle1, angle2, angle3]
            methods_info = [method1_info, method2_info, method3_info]
            angle_counts = {}
            
            for angle in angles:
                if angle in angle_counts:
                    angle_counts[angle] += 1
                else:
                    angle_counts[angle] = 1
            
            # 记录详细的检测信息
            logger.debug(f"角度检测详情: 霍夫线={angle1}°, 投影={angle2}°, 形态学={angle3}°")
            logger.debug(f"角度统计: {angle_counts}")
            
            # 返回最常见的角度，如果平票则优先返回非0角度
            if angle_counts:
                max_count = max(angle_counts.values())
                best_angles = [angle for angle, count in angle_counts.items() if count == max_count]
                
                # 优先返回非0的角度
                for angle in [90, 180, 270]:
                    if angle in best_angles:
                        logger.debug(f"最终选择角度: {angle}° (投票数: {max_count})")
                        return angle
                
                final_angle = best_angles[0]
                logger.debug(f"最终选择角度: {final_angle}° (投票数: {max_count})")
                return final_angle
            
            return 0
            
        except Exception as e:
            logger.warning(f"文本方向检测失败: {e}")
            return 0
    
    def _detect_angle_by_hough_lines(self, gray) -> tuple:
        """使用霍夫线变换检测角度"""
        try:
            # 自适应阈值二值化
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 15, 10)
            
            # 形态学操作增强线条
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 边缘检测
            edges = cv2.Canny(binary, 50, 150, apertureSize=3)
            
            # 霍夫线变换
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=50)
            
            if lines is not None and len(lines) > 10:
                angles = []
                
                for line in lines:
                    rho, theta = line[0]
                    angle_deg = np.degrees(theta)
                    
                    # 将角度标准化到 [0, 180) 区间
                    angle_deg = angle_deg % 180
                    
                    # 将角度映射到标准方向
                    if angle_deg <= 45:
                        angles.append(0)  # 水平
                    elif angle_deg <= 135:
                        angles.append(90)  # 垂直
                    else:
                        angles.append(0)  # 水平
                
                if angles:
                    # 统计最频繁的角度
                    from collections import Counter
                    angle_counter = Counter(angles)
                    most_common_angle, count = angle_counter.most_common(1)[0]
                    
                    info = f"检测到{len(lines)}条线，{count}条{most_common_angle}°线"
                    
                    # 如果垂直线条多，可能是旋转90度
                    if most_common_angle == 90:
                        return 90, info
                    else:
                        return 0, info
            
            return 0, f"检测到{len(lines) if lines is not None else 0}条线，不足以判断"
            
        except Exception as e:
            logger.warning(f"霍夫线变换角度检测失败: {e}")
            return 0, f"检测失败: {str(e)}"
    
    def _detect_angle_by_projection(self, gray) -> tuple:
        """使用投影法检测角度"""
        try:
            # 二值化
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 计算水平和垂直投影
            h_proj = np.sum(binary == 0, axis=1)  # 水平投影
            v_proj = np.sum(binary == 0, axis=0)  # 垂直投影
            
            # 计算投影的方差，方差大说明该方向上文本分布不均匀，可能是正确方向
            h_variance = np.var(h_proj)
            v_variance = np.var(v_proj)
            
            ratio = v_variance / h_variance if h_variance > 0 else 0
            info = f"水平方差={h_variance:.2f}, 垂直方差={v_variance:.2f}, 比值={ratio:.2f}"
            
            # 如果垂直投影方差明显大于水平投影，说明可能需要旋转90度
            if v_variance > h_variance * 1.5:
                return 90, info
            else:
                return 0, info
                
        except Exception as e:
            logger.warning(f"投影法角度检测失败: {e}")
            return 0, f"检测失败: {str(e)}"
    
    def _detect_angle_by_morphology(self, gray) -> tuple:
        """使用形态学操作检测角度"""
        try:
            # 二值化
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 水平和垂直结构元素
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
            
            # 检测水平和垂直线条
            h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
            v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
            
            # 统计线条数量
            h_count = cv2.countNonZero(h_lines)
            v_count = cv2.countNonZero(v_lines)
            
            ratio = v_count / h_count if h_count > 0 else 0
            info = f"水平线={h_count}像素, 垂直线={v_count}像素, 比值={ratio:.2f}"
            
            # 如果垂直线条明显多于水平线条，可能需要旋转
            if v_count > h_count * 1.3:
                return 90, info
            else:
                return 0, info
                
        except Exception as e:
            logger.warning(f"形态学角度检测失败: {e}")
            return 0, f"检测失败: {str(e)}"
    
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
                
                # 检测文本方向
                detected_angle = self.detect_text_orientation(cv_image)
                log_messages.append(f"🔍 智能角度检测结果: {detected_angle}°")
                
                # 获取详细的检测信息（临时启用debug级别）
                old_level = logger.level
                logger.setLevel(logging.DEBUG)
                
                # 重新运行检测以获取详细信息
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                angle1, method1_info = self._detect_angle_by_hough_lines(gray)
                angle2, method2_info = self._detect_angle_by_projection(gray)
                angle3, method3_info = self._detect_angle_by_morphology(gray)
                
                log_messages.append(f"   📊 霍夫线变换: {angle1}° ({method1_info})")
                log_messages.append(f"   📊 投影分析: {angle2}° ({method2_info})")
                log_messages.append(f"   📊 形态学分析: {angle3}° ({method3_info})")
                
                # 恢复原日志级别
                logger.setLevel(old_level)
                
                # 基于检测结果优化角度尝试策略
                if detected_angle == 0:
                    # 如果检测为正常方向，优先尝试0度，然后尝试其他角度
                    angles_to_try = [0, 90, 270, 180]
                    log_messages.append("📐 使用标准角度序列: 0° → 90° → 270° → 180°")
                elif detected_angle == 90:
                    # 如果检测为90度旋转，优先尝试-90度(270度)校正
                    angles_to_try = [270, 90, 0, 180]
                    log_messages.append("📐 检测到90°旋转，优先尝试270°校正")
                else:
                    # 其他情况按检测角度优先
                    angles_to_try = [detected_angle, 0, 90, 270, 180]
                    log_messages.append(f"📐 按检测角度{detected_angle}°优先尝试")
                
                # 去重
                angles_to_try = list(dict.fromkeys(angles_to_try))
                
                for angle in angles_to_try:
                    try:
                        # 旋转图像
                        if angle != 0:
                            rotated_cv = self.rotate_image(cv_image, angle)
                            rotated_pil = Image.fromarray(cv2.cvtColor(rotated_cv, cv2.COLOR_BGR2RGB))
                        else:
                            rotated_pil = pil_image
                        
                        # 多层图像增强处理
                        enhanced_image = self._enhance_image_for_ocr(rotated_pil)
                        
                        # 双重验证策略：Tesseract初识别 + EasyOCR精确确认
                        tesseract_results = []
                        easyocr_results = []
                        final_text = ""
                        ocr_method_used = ""
                        
                        # 第一步：Tesseract快速初步识别
                        log_messages.append(f"⚡ 第一步：Tesseract快速扫描 (角度: {angle}°)...")
                        
                        ocr_configs = [
                            # 配置1：专门针对数字和连字符的识别
                            r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789-_：: ',
                            # 配置2：包含字母的订单号
                            r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_：: ',
                            # 配置3：包含中文的完整识别
                            r'--oem 3 --psm 6',
                        ]
                        
                        tesseract_found_candidates = False
                        for config_index, custom_config in enumerate(ocr_configs):
                            try:
                                tesseract_text = pytesseract.image_to_string(enhanced_image, lang='chi_sim+eng', config=custom_config)
                                if tesseract_text and tesseract_text.strip():
                                    # 检查是否包含潜在的订单号候选
                                    potential_orders = self.find_all_order_candidates(tesseract_text)
                                    if potential_orders:
                                        tesseract_results.append({
                                            'text': tesseract_text,
                                            'config': config_index + 1,
                                            'candidates': potential_orders
                                        })
                                        tesseract_found_candidates = True
                                        log_messages.append(f"✅ Tesseract配置{config_index + 1}找到{len(potential_orders)}个候选")
                                        break
                            except Exception as e:
                                log_messages.append(f"⚠️ Tesseract配置{config_index + 1}失败: {str(e)}")
                                continue
                        
                        # 第二步：根据Tesseract结果决定EasyOCR策略
                        if tesseract_found_candidates:
                            # 策略A：有候选结果，用EasyOCR精确验证
                            log_messages.append(f"🎯 第二步：EasyOCR精确验证Tesseract候选结果...")
                            easyocr_text, easyocr_info = self._extract_text_with_easyocr(enhanced_image)
                            
                            if easyocr_text and easyocr_text.strip():
                                easyocr_candidates = self.find_all_order_candidates(easyocr_text)
                                easyocr_results.append({
                                    'text': easyocr_text,
                                    'info': easyocr_info,
                                    'candidates': easyocr_candidates
                                })
                                log_messages.append(f"✅ EasyOCR验证：{easyocr_info}，找到{len(easyocr_candidates)}个候选")
                            
                            # 比较两个引擎的结果
                            best_result = self._compare_ocr_results(tesseract_results, easyocr_results, log_messages)
                            if best_result:
                                final_text = best_result['text']
                                ocr_method_used = best_result['method']
                        else:
                            # 策略B：Tesseract没找到候选，直接用EasyOCR全力识别
                            log_messages.append(f"🤖 第二步：Tesseract无候选，EasyOCR全力识别...")
                            easyocr_text, easyocr_info = self._extract_text_with_easyocr(enhanced_image)
                            
                            if easyocr_text and easyocr_text.strip():
                                final_text = easyocr_text
                                ocr_method_used = f"EasyOCR独立识别 ({easyocr_info})"
                                log_messages.append(f"✅ EasyOCR独立识别：{easyocr_info}")
                            else:
                                log_messages.append(f"❌ 双引擎均未识别到有效文本")
                        
                        text = final_text
                        
                        if text.strip():
                            log_messages.append(f"📝 使用{ocr_method_used}识别文本片段: {text[:150]}...")
                            
                            # 查找销货出库单号
                            candidates = self.find_all_order_candidates(text)
                            if candidates:
                                best_candidate = candidates[0]  # 已按置信度排序
                                order_number = best_candidate['number']
                                log_messages.append(f"✅ 找到销货出库单号: {order_number} (使用{ocr_method_used}，置信度: {best_candidate['confidence']})")
                                doc.close()
                                return order_number, log_messages
                        else:
                            log_messages.append(f"⚠️ 角度{angle}°所有OCR方法都未识别到文本")
                        
                    except Exception as e:
                        log_messages.append(f"⚠️ 角度{angle}°处理失败: {str(e)}")
                        continue
            
            doc.close()
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
    
    # 开始处理前只清理原始文件名格式的文件（保留之前的正确结果）
    cleaned_count = clean_original_filename_files()
    if cleaned_count > 0:
        logger.info(f"🧹 处理开始前清理了 {cleaned_count} 个原始文件名格式文件")
    
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
        
        # 返回实际找到的文件，但保持用户请求的下载文件名
        return FileResponse(
            file_path,
            filename=filename,  # 使用用户请求的文件名作为下载名称
            media_type="application/pdf"
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
    """批量下载所有重命名文件（ZIP格式）"""
    downloads_dir = Path("downloads")
    
    if not downloads_dir.exists() or not list(downloads_dir.glob("*.pdf")):
        raise HTTPException(status_code=404, detail="没有可下载的文件")
    
    # 创建ZIP文件
    from datetime import datetime
    zip_filename = f"renamed_pdfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = f"temp_{zip_filename}"
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for pdf_file in downloads_dir.glob("*.pdf"):
                zipf.write(pdf_file, pdf_file.name)
        
        logger.info(f"创建批量下载ZIP: {zip_filename}")
        
        def cleanup_zip():
            try:
                os.remove(zip_path)
            except:
                pass
        
        return FileResponse(
            zip_path,
            filename=zip_filename,
            media_type="application/zip",
            background=cleanup_zip
        )
        
    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(status_code=500, detail=f"创建下载文件失败: {str(e)}")

@app.post("/download-selected")
async def download_selected(filenames: List[str]):
    """选择性下载指定文件（ZIP格式）"""
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
    zip_filename = f"selected_pdfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = f"temp_{zip_filename}"
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for pdf_file in existing_files:
                zipf.write(pdf_file, pdf_file.name)
        
        logger.info(f"创建选择性下载ZIP: {zip_filename}, 包含 {len(existing_files)} 个文件")
        
        def cleanup_zip():
            try:
                os.remove(zip_path)
            except:
                pass
        
        return FileResponse(
            zip_path,
            filename=zip_filename,
            media_type="application/zip",
            background=cleanup_zip
        )
        
    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(status_code=500, detail=f"创建下载文件失败: {str(e)}")

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
async def clear_backup(date: str = None):
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

if __name__ == "__main__":
    start_server()

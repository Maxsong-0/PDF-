#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字识别增强模块
专门解决数字OCR识别不准确的问题，如140被误识别为1410等
"""

# PIL兼容性补丁 - 处理Pillow 10.0.0+中ANTIALIAS被移除的问题
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
        Image.NEAREST = Image.Resampling.NEAREST
        Image.BILINEAR = Image.Resampling.BILINEAR
        Image.BICUBIC = Image.Resampling.BICUBIC
        Image.BOX = Image.Resampling.BOX
        Image.HAMMING = Image.Resampling.HAMMING
        Image.LANCZOS = Image.Resampling.LANCZOS
except ImportError:
    pass

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import re
import logging

logger = logging.getLogger(__name__)

class DigitEnhancer:
    def __init__(self):
        self.easyocr_reader = None
    
    def get_easyocr_reader(self):
        """获取EasyOCR读取器"""
        if self.easyocr_reader is None:
            try:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
                logger.info("✅ 数字识别引擎初始化完成")
            except ImportError:
                logger.error("❌ EasyOCR未安装")
                return None
        return self.easyocr_reader
    
    def enhance_for_digit_recognition(self, image):
        """专门针对数字识别的图像增强"""
        enhanced_versions = []
        
        # 方法1: 高对比度 + 锐化（适合模糊数字）
        version1 = self._high_contrast_enhancement(image)
        enhanced_versions.append(("高对比度锐化", version1))
        
        # 方法2: 形态学增强（适合细线条数字）
        version2 = self._morphological_enhancement(image)
        enhanced_versions.append(("形态学增强", version2))
        
        # 方法3: 双边滤波 + 自适应阈值（适合不均匀光照）
        version3 = self._adaptive_threshold_enhancement(image)
        enhanced_versions.append(("自适应阈值", version3))
        
        # 方法4: 多尺度增强（适合小数字）
        version4 = self._multi_scale_enhancement(image)
        enhanced_versions.append(("多尺度增强", version4))
        
        # 方法5: 边缘增强（突出数字轮廓）
        version5 = self._edge_enhancement(image)
        enhanced_versions.append(("边缘增强", version5))
        
        return enhanced_versions
    
    def _high_contrast_enhancement(self, image):
        """高对比度锐化增强"""
        try:
            # 转为灰度
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            # 极高对比度
            enhancer = ImageEnhance.Contrast(gray)
            high_contrast = enhancer.enhance(3.5)
            
            # 锐化
            enhancer = ImageEnhance.Sharpness(high_contrast)
            sharpened = enhancer.enhance(3.0)
            
            # 转OpenCV格式
            cv_img = np.array(sharpened)
            
            # 高斯模糊去噪
            blurred = cv2.GaussianBlur(cv_img, (1, 1), 0)
            
            # OTSU二值化
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return Image.fromarray(binary)
            
        except Exception as e:
            logger.error(f"高对比度增强失败: {e}")
            return image
    
    def _morphological_enhancement(self, image):
        """形态学操作增强数字轮廓"""
        try:
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            cv_img = np.array(gray)
            
            # 直方图均衡化
            equalized = cv2.equalizeHist(cv_img)
            
            # OTSU二值化
            _, binary = cv2.threshold(equalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 形态学操作 - 先闭运算填补断裂
            kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
            
            # 再开运算去除小噪声
            kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)
            
            # 轻微膨胀增强数字笔画
            kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            dilated = cv2.dilate(opened, kernel_dilate, iterations=1)
            
            return Image.fromarray(dilated)
            
        except Exception as e:
            logger.error(f"形态学增强失败: {e}")
            return image
    
    def _adaptive_threshold_enhancement(self, image):
        """自适应阈值增强"""
        try:
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            # 对比度增强
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(2.0)
            
            cv_img = np.array(enhanced)
            
            # 双边滤波保持边缘
            bilateral = cv2.bilateralFilter(cv_img, 9, 80, 80)
            
            # 自适应阈值
            adaptive = cv2.adaptiveThreshold(bilateral, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY, 11, 2)
            
            return Image.fromarray(adaptive)
            
        except Exception as e:
            logger.error(f"自适应阈值增强失败: {e}")
            return image
    
    def _multi_scale_enhancement(self, image):
        """多尺度处理增强小数字"""
        try:
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            # 先放大图像
            upscaled = gray.resize((gray.size[0] * 2, gray.size[1] * 2), Image.Resampling.LANCZOS)
            
            # 高对比度处理
            enhancer = ImageEnhance.Contrast(upscaled)
            contrast_enhanced = enhancer.enhance(2.5)
            
            cv_img = np.array(contrast_enhanced)
            
            # 高斯模糊
            blurred = cv2.GaussianBlur(cv_img, (1, 1), 0)
            
            # OTSU二值化
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 形态学清理
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 恢复原始大小
            final = cv2.resize(cleaned, gray.size)
            
            return Image.fromarray(final)
            
        except Exception as e:
            logger.error(f"多尺度增强失败: {e}")
            return image
    
    def _edge_enhancement(self, image):
        """边缘增强突出数字轮廓"""
        try:
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            cv_img = np.array(gray)
            
            # Sobel边缘检测
            grad_x = cv2.Sobel(cv_img, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(cv_img, cv2.CV_64F, 0, 1, ksize=3)
            gradient = np.sqrt(grad_x**2 + grad_y**2)
            gradient = np.uint8(gradient)
            
            # 组合原图和边缘
            combined = cv2.addWeighted(cv_img, 0.7, gradient, 0.3, 0)
            
            # OTSU二值化
            _, binary = cv2.threshold(combined, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return Image.fromarray(binary)
            
        except Exception as e:
            logger.error(f"边缘增强失败: {e}")
            return image
    
    def test_multiple_enhancements(self, image, target_region=None):
        """测试多种增强方法，找到最佳数字识别结果"""
        try:
            reader = self.get_easyocr_reader()
            if not reader:
                return None, []
            
            # 如果指定了目标区域，先裁剪
            if target_region:
                x1, y1, x2, y2 = target_region
                image = image.crop((x1, y1, x2, y2))
            
            # 获取所有增强版本
            enhanced_versions = self.enhance_for_digit_recognition(image)
            
            results = []
            
            for method_name, enhanced_img in enhanced_versions:
                logger.info(f"🔍 测试 {method_name} 方法...")
                
                # 不保存调试图像（避免文件堆积）
                # 如果需要调试，可以临时启用下面的代码
                # try:
                #     debug_filename = f"debug_digit_{method_name.replace(' ', '_')}.png"
                #     enhanced_img.save(debug_filename)
                #     logger.debug(f"保存调试图像: {debug_filename}")
                # except:
                #     pass
                
                # OCR识别
                cv_img = cv2.cvtColor(np.array(enhanced_img), cv2.COLOR_RGB2BGR)
                ocr_results = reader.readtext(cv_img, detail=1, paragraph=False)
                
                # 提取数字
                detected_numbers = []
                for bbox, text, confidence in ocr_results:
                    if confidence > 0.3:  # 置信度过滤
                        # 查找数字模式
                        numbers = re.findall(r'\d+', text)
                        for num in numbers:
                            if len(num) >= 3:  # 至少3位数字
                                detected_numbers.append({
                                    'number': num,
                                    'confidence': confidence,
                                    'text': text,
                                    'method': method_name
                                })
                
                results.append({
                    'method': method_name,
                    'numbers': detected_numbers,
                    'raw_results': ocr_results
                })
                
                if detected_numbers:
                    logger.info(f"   ✅ {method_name} 发现数字: {[n['number'] for n in detected_numbers]}")
                else:
                    logger.info(f"   ❌ {method_name} 未发现有效数字")
            
            return self._select_best_digit_result(results), results
            
        except Exception as e:
            logger.error(f"多重增强测试失败: {e}")
            return None, []
    
    def _select_best_digit_result(self, results):
        """从多个结果中选择最佳的数字识别结果"""
        try:
            all_candidates = []
            
            # 收集所有候选数字
            for result in results:
                for num_info in result['numbers']:
                    all_candidates.append(num_info)
            
            if not all_candidates:
                return None
            
            # 按长度和置信度排序（优先选择4位数字，置信度高的）
            def score_candidate(candidate):
                num = candidate['number']
                conf = candidate['confidence']
                
                # 长度评分（4位数字得分最高）
                if len(num) == 4:
                    length_score = 10
                elif len(num) == 3:
                    length_score = 5
                else:
                    length_score = len(num)
                
                # 是否符合订单号前缀模式
                prefix_score = 0
                if num.startswith(('1403', '1404', '1405', '1410')):
                    prefix_score = 15
                elif num.startswith('14'):
                    prefix_score = 8
                elif num.startswith('1'):
                    prefix_score = 3
                
                # 综合评分
                total_score = length_score + prefix_score + conf * 5
                return total_score
            
            # 排序并选择最佳候选
            sorted_candidates = sorted(all_candidates, key=score_candidate, reverse=True)
            best_candidate = sorted_candidates[0]
            
            logger.info(f"🎯 最佳数字识别结果: {best_candidate['number']} (方法: {best_candidate['method']}, 置信度: {best_candidate['confidence']:.3f})")
            
            return best_candidate
            
        except Exception as e:
            logger.error(f"结果选择失败: {e}")
            return None
    
    def correct_common_digit_errors(self, text):
        """纠正常见的数字识别错误"""
        try:
            corrected = text
            
            # 常见的OCR数字识别错误纠正
            corrections = {
                # 140 -> 1410 类型的错误（只在销货单号格式中纠正）
                r'(?<!\d)140(?=[-_]\d{12})': '1410',     # 140-12位数字 -> 1410（标准销货单格式）
                r'(?<!\d)140(?=\s+\d{12})': '1410',     # 140 12位数字 -> 1410（空格分隔）
                
                # 新增常见数字识别错误纠正
                r'(?<!\d)149(?=[-_]\d{8,})': '1403',     # 3被识别为9的情况
                r'(?<!\d)140(?=9[-_]\d{8,})': '1403',    # 3被识别为9，变成1409
                r'(?<!\d)(\d{2})09(?=[-_]\d{8,})': r'\g<1>03',  # 末尾3被识别为9
                r'(?<!\d)0(?=[-_]\d{12})': '1403',       # 1403开头的1丢失，变成0XX
                r'(?<!\d)403(?=[-_]\d{12})': '1403',     # 1403开头的1丢失，变成403
                
                # 其他常见错误
                r'\b0(\d{3})\b': r'\1',         # 前导0错误
                r'\b(\d+)O\b': r'\g<1>0',       # O被识别为0
                r'\bO(\d+)\b': r'0\1',          # 开头的O
                r'\b(\d+)l\b': r'\g<1>1',       # l被识别为1
                r'\bl(\d+)\b': r'1\1',          # 开头的l
                
                # 特定的销货单号格式纠正
                r'\b14O(\d+)\b': r'140\1',      # 14O -> 140
                r'\b1lO(\d+)\b': r'140\1',      # 1lO -> 140
                r'\b1l(\d+)\b': r'14\1',        # 1l -> 14
            }
            
            for pattern, replacement in corrections.items():
                before = corrected
                corrected = re.sub(pattern, replacement, corrected)
                if before != corrected:
                    logger.info(f"🔧 数字纠正: {before} -> {corrected}")
            
            return corrected
            
        except Exception as e:
            logger.error(f"数字纠正失败: {e}")
            return text

# 创建全局实例
digit_enhancer = DigitEnhancer() 
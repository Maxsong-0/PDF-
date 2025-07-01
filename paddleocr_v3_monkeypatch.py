#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaddleOCR 3.0.1 MonkeyPatch修复
通过monkey patching解决set_mkldnn_cache_capacity缺失的问题
"""

import os
import logging
import warnings
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 设置环境变量 - 解决MKLDNN和兼容性问题
os.environ['PADDLE_DISABLE_MKLDNN'] = '1'        # 禁用MKLDNN（解决macOS编译问题）
os.environ['PADDLE_DISABLE_CUDA'] = '1'         # 禁用CUDA（使用CPU）
os.environ['PADDLE_CPP_LOG_LEVEL'] = '3'        # 减少日志输出
os.environ['PADDLE_NUM_THREADS'] = '4'          # 限制线程数
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'  # 内存自动增长策略
os.environ['FLAGS_fraction_of_gpu_memory_to_use'] = '0'  # 不使用GPU内存

# 忽略警告
warnings.filterwarnings('ignore', category=UserWarning, module='paddle')
warnings.filterwarnings('ignore', category=FutureWarning, module='paddle')

def apply_paddle_monkeypatch():
    """
    应用monkey patch来修复PaddlePaddle的兼容性问题
    """
    try:
        import paddle
        
        # 获取AnalysisConfig类
        config_class = paddle.base.libpaddle.AnalysisConfig
        
        # 检查是否已经有这个方法
        if not hasattr(config_class, 'set_mkldnn_cache_capacity'):
            # 添加缺失的方法
            def set_mkldnn_cache_capacity(self, capacity):
                """
                添加缺失的set_mkldnn_cache_capacity方法
                在新版本中这个方法被移除了，我们提供一个空实现
                """
                # 空实现，不做任何事情
                logger.debug(f"set_mkldnn_cache_capacity({capacity}) - monkey patched (ignored)")
                pass
            
            # 将方法添加到类中
            config_class.set_mkldnn_cache_capacity = set_mkldnn_cache_capacity
            logger.info("✅ 已应用set_mkldnn_cache_capacity monkey patch")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ 应用monkey patch失败: {e}")
        return False

class PaddleOCR3MonkeyPatch:
    """使用monkey patch修复的PaddleOCR 3.0.1适配器"""
    
    def __init__(self):
        self.ocr_engine = None
        self.initialized = False
        self.init_error = None
        
        # 立即应用monkey patch
        apply_paddle_monkeypatch()
    
    def initialize(self):
        """初始化PaddleOCR 3.0.1"""
        if self.initialized:
            return self.ocr_engine is not None
            
        try:
            # 确保monkey patch已应用
            apply_paddle_monkeypatch()
            
            from paddleocr import PaddleOCR
            
            logger.info("🔥 初始化PaddleOCR 3.0.1 (with monkey patch)...")
            
            # 使用用户推荐的配置
            self.ocr_engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False
            )
            
            logger.info("✅ PaddleOCR 3.0.1初始化成功 (with monkey patch)")
            self.initialized = True
            return True
            
        except Exception as e:
            self.init_error = str(e)
            logger.error(f"❌ PaddleOCR 3.0.1初始化失败: {e}")
            self.initialized = True
            return False
    
    def predict_to_old_format(self, image_path: str) -> Optional[List[List]]:
        """
        使用新的predict方法，但返回旧格式的结果
        """
        if not self.initialize():
            return None
            
        try:
            # 使用新的predict方法
            logger.info(f"开始预测: {image_path}")
            results = self.ocr_engine.predict(input=image_path)
            
            logger.info(f"原始结果类型: {type(results)}")
            logger.info(f"结果数量: {len(results) if results else 0}")
            
            # 调试：打印结果结构
            for i, result in enumerate(results):
                logger.info(f"结果 {i}: 类型={type(result)}")
                logger.info(f"结果 {i}: 属性={[attr for attr in dir(result) if not attr.startswith('_')]}")
                if hasattr(result, 'results'):
                    logger.info(f"结果 {i}: results属性={result.results}")
                    logger.info(f"结果 {i}: results类型={type(result.results)}")
                    if result.results:
                        logger.info(f"结果 {i}: results长度={len(result.results)}")
                        for j, item in enumerate(result.results[:3]):  # 只显示前3个
                            logger.info(f"  项目 {j}: 类型={type(item)}")
                            logger.info(f"  项目 {j}: 属性={[attr for attr in dir(item) if not attr.startswith('_')]}")
                            logger.info(f"  项目 {j}: 内容={item}")
            
            # 转换为旧格式
            converted_results = []
            
            for result in results:
                page_result = []
                
                # 根据新格式解析结果（使用字典访问方式）
                try:
                    texts = result.get('rec_texts', [])
                    scores = result.get('rec_scores', [])
                    polys = result.get('rec_polys', [])
                    
                    if texts and scores and polys:
                        logger.info(f"处理页面结果，包含 {len(texts)} 个文本项目")
                        
                        # 确保三个列表长度一致
                        min_len = min(len(texts), len(scores), len(polys))
                        
                        for i in range(min_len):
                            try:
                                text = texts[i]
                                confidence = float(scores[i])
                                poly = polys[i]
                                
                                # 转换边界框格式
                                # poly是numpy数组，形状可能是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                                if len(poly) >= 4:
                                    points = [[int(p[0]), int(p[1])] for p in poly[:4]]
                                else:
                                    # 如果边界框不完整，使用默认值
                                    points = [[0, 0], [100, 0], [100, 50], [0, 50]]
                                
                                logger.info(f"转换项目 {i}: 文本='{text}', 置信度={confidence:.3f}")
                                
                                # 添加到结果中，格式: [points, (text, confidence)]
                                page_result.append([points, (text, confidence)])
                                
                            except Exception as e:
                                logger.warning(f"转换项目 {i} 时出错: {e}")
                                continue
                                
                    else:
                        logger.warning(f"结果数据为空: texts={len(texts) if texts else 0}, scores={len(scores) if scores else 0}, polys={len(polys) if polys else 0}")
                
                except Exception as e:
                    logger.warning(f"解析结果时出错: {e}")
                    
                    # 备用方法：尝试属性访问
                    try:
                        if hasattr(result, 'rec_texts') and hasattr(result, 'rec_scores') and hasattr(result, 'rec_polys'):
                            texts = result.rec_texts
                            scores = result.rec_scores
                            polys = result.rec_polys
                            
                            logger.info(f"使用属性访问成功，包含 {len(texts)} 个文本项目")
                            
                            min_len = min(len(texts), len(scores), len(polys))
                            for i in range(min_len):
                                try:
                                    text = texts[i]
                                    confidence = float(scores[i])
                                    poly = polys[i]
                                    
                                    if len(poly) >= 4:
                                        points = [[int(p[0]), int(p[1])] for p in poly[:4]]
                                    else:
                                        points = [[0, 0], [100, 0], [100, 50], [0, 50]]
                                    
                                    page_result.append([points, (text, confidence)])
                                    
                                except Exception as e:
                                    logger.warning(f"属性访问转换项目 {i} 时出错: {e}")
                                    continue
                        else:
                            logger.warning(f"属性访问失败: rec_texts={hasattr(result, 'rec_texts')}, rec_scores={hasattr(result, 'rec_scores')}, rec_polys={hasattr(result, 'rec_polys')}")
                    except Exception as e2:
                        logger.error(f"备用属性访问也失败: {e2}")
                
                converted_results.append(page_result)
            
            logger.info(f"转换完成，共转换 {len(converted_results)} 页，总文本块数: {sum(len(page) for page in converted_results)}")
            return converted_results
            
        except Exception as e:
            logger.error(f"❌ PaddleOCR 3.0.1预测失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.initialize()
    
    def get_error(self) -> Optional[str]:
        """获取初始化错误信息"""
        return self.init_error

# 全局实例
_paddle_ocr3_monkeypatch = None

def get_paddle_ocr3_monkeypatch():
    """获取全局PaddleOCR 3.0.1 monkey patch适配器实例"""
    global _paddle_ocr3_monkeypatch
    if _paddle_ocr3_monkeypatch is None:
        _paddle_ocr3_monkeypatch = PaddleOCR3MonkeyPatch()
    return _paddle_ocr3_monkeypatch

def paddle_ocr3_predict_with_monkeypatch(image_path: str) -> Optional[List[List]]:
    """
    使用monkey patch修复的PaddleOCR 3.0.1进行预测
    """
    adapter = get_paddle_ocr3_monkeypatch()
    return adapter.predict_to_old_format(image_path)

def test_paddle_ocr3_monkeypatch():
    """测试PaddleOCR 3.0.1 monkey patch适配器"""
    print("🧪 测试PaddleOCR 3.0.1 MonkeyPatch适配器...")
    
    adapter = get_paddle_ocr3_monkeypatch()
    
    if adapter.is_available():
        print("✅ PaddleOCR 3.0.1 MonkeyPatch适配器初始化成功")
        return True
    else:
        print(f"❌ PaddleOCR 3.0.1 MonkeyPatch适配器初始化失败: {adapter.get_error()}")
        return False

if __name__ == "__main__":
    # 测试monkey patch适配器
    test_paddle_ocr3_monkeypatch() 
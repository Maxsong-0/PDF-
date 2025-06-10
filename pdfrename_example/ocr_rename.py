import easyocr
import os
import re
import shutil
import logging
import numpy as np
import cv2
import pdf2image
from typing import Optional, List

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class PDFInvoiceRenamer:
    def __init__(self, debug: bool = False, debug_folder: str = "debug_output"):
        """
        初始化OCR引擎和配置
        :param debug: 是否启用调试模式
        :param debug_folder: 调试文件输出目录
        """
        logger.info("正在初始化EasyOCR引擎...")
        self.reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        # 使用旧代码的灵活正则表达式模式：3-4位数字 + 连字符 + 6-12位数字
        self.invoice_pattern = re.compile(r'\d{3,4}-\d{6,12}')
        self.debug = debug
        self.debug_folder = debug_folder
        self.pdf_count = 0  # 已处理的PDF计数

        if self.debug:
            os.makedirs(self.debug_folder, exist_ok=True)
            logger.info(f"调试模式已启用，中间文件将保存到: {self.debug_folder}")
        logger.info("EasyOCR引擎初始化完成")

    def pdf_to_image(self, pdf_path: str) -> Optional[np.ndarray]:
        """将PDF第一页转换为OpenCV图像"""
        try:
            logger.debug(f"开始转换PDF: {os.path.basename(pdf_path)}")
            pil_images = pdf2image.convert_from_path(
                pdf_path,
                dpi=300,
                first_page=1,
                last_page=1,
                poppler_path=POPPLER_PATH,
                thread_count=4
            )
            logger.debug(f"PDF转换成功: {os.path.basename(pdf_path)}")
            return cv2.cvtColor(np.array(pil_images[0]), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"PDF转换失败: {pdf_path}\n错误: {str(e)}")
            return None

    def rotate_image(self, img: np.ndarray, angle: int) -> np.ndarray:
        """图像旋转辅助函数"""
        if angle == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img

    def auto_rotate(self, img: np.ndarray, file_id: str = "") -> np.ndarray:
        """自动检测最佳旋转角度"""
        best_angle = 0
        best_conf = 0
        best_img = img

        logger.debug("开始旋转校正...")
        for angle in [0, 90, 180, 270]:
            rotated = self.rotate_image(img, angle)
            results = self.reader.readtext(rotated, paragraph=False)
            conf = np.mean([res[2] for res in results]) if results else 0

            if conf > best_conf:
                best_conf = conf
                best_angle = angle
                best_img = rotated
        logger.debug(f"最优旋转角度: {best_angle}°, 置信度: {best_conf:.2f}")

        if self.debug:
            # 确保文件名合法，移除可能存在的特殊字符
            safe_file_id = re.sub(r'[\\/*?:"<>|]', "_", file_id)
            debug_path = os.path.join(self.debug_folder, f"{safe_file_id}_rotated_{best_angle}.jpg")
            cv2.imwrite(debug_path, best_img)

        return best_img

    def extract_invoice_number(self, img: np.ndarray, file_id: str = "") -> Optional[str]:
        """从图像顶部区域提取发票号码（整合旧代码逻辑）"""
        logger.debug("开始识别单号...")
        h, w = img.shape[:2]
        top_region = img[:int(h * 0.4), :]  # 只检测顶部40%区域

        if self.debug:
            # 确保文件名合法，移除可能存在的特殊字符
            safe_file_id = re.sub(r'[\\/*?:"<>|]', "_", file_id)
            debug_path = os.path.join(self.debug_folder, f"{safe_file_id}_top.jpg")
            cv2.imwrite(debug_path, top_region)

        # 使用旧代码的识别逻辑
        results = self.reader.readtext(top_region, paragraph=False)
        logger.debug(f"检测到{len(results)}个文本块")

        # 清理文本并尝试匹配
        for i, (_, text, _) in enumerate(results):
            # 旧代码的文本清理方式
            clean_text = text.replace(" ", "").replace(":", "").replace("：", "")

            # 优先查找"销货出库单号"关键词下方的号码（旧代码逻辑）
            if "销货出库单号" in clean_text:
                logger.debug("检测到关键字段'销货出库单号'")
                # 检查后续3行（旧代码逻辑）
                for j in range(i + 1, min(i + 4, len(results))):
                    candidate = results[j][1].replace(" ", "")
                    if match := self.invoice_pattern.search(candidate):
                        invoice_num = match.group()
                        logger.debug(f"在关键词下方识别到单号: {invoice_num}")
                        return invoice_num

            # 直接匹配模式（旧代码逻辑）
            if match := self.invoice_pattern.search(clean_text):
                invoice_num = match.group()
                logger.debug(f"直接识别到单号: {invoice_num}")
                return invoice_num

        logger.warning("未识别到有效单号")
        return None

    # === GUI专用方法 ===
    def process_pdf(self, pdf_path: str) -> List[str]:
        """为GUI提供的处理接口: 返回识别结果列表"""
        self.pdf_count += 1
        file_id = f"{self.pdf_count}_{os.path.splitext(os.path.basename(pdf_path))[0]}"

        try:
            # 转换PDF为图像
            img = self.pdf_to_image(pdf_path)
            if img is None:
                return []

            # 自动旋转校正
            rotated_img = self.auto_rotate(img, file_id)

            # 提取发票号码
            invoice_number = self.extract_invoice_number(rotated_img, file_id)

            if invoice_number:
                return [invoice_number]

        except Exception as e:
            logger.error(f"处理PDF失败: {pdf_path}\n错误: {str(e)}")

        return []

    # === 命令行模式专用方法 ===
    def process_single_pdf(self, pdf_path: str, output_dir: str) -> bool:
        """处理单个PDF文件"""
        filename = os.path.basename(pdf_path)
        file_id = os.path.splitext(filename)[0]

        try:
            # 转换PDF为图像
            img = self.pdf_to_image(pdf_path)
            if img is None:
                return False

            # 自动旋转校正
            rotated_img = self.auto_rotate(img, file_id)

            # 提取发票号码
            invoice_number = self.extract_invoice_number(rotated_img, file_id)

            if not invoice_number:
                logger.warning(f"未识别到有效出库单号: {filename}")
                return False

            # 重命名文件
            new_name = f"{invoice_number}.pdf"
            new_path = os.path.join(output_dir, new_name)

            # 处理文件名冲突
            counter = 1
            while os.path.exists(new_path):
                new_name = f"{invoice_number}_{counter}.pdf"
                new_path = os.path.join(output_dir, new_name)
                counter += 1

            shutil.copy2(pdf_path, new_path)
            logger.info(f"成功重命名: {filename} -> {new_name}")
            return True

        except Exception as e:
            logger.error(f"处理文件失败: {filename}\n错误: {str(e)}")
            return False

    def process_batch(self, input_dir: str, output_dir: str) -> dict:
        """批量处理PDF文件"""
        pdf_files = [
            os.path.join(input_dir, f)
            for f in os.listdir(input_dir)
            if f.lower().endswith(".pdf")
        ]

        if not pdf_files:
            logger.warning("输入目录中没有找到PDF文件")
            return {"total": 0, "success": 0, "failed": 0}

        os.makedirs(output_dir, exist_ok=True)
        results = {"total": len(pdf_files), "success": 0, "failed": 0}

        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n处理进度: {i}/{results['total']}")
            if self.process_single_pdf(pdf_path, output_dir):
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(f"\n处理完成! 成功: {results['success']}, 失败: {results['failed']}")
        return results


# 全局配置
POPPLER_PATH = r"D:\poppler-24.08.0\Library\bin"  # 修改为您的实际路径

if __name__ == "__main__":
    # 调试模式下的直接运行
    processor = PDFInvoiceRenamer(debug=True)

    # GUI兼容性测试
    test_pdf = "test.pdf"
    if os.path.exists(test_pdf):
        print("GUI兼容性测试结果:", processor.process_pdf(test_pdf))

    # 命令行模式测试
    processor.process_batch("pdf_input", "pdf_output")
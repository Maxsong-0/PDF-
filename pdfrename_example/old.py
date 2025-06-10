import easyocr
import cv2
import re
import numpy as np
import pdf2image
import os
import logging
import shutil
from typing import Optional

# 设置参数
PDF_INPUT_DIR = "pdf_input"
PDF_OUTPUT_DIR = "pdf_output"
DEBUG_OUTPUT_DIR = "debug_output"
POPPLER_PATH = r"D:\poppler-24.08.0\Library\bin"  # 改为你的 Poppler 安装路径
SAVE_DEBUG_IMAGES = False  # 设置为 False 可关闭中间图像输出

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

class PDFInvoiceRenamer:
    def __init__(self):
        self.reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        self.pattern = re.compile(r'\d{3,4}-\d{6,12}')
        if SAVE_DEBUG_IMAGES:
            os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
        os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

    def pdf_to_image(self, pdf_path: str) -> Optional[np.ndarray]:
        """提取PDF第一页图像"""
        try:
            pil_images = pdf2image.convert_from_path(
                pdf_path,
                dpi=300,
                first_page=1,
                last_page=1,
                poppler_path=POPPLER_PATH,
                thread_count=4
            )
            return cv2.cvtColor(np.array(pil_images[0]), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.warning(f"❌ 无法读取PDF: {pdf_path}，错误: {e}")
            return None

    def rotate_image(self, img: np.ndarray, angle: int) -> np.ndarray:
        if angle == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img

    def auto_rotate(self, img: np.ndarray, file_id: str = "") -> np.ndarray:
        best_angle = 0
        best_conf = 0
        best_img = img

        for angle in [0, 90, 180, 270]:
            rotated = self.rotate_image(img, angle)
            results = self.reader.readtext(rotated, paragraph=False)
            conf = np.mean([res[2] for res in results]) if results else 0
            if conf > best_conf:
                best_conf = conf
                best_angle = angle
                best_img = rotated

        if SAVE_DEBUG_IMAGES:
            cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, f"{file_id}_rotated_{best_angle}.jpg"), best_img)
        return best_img

    def extract_invoice_number(self, img: np.ndarray, file_id: str = "") -> Optional[str]:
        h, w = img.shape[:2]
        top_region = img[:int(h * 0.4), :]

        if SAVE_DEBUG_IMAGES:
            cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, f"{file_id}_top.jpg"), top_region)

        results = self.reader.readtext(top_region, paragraph=False)
        for i, (_, text, _) in enumerate(results):
            clean = text.replace(" ", "").replace(":", "").replace("：", "")
            if "销货出库单号" in clean:
                for j in range(i + 1, min(i + 4, len(results))):
                    maybe_number = results[j][1].replace(" ", "")
                    if match := self.pattern.search(maybe_number):
                        return match.group()
            if match := self.pattern.search(clean):
                return match.group()
        return None

    def process_single_pdf(self, pdf_path: str, index: int, total: int):
        filename = os.path.basename(pdf_path)
        file_id = os.path.splitext(filename)[0]
        logger.info(f"[{index}/{total}] 正在处理：{filename}")

        img = self.pdf_to_image(pdf_path)
        if img is None:
            return

        if SAVE_DEBUG_IMAGES:
            cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, f"{file_id}_original.jpg"), img)

        rotated_img = self.auto_rotate(img, file_id=file_id)
        invoice_number = self.extract_invoice_number(rotated_img, file_id=file_id)

        if invoice_number:
            new_name = f"{invoice_number}.pdf"
            new_path = os.path.join(PDF_OUTPUT_DIR, new_name)
            shutil.copy2(pdf_path, new_path)
            logger.info(f"✅ 成功识别并保存为: {new_name}")
        else:
            logger.warning(f"⚠️ 无法识别出库单号，文件跳过：{filename}")

    def process_all(self):
        pdf_files = [os.path.join(PDF_INPUT_DIR, f)
                     for f in os.listdir(PDF_INPUT_DIR)
                     if f.lower().endswith(".pdf")]
        total = len(pdf_files)

        if total == 0:
            logger.info("❗ 未找到任何 PDF 文件")
            return

        logger.info(f"📄 开始批量处理 {total} 个 PDF 文件...\n")
        for i, pdf_path in enumerate(pdf_files, 1):
            self.process_single_pdf(pdf_path, i, total)

        logger.info("\n✅ 全部处理完成！")

if __name__ == "__main__":
    processor = PDFInvoiceRenamer()
    processor.process_all()

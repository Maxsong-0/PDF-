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

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


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

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

class PDFProcessor:
    def __init__(self):
        self.patterns = [
            r'销货出库单号[：:\s]*([A-Za-z0-9\-_]+)',
            r'出库单号[：:\s]*([A-Za-z0-9\-_]+)',
            r'单号[：:\s]*([A-Za-z0-9\-_]+)',
            r'订单号[：:\s]*([A-Za-z0-9\-_]+)',
            r'SO[：:\s]*([A-Za-z0-9\-_]+)',
        ]
        
    def extract_order_number(self, pdf_path: str) -> Tuple[Optional[str], str]:
        """从PDF中提取销货出库单号，返回(订单号, 处理日志) - 云端演示版"""
        log_messages = []
        
        try:
            filename = os.path.basename(pdf_path)
            log_messages.append("✅ PDF文件上传成功")
            
            if "test" in filename.lower() or "demo" in filename.lower():
                demo_order = "SO2024001"
                log_messages.append("🎯 演示模式激活")
                log_messages.append(f"✅ 模拟识别订单号: {demo_order}")
                log_messages.append("")
                log_messages.append("📋 演示处理流程：")
                log_messages.append("• 文件上传检测 ✓")
                log_messages.append("• PDF内容解析 ✓") 
                log_messages.append("• OCR文字识别 ✓")
                log_messages.append("• 订单号模式匹配 ✓")
                log_messages.append("• 文件重命名准备 ✓")
                log_messages.append("")
                log_messages.append("💡 演示说明：")
                log_messages.append("• 这是云端演示版本的模拟处理")
                log_messages.append("• 完整OCR功能请使用本地部署版本")
                log_messages.append("• 本地版本支持真实PDF文档识别")
                return demo_order, "\n".join(log_messages)
            
            log_messages.append("⚠️ 云端演示版本限制：")
            log_messages.append("• 由于云平台内存限制，无法加载OCR库")
            log_messages.append("• 本版本仅展示WebUI界面和交互流程")
            log_messages.append("• 完整功能请下载本地部署版本使用")
            log_messages.append("")
            log_messages.append("🔧 体验演示功能：")
            log_messages.append("• 上传文件名包含'test'或'demo'的PDF")
            log_messages.append("• 例如：test_order.pdf, demo_file.pdf")
            log_messages.append("• 演示模式将模拟完整的处理流程")
            
            return None, "\n".join(log_messages)
            
        except Exception as e:
            error_msg = f"❌ 处理失败: {str(e)}"
            log_messages.append(error_msg)
            logger.error(error_msg)
            return None, "\n".join(log_messages)
    
    def find_order_number_in_text(self, text: str) -> Optional[str]:
        """在文本中查找销货出库单号"""
        for pattern in self.patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None
    
    def detect_text_orientation(self, image) -> float:
        """简化的文本方向检测 - 移除opencv依赖"""
        return 0
    
    def extract_with_ocr(self, pdf_path: str) -> Tuple[Optional[str], List[str]]:
        """OCR功能在云端演示版本中不可用"""
        return None, ["⚠️ OCR功能在云端演示版本中不可用"]
    
    def clean_filename(self, order_number: str) -> str:
        """清理文件名，移除特殊字符"""
        return re.sub(r'[<>:"/\\|?*]', '_', order_number)

processor = PDFProcessor()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传并处理PDF文件"""
    if not files:
        raise HTTPException(status_code=400, detail="没有上传文件")
    
    results = []
    processed_files = []
    
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            results.append({
                "filename": file.filename,
                "success": False,
                "message": "❌ 不是PDF文件",
                "log": "文件格式不支持"
            })
            continue
        
        try:
            upload_path = f"uploads/{file.filename}"
            with open(upload_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            order_number, log = processor.extract_order_number(upload_path)
            
            if order_number:
                clean_order = processor.clean_filename(order_number)
                new_filename = f"{clean_order}.pdf"
                
                counter = 1
                output_path = f"downloads/{new_filename}"
                while os.path.exists(output_path):
                    new_filename = f"{clean_order}_{counter}.pdf"
                    output_path = f"downloads/{new_filename}"
                    counter += 1
                
                import shutil
                shutil.copy2(upload_path, output_path)
                
                processed_files.append(new_filename)
                
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "message": f"✅ 成功识别订单号: {order_number}",
                    "new_filename": new_filename,
                    "log": log
                })
            else:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": "❌ 未找到销货出库单号",
                    "log": log
                })
            
            os.remove(upload_path)
            
            import gc
            gc.collect()
            
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "message": f"❌ 处理失败: {str(e)}",
                "log": f"系统错误: {str(e)}"
            })
            import gc
            gc.collect()
    
    return JSONResponse({
        "results": results,
        "processed_files": processed_files,
        "download_available": len(processed_files) > 0
    })

@app.get("/download")
async def download_files():
    """下载处理后的文件"""
    download_dir = Path("downloads")
    files = list(download_dir.glob("*.pdf"))
    
    if not files:
        raise HTTPException(status_code=404, detail="没有可下载的文件")
    
    if len(files) == 1:
        return FileResponse(
            files[0],
            media_type="application/pdf",
            filename=files[0].name
        )
    else:
        zip_path = "downloads/renamed_pdfs.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in files:
                zipf.write(file, file.name)
        
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename="renamed_pdfs.zip"
        )

@app.post("/clear")
async def clear_files():
    """清理下载目录"""
    download_dir = Path("downloads")
    for file in download_dir.glob("*"):
        if file.is_file():
            os.remove(file)
    
    return JSONResponse({"message": "✅ 文件已清理"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

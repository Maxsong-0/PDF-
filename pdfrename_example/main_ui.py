import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ocr_rename import PDFInvoiceRenamer

class PDFOCRApp:
    def __init__(self, master):
        self.master = master
        master.title("PDF 出库单号识别与重命名工具")
        master.geometry("600x300")

        self.pdf_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.save_debug = tk.BooleanVar(value=True)

        # UI布局
        self.create_widgets()

    def create_widgets(self):
        padding = {'padx': 10, 'pady': 10}

        tk.Label(self.master, text="📂 PDF 文件夹:").grid(row=0, column=0, sticky='w', **padding)
        tk.Entry(self.master, textvariable=self.pdf_folder, width=50).grid(row=0, column=1, **padding)
        tk.Button(self.master, text="浏览", command=self.browse_pdf_folder).grid(row=0, column=2, **padding)

        tk.Label(self.master, text="📁 输出文件夹:").grid(row=1, column=0, sticky='w', **padding)
        tk.Entry(self.master, textvariable=self.output_folder, width=50).grid(row=1, column=1, **padding)
        tk.Button(self.master, text="浏览", command=self.browse_output_folder).grid(row=1, column=2, **padding)

        tk.Checkbutton(self.master, text="保存中间调试图像", variable=self.save_debug).grid(row=2, column=1, sticky='w', **padding)

        self.progress = ttk.Progressbar(self.master, mode='determinate', length=400)
        self.progress.grid(row=3, column=1, columnspan=2, **padding)

        self.status = tk.Label(self.master, text="等待操作", fg="blue")
        self.status.grid(row=4, column=1, columnspan=2, **padding)

        tk.Button(self.master, text="开始处理", command=self.start_processing, bg="#4CAF50", fg="white").grid(row=5, column=1, **padding)

    def browse_pdf_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.pdf_folder.set(folder)

    def browse_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def start_processing(self):
        thread = threading.Thread(target=self.process_pdfs)
        thread.start()

    def process_pdfs(self):
        input_dir = self.pdf_folder.get()
        output_dir = self.output_folder.get()
        debug_dir = "debug_output"
        save_debug = self.save_debug.get()

        if not input_dir or not output_dir:
            messagebox.showerror("错误", "请选择输入和输出文件夹！")
            return

        pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
        total = len(pdf_files)
        if total == 0:
            messagebox.showwarning("无文件", "输入文件夹中没有 PDF 文件！")
            return

        self.progress["maximum"] = total
        self.status.config(text="正在处理...")
        ocr_engine = PDFInvoiceRenamer(debug=save_debug, debug_folder=debug_dir)

        for i, pdf in enumerate(pdf_files):
            src_path = os.path.join(input_dir, pdf)
            try:
                numbers = ocr_engine.process_pdf(src_path)
                new_name = numbers[0] + ".pdf" if numbers else f"未识别_{i+1}.pdf"
                dst_path = os.path.join(output_dir, new_name)
                shutil.copy(src_path, dst_path)
                self.status.config(text=f"完成 {i+1}/{total}: {new_name}")
            except Exception as e:
                self.status.config(text=f"错误处理 {pdf}: {e}")

            self.progress["value"] = i + 1

        self.status.config(text="全部完成！")
        messagebox.showinfo("完成", f"共处理 {total} 个PDF文件！")


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFOCRApp(root)
    root.mainloop()

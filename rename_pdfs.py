import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from pdf2image import convert_from_path
    import pytesseract
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e.name}. Please install required packages.")

# Regular expression to capture the sales order number after the keyword
NUMBER_RE = re.compile(r"销货出库单号[:：]?\s*(\S+)")


def extract_order_number(pdf_path):
    """Extract the order number from a scanned PDF using OCR."""
    text = []
    try:
        # Convert all pages to images
        pages = convert_from_path(pdf_path)
    except Exception as e:
        print(f"Failed to open {pdf_path}: {e}")
        return None

    for img in pages:
        try:
            ocr_result = pytesseract.image_to_string(img, lang="chi_sim")
        except pytesseract.TesseractError as e:
            print(f"OCR error in {pdf_path}: {e}")
            return None
        text.append(ocr_result)

    joined = "\n".join(text)
    match = NUMBER_RE.search(joined)
    if match:
        return match.group(1)
    return None


def rename_pdf(pdf_path, new_name):
    directory = os.path.dirname(pdf_path)
    target = os.path.join(directory, f"{new_name}.pdf")
    # Avoid overwriting existing files
    if os.path.abspath(pdf_path) == os.path.abspath(target):
        return True
    counter = 1
    base_target = target
    while os.path.exists(target):
        target = os.path.join(directory, f"{new_name}_{counter}.pdf")
        counter += 1
    try:
        os.rename(pdf_path, target)
        return True
    except Exception as e:
        print(f"Failed to rename {pdf_path}: {e}")
        return False


def process_files(files, status_var):
    success = 0
    for idx, pdf in enumerate(files, 1):
        status_var.set(f"Processing {idx}/{len(files)}: {os.path.basename(pdf)}")
        root.update_idletasks()
        new_name = extract_order_number(pdf)
        if new_name:
            if rename_pdf(pdf, new_name):
                success += 1
        else:
            print(f"No order number found in {pdf}")
    status_var.set(f"Completed. Renamed {success}/{len(files)} files.")


def select_files():
    files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
    if not files:
        return
    process_files(files, status_var)
    messagebox.showinfo("Finished", status_var.get())


root = tk.Tk()
root.title("PDF Batch Renamer")
root.resizable(False, False)

frame = tk.Frame(root, padx=20, pady=20)
frame.pack()

select_btn = tk.Button(frame, text="Select PDFs", command=select_files)
select_btn.pack(pady=(0, 10))

status_var = tk.StringVar(value="Ready")
status_label = tk.Label(frame, textvariable=status_var, width=40, anchor="w")
status_label.pack()

root.mainloop()

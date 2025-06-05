# PDF Batch Renamer

A simple GUI tool for batch renaming scanned PDF files based on the text "销货出库单号" extracted via OCR.

## Features

- Select multiple PDF files and automatically rename them using the extracted order number.
- Displays processing progress and summary of renamed files.
- Keeps the original file when no order number is detected.

## Requirements

- Python 3.8 or later
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and available in `PATH`.
- Python packages:
  - `pytesseract`
  - `pdf2image`
  - `tk`

Install dependencies with pip:

```bash
pip install pytesseract pdf2image
```

On Windows or macOS you may need to install [Poppler](https://github.com/oschwartz10612/poppler-windows) for `pdf2image` to work.

## Usage

Run the application and choose the PDF files to rename:

```bash
python rename_pdfs.py
```

A window will open allowing you to select one or more PDF files. The tool will attempt to read the text within each file and rename it using the detected `销货出库单号` value.

If no order number is found, the file is left unchanged and a message is printed in the console.

## Notes

The OCR accuracy depends on the quality of your scanned PDFs. Ensure that Tesseract and the Chinese language data (`chi_sim`) are installed for best results.

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


def detect_format(file_bytes: bytes, filename: str) -> str:
    """Detect the file format from bytes and filename."""
    ext = filename.lower().split(".")[-1]
    if ext in ("xlsx", "xls", "csv"):
        return "excel"
    if ext == "docx":
        return "docx"
    if ext == "pdf":
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if len(doc) == 0:
                return "pdf_digital"
            text = doc[0].get_text()
            doc.close()
            return "pdf_scanned" if len(text.strip()) < 100 else "pdf_digital"
        except Exception as e:
            logger.warning(f"Error detecting PDF format: {e}")
            return "pdf_digital"
    return "pdf_digital"


def extract_pdf_text(file_bytes: bytes, file_format: str) -> str:
    """Extract text from a PDF file, using OCR if scanned."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    texts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        if file_format == "pdf_digital":
            text = page.get_text()
            texts.append(text)
        else:
            # OCR for scanned PDFs
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img)
            texts.append(text)

    doc.close()
    return "\n\n".join(texts)

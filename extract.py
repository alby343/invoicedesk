import os
import re
import pdfplumber
import pytesseract
from PIL import Image, ImageOps

# Windows only: tell Python where Tesseract was installed. On a Linux server this path doesn't exist, so it is skipped.
WIN_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(WIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = WIN_TESSERACT


IMAGE_TYPES = (".jpg", ".jpeg", ".png")


def ocr_image(image):
    """Clean up a photo a little, then read it with Tesseract."""
    image = ImageOps.exif_transpose(image)        # phones store rotation in a tag; apply it
    image = ImageOps.grayscale(image)             # colour only adds noise for OCR
    image = ImageOps.autocontrast(image)          # stretch dark/washed-out photos
    if image.width < 1600:                        # small images OCR badly; enlarge them
        scale = 1600 / image.width
        image = image.resize((1600, int(image.height * scale)))
    return pytesseract.image_to_string(image, config="--psm 6")


def read_text(path):
    """Return the invoice text from a PDF (text layer, else OCR) or from a photo (OCR)."""
    if str(path).lower().endswith(IMAGE_TYPES):
        return ocr_image(Image.open(path))
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""
        if len(text.strip()) >= 40:
            return text
        image = page.to_image(resolution=200).original   # render the page as a picture
        return pytesseract.image_to_string(image, config="--psm 6")


def find(patterns, text):
    """Try each pattern in order. Return the first captured value, or None."""
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def to_number(s):
    return float(s.replace(",", "")) if s else None


def find_bank_last4(text):
    acct = find([r"(?:Account|Acct|A/C)\s*(?:No\b\.?|Number|#)?\s*:?\s*([\d -]{6,})"], text)
    digits = re.sub(r"\D", "", acct) if acct else ""
    return digits[-4:] if digits else None


def extract_fields(text):
    return {
        "invoice_no": find([r"(?:Invoice|Inv\.?)\s*(?:No\b\.?|Number|#)\s*:?\s*(\S+)"], text),
        "po": find([r"\b(PO-\d+)\b"], text),
        "bank_last4": find_bank_last4(text),
        "subtotal": to_number(find([r"(?:Sub-?\s?total|Net Amount)\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
        "tax": to_number(find([r"(?:Sales\s+Tax|VAT|GST|Tax)\s*(?:\([^)]*\))?\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
        "total": to_number(find([r"(?:Total Due|Amount Due|Grand Total)\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
    }
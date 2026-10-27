import re
import pdfplumber


def read_text(path):
    with pdfplumber.open(path) as pdf:
        return pdf.pages[0].extract_text() or ""


def find(patterns, text):
    """Try each pattern in order. Return the first captured value, or None."""
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def to_number(s):
    return float(s.replace(",", "")) if s else None


def extract_fields(text):
    return {
        "invoice_no": find([r"(?:Invoice|Inv\.?)\s*(?:No\b\.?|Number|#)\s*:?\s*(\S+)"], text),
        "po": find([r"\b(PO-\d+)\b"], text),
        "total": to_number(find([r"(?:Total Due|Amount Due|Grand Total)\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
    }


for name in ["01_clean_happy_path.pdf", "02_within_tolerance.pdf", "06_scanned_image_only.pdf"]:
    text = read_text("samples/" + name)
    print(name, extract_fields(text))
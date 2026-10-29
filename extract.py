import csv
import email
import os
import re
import tempfile
from email import policy
import pdfplumber
import pytesseract
from PIL import Image, ImageOps

# Windows only: tell Python where Tesseract was installed. On a Linux server this path doesn't exist, so it is skipped.
WIN_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(WIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = WIN_TESSERACT


IMAGE_TYPES = (".jpg", ".jpeg", ".png")
SHEET_TYPES = (".csv", ".xlsx")
ATTACHMENT_TYPES = (".pdf",) + IMAGE_TYPES + SHEET_TYPES
INVOICE_NO_PATTERN = r"(?:Invoice|Inv\.?)\s*(?:No\b\.?|Number|#)\s*:?\s*(\S+)"


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


def page_text(page):
    """Text of one PDF page: the text layer, or OCR when the page is only a picture."""
    text = page.extract_text() or ""
    if len(text.strip()) >= 40:
        return text
    return pytesseract.image_to_string(page.to_image(resolution=200).original, config="--psm 6")


def pdf_documents(path):
    """Return a list of texts, one per invoice. A PDF may hold several invoices back to back.

    A page that shows an invoice number different from the one before it starts a new invoice.
    A page with no invoice number (for example 'page 2 of 2') belongs to the invoice before it.
    """
    groups = []          # each item: [invoice_number_or_None, [page texts]]
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page_text(page)
            number = find([INVOICE_NO_PATTERN], text)
            if groups and (number is None or number == groups[-1][0]):
                groups[-1][1].append(text)          # continuation of the current invoice
                if groups[-1][0] is None:
                    groups[-1][0] = number
            else:
                groups.append([number, [text]])     # a new invoice starts here
    return ["\n".join(pages) for _, pages in groups] or [""]


# ---- Spreadsheets -------------------------------------------------------------------------------

# Column header words -> the label the extractor already understands.
COLUMN_LABELS = [
    ("vendor",   ("vendor", "supplier", "company")),
    ("subtotal", ("subtotal", "sub-total", "net")),
    ("tax",      ("tax", "vat", "gst")),
    ("total",    ("total", "amount")),
    ("po",       ("po", "purchase")),
    ("bank",     ("bank", "account")),
    ("invoice",  ("invoice",)),
]


def cell_text(value):
    """A spreadsheet cell as text. Numbers get two decimals so '4752' reads like '4,752.00'."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value).strip()


def money(value):
    """'5400' or '$5,400' -> '5,400.00', so the amount patterns can read it. Anything else is left alone."""
    try:
        return f"{float(value.replace('$', '').replace(',', '')):,.2f}"
    except ValueError:
        return value


def read_rows(path):
    """All rows of a CSV or XLSX file as lists of text cells (first sheet only)."""
    if str(path).lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            return [[c.strip() for c in row] for row in csv.reader(f)]
    import openpyxl
    sheet = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    return [[cell_text(c) for c in row] for row in sheet.iter_rows(values_only=True)]


def label_for(header):
    h = header.strip().lower()
    for label, words in COLUMN_LABELS:
        if any(w in h.split() or (len(w) > 3 and w in h) for w in words):
            return label
    return None


def sheet_documents(path):
    """One text per invoice. A table with one invoice per row gives one text per row.
    A sheet laid out like a single invoice (label in one cell, value in the next) gives one text."""
    rows = [r for r in read_rows(path) if any(c for c in r)]
    if not rows:
        return [""]
    labels = [label_for(c) for c in rows[0]]
    if "invoice" in labels and "total" in labels and len(rows) > 1:        # table mode
        texts = []
        for row in rows[1:]:
            data = {}
            for label, value in zip(labels, row):
                if label and value and label not in data:
                    data[label] = money(value) if label in ("subtotal", "tax", "total") else value
            lines = [data.get("vendor", "")]
            for label, text_label in (("invoice", "Invoice No"), ("po", "PO Number"), ("subtotal", "Subtotal"),
                                      ("tax", "Sales Tax"), ("total", "Total Due"), ("bank", "Account No")):
                if label in data:
                    lines.append(f"{text_label}: {data[label]}")
            texts.append("\n".join(l for l in lines if l))
        return texts
    lines = []                                                              # single-invoice mode
    for row in rows:
        cells = [c for c in row if c]
        if len(cells) == 2 and label_for(cells[0]) in ("subtotal", "tax", "total"):
            cells[1] = money(cells[1])
        lines.append(": ".join(cells) if len(cells) == 2 else " ".join(cells))
    return ["\n".join(lines)]


# ---- Emails -------------------------------------------------------------------------------------

def email_documents(path):
    """Read a saved email (.eml). Invoices attached to it are read like any other file;
    if nothing is attached, the body of the email is treated as the invoice."""
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    texts = []
    with tempfile.TemporaryDirectory() as folder:
        for part in msg.iter_attachments():
            name = os.path.basename(part.get_filename() or "")
            if name.lower().endswith(ATTACHMENT_TYPES):
                saved = os.path.join(folder, name)
                with open(saved, "wb") as out:
                    out.write(part.get_payload(decode=True))
                texts += read_documents(saved)
    if texts:
        return texts
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    if body is not None and body.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", "\n", text)                                # crude: drop the tags
    return [text]


def read_documents(path):
    """Return a list of texts, one per invoice, whatever the file type."""
    name = str(path).lower()
    if name.endswith(IMAGE_TYPES):
        return [ocr_image(Image.open(path))]
    if name.endswith(SHEET_TYPES):
        return sheet_documents(path)
    if name.endswith(".eml"):
        return email_documents(path)
    return pdf_documents(path)


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
        "invoice_no": find([INVOICE_NO_PATTERN], text),
        "po": find([r"\b(PO-\d+)\b"], text),
        "bank_last4": find_bank_last4(text),
        "subtotal": to_number(find([r"(?:Sub-?\s?total|Net Amount)\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
        "tax": to_number(find([r"(?:Sales\s+Tax|VAT|GST|Tax)\s*(?:\([^)]*\))?\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
        "total": to_number(find([r"(?:Total Due|Amount Due|Grand Total)\s*:?\s*\$?([\d,]+\.\d{2})"], text)),
    }

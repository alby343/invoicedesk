import re
import pdfplumber

with pdfplumber.open("samples/01_clean_happy_path.pdf") as pdf:
    text = pdf.pages[0].extract_text()

invoice_no = re.search(r"Invoice No:\s*(\S+)", text)
po = re.search(r"PO Number:\s*(\S+)", text)
total = re.search(r"Total Due\s*\$([\d,]+\.\d{2})", text)

print(invoice_no.group(1))
print(po.group(1))
print(total.group(1))

total_value = float(total.group(1).replace(",", ""))
print(total_value)
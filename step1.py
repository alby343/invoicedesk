import pdfplumber

with pdfplumber.open("samples/01_clean_happy_path.pdf") as pdf:
    text = pdf.pages[0].extract_text()

print(text)
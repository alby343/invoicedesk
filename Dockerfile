FROM python:3.12-slim

# Tesseract is the OCR engine used for scanned invoices
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8000
# One worker (the run history lives in one SQLite file); threads keep the live streaming responsive.
CMD gunicorn -k gthread --threads 8 -w 1 --timeout 180 -b 0.0.0.0:$PORT app:app

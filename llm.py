import json
import os
import urllib.request

BASE = os.environ.get("GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta")

PROMPT = """You read invoices. Return ONE JSON object with exactly these keys:
invoice_no, po, subtotal, tax, total, bank_last4.
Rules:
- subtotal, tax and total are plain numbers (no currency symbols, no thousands commas).
- po looks like PO-1234 and must appear in the text.
- bank_last4 is the last 4 digits of the bank account number.
- Use null for anything that is not explicitly written in the text. Never guess and never calculate.

Invoice text:
"""


def ai_available():
    return bool(os.environ.get("GEMINI_API_KEY"))


def ai_extract(text):
    """Ask Gemini to read the invoice. Returns a dict, or None if there is no key or anything fails."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    body = json.dumps({
        "contents": [{"parts": [{"text": PROMPT + text[:6000]}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/models/{model}:generateContent", data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:                       # the process must never break because the AI did
        print("AI extraction failed:", repr(e))
        return None
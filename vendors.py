import csv
import difflib
import re

LOOKALIKE_THRESHOLD = 0.85   # names this similar (but not equal) to an approved vendor are suspicious


def load_vendors(path):
    vendors = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            vendors[row["vendor_id"]] = row
    return vendors


def norm(s):
    """Lowercase and keep only letters and digits: 'INV-2041' and 'INV2041' both become 'inv2041'."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def identify_vendor(text, vendors):
    """Work out who sent the invoice. Returns {status, vendor, raw_name, ratio}.
    status: 'approved' (exact name found), 'lookalike' (almost an approved name), or 'unknown'."""
    t = norm(text)
    for v in vendors.values():
        if norm(v["name"]) in t:
            return {"status": "approved", "vendor": v, "raw_name": v["name"], "ratio": 1.0}

    # No exact match: compare the first few lines (where the sender's name sits) with every approved name.
    lines = [l.strip() for l in text.splitlines() if l.strip() and "invoice" not in l.lower()][:5]
    best = {"ratio": 0.0, "vendor": None, "raw_name": lines[0] if lines else None}
    for line in lines:
        for v in vendors.values():
            ratio = difflib.SequenceMatcher(None, norm(line), norm(v["name"])).ratio()
            if ratio > best["ratio"]:
                best = {"ratio": ratio, "vendor": v, "raw_name": line}
    status = "lookalike" if best["ratio"] >= LOOKALIKE_THRESHOLD else "unknown"
    return {"status": status, "vendor": best["vendor"] if status == "lookalike" else None,
            "raw_name": best["raw_name"], "ratio": round(best["ratio"], 2)}
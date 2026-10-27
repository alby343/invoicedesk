from extract import read_text, extract_fields
from loaders import load_pos

# ---- Policy: the business rules, in one place ----
TOLERANCE_PCT = 2        # over the PO by up to 2%  -> still fine
REVIEW_CEILING_PCT = 10  # over by 2%-10%           -> a human must look; above 10% -> reject

SEVERITY = {"ok": 0, "info": 1, "review": 2, "hold": 3, "reject": 4}
DECISION = {0: "APPROVE", 1: "APPROVE", 2: "REVIEW", 3: "HOLD", 4: "REJECT"}


def finding(severity, code, message):
    return {"severity": severity, "code": code, "message": message}


def check_missing(fields):
    findings = []
    for key, label in [("invoice_no", "invoice number"), ("total", "total amount")]:
        if fields[key] is None:
            findings.append(finding("hold", "MISSING_" + key.upper(), f"The invoice has no {label}."))
    return findings


def check_po(fields, pos):
    if fields["po"] is None:
        return [finding("review", "NO_PO", "No PO number on the invoice.")]
    if fields["po"] not in pos:
        return [finding("review", "PO_NOT_FOUND", f"{fields['po']} is not in the system.")]
    return [finding("ok", "PO_FOUND", f"{fields['po']} exists.")]


def check_amount(fields, pos):
    po = pos.get(fields["po"])
    if po is None or fields["total"] is None:
        return []  # nothing to compare yet; other checks already report why
    over = fields["total"] - po["amount"]
    pct = over / po["amount"] * 100
    if over <= 0:
        return [finding("ok", "WITHIN_PO", "Invoice is within the PO amount.")]
    if pct <= TOLERANCE_PCT:
        return [finding("info", "WITHIN_TOLERANCE", f"Over the PO by {over:.2f} ({pct:.1f}%), inside the {TOLERANCE_PCT}% tolerance.")]
    if pct <= REVIEW_CEILING_PCT:
        return [finding("review", "OVER_PO", f"Over the PO by {over:.2f} ({pct:.1f}%), above tolerance.")]
    return [finding("reject", "OVER_PO_HARD", f"Over the PO by {over:.2f} ({pct:.1f}%), far above tolerance.")]


def decide(findings):
    worst = max((SEVERITY[f["severity"]] for f in findings), default=0)
    return DECISION[worst]


pos = load_pos("data/pos.csv")

for name in ["01_clean_happy_path.pdf", "02_within_tolerance.pdf", "06_scanned_image_only.pdf"]:
    fields = extract_fields(read_text("samples/" + name))
    findings = check_missing(fields) + check_po(fields, pos) + check_amount(fields, pos)
    print(name, "->", decide(findings))
    for f in findings:
        print("   ", f["severity"].upper(), "-", f["message"])
    print()
# ---- Policy: the business rules, in one place ----
TOLERANCE_PCT = 2
REVIEW_CEILING_PCT = 10

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
        return []
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


def check_vendor(info, fields):
    vendor = info["vendor"]
    if info["status"] == "lookalike":
        msg = (f"'{info['raw_name']}' is not an approved vendor but is {int(info['ratio'] * 100)}% similar to "
               f"'{vendor['name']}'. Possible impersonation.")
        if fields["bank_last4"] and fields["bank_last4"] != vendor["bank_last4"]:
            msg += f" Its bank account (...{fields['bank_last4']}) also differs from the real vendor's (...{vendor['bank_last4']})."
        return [finding("reject", "LOOKALIKE", msg)]
    if info["status"] == "unknown":
        return [finding("review", "VENDOR_UNKNOWN", f"'{info['raw_name']}' is not in the approved vendor list.")]
    out = [finding("ok", "VENDOR_OK", f"Approved vendor: {vendor['name']}")]
    if fields["bank_last4"]:
        if fields["bank_last4"] != vendor["bank_last4"]:
            out.append(finding("review", "BANK_MISMATCH",
                               f"Bank account on the invoice (...{fields['bank_last4']}) differs from the one on file (...{vendor['bank_last4']})."))
        else:
            out.append(finding("ok", "BANK_OK", "Bank account matches the vendor record."))
    return out


def check_duplicate(prior):
    if prior is None:
        return [finding("ok", "NO_DUPLICATE", "No earlier invoice with this number from this vendor.")]
    return [finding("reject", "DUPLICATE",
                    f"Invoice {prior['invoice_no']} from this vendor was already processed (run #{prior['id']}, {prior['decision']}).")]

def check_balance(fields, pos, already_billed):
    """Compare the invoice with what is LEFT on the PO, not the whole PO."""
    po = pos.get(fields["po"])
    if po is None or fields["total"] is None:
        return []
    remaining = round(po["amount"] - already_billed, 2)
    over = round(fields["total"] - remaining, 2)
    pct = over / po["amount"] * 100
    if over <= 0:
        left = remaining - fields["total"]
        note = f"PO is fully invoiced." if left < 0.005 else f"{left:,.2f} will remain on {po['po_number']}."
        return [finding("ok", "WITHIN_BALANCE", f"Invoice {fields['total']:,.2f} fits the remaining balance of {remaining:,.2f}. {note}")]
    if pct <= TOLERANCE_PCT:
        return [finding("info", "WITHIN_TOLERANCE", f"Over the remaining balance ({remaining:,.2f}) by {over:,.2f} ({pct:.1f}% of the PO), inside the {TOLERANCE_PCT}% tolerance.")]
    if pct <= REVIEW_CEILING_PCT:
        return [finding("review", "OVER_PO", f"Over the remaining balance ({remaining:,.2f}) by {over:,.2f} ({pct:.1f}% of the PO).")]
    return [finding("reject", "OVER_PO_HARD", f"Over the remaining balance by {over:,.2f} ({pct:.1f}% of the PO). Only {remaining:,.2f} is left on {po['po_number']} after earlier invoices.")]

def check_math(fields):
    """Subtotal + tax must equal the total. Guards against typos and misread digits."""
    sub, tax, total = fields["subtotal"], fields["tax"], fields["total"]
    if total is None or sub is None or tax is None:
        return [finding("info", "NO_BREAKDOWN", "No subtotal/tax breakdown to check, so the arithmetic check was skipped.")]
    calc = round(sub + tax, 2)
    if abs(calc - total) > 0.01:
        return [finding("review", "MATH_MISMATCH",
                        f"Subtotal {sub:,.2f} + tax {tax:,.2f} = {calc:,.2f}, but the invoice states {total:,.2f} (difference {abs(calc - total):,.2f}).")]
    return [finding("ok", "MATH_OK", f"Subtotal {sub:,.2f} + tax {tax:,.2f} equals the stated total.")]
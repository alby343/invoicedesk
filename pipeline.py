from extract import read_documents, extract_fields
from loaders import load_pos
from vendors import load_vendors, identify_vendor, norm
import checks
import db
import llm

STAGE_NAMES = {
    "read": "Read document",
    "extract": "Extract fields",
    "validate": "Validate arithmetic",
    "vendor": "Verify vendor",
    "duplicate": "Duplicate check",
    "po": "Match purchase order",
    "amount": "Check amount",
    "decision": "Decide",
}


def stage_status(findings):
    """Worst severity of a stage's findings: ok, review, hold or reject."""
    worst = max((checks.SEVERITY[f["severity"]] for f in findings), default=0)
    return {0: "ok", 1: "ok", 2: "review", 3: "hold", 4: "reject"}[worst]


def event(stage, status, detail="", findings=None):
    return {"stage": stage, "title": STAGE_NAMES[stage], "status": status,
            "detail": detail, "findings": findings or []}


def process(path, filename):
    """Run a file through every stage. A PDF holding several invoices is processed one invoice at a time."""
    db.init_db()
    yield event("read", "running")
    texts = read_documents(path)
    for n, text in enumerate(texts, 1):
        if len(texts) > 1:
            yield {"stage": "batch", "index": n, "count": len(texts), "file": filename}
        label = filename if len(texts) == 1 else f"{filename} (invoice {n} of {len(texts)})"
        yield from process_one(text, label)


def process_one(text, filename):
    """Run one invoice's text through the checks. Yields an event as each stage starts and finishes."""
    pos = load_pos("data/pos.csv")
    vendors = load_vendors("data/vendors.csv")
    all_findings = []

    yield event("read", "ok", f"{len(text)} characters read")

    yield event("extract", "running")
    fields = extract_fields(text)

    # AI reads only what the rules could not find. The arithmetic check below then verifies the numbers.
    ai_filled = []
    gaps = [k for k in ("invoice_no", "po", "subtotal", "tax", "total") if fields[k] is None]
    if gaps and llm.ai_available():
        yield event("extract", "running", "Rules missed some fields. Asking the AI to read the document...")
        ai = llm.ai_extract(text) or {}
        for k in gaps:
            v = ai.get(k)
            if v in (None, ""):
                continue
            if k in ("subtotal", "tax", "total"):
                try:
                    v = float(str(v).replace(",", ""))
                except ValueError:
                    continue
            fields[k] = v
            ai_filled.append(k)

    f = checks.check_missing(fields)
    if ai_filled:
        f.append(checks.finding("info", "AI_EXTRACTED",
                                f"The AI read these fields because the rules could not: {', '.join(ai_filled)}. The arithmetic check verifies them."))
    all_findings += f
    shown = f"invoice {fields['invoice_no']}, PO {fields['po']}, total {fields['total']}"
    if ai_filled:
        shown += f"  [AI filled: {', '.join(ai_filled)}]"
    yield event("extract", stage_status(f), shown, f)

    yield event("validate", "running")
    f = checks.check_math(fields)
    all_findings += f
    yield event("validate", stage_status(f), f[0]["message"], f)

    yield event("vendor", "running")
    info = identify_vendor(text, vendors)
    vendor_id = info["vendor"]["vendor_id"] if info["status"] == "approved" else None
    f = checks.check_vendor(info, fields)
    all_findings += f
    yield event("vendor", stage_status(f), f[0]["message"], f)

    yield event("duplicate", "running")
    inv_key = norm(fields["invoice_no"])
    f = checks.check_duplicate(db.find_duplicate(vendor_id, inv_key))
    all_findings += f
    yield event("duplicate", stage_status(f), f[0]["message"], f)

    yield event("po", "running")
    f = checks.check_po(fields, pos)
    all_findings += f
    yield event("po", stage_status(f), f[0]["message"], f)

    yield event("amount", "running")
    f = checks.check_balance(fields, pos, db.consumed(fields["po"]))
    all_findings += f
    yield event("amount", stage_status(f), f[0]["message"] if f else "Skipped: nothing to compare", f)

    decision = checks.decide(all_findings)
    db.save_run(filename, vendor_id, fields, inv_key, decision, all_findings)
    problems = [x for x in all_findings if checks.SEVERITY[x["severity"]] >= 2]
    reason = problems[0]["message"] if problems else "All checks passed."
    yield {"stage": "decision", "title": STAGE_NAMES["decision"], "status": "final",
           "decision": decision, "detail": reason, "findings": all_findings}

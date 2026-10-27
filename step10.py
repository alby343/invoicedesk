from extract import read_text, extract_fields
from loaders import load_pos
from vendors import load_vendors, identify_vendor, norm
from checks import check_missing, check_po, check_balance, check_vendor, check_duplicate, decide
import db

db.init_db()
pos = load_pos("data/pos.csv")
vendors = load_vendors("data/vendors.csv")

for name in ["03_split_po_part1.pdf", "04_split_po_part2.pdf", "05_split_po_overbill.pdf"]:
    text = read_text("samples/" + name)
    fields = extract_fields(text)
    info = identify_vendor(text, vendors)
    vendor_id = info["vendor"]["vendor_id"] if info["status"] == "approved" else None
    inv_key = norm(fields["invoice_no"])

    prior = db.find_duplicate(vendor_id, inv_key)
    billed = db.consumed(fields["po"])
    findings = (check_missing(fields) + check_vendor(info, fields) + check_duplicate(prior)
                + check_po(fields, pos) + check_balance(fields, pos, billed))
    decision = decide(findings)
    db.save_run(name, vendor_id, fields, inv_key, decision, findings)

    print(name, "->", decision)
    for f in findings:
        print("   ", f["severity"].upper(), "-", f["message"])
    print()
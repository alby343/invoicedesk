from extract import read_text, extract_fields
from loaders import load_pos
from vendors import load_vendors, find_vendor, norm
from checks import check_missing, check_po, check_amount, check_vendor, check_duplicate, decide
import db

db.init_db()
pos = load_pos("data/pos.csv")
vendors = load_vendors("data/vendors.csv")

for name in ["01_clean_happy_path.pdf", "07_duplicate_resubmission.pdf"]:
    text = read_text("samples/" + name)
    fields = extract_fields(text)
    vendor = find_vendor(text, vendors)
    vendor_id = vendor["vendor_id"] if vendor else None
    inv_key = norm(fields["invoice_no"])

    prior = db.find_duplicate(vendor_id, inv_key)
    findings = (check_missing(fields) + check_vendor(vendor) + check_duplicate(prior)
                + check_po(fields, pos) + check_amount(fields, pos))
    decision = decide(findings)
    db.save_run(name, vendor_id, fields, inv_key, decision, findings)

    print(name, "->", decision)
    for f in findings:
        print("   ", f["severity"].upper(), "-", f["message"])
    print()
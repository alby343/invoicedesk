from extract import read_text, extract_fields
from loaders import load_pos
from checks import check_missing, check_po, check_amount, decide
import db

db.init_db()
pos = load_pos("data/pos.csv")

for name in ["01_clean_happy_path.pdf", "02_within_tolerance.pdf", "06_scanned_image_only.pdf"]:
    fields = extract_fields(read_text("samples/" + name))
    findings = check_missing(fields) + check_po(fields, pos) + check_amount(fields, pos)
    decision = decide(findings)
    db.save_run(name, fields, decision, findings)
    print("saved:", name, "->", decision)

print()
print("Run history in the database:")
for r in db.list_runs():
    print(r["id"], r["ts"], r["filename"], r["invoice_no"], r["po"], r["total"], r["decision"])
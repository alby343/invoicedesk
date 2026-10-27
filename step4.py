import csv
from extract import read_text, extract_fields


def load_pos(path):
    pos = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            row["amount"] = float(row["amount"])
            pos[row["po_number"]] = row
    return pos


pos = load_pos("data/pos.csv")

for name in ["01_clean_happy_path.pdf", "02_within_tolerance.pdf"]:
    fields = extract_fields(read_text("samples/" + name))
    po = pos.get(fields["po"])
    print("Invoice:", fields["invoice_no"], "| total:", fields["total"])
    if po is None:
        print("  PO not found in system:", fields["po"])
    else:
        diff = fields["total"] - po["amount"]
        print("  PO", po["po_number"], "for", po["vendor"], "| amount:", po["amount"], "| difference:", diff)
    print()
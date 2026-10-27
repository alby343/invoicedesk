import csv


def load_pos(path):
    pos = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            row["amount"] = float(row["amount"])
            pos[row["po_number"]] = row
    return pos
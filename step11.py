import time
from pipeline import process

for name in ["01_clean_happy_path.pdf", "07_duplicate_resubmission.pdf", "10_lookalike_vendor.pdf"]:
    print("=== Processing", name)
    for ev in process("samples/" + name, name):
        if ev["status"] == "running":
            print("  ...", ev["title"])
            time.sleep(0.4)          # slow it down so you can watch it happen
        elif ev["status"] == "final":
            print("  DECISION:", ev["decision"], "-", ev["detail"])
        else:
            print("  [" + ev["status"].upper() + "]", ev["title"], "-", ev["detail"])
    print()
from pipeline import process

for name in ["01_clean_happy_path.pdf", "11_math_mismatch.pdf"]:
    print("=== Processing", name)
    for ev in process("samples/" + name, name):
        if ev["status"] == "running":
            continue
        elif ev["status"] == "final":
            print("  DECISION:", ev["decision"], "-", ev["detail"])
        else:
            print("  [" + ev["status"].upper() + "]", ev["title"], "-", ev["detail"])
    print()
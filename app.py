import json
import os
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

import checks
import db
from loaders import load_pos
from pipeline import process
from vendors import load_vendors

app = Flask(__name__)
SAMPLES = Path("samples")
UPLOADS = Path("uploads")
UPLOADS.mkdir(exist_ok=True)


@app.get("/")
def index():
    samples = sorted(p.name for p in SAMPLES.glob("*.pdf"))
    return render_template("index.html", samples=samples)


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.post("/run")
def run():
    upload = request.files.get("file")
    if upload and upload.filename:
        filename = secure_filename(upload.filename)
        path = UPLOADS / filename
        upload.save(path)
    else:
        filename = request.form.get("sample", "")
        if filename not in {p.name for p in SAMPLES.glob("*.pdf")}:
            return "Unknown sample", 400
        path = SAMPLES / filename

    def stream():
        for ev in process(str(path), filename):
            yield json.dumps(ev) + "\n"     # one JSON message per line
            time.sleep(0.5)                  # slow down so the audience can follow

    return Response(stream(), mimetype="application/x-ndjson")


@app.get("/api/dashboard")
def api_dashboard():
    db.init_db()
    runs = db.list_runs()
    vendors = load_vendors("data/vendors.csv")
    pos = load_pos("data/pos.csv")

    counts = {"APPROVE": 0, "REVIEW": 0, "HOLD": 0, "REJECT": 0}
    approved_value = 0.0
    rejected_value = 0.0
    rows = []
    for r in runs:
        counts[r["decision"]] += 1
        total = r["total"] or 0
        if r["decision"] == "APPROVE":
            approved_value += total
        if r["decision"] == "REJECT":
            rejected_value += total
        findings = json.loads(r["findings"])
        problems = [f for f in findings if checks.SEVERITY[f["severity"]] >= 2]
        rows.append({
            "id": r["id"], "time": r["ts"], "file": r["filename"],
            "vendor": vendors.get(r["vendor_id"], {}).get("name", "Unknown vendor"),
            "invoice_no": r["invoice_no"], "total": r["total"], "po": r["po"],
            "decision": r["decision"],
            "reason": problems[0]["message"] if problems else "All checks passed.",
        })
    rows.reverse()    # newest first

    util = [{"po": p["po_number"], "vendor": p["vendor"], "amount": p["amount"],
             "billed": db.consumed(p["po_number"])} for p in pos.values()]
    n = len(runs)
    return jsonify(total=n, counts=counts,
                   auto_rate=round(counts["APPROVE"] / n * 100) if n else 0,
                   approved_value=approved_value, rejected_value=rejected_value,
                   runs=rows, util=util)


@app.post("/reset")
def reset():
    if os.path.exists(db.DB_FILE):
        os.remove(db.DB_FILE)
    db.init_db()
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True)
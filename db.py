import json
import sqlite3
from datetime import datetime

DB_FILE = "runs.db"


def connect():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = connect()
    con.execute(
        """CREATE TABLE IF NOT EXISTS runs (
               id         INTEGER PRIMARY KEY AUTOINCREMENT,
               ts         TEXT,
               filename   TEXT,
               vendor_id  TEXT,
               invoice_no TEXT,
               inv_key    TEXT,
               po         TEXT,
               total      REAL,
               decision   TEXT,
               findings   TEXT
           )"""
    )
    con.commit()
    con.close()


def save_run(filename, vendor_id, fields, inv_key, decision, findings):
    con = connect()
    con.execute(
        "INSERT INTO runs (ts, filename, vendor_id, invoice_no, inv_key, po, total, decision, findings) VALUES (?,?,?,?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename, vendor_id, fields["invoice_no"],
         inv_key, fields["po"], fields["total"], decision, json.dumps(findings)),
    )
    con.commit()
    con.close()


def find_duplicate(vendor_id, inv_key):
    """Earlier run from the same vendor with the same invoice number that was not rejected."""
    if not vendor_id or not inv_key:
        return None
    con = connect()
    row = con.execute(
        "SELECT * FROM runs WHERE vendor_id=? AND inv_key=? AND decision IN ('APPROVE','REVIEW') ORDER BY id LIMIT 1",
        (vendor_id, inv_key),
    ).fetchone()
    con.close()
    return row


def list_runs():
    con = connect()
    rows = con.execute("SELECT * FROM runs ORDER BY id").fetchall()
    con.close()
    return rows

def consumed(po_number):
    """Total of invoices already approved against this PO."""
    if not po_number:
        return 0.0
    con = connect()
    total = con.execute(
        "SELECT COALESCE(SUM(total), 0) FROM runs WHERE po=? AND decision='APPROVE'", (po_number,)
    ).fetchone()[0]
    con.close()
    return round(total, 2)
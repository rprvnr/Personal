"""Parse bank and card statements into one normalised transaction list.

Usage: python3 -I parse.py <data_dir> <out_json>

Expected files in <data_dir> (raw statements stay outside the repo):
  hdfc_savings_*.xls      HDFC NetBanking "Excel" account statement
  axis_savings_*.csv      Axis account statement CSV (one file per account)
  axis_card_*.xlsx        Axis credit card monthly statement (xlsx export)
  axis_card_unbilled.csv  date,desc,amount,dc  (hand-entered unbilled rows)
  hdfc_card_*.pdf         HDFC Pixel card statement PDFs; set HDFC_CARD_PASSWORD to open them
"""
import csv
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import categorise  # noqa: E402

txns = []


def add(date, account, desc, amount, direction, source):
    amount = round(float(amount), 2)
    if amount == 0:
        return
    base = f"{date}|{account}|{desc}|{amount}|{direction}"
    n = sum(1 for t in txns if t["_base"] == base)
    tid = hashlib.sha1(f"{base}|{n}".encode()).hexdigest()[:10]
    cat = categorise(desc, amount, direction, account, date)
    txns.append({
        "_base": base,
        "id": tid,
        "date": date,
        "account": account,
        "desc": re.sub(r"\s+", " ", desc).strip(),
        "amount": amount,
        "dir": direction,
        "source": source,
        **cat,
    })


def num(v):
    if v is None:
        return 0.0
    s = str(v).replace(",", "").replace("₹", "").strip()
    if s in ("", "nan", "-"):
        return 0.0
    return float(s)


def parse_hdfc(path):
    df = pd.read_excel(path, header=None)
    rows = df[df[0].astype(str).str.match(r"^\d\d/\d\d/\d\d$")]
    for r in rows.itertuples(index=False):
        date = datetime.strptime(r[0], "%d/%m/%y").date().isoformat()
        dr, cr = num(r[4]), num(r[5])
        if dr:
            add(date, "HDFC Savings", str(r[1]), dr, "out", os.path.basename(path))
        if cr:
            add(date, "HDFC Savings", str(r[1]), cr, "in", os.path.basename(path))


def parse_axis_savings(path):
    acct = re.search(r"(\d{4})\.csv$", path).group(1)
    with open(path, newline="") as f:
        lines = f.read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Tran Date,"))
    for row in csv.reader(lines[start + 1:]):
        if not row or not re.match(r"\d\d-\d\d-\d{4}", row[0]):
            continue
        date = datetime.strptime(row[0], "%d-%m-%Y").date().isoformat()
        dr, cr = num(row[3]), num(row[4])
        name = f"Axis Savings ··{acct}"
        if dr:
            add(date, name, row[2], dr, "out", os.path.basename(path))
        if cr:
            add(date, name, row[2], cr, "in", os.path.basename(path))


def parse_axis_card(path):
    df = pd.read_excel(path, header=None)
    for r in df.itertuples(index=False):
        m = re.match(r"(\d\d) (\w{3}) '(\d\d)$", str(r[0]))
        if not m:
            continue
        date = datetime.strptime(f"{m[1]} {m[2]} 20{m[3]}", "%d %b %Y").date().isoformat()
        direction = "in" if str(r[4]).strip() == "Credit" else "out"
        add(date, "Axis Card ··1282", str(r[1]), num(r[3]), direction, os.path.basename(path))


HDFC_LINE = re.compile(r"^(\d{1,2}) ?([A-Za-z]{3,4}) ?(\d{4}), ?\d\d:\d\d (.*?)(?: \+\d+)? ?(\+?)₹([\d,]+\.\d\d)$")


def parse_hdfc_card(path, password):
    """HDFC Pixel consolidated statement PDF (password protected). Uses pdftotext -raw."""
    import subprocess
    text = subprocess.run(["pdftotext", "-upw", password, "-raw", path, "-"], capture_output=True,
                          text=True, check=True).stdout
    card, buf = "", ""
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"Card no\. ?XX(\d{4}) - (\w+)", line)
        if m:
            card = f"HDFC Pixel {m.group(2)} ··{m.group(1)}"
            continue
        if re.match(r"^\d{1,2} ?[A-Za-z]{3,4} ?\d{4},", line):
            buf = line
        elif buf:
            buf += " " + line
        else:
            continue
        m = HDFC_LINE.match(buf)
        if not m:
            if len(buf) > 400:
                buf = ""
            continue
        buf = ""
        day, mon, year, desc, plus, amt = m.groups()
        date = datetime.strptime(f"{day} {mon[:3]} {year}", "%d %b %Y").date().isoformat()
        if date < "2026-04-01":
            continue
        desc = re.sub(r"\s+IND$", "", desc.replace("Paym ent", "Payment")).strip()
        add(date, card or "HDFC Pixel card", desc, num(amt), "in" if plus else "out", os.path.basename(path))


def parse_unbilled(path):
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            direction = "in" if row["dc"] == "Credit" else "out"
            add(row["date"], "Axis Card ··1282", row["desc"], num(row["amount"]), direction,
                "axis card screenshots")


def main(data_dir, out_path):
    for p in sorted(glob.glob(os.path.join(data_dir, "hdfc_savings_*.xls"))):
        parse_hdfc(p)
    for p in sorted(glob.glob(os.path.join(data_dir, "axis_savings_*.csv"))):
        parse_axis_savings(p)
    for p in sorted(glob.glob(os.path.join(data_dir, "axis_card_*.xlsx"))):
        parse_axis_card(p)
    pw = os.environ.get("HDFC_CARD_PASSWORD")
    for p in sorted(glob.glob(os.path.join(data_dir, "hdfc_card_*.pdf"))):
        if pw:
            parse_hdfc_card(p, pw)
    unbilled = os.path.join(data_dir, "axis_card_unbilled.csv")
    if os.path.exists(unbilled):
        parse_unbilled(unbilled)
    for t in txns:
        del t["_base"]
    txns.sort(key=lambda t: (t["date"], t["account"], t["desc"]))
    with open(out_path, "w") as f:
        json.dump(txns, f, ensure_ascii=False, indent=0)
    print(f"{len(txns)} transactions -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

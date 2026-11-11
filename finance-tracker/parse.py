"""Parse bank and card statements into one normalised transaction list.

Usage: python3 -I parse.py <data_dir> <out_json>

Expected files in <data_dir> (raw statements stay outside the repo):
  hdfc_savings_*.xls      HDFC NetBanking "Excel" account statement
  axis_savings_*.csv      Axis account statement CSV (one file per account)
  axis_card_*.xlsx        Axis credit card monthly statement (xlsx export)
  snapshot.json           rows parsed from statements in earlier runs, plus how far each account's
                          statements reach (written with SNAPSHOT_OUT=<path>)
  alerts.csv              date,account,desc,amount,dc,source  (email alerts / app screenshots;
                          dropped once a statement covers the date)
  position.csv            label,amount,type,account  (cash on hand, money owed to you, card limits)
  personal_rules.csv      pattern,merchant,category,dir,review,note  (rules naming people, employer
                          or landlord; checked before the general rules)
  overrides.csv           date,match,amount,category,note[,merchant]  (one-off fixes to specific rows)
  adjustments.csv         date,desc,amount,dir,category,note[,merchant]  (entries no statement shows)
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
from rules import CATEGORIES, ONE_OFF_MIN, SPEND_TYPES, categorise, load_personal_rules, spend_type, subcategory  # noqa: E402,E501

txns = []
rows = []          # raw rows read by the statement/alert parsers, before categorising
coverage = {}      # account -> last date its statements cover
balances = {}      # bank account -> {"date", "balance"} from the latest statement row
card_stmts = {}    # card account -> {"date", "due", "min_due", "due_date"} from the latest statement


def note_balance(account, date, balance):
    if balance is None:
        return
    if account not in balances or date >= balances[account]["date"]:
        balances[account] = {"date": date, "balance": round(balance, 2)}


def note_card_stmt(account, date, due, min_due, due_date):
    if account not in card_stmts or date >= card_stmts[account]["date"]:
        card_stmts[account] = {"date": date, "due": round(due, 2), "min_due": round(min_due, 2),
                               "due_date": due_date}


def add(date, account, desc, amount, direction, source):
    """Record a raw row; categorising happens later in finalize()."""
    amount = round(float(amount), 2)
    if amount == 0:
        return
    rows.append({"date": date, "account": account, "desc": re.sub(r"\s+", " ", desc).strip(),
                 "amount": amount, "dir": direction, "source": source})


def finalize(date, account, desc, amount, direction, source):
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
    return txns[-1]


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
        note_balance("HDFC Savings", date, num(r[6]))


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
        note_balance(name, date, num(row[5]))


def parse_axis_card(path):
    df = pd.read_excel(path, header=None)
    cells = " | ".join(str(v) for v in df.values.flatten() if str(v) != "nan")
    def money(label):
        m = re.search(label + r"\s*₹\s*([\d,]+\.\d\d)", cells)
        return num(m.group(1)) if m else 0.0
    m = re.search(r"Payment Due Date\s*(\d\d \w{3}) '(\d\d)", cells)
    due_date = datetime.strptime(f"{m[1]} 20{m[2]}", "%d %b %Y").date().isoformat() if m else ""
    dates = []
    for r in df.itertuples(index=False):
        m = re.match(r"(\d\d) (\w{3}) '(\d\d)$", str(r[0]))
        if not m:
            continue
        date = datetime.strptime(f"{m[1]} {m[2]} 20{m[3]}", "%d %b %Y").date().isoformat()
        direction = "in" if str(r[4]).strip() == "Credit" else "out"
        add(date, "Axis Card ··1282", str(r[1]), num(r[3]), direction, os.path.basename(path))
        dates.append(date)
    if dates:  # the statement closes on its last transaction date
        note_card_stmt("Axis Card ··1282", max(dates), money("Total Payment Due"), money("Minimum Payment Due"),
                       due_date)


HDFC_LINE = re.compile(r"^(\d{1,2}) ?([A-Za-z]{3,4}) ?(\d{4}), ?\d\d:\d\d (.*?)(?: \+\d+)? ?(\+?)₹([\d,]+\.\d\d)$")


def parse_hdfc_card(path, password):
    """HDFC Pixel consolidated statement PDF (password protected). Uses pdftotext -raw."""
    import subprocess
    text = subprocess.run(["pdftotext", "-upw", password, "-raw", path, "-"], capture_output=True,
                          text=True, check=True).stdout
    card, buf = "", ""
    m = re.search(r"Statement Date (\d{1,2} \w{3})\w* (\d{4})", text)
    stmt_date = datetime.strptime(" ".join(m.groups()), "%d %b %Y").date().isoformat() if m else ""
    flat = re.sub(r"\s+", "", text)
    due = re.search(r"TOTALAMOUNTDUE₹([\d,]+\.\d\d)", flat)
    mind = re.search(r"MINIMUMDUE₹([\d,]+\.\d\d)", flat)
    dd = re.search(r"DUEDATE(\d{1,2})([A-Za-z]{3})[a-z]*(\d{4})", flat)
    due_date = datetime.strptime(f"{dd[1]} {dd[2]} {dd[3]}", "%d %b %Y").date().isoformat() if dd else ""
    stmt_card = None
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
        desc = re.sub(r"\s+IND$", "", desc.replace("Paym ent", "Payment")).strip()
        add(date, card or "HDFC Pixel card", desc, num(amt), "in" if plus else "out", os.path.basename(path))
        acct = card or "HDFC Pixel card"
        coverage[acct] = max(coverage.get(acct, ""), stmt_date)
        stmt_card = acct
    if stmt_card and stmt_date and due:
        note_card_stmt(stmt_card, stmt_date, num(due[1]), num(mind[1]) if mind else 0.0, due_date)


def parse_alerts(path):
    """alerts.csv: date,account,desc,amount,dc,source -- rows not yet on a statement (email alerts,
    app screenshots). A row is dropped once a statement for its account covers its date."""
    out = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            direction = "in" if row["dc"] == "Credit" else "out"
            out.append({"date": row["date"], "account": row["account"],
                        "desc": re.sub(r"\s+", " ", row["desc"]).strip(),
                        "amount": round(num(row["amount"]), 2), "dir": direction, "source": row["source"]})
    return out


def next_month(month):
    y, m = int(month[:4]), int(month[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def budget_month(t):
    """Month a transaction counts toward. Salary paid from the 25th onward is next month's
    salary (it arrives on the last working day of the previous month)."""
    month = t["date"][:7]
    if t["category"] == "Salary" and int(t["date"][8:10]) >= 25:
        y, m = int(month[:4]), int(month[5:7])
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        month = f"{y:04d}-{m:02d}"
    return month


def apply_overrides(path):
    """overrides.csv: date,match,amount,category,note[,merchant] -- one-off fixes for specific rows."""
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            pat = re.compile(row["match"], re.I)
            hits = [t for t in txns if t["date"] == row["date"] and pat.search(t["desc"])
                    and (not row["amount"] or abs(t["amount"] - float(row["amount"])) < 0.01)]
            if not hits:
                print(f"override matched nothing: {row}", file=sys.stderr)
            for t in hits:
                t["category"] = row["category"]
                t["note"] = row["note"]
                if row.get("merchant"):
                    t["merchant"] = row["merchant"]
                t["review"] = False


def add_adjustments(path):
    """adjustments.csv: date,desc,amount,dir,category,note[,merchant] -- entries no statement shows."""
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            t = finalize(row["date"], "Adjustment", row["desc"], round(num(row["amount"]), 2), row["dir"],
                         "adjustments.csv")
            t.update(merchant=row.get("merchant") or row["desc"], category=row["category"], note=row["note"],
                     review=False)


def key(r):
    return (r["date"], r["account"], r["desc"], r["amount"], r["dir"])


def main(data_dir, out_path):
    if os.path.exists(os.path.join(data_dir, "personal_rules.csv")):
        load_personal_rules(os.path.join(data_dir, "personal_rules.csv"))
    # 1. Statement rows: from statement files, plus the saved snapshot (snapshot.json) of rows
    #    parsed from statements in earlier runs. The same row from both is kept once.
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
    for r in rows:
        coverage[r["account"]] = max(coverage.get(r["account"], ""), r["date"])
    snap_path = os.path.join(data_dir, "snapshot.json")
    if os.path.exists(snap_path):
        snap = json.load(open(snap_path))
        from collections import Counter
        have = Counter(key(r) for r in rows)
        seen = Counter()
        for r in snap["rows"]:
            seen[key(r)] += 1
            if seen[key(r)] > have[key(r)]:
                rows.append(r)
        for acct, d in snap.get("coverage", {}).items():
            coverage[acct] = max(coverage.get(acct, ""), d)
        for acct, b in snap.get("balances", {}).items():
            note_balance(acct, b["date"], b["balance"])
        for acct, c in snap.get("card_statements", {}).items():
            note_card_stmt(acct, c["date"], c["due"], c["min_due"], c["due_date"])
    statement_rows = list(rows)
    # 2. Alert rows for dates no statement covers yet.
    alerts_path = os.path.join(data_dir, "alerts.csv")
    if os.path.exists(alerts_path):
        rows.extend(r for r in parse_alerts(alerts_path) if r["date"] > coverage.get(r["account"], ""))
    snap_out = os.environ.get("SNAPSHOT_OUT")
    if snap_out:
        start = os.environ.get("TRACK_FROM")
        if start:
            if len(start) == 10:      # a date: keep from that day
                cutoff = start
            else:                     # a month: keep a week before it (late salary belongs to it)
                y, m = int(start[:4]), int(start[5:7])
                y, m = (y - 1, 12) if m == 1 else (y, m - 1)
                cutoff = f"{y:04d}-{m:02d}-24"
            statement_rows = [r for r in statement_rows if r["date"] >= cutoff]
        with open(snap_out, "w") as f:
            json.dump({"rows": sorted(statement_rows, key=key), "coverage": coverage, "balances": balances,
                       "card_statements": card_stmts}, f, ensure_ascii=False)
    for r in rows:
        finalize(r["date"], r["account"], r["desc"], r["amount"], r["dir"], r["source"])
    if os.path.exists(os.path.join(data_dir, "overrides.csv")):
        apply_overrides(os.path.join(data_dir, "overrides.csv"))
    if os.path.exists(os.path.join(data_dir, "adjustments.csv")):
        add_adjustments(os.path.join(data_dir, "adjustments.csv"))
    big = {t["merchant"] for t in txns if CATEGORIES.get(t["category"]) == "spend" and t["dir"] == "out"
           and t["amount"] >= ONE_OFF_MIN and t["category"] not in SPEND_TYPES["Fixed"] | SPEND_TYPES["People"]}
    for t in txns:
        t["type"] = spend_type(t, big)
    for t in txns:
        del t["_base"]
        assert t["category"] in CATEGORIES, t
        t["sub"] = subcategory(t["category"], t["merchant"], t["desc"])
        t["month"] = budget_month(t)
    # TRACK_FROM: a month (2026-08) drops everything budgeted before it; a date (2026-08-26) drops
    # everything before that day and folds the rest of that partial month into the next month.
    start = os.environ.get("TRACK_FROM")
    if start and len(start) == 10:
        txns[:] = [t for t in txns if t["date"] >= start]
        for t in txns:
            if t["month"] == start[:7]:
                t["month"] = next_month(start[:7])
    elif start:
        txns[:] = [t for t in txns if t["month"] >= start]
    txns.sort(key=lambda t: (t["date"], t["account"], t["desc"]))
    with open(out_path, "w") as f:
        json.dump(txns, f, ensure_ascii=False, indent=0)
    pos = positions(rows, os.path.join(data_dir, "position.csv"))
    with open(re.sub(r"\.json$", "", out_path) + ".positions.json", "w") as f:
        json.dump(pos, f, ensure_ascii=False, indent=1)
    print(f"{len(txns)} transactions -> {out_path}")


def positions(all_rows, extra_path):
    """Where each account stands now: last statement figure plus every row dated after it.
    position.csv (label,amount,type,account) adds cash on hand (type cash), money owed to you
    (owed_to_you) and card limits (card_limit, with the card's account name)."""
    out = {"banks": [], "cards": [], "other": []}
    limits, confirmed = {}, {}
    if os.path.exists(extra_path):
        with open(extra_path, newline="") as f:
            for row in csv.DictReader(f):
                if row["type"] == "card_limit":
                    limits[row["account"]] = num(row["amount"])
                elif row["type"] == "card_confirmed":   # balance read off the card app; label = date
                    confirmed[row["account"]] = (row["label"], num(row["amount"]))
                else:
                    out["other"].append({"label": row["label"], "amount": num(row["amount"]), "type": row["type"]})
    for acct, b in sorted(balances.items()):
        later = [r for r in all_rows if r["account"] == acct and r["date"] > b["date"]]
        now = b["balance"] + sum(r["amount"] if r["dir"] == "in" else -r["amount"] for r in later)
        last = max([b["date"]] + [r["date"] for r in later])
        out["banks"].append({"account": acct, "balance": round(now, 2), "as_of": last,
                             "statement_date": b["date"], "statement_balance": b["balance"]})
    for acct, c in sorted(card_stmts.items()):
        later = [r for r in all_rows if r["account"] == acct and r["date"] > c["date"]]
        spent = sum(r["amount"] for r in later if r["dir"] == "out")
        credits = sum(r["amount"] for r in later if r["dir"] == "in")
        out["cards"].append({
            "account": acct, "statement_date": c["date"], "statement_due": c["due"], "min_due": c["min_due"],
            "due_date": c["due_date"], "paid_since_statement": round(credits, 2),
            "statement_left_to_pay": round(max(0.0, c["due"] - credits), 2),
            "new_spends_since_statement": round(spent, 2),
            "outstanding_now": round(c["due"] + spent - credits, 2), "limit": limits.get(acct),
            "as_of": max([c["date"]] + [r["date"] for r in later])})
        card = out["cards"][-1]
        if acct in confirmed and confirmed[acct][0] >= c["date"]:
            # The card app's figure wins. Rows after that date still move it. The gap to our own
            # total is shown, not hidden, until the next statement explains it.
            cdate, camt = confirmed[acct]
            after = sum(r["amount"] if r["dir"] == "out" else -r["amount"] for r in later if r["date"] > cdate)
            card["computed_now"] = card["outstanding_now"]
            card["outstanding_now"] = round(camt + after, 2)
            card["confirmed"] = {"date": cdate, "amount": camt}
            card["unexplained"] = round(card["outstanding_now"] - card["computed_now"], 2)
            card["statement_left_to_pay"] = 0.0   # confirmed paid in full and on time
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

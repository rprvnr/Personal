"""Build the dashboard page and the Excel workbook from parsed transactions.

Usage: python3 -I build.py <transactions.json> <out_dir> [<edits.json>]

<edits.json> is optional: the {"overrides": ..., "rules": ...} document the
dashboard saves, so the workbook matches the edits made on the page.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openpyxl import Workbook  # noqa: E402
from openpyxl.formatting.rule import FormulaRule  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from rules import CATEGORIES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def gaps(tx):
    """Notes shown at the top of the dashboard and on the workbook's Notes sheet."""
    out = []
    if any(t.get("source") == "HDFC card email alerts" for t in tx):
        out.append({"title": "HDFC card purchases since 15 Oct come from email alerts.",
                    "detail": "They'll be checked against the statement that arrives around 15–18 Nov. "
                              "Anything HDFC didn't send an alert for will only show up then."})
    unclear = sum(t["amount"] if t["dir"] == "out" else -t["amount"] for t in tx
                  if t.get("sub", "").startswith("Swiggy (food, Instamart"))
    if unclear > 0:
        out.append({"title": f"₹{unclear:,.0f} of Swiggy can't be split into food, Instamart or Dineout.",
                    "detail": "The card statements only say 'Swiggy'. Your Swiggy order history would settle it."})
    cash = os.environ.get("CASH_ON_HAND")
    if cash:
        out.append({"title": f"Cash on hand: ₹{float(cash):,.0f}.",
                    "detail": "ATM withdrawals go into your wallet and aren't counted as spending. "
                              "Cash you spend is recorded as its own row."})
    return out


def apply_edits(tx, edits):
    ov, rules = edits.get("overrides", {}), edits.get("rules", {})
    for t in tx:
        o, r = ov.get(t["id"], {}), rules.get(t["merchant"], {})
        t["category"] = o.get("cat") or r.get("cat") or t["category"]
        inc = o.get("inc", r.get("inc"))
        t["counted"] = inc if inc is not None else CATEGORIES[t["category"]] != "excluded"


def build_html(tx, out_dir):
    payload = {"transactions": tx, "categories": CATEGORIES, "gaps": gaps(tx),
               "built": datetime.now().strftime("%d %b %Y")}
    with open(os.path.join(HERE, "template.html")) as f:
        html = f.read()
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("__DATA__", data)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w") as f:
        f.write(html)
    return path


HEAD = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1F2937")
INR = '[$₹-4009]#,##,##0;-[$₹-4009]#,##,##0'


def header(ws, cols, widths):
    ws.append(cols)
    for i, w in enumerate(widths, 1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill = HEAD, HEAD_FILL
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def build_xlsx(tx, out_dir):
    wb = Workbook()
    months = sorted({t["month"] for t in tx})
    mlabel = {m: datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months}

    # --- Categories (lookup table) ---
    wc = wb.active
    wc.title = "Categories"
    header(wc, ["Category", "Group"], [32, 12])
    for c, g in CATEGORIES.items():
        wc.append([c, g])
    ncat = len(CATEGORIES) + 1

    # --- Transactions ---
    wt = wb.create_sheet("Transactions", 0)
    cols = ["Date", "Month", "Account", "Merchant", "Category", "Direction", "Amount", "Count it?",
            "Group", "Counted spending", "Counted income", "Note", "Narration", "Subcategory"]
    header(wt, cols, [11, 9, 18, 28, 30, 9, 12, 9, 10, 15, 15, 45, 80, 34])
    for i, t in enumerate(tx, start=2):
        wt.append([
            datetime.strptime(t["date"], "%Y-%m-%d"), t["month"], t["account"], t["merchant"], t["category"],
            "In" if t["dir"] == "in" else "Out", t["amount"], "Yes" if t["counted"] else "No",
            f'=IFERROR(VLOOKUP(E{i},Categories!$A$2:$B${ncat},2,FALSE),"spend")',
            f'=IF(H{i}="Yes",IF(I{i}="spend",IF(F{i}="Out",G{i},-G{i}),IF(I{i}="excluded",IF(F{i}="Out",G{i},0),0)),0)',
            f'=IF(H{i}="Yes",IF(I{i}="income",IF(F{i}="In",G{i},-G{i}),IF(I{i}="excluded",IF(F{i}="In",G{i},0),0)),0)',
            t.get("note", ""), t["desc"], t.get("sub", ""),
        ])
        wt.cell(row=i, column=1).number_format = "dd-mmm-yy"
        for col in (7, 10, 11):
            wt.cell(row=i, column=col).number_format = INR
    n = len(tx) + 1
    dv_yes = DataValidation(type="list", formula1='"Yes,No"', allow_blank=False)
    dv_cat = DataValidation(type="list", formula1=f"=Categories!$A$2:$A${ncat}", allow_blank=False)
    wt.add_data_validation(dv_yes)
    wt.add_data_validation(dv_cat)
    dv_yes.add(f"H2:H{n}")
    dv_cat.add(f"E2:E{n}")
    wt.conditional_formatting.add(f"A2:N{n}", FormulaRule(formula=[f'$H2="No"'], font=Font(color="9CA3AF")))
    wt.auto_filter.ref = f"A1:N{n}"

    rng = lambda col: f"Transactions!${col}$2:${col}${n}"  # noqa: E731

    # --- Monthly summary ---
    ws = wb.create_sheet("Monthly summary", 0)
    header(ws, ["Month", "Month key", "Income", "Of which from Dad", "Earned income", "Spending", "Left over",
                "Savings rate"], [12, 10, 14, 17, 15, 14, 14, 13])
    for r, m in enumerate(months, start=2):
        ws.append([mlabel[m], m,
                   f'=SUMIFS({rng("K")},{rng("B")},B{r})',
                   f'=SUMIFS({rng("K")},{rng("B")},B{r},{rng("E")},"From Dad")',
                   f"=C{r}-D{r}",
                   f'=SUMIFS({rng("J")},{rng("B")},B{r})',
                   f"=C{r}-F{r}",
                   f'=IF(C{r}=0,"",G{r}/C{r})'])
    last = len(months) + 1
    t = last + 1
    ws.append(["Total", "", f"=SUM(C2:C{last})", f"=SUM(D2:D{last})", f"=SUM(E2:E{last})",
               f"=SUM(F2:F{last})", f"=SUM(G2:G{last})", f'=IF(C{t}=0,"",G{t}/C{t})'])
    ws.append(["Monthly average", "", f"=C{t}/{len(months)}", f"=D{t}/{len(months)}", f"=E{t}/{len(months)}",
               f"=F{t}/{len(months)}", f"=G{t}/{len(months)}", ""])
    # last three complete months (the latest month is usually partial)
    l3 = months[-4:-1] if len(months) >= 4 else months
    a, b = months.index(l3[0]) + 2, months.index(l3[-1]) + 2
    lbl = f"{mlabel[l3[0]][:3]}–{mlabel[l3[-1]][:3]}"
    ws.append([f"Last 3 months ({lbl})", "", *[f"=SUM({c}{a}:{c}{b})" for c in "CDEFG"], f'=IF(C{t + 2}=0,"",G{t + 2}/C{t + 2})'])
    ws.append([f"Last 3 months, per month", "", *[f"={c}{t + 2}/3" for c in "CDEFG"], ""])
    for row in ws.iter_rows(min_row=2, max_row=t + 3):
        for c in row[2:7]:
            c.number_format = INR
        row[7].number_format = "0%"
    for c in ws[t] + ws[t + 1] + ws[t + 2] + ws[t + 3]:
        c.font = Font(bold=True)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].hidden = True
    ws.cell(row=t + 5, column=1, value="Edit the Category or 'Count it?' columns on the Transactions sheet; "
                                       "every total here updates.").font = Font(italic=True, color="6B7280")

    # --- Spending by category x month ---
    wk = wb.create_sheet("Spending by category", 1)
    l3 = months[-4:-1] if len(months) >= 4 else months
    l3a, l3b = get_column_letter(months.index(l3[0]) + 2), get_column_letter(months.index(l3[-1]) + 2)
    header(wk, ["Category"] + [mlabel[m] for m in months] + ["Total", "Share", "Last 3 months, per month"],
           [30] + [11] * len(months) + [13, 8, 14])
    spend_cats = [c for c, g in CATEGORIES.items() if g == "spend"]
    tot_col = get_column_letter(len(months) + 2)
    share_col = get_column_letter(len(months) + 3)
    end_row = len(spend_cats) + 1
    for r, c in enumerate(spend_cats, start=2):
        row = [c]
        for m in months:
            row.append(f'=SUMIFS({rng("J")},{rng("E")},$A{r},{rng("B")},"{m}")')
        row.append(f"=SUM(B{r}:{get_column_letter(len(months) + 1)}{r})")
        row.append(f"=IF(${tot_col}${end_row + 1}=0,0,{tot_col}{r}/${tot_col}${end_row + 1})")
        row.append(f"=SUM({l3a}{r}:{l3b}{r})/3")
        wk.append(row)
    l3col = get_column_letter(len(months) + 4)
    total_row = ["Total"] + [f"=SUM({get_column_letter(j)}2:{get_column_letter(j)}{end_row})"
                             for j in range(2, len(months) + 3)] + ["", f"=SUM({l3col}2:{l3col}{end_row})"]
    wk.append(total_row)
    for row in wk.iter_rows(min_row=2, max_row=end_row + 1):
        for c in row[1:len(months) + 2]:
            c.number_format = INR
        row[-2].number_format = "0%"
        row[-1].number_format = INR
    for c in wk[end_row + 1]:
        c.font = Font(bold=True)

    # --- Spending by subcategory ---
    wsub = wb.create_sheet("Spending by subcategory", 2)
    header(wsub, ["Category", "Subcategory"] + [mlabel[m] for m in months] + ["Total", "Last 3 months, per month"],
           [28, 40] + [11] * len(months) + [13, 14])
    pairs = sorted({(t["category"], t.get("sub", "")) for t in tx
                    if CATEGORIES.get(t["category"]) == "spend" and t.get("sub")})
    for r, (c, sub) in enumerate(pairs, start=2):
        row = [c, sub]
        for m in months:
            row.append(f'=SUMIFS({rng("J")},{rng("E")},$A{r},{rng("N")},$B{r},{rng("B")},"{m}")')
        first, lastc = get_column_letter(3), get_column_letter(len(months) + 2)
        row.append(f"=SUM({first}{r}:{lastc}{r})")
        a3 = get_column_letter(months.index(l3[0]) + 3)
        b3 = get_column_letter(months.index(l3[-1]) + 3)
        row.append(f"=SUM({a3}{r}:{b3}{r})/3")
        wsub.append(row)
        for c_ in wsub[r][2:]:
            c_.number_format = INR
    wsub.cell(row=len(pairs) + 3, column=1, value="Only categories with a breakdown are listed here; "
              "the full list is on 'Spending by category'.").font = Font(italic=True, color="6B7280")

    # --- Notes ---
    wn = wb.create_sheet("Notes")
    wn.column_dimensions["A"].width = 120
    wn.append(["How this workbook works"])
    wn["A1"].font = Font(bold=True, size=13)
    for line in [
        "Every row on Transactions is one statement line. 'Count it?' decides whether it affects the totals.",
        "Spending categories: money out adds to spending; refunds and money back reduce it.",
        "Income categories: money in adds to income. 'From Dad' is income, shown separately on the summary.",
        "Excluded categories (own transfers, card bills, family transfers, lending) are off by default. "
        "If you switch one on, money out counts as spending and money in as income.",
        "Card bill payments are excluded because the card purchases themselves are listed.",
        "",
        "Gaps in the data:",
    ] + [f"• {g['title']} {g['detail']}" for g in gaps(tx)]:
        wn.append([line])
        wn.cell(row=wn.max_row, column=1).alignment = Alignment(wrap_text=True)

    path = os.path.join(out_dir, "money-tracker.xlsx")
    wb.save(path)
    return path


def main(tx_path, out_dir, edits_path=None):
    tx = json.load(open(tx_path))
    edits = json.load(open(edits_path)) if edits_path else {}
    os.makedirs(out_dir, exist_ok=True)
    print(build_html(tx, out_dir))
    apply_edits(tx, edits)
    print(build_xlsx(tx, out_dir))


if __name__ == "__main__":
    main(*sys.argv[1:])

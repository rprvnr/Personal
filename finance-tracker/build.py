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
    lak_out = sum(t["amount"] for t in tx if t["merchant"] == "Lakshana B" and t["dir"] == "out")
    lak_in = sum(t["amount"] for t in tx if t["merchant"] == "Lakshana B" and t["dir"] == "in")
    out = []
    out.append({"title": "HDFC Pixel card purchases from 15 Oct onward are missing.",
                "detail": "The last emailed statement ends 14 Oct; the next one arrives around 15 Nov. "
                          "Rent for November and any other spends on that card since 15 Oct aren't counted yet."})
    out.append({"title": "3 Axis card transactions from Oct–Nov are missing.",
                "detail": "The card app lists 74 unbilled transactions and the screenshots show 71. They fall on "
                          "13–14 Oct or around 26–27 Oct. They'll appear in the November statement."})
    if lak_out or lak_in:
        out.append({"title": "Lakshana B is treated as lending.",
                    "detail": f"₹{lak_out:,.0f} sent and ₹{lak_in:,.0f} received, none of it counted. "
                              "If some of it was spending, change those rows' category."})
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
    months = sorted({t["date"][:7] for t in tx})
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
            "Group", "Counted spending", "Counted income", "Note", "Narration"]
    header(wt, cols, [11, 9, 18, 28, 30, 9, 12, 9, 10, 15, 15, 45, 80])
    for i, t in enumerate(tx, start=2):
        wt.append([
            datetime.strptime(t["date"], "%Y-%m-%d"), t["date"][:7], t["account"], t["merchant"], t["category"],
            "In" if t["dir"] == "in" else "Out", t["amount"], "Yes" if t["counted"] else "No",
            f'=IFERROR(VLOOKUP(E{i},Categories!$A$2:$B${ncat},2,FALSE),"spend")',
            f'=IF(H{i}="Yes",IF(I{i}="spend",IF(F{i}="Out",G{i},-G{i}),IF(I{i}="excluded",IF(F{i}="Out",G{i},0),0)),0)',
            f'=IF(H{i}="Yes",IF(I{i}="income",IF(F{i}="In",G{i},-G{i}),IF(I{i}="excluded",IF(F{i}="In",G{i},0),0)),0)',
            t.get("note", ""), t["desc"],
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
    wt.conditional_formatting.add(f"A2:M{n}", FormulaRule(formula=[f'$H2="No"'], font=Font(color="9CA3AF")))
    wt.auto_filter.ref = f"A1:M{n}"

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
    for row in ws.iter_rows(min_row=2, max_row=t + 1):
        for c in row[2:7]:
            c.number_format = INR
        row[7].number_format = "0%"
    for c in ws[t] + ws[t + 1]:
        c.font = Font(bold=True)
    ws.column_dimensions["B"].hidden = True
    ws.cell(row=t + 3, column=1, value="Edit the Category or 'Count it?' columns on the Transactions sheet; "
                                       "every total here updates.").font = Font(italic=True, color="6B7280")

    # --- Spending by category x month ---
    wk = wb.create_sheet("Spending by category", 1)
    header(wk, ["Category"] + [mlabel[m] for m in months] + ["Total", "Share"],
           [30] + [11] * len(months) + [13, 8])
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
        wk.append(row)
    total_row = ["Total"] + [f"=SUM({get_column_letter(j)}2:{get_column_letter(j)}{end_row})"
                             for j in range(2, len(months) + 3)] + [""]
    wk.append(total_row)
    for row in wk.iter_rows(min_row=2, max_row=end_row + 1):
        for c in row[1:len(months) + 2]:
            c.number_format = INR
        row[-1].number_format = "0%"
    for c in wk[end_row + 1]:
        c.font = Font(bold=True)

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

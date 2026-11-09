# Money Tracker

Turns bank and credit card statements into one categorised list of transactions,
an interactive dashboard and an Excel workbook.

Raw statements and the generated files hold personal financial data. They live
outside this repo (see `.gitignore`); only the code is committed.

## Files

- `rules.py`: categories and the rules that map statement lines to merchants and categories.
- `parse.py`: reads the statements into `transactions.json`. HDFC Pixel card PDFs need `HDFC_CARD_PASSWORD` set in the environment.
- `build.py`: builds `index.html` (the dashboard) and `money-tracker.xlsx`.
- `template.html`: the dashboard page; data is injected at build time.

## Run

```bash
python3 -I parse.py <data_dir> <out_dir>/transactions.json
python3 -I build.py <out_dir>/transactions.json <out_dir> [edits.json]
```

Environment: `HDFC_CARD_PASSWORD` opens the HDFC PDFs, `TRACK_FROM=YYYY-MM` drops earlier months,
`CASH_ON_HAND` (build only) shows your wallet cash in the notes.

`edits.json` is the `settings/state` document the dashboard saves (row overrides
and per-merchant rules), so the workbook can match the edits made on the page.

## Counting rules

- Spending categories: money out adds, refunds or money back subtract.
- Income categories: money in adds. "From Dad" is income, shown separately.
- Excluded categories (own transfers, card bill payments, family transfers,
  lending) don't count unless switched on for a row.
- Salary paid on or after the 25th counts toward the next month (it's that month's salary).
- ATM withdrawals move cash into your wallet and aren't spending; cash you spend is
  added as its own row in `adjustments.csv`.

## Refreshing (dashboard button or the every-3-days schedule)

The dashboard's "Update with latest data" button sends Claude a comment; a scheduled task does
the same every three days. A refresh restores the private data folder, pulls new statements,
card/bank alerts and Swiggy Dineout receipts from email into it (`alerts.csv`, `overrides.csv`),
re-runs `parse.py` (with `SNAPSHOT_OUT` so `snapshot.json` stays current) and `build.py`,
republishes the page and posts a summary. Alert rows drop out once a statement covers their dates.

Personal rules (names of people, employer, landlord, own account handles) live in the data
folder's `personal_rules.csv`, not in this repo.

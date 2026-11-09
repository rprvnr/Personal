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

`edits.json` is the `settings/state` document the dashboard saves (row overrides
and per-merchant rules), so the workbook can match the edits made on the page.

## Counting rules

- Spending categories: money out adds, refunds or money back subtract.
- Income categories: money in adds. "From Dad" is income, shown separately.
- Excluded categories (own transfers, card bill payments, family transfers,
  lending) don't count unless switched on for a row.

#!/usr/bin/env python3
"""Build the two single-file pages from src/.

  index.html            classic look   (src/classic.css)
  ../task-tracker-glass/index.html   glass look (src/glass.css)

Both share src/app.js and src/seed.json. Edit src/, then run: python3 build.py
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="{theme}">
<title>{title}</title>
<style id="css">
{css}</style>
</head>
<body class="ui-{ui}">
{backdrop}<div class="wrap" id="root"></div>
<div class="toast" id="toast" role="status" aria-live="polite"><span id="toastMsg"></span><button id="toastUndo" type="button">Undo</button></div>
<script id="state" type="application/json">{seed}</script>
<script id="app">
window.TASKS_UI = "{ui}";
{js}</script>
</body>
</html>
"""

VARIANTS = [
    dict(ui="classic", css="classic.css", out=HERE / "index.html", title="Praveen's Tasks", theme="#0f1013", backdrop=""),
    dict(ui="glass", css="glass.css", out=HERE.parent / "task-tracker-glass" / "index.html", title="Praveen's Tasks · Glass", theme="#05060a",
         backdrop='<div class="backdrop" aria-hidden="true"><i class="b1"></i><i class="b2"></i><i class="b3"></i></div>\n'),
]


def main():
    js = (SRC / "app.js").read_text()
    seed = json.dumps(json.loads((SRC / "seed.json").read_text()), ensure_ascii=False, separators=(", ", ": "))
    seed = seed.replace("</", "<\\/")
    for v in VARIANTS:
        html = SHELL.format(css=(SRC / v["css"]).read_text(), js=js, seed=seed, ui=v["ui"], title=v["title"], theme=v["theme"], backdrop=v["backdrop"])
        v["out"].parent.mkdir(parents=True, exist_ok=True)
        v["out"].write_text(html)
        print("wrote", v["out"].relative_to(HERE.parent), len(html), "bytes")


if __name__ == "__main__":
    main()

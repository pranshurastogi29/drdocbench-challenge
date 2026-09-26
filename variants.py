"""Structural-only variants of a predictions file, for using the leaderboard as a per-column diagnostic.

  python variants.py runs/test_all_final_math.jsonl

Writes submission_<name>.zip (each holding predictions.jsonl) for:
  sep     block separators use 4 newlines (dev ground truth mostly uses 4-6 between blocks; we emit 2)
  tables  tables rewritten to the ground-truth HTML convention: <table><tbody>...</tbody></table>, one tag per line,
          <td style="text-align: left;">, <thead>/<th> kept when present, pipe tables converted to HTML
Text content is never changed; only whitespace and table markup.
"""
import json
import os
import re
import sys
import zipfile

TAG = re.compile(r"<(/?)([a-zA-Z0-9]+)([^>]*)>|([^<]+)")
TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
PIPE_BLOCK = re.compile(r"(?:^[ \t]*\|.*\|[ \t]*\n?){2,}", re.M)
PIPE_SEP = re.compile(r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$")


def _cell_open(tag, attrs):
    attrs = attrs.strip()
    if "style=" not in attrs:
        attrs = (attrs + " " if attrs else "") + 'style="text-align: left;"'
    return f"<{tag} {attrs}>"


def normalize_table(html):
    """Rewrite one <table> to GT convention. Same rows/cells/text; only structure tags and whitespace change."""
    out, in_body, in_head, cell = ["<table>"], False, False, None  # cell = [tag, attrs, parts]

    def flush():
        nonlocal cell
        if cell is not None:
            body = " ".join("".join(cell[2]).split())
            out.append(f"{_cell_open(cell[0], cell[1])}{body}</{cell[0]}>")
            cell = None

    for m in TAG.finditer(html):
        closing, tag, attrs, text = m.group(1), (m.group(2) or "").lower(), m.group(3), m.group(4)
        if text is not None:
            if cell is not None:
                cell[2].append(text)
            continue
        if tag in ("td", "th"):
            flush()
            if not closing:
                cell = ["th" if tag == "th" else "td", attrs, []]
            continue
        if tag not in ("table", "thead", "tbody", "tr"):
            if cell is not None:  # inline markup inside a cell (<br>, <strong>, ...) is kept verbatim
                cell[2].append(m.group(0))
            continue
        flush()
        if tag == "thead":
            out.append("</thead>" if closing else "<thead>")
            in_head = not closing
        elif tag == "tr":
            if closing:
                out.append("</tr>")
            else:
                if not in_head and not in_body:
                    out.append("<tbody>")
                    in_body = True
                out.append("<tr>")
    flush()
    if in_body:
        out.append("</tbody>")
    out.append("</table>")
    return "\n".join(out)


def pipe_to_html(block):
    rows = [r.strip() for r in block.strip("\n").split("\n") if r.strip()]
    rows = [r for r in rows if not PIPE_SEP.match(r)]
    has_head = len(block.strip().split("\n")) > 1 and PIPE_SEP.match(block.strip().split("\n")[1].strip() or "")
    html = ["<table>"]
    for i, r in enumerate(rows):
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        tag = "th" if (has_head and i == 0) else "td"
        if has_head and i == 0:
            html.append("<thead>")
        elif i == (1 if has_head else 0):
            html.append("<tbody>")
        html.append("<tr>")
        html += [f'<{tag} style="text-align: left;">{c}</{tag}>' for c in cells]
        html.append("</tr>")
        if has_head and i == 0:
            html.append("</thead>")
    html += ["</tbody>", "</table>"]
    return "\n".join(html) + "\n"


def tables_variant(md):
    md = PIPE_BLOCK.sub(lambda m: pipe_to_html(m.group(0)), md)
    return TABLE.sub(lambda m: normalize_table(m.group(0)), md)


def sep_variant(md):
    parts = re.split(r"(<table\b.*?</table>)", md, flags=re.S | re.I)  # keep table interiors untouched
    return "".join(p if p.lower().startswith("<table") else re.sub(r"\n{2,}", "\n\n\n\n", p) for p in parts)


def write_zip(rows, name):
    rows = sorted(rows, key=lambda r: (r["subject"], r["document_id"], r["page"]))
    with open("predictions.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: r[k] for k in ("subject", "document_id", "page", "markdown")}, ensure_ascii=False) + "\n")
    with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
        z.write("predictions.jsonl")
    print(f"{name}: {len(rows)} rows, {os.path.getsize(name)} bytes")


if __name__ == "__main__":
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    os.makedirs("submissions", exist_ok=True)
    for name, fn in (("sep", sep_variant), ("tables", tables_variant)):
        write_zip([{**r, "markdown": fn(r["markdown"])} for r in rows], f"submissions/submission_v3m_{name}.zip")

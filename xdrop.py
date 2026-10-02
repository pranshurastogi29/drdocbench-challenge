"""On pages where we write much more text than PaddleOCR-VL finds, drop our paragraphs that Paddle does not have at all.

Why: pages where our text is > 1.1x Paddle's are 13% of dev but 25% of test, and on dev up to 63% of their loss is extra text
the reference does not have (text inside pictures, artwork, inset pages). Tables, formulas, headings and images are kept.

  python xdrop.py runs/dev_all_rebuilt_final5.jsonl runs/dev_all_xd.jsonl --ratio 1.3 --match 60
"""
import argparse
import json
import re

from rapidfuzz import fuzz

KEEP = re.compile(r"^\s*(#|<table|<div|\$\$|\$\\|!\[)")


def N(s):
    return re.sub(r"\W", "", re.sub(r"<[^>]+>", " ", s).lower())   # tags out first: Paddle's table HTML would split every entry


def xdrop(md, paddle_md, ratio=1.3, match=60, min_chars=15, min_keep=0):
    p = N(paddle_md or "")
    tab = sum(len(N(t)) for t in re.findall(r"<table\b.*?</table>", paddle_md or "", re.S))
    if tab > 0.5 * len(p):   # Paddle read the page as a table: its table recognition is too unreliable to judge our text by
        return md
    if len(p) < 50 or len(N(md)) <= ratio * len(p):   # no Paddle text to judge by, or lengths agree
        return md
    paras = [x.strip() for x in re.split(r"\n\s*\n", md.strip()) if x.strip()]
    keep = [x for x in paras
            if KEEP.match(x) or len(N(x)) < min_chars or fuzz.partial_ratio(N(x)[:200], p) >= match]
    if len(keep) < min_keep:   # reading order on a page with only a few matched blocks swings 0-100 on one removal
        return md
    return "\n\n".join(keep)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--paddle", default="runs/paddle_dev.jsonl")
    ap.add_argument("--ratio", type=float, default=1.3); ap.add_argument("--match", type=int, default=60); ap.add_argument("--min-keep", type=int, default=0)
    a = ap.parse_args()
    pad = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(a.paddle, encoding="utf-8"))}
    n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            m = xdrop(r["markdown"], pad.get((r["document_id"], r["page"])), a.ratio, a.match, min_keep=a.min_keep)
            n += m != r["markdown"]
            f.write(json.dumps({**r, "markdown": m}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

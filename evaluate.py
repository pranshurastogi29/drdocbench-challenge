"""Local proxy scorer for dev predictions.

NOT the official metric. The official scorer aligns predicted Markdown to ground-truth blocks and uses
real TEDS and CDM (rendered-formula F1). This uses cheap stand-ins so you can compare runs offline:

  text   : 1 - normalized Levenshtein on page text with tables/display formulas removed   (~ Text edit dist)
  table  : similarity of row/cell text sequences of <table> blocks                        (~ TEDS, content only)
  formula: 1 - normalized Levenshtein on display-formula LaTeX                            (~ CDM, string only)
  order  : reading_order.py - GT blocks located in the prediction by fuzzy match; 1 - normalized edit distance
           of their order (oracle ceiling on dev = 98.0)

Overall = mean of the components present on each page, then averaged over pages (as in the README).

  python evaluate.py predictions_dev_claude.jsonl
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from common import gt_markdown
from reading_order import load_page, score_page

TABLE_RE = re.compile(r"<table.*?</table>", re.S | re.I)
DISPLAY_RE = re.compile(r"\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.S)


class _Cells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cur, self.buf, self.in_cell = [], [], [], False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self.in_cell, self.buf = True, []
        elif tag == "tr":
            self.cur = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cur.append(" ".join("".join(self.buf).split()))
            self.in_cell = False
        elif tag == "tr":
            self.rows.append(self.cur)

    def handle_data(self, data):
        if self.in_cell:
            self.buf.append(data)


def table_text(html):
    p = _Cells()
    p.feed(html)
    return "\n".join("\t".join(r) for r in p.rows)


def norm(s):
    return " ".join(s.split())


IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def strip_markup(md):
    md = IMG_RE.sub(" ", md)  # figures are ignored by the task; GT keeps their crop links
    md = re.sub(r"[*_#`>]", "", md)
    md = re.sub(r"\\[()]|\$", "", md)
    return norm(md)


def sim(a, b):
    if not a and not b:
        return None
    return 1 - Levenshtein.normalized_distance(a, b)


def parts(md):
    tables = [table_text(t) for t in TABLE_RE.findall(md)]
    md = TABLE_RE.sub(" ", md)
    formulas = [norm(a or b) for a, b in DISPLAY_RE.findall(md)]
    md = DISPLAY_RE.sub(" ", md)
    return strip_markup(md), tables, formulas


def list_sim(pred, gt):
    """Greedy content match of table/formula lists. Unmatched GT items score 0; extra preds are ignored."""
    if not gt:
        return None
    scores, pool = [], list(pred)
    for g in gt:
        if not pool:
            scores.append(0.0)
            continue
        best = max(range(len(pool)), key=lambda i: fuzz.ratio(pool[i], g))
        scores.append(1 - Levenshtein.normalized_distance(pool[best], g))
        pool.pop(best)
    return sum(scores) / len(scores)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pred")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--restrict-to", help="only score pages that also appear in this predictions file (for A/B comparisons)")
    ap.add_argument("--worst", type=int, default=0, help="print the N lowest-scoring pages with GT vs prediction heads")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.pred, encoding="utf-8")]
    if args.restrict_to:
        keep = {(r["document_id"], r["page"]) for r in map(json.loads, open(args.restrict_to, encoding="utf-8"))}
        rows = [r for r in rows if (r["document_id"], r["page"]) in keep]
    comp = defaultdict(list)
    per_subject = defaultdict(list)
    page_scores = []
    order_by = defaultdict(list)  # (attribute, value) -> order scores
    coverage = []
    for r in rows:
        gt = gt_markdown(args.split, r["subject"], r["document_id"], r["page"])
        gtxt, gtab, gform = parts(gt)
        ptxt, ptab, pform = parts(r["markdown"])
        rec = load_page(args.split, r["subject"], r["document_id"], r["page"])
        o, cov, _ = score_page(rec, r["markdown"]) if rec else (None, None, 0)
        scores = {"text": sim(ptxt, gtxt), "table": list_sim(ptab, gtab), "formula": list_sim(pform, gform), "order": o}
        if cov is not None:
            coverage.append(cov)
        if o is not None:
            attr = rec["page_info"].get("page_attribute", {})
            order_by[("layout", attr.get("layout"))].append(o)
            order_by[("source", attr.get("data_source"))].append(o)
        present = [v for v in scores.values() if v is not None]
        for k, v in scores.items():
            if v is not None:
                comp[k].append(v)
        if present:
            overall = sum(present) / len(present)
            comp["overall"].append(overall)
            page_scores.append((overall, scores, r, gt))
            per_subject[r["subject"]].append(overall)

    print(f"pages scored: {len(rows)}")
    for k in ("text", "table", "formula", "order", "overall"):
        v = comp[k]
        print(f"{k:8s} {100 * sum(v) / len(v):6.2f}  (n={len(v)})" if v else f"{k:8s}    n/a")
    if coverage:
        print(f"order proxy: GT blocks located in prediction on average {100 * sum(coverage) / len(coverage):.0f}%")
    print("\nreading order by page type:")
    for (a, v), s in sorted(order_by.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        if len(s) >= 5:
            print(f"  {a:7s} {str(v):22s} {100 * sum(s) / len(s):6.1f}  (n={len(s)})")
    print("\nworst subjects (overall):")
    for s, v in sorted(per_subject.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[:5]:
        print(f"  {s:32s} {100 * sum(v) / len(v):6.2f}  (n={len(v)})")

    if args.worst:
        print("\nworst pages:")
        for overall, scores, r, gt in sorted(page_scores, key=lambda t: t[0])[: args.worst]:
            fmt = {k: (None if v is None else round(v, 2)) for k, v in scores.items()}
            print(f"\n=== {r['subject']}/{r['document_id'][:8]} p{r['page']}  overall={overall:.2f} {fmt}")
            print("--- GT   :", gt.strip()[:400].replace("\n", " ⏎ "))
            print("--- PRED :", r["markdown"].strip()[:400].replace("\n", " ⏎ "))


if __name__ == "__main__":
    sys.exit(main())

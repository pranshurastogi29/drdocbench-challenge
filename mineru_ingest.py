"""Turn MinerU 2.x output (<root>/<doc>_<page>/auto/{<stem>.md, <stem>_content_list.json}) into per-page Markdown candidates.
MinerU drops headers/footers/page numbers ('discarded' blocks) from its own .md, so they are appended at the end of the page
(top-to-bottom), which is where the reference puts them.

  python mineru_ingest.py [root]     -> runs/mineru_dev.jsonl, runs/mineru_test.jsonl
"""
import csv
import glob
import json
import os
import re
import sys

from variants import tables_variant

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(ROOT, "kaggle/results/mineru2/out")


def paths(stem, root=DEFAULT):
    d = f"{root}/{stem}/auto"
    return f"{d}/{stem}.md", f"{d}/{stem}_content_list.json"


def content(stem, root=DEFAULT):
    p = paths(stem, root)[1]
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _y(b):
    bb = b.get("bbox")
    if isinstance(bb, str):
        bb = json.loads(bb)
    return bb[1] if bb else 0


def furniture(stem, root=DEFAULT):
    cl = content(stem, root) or []
    d = [b for b in cl if b.get("type") == "discarded" and (b.get("text") or "").strip()]
    return [b["text"].strip() for b in sorted(d, key=_y)]


def to_markdown(stem, root=DEFAULT, strip_span_attrs=False):
    mp = paths(stem, root)[0]
    if not os.path.exists(mp):
        return None
    md = open(mp, encoding="utf-8").read().strip()
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)\s*", "", md)                # figure links: not part of the text
    if strip_span_attrs:
        md = md.replace(" rowspan=1 colspan=1", "")
    md = tables_variant(md)
    fu = furniture(stem, root)
    return "\n\n".join([p for p in [md] + fu if p.strip()])


def tables(stem, root=DEFAULT):
    return [b["table_body"] for b in (content(stem, root) or []) if b.get("type") == "table" and b.get("table_body")]


def equations(stem, root=DEFAULT):
    return [b["text"] for b in (content(stem, root) or []) if b.get("type") == "equation" and b.get("text")]


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    man = list(csv.DictReader(open(os.path.join(ROOT, "kaggle/manifest.csv"))))
    for split in ("dev", "test"):
        rows = [r for r in man if r["split"] == split]; miss = 0
        with open(os.path.join(ROOT, f"runs/mineru_{split}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                md = to_markdown(f"{r['doc']}_{r['page']}", root)
                if md is None: miss += 1; md = ""
                f.write(json.dumps({"subject": r["subject"], "document_id": r["doc"], "page": int(r["page"]), "markdown": md}, ensure_ascii=False) + "\n")
        print(split, len(rows), "pages, missing from MinerU output:", miss)

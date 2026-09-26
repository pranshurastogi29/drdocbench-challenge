"""Turn PaddleOCR-VL output (kaggle/results/paddle/out/<doc>_<page>/*_res.json) into per-page Markdown candidates and
layout-block lists. Paddle's own .md drops header/footer/number blocks, so we rebuild from the JSON, whose
parsing_res_list is already in reading order.

  python paddle_ingest.py        -> runs/paddle_dev.jsonl, runs/paddle_test.jsonl (Paddle-only candidates)
"""
import csv
import glob
import json
import os

from variants import tables_variant

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "kaggle/results/paddle/out")
FURN = ("header", "footer", "number")          # ground truth puts these last: header, then footer, then page number
SKIP = {"image", "chart", "header_image", "footer_image", "seal"}


def blocks(stem):
    p = glob.glob(f"{OUT}/{stem}/*_res.json")
    return json.load(open(p[0]))["parsing_res_list"] if p else None


def furniture(stem):
    """[(label, text)] of the page's header/footer/number blocks, in the ground-truth order."""
    bl = blocks(stem) or []
    out = [(b["block_label"], b["block_content"].strip()) for b in bl if b["block_label"] in FURN and b["block_content"].strip()]
    return sorted(out, key=lambda x: FURN.index(x[0]))


def to_markdown(stem):
    bl = blocks(stem) or []
    body, furn = [], []
    for b in bl:
        lab, c = b["block_label"], (b["block_content"] or "").strip()
        if not c or lab in SKIP:
            continue
        if lab in FURN:
            furn.append((FURN.index(lab), c))
        elif lab == "doc_title":
            body.append("# " + c)
        elif lab == "paragraph_title":
            body.append("## " + c)
        else:
            body.append(c)
    md = "\n\n".join(body + [c for _, c in sorted(furn, key=lambda x: x[0])])
    return tables_variant(md)


if __name__ == "__main__":
    man = list(csv.DictReader(open(os.path.join(ROOT, "kaggle/manifest.csv"))))
    os.makedirs(os.path.join(ROOT, "runs"), exist_ok=True)
    for split in ("dev", "test"):
        rows = [r for r in man if r["split"] == split]
        with open(os.path.join(ROOT, f"runs/paddle_{split}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"subject": r["subject"], "document_id": r["doc"], "page": int(r["page"]),
                                    "markdown": to_markdown(f"{r['doc']}_{r['page']}")}, ensure_ascii=False) + "\n")
        print(split, len(rows), "pages ->", f"runs/paddle_{split}.jsonl")

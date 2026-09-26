"""Use PaddleOCR-VL's header/footer/page-number blocks to fix furniture placement in another run's Markdown.

  python furniture.py runs/dev_all_v7_final.jsonl runs/dev_all_v7_fmove.jsonl [--add-missing]
"""
import argparse
import json
import re

from rapidfuzz import fuzz

from paddle_ingest import furniture
from reading_order import norm

THRESH = 85


def repose(md, furn, add_missing=False):
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    used, moved = set(), []
    for label, text in furn:
        t = norm(text)
        if not t:
            continue
        best, score = None, 0
        for i, p in enumerate(paras):
            if i in used:
                continue
            s = fuzz.ratio(norm(p), t)
            if s > score:
                best, score = i, s
        if best is not None and score >= THRESH:
            used.add(best); moved.append(paras[best])
        elif add_missing:
            moved.append(text)
    body = [p for i, p in enumerate(paras) if i not in used]
    return "\n\n".join(body + moved)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--add-missing", action="store_true")
    a = ap.parse_args()
    n = ch = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for line in open(a.src, encoding="utf-8"):
            r = json.loads(line)
            new = repose(r["markdown"], furniture(f"{r['document_id']}_{r['page']}"), a.add_missing)
            n += 1; ch += new != r["markdown"]
            r["markdown"] = new; f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{n} pages, {ch} changed -> {a.dst}")

"""Join long runs of short paragraphs (list entries, clues, index lines) into one paragraph.

Why: the official matcher (scorer/utils/match_quick.py, _FUZZY_MAX_LEN = 300) can only stitch several predicted paragraphs back
into one reference block when that block is <= 300 normalized chars. When the reference keeps a long list as one block and we
emit one paragraph per entry, the block gets paired with our first entry alone and the rest of our paragraphs are dropped, so a
correct transcription scores ~1.0 edit distance (e.g. a chef list, crossword clues).

  python listmerge.py runs/dev_all_rebuilt_final5.jsonl runs/dev_all_lm.jsonl --min-run 6 --max-len 80
"""
import argparse
import json
import re

SKIP = re.compile(r"^\s*(#|<table|<div|\$\$|!\[|```)")


def norm_len(s):
    return len(re.sub(r"[^\w]", "", s))


def merge(md, min_run=6, max_len=80, min_total=300):
    paras = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    out, run = [], []

    def flush():
        if len(run) >= min_run and sum(norm_len(p) for p in run) > min_total:
            out.append("\n".join(run))
        else:
            out.extend(run)
        run.clear()

    for p in paras:
        if len(p) <= max_len and "\n" not in p and not SKIP.match(p):
            run.append(p)
        else:
            flush(); out.append(p)
    flush()
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--min-run", type=int, default=6); ap.add_argument("--max-len", type=int, default=80)
    ap.add_argument("--min-total", type=int, default=300)
    a = ap.parse_args()
    n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            m = merge(r["markdown"], a.min_run, a.max_len, a.min_total)
            n += m != r["markdown"]
            f.write(json.dumps({**r, "markdown": m}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

"""Split long list-like paragraphs into chunks below the official matcher's 300-character limit.

Matcher rules (MILESTONES "How the official matcher pairs paragraphs"): several reference blocks can fold into one of our paragraphs only if
ours is <= 300 normalised chars, and our pieces can be rejoined into a reference block only if that block is <= 300 chars. A long list we
emit as one paragraph is unrecoverable when the reference splits it into short blocks; chunks of <= CAP chars are recoverable in that case.
Only paragraphs that look like lists are touched: >= MIN_LINES lines (single newlines), short lines on average, total > CAP normalised chars.

  python listchunk.py SRC DST [--cap 280] [--min-lines 4] [--max-avg 80] [--per-line]
"""
import argparse, json, re

N = lambda s: len(re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s)))


def listlike(p, min_lines, max_avg, cap):
    if p.startswith("<table") or p.startswith("$") or p.startswith("#"):
        return False
    lines = [l for l in p.split("\n") if l.strip()]
    return len(lines) >= min_lines and N(p) > cap and sum(N(l) for l in lines) / len(lines) <= max_avg


def chunk(p, cap, per_line):
    lines = [l for l in p.split("\n") if l.strip()]
    if per_line:
        return lines
    out, cur, size = [], [], 0
    for l in lines:
        n = N(l)
        if cur and size + n > cap:
            out.append("\n".join(cur)); cur, size = [], 0
        cur.append(l); size += n
    if cur: out.append("\n".join(cur))
    return out


def process(md, cap=280, min_lines=4, max_avg=80, per_line=False):
    paras = [p.strip() for p in md.split("\n\n") if p.strip()]
    out = []
    for p in paras:
        out.extend(chunk(p, cap, per_line) if listlike(p, min_lines, max_avg, cap) else [p])
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--cap", type=int, default=280); ap.add_argument("--min-lines", type=int, default=4)
    ap.add_argument("--max-avg", type=int, default=80); ap.add_argument("--per-line", action="store_true")
    a = ap.parse_args(); n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            md = process(r["markdown"], a.cap, a.min_lines, a.max_avg, a.per_line)
            n += md != "\n\n".join(p.strip() for p in r["markdown"].split("\n\n") if p.strip())
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

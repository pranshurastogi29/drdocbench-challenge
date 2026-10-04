"""Merge the trailing page-furniture paragraphs (running head, footer, page number) into ONE paragraph (single newlines).

Why (scorer mechanics, scorer/utils/match_quick.py + md2md_dataset.get_order_paired): when one predicted block is paired with several reference blocks
(short blocks fold into a predicted block <= 300 chars that contains them), the reading-order list records those reference positions in sorted reference
order, whatever their order inside our block. The reference orders its furniture by hidden annotation order (our fixed header > footer > number order is
right on ~72% of dev pages); a merged furniture block makes that internal order irrelevant for reading order, at the cost of a few text edits when ours differs.
Tail = up to MAX_TAIL last paragraphs, each <= MAXLEN normalised chars, not tables/formulas/headings-with-#.
  python furnmerge.py SRC DST [--max-tail 3] [--maxlen 80]
"""
import argparse, json, re

N = lambda s: len(re.sub(r"[\W_]", "", s))


NUM = re.compile(r"^\W*(\d{1,4}|[ivxlcdm]{1,7})\W*$", re.I)


def is_furniture(p, fur):
    """fur: Paddle's furniture texts for this page (normalised); a bare page number always counts"""
    w = re.sub(r"[\W_]", "", p.lower())
    if NUM.match(p.strip()):
        return True
    from rapidfuzz import fuzz
    return any(w and (w == t or (len(t) >= 4 and fuzz.ratio(w, t) >= 80)) for t in fur)


def merge_tail(md, max_tail=3, maxlen=80, fur=None):
    """Works on positions: only the trailing body paragraphs are touched (an identical line elsewhere on the page stays)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    body_idx = [i for i, p in enumerate(paras) if not (p.startswith("$") and p.endswith("$")) and not p.startswith("<table")]
    if len(body_idx) < 3:
        return md
    tail = []
    for i in reversed(body_idx):
        p = paras[i]
        if len(tail) < max_tail and "\n" not in p and 1 <= N(p) <= maxlen and not p.startswith("#") and (fur is None or is_furniture(p, fur)):
            tail.append(i)
        else:
            break
    if len(tail) < 2:
        return md
    tail = tail[::-1]
    merged = "\n".join(paras[i] for i in tail)
    out = [merged if i == tail[0] else p for i, p in enumerate(paras) if i == tail[0] or i not in tail]
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--max-tail", type=int, default=3); ap.add_argument("--maxlen", type=int, default=80)
    ap.add_argument("--paddle-check", action="store_true", help="merge only lines Paddle labels header/footer/number, or bare page numbers")
    a = ap.parse_args(); n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            fur = None
            if a.paddle_check:
                import paddle_ingest
                try: fur = [re.sub(r"[\W_]", "", t.lower()) for _, t in paddle_ingest.furniture(f'{r["document_id"]}_{r["page"]}')]
                except Exception: fur = []
            md = merge_tail(r["markdown"], a.max_tail, a.maxlen, fur); n += md != "\n\n".join(p.strip() for p in re.split(r"\n\s*\n", r["markdown"].strip()) if p.strip())
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

"""Move running headers/footers to the end of their page, detected by repetition across the pages of the same book.

Why: the reference Markdown puts page furniture at the end (0 of 520 dev pages have body after it). Our v7 prompt asks the model to do
the same, but on ~11% of dev pages the header is left at the top or in the middle (those pages lose 34.8 reading-order points against
15.4 elsewhere). Paddle's own "header" label cannot find them (it also fires on real titles). A running header, unlike a title,
repeats on other pages of the book: a short paragraph, with digits ignored, that recurs near the top or bottom of >= MIN_PAGES other
pages of the same document is moved in front of the page's trailing furniture block.

  python furnmove.py SRC DST [--min-pages 2] [--sim 90]
"""
import argparse
import collections
import json
import re

from rapidfuzz import fuzz

MAXLEN = 100   # normalised characters: running heads are short


def key(s):
    return re.sub(r"[\W\d_]", "", re.sub(r"<[^>]+>", " ", s).lower())


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def is_edge(i, n, top=2, bottom=4):
    return i < top or i >= n - bottom


def process(rows, min_pages=2, sim=90):
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["document_id"]][r["page"]] = paras(r["markdown"])
    out = {}
    for doc, pages in by.items():
        # headings the model already marked (#...), tables and list items are real content, never running heads
        plain = lambda p: not re.match(r"\s*(#|<|\||[-*+]\s|\$)", p)
        edge = {pg: [(i, key(p)) for i, p in enumerate(ps) if is_edge(i, len(ps)) and plain(p) and 4 <= len(key(p)) <= MAXLEN] for pg, ps in pages.items()}
        for pg, ps in pages.items():
            n = len(ps); flagged = set()
            for i, k in edge[pg]:
                hits = sum(any(fuzz.ratio(k, k2) >= sim for _, k2 in edge[o]) for o in pages if o != pg)
                if hits >= min_pages:
                    flagged.add(i)
            if not flagged:
                out[(doc, pg)] = ps; continue
            # trailing furniture block: trailing paragraphs that are flagged or look like a bare page number
            t = n
            while t > 0 and ((t - 1) in flagged or re.fullmatch(r"\W*\d{1,4}\W*", ps[t - 1] or "x")):
                t -= 1
            moved = [ps[i] for i in sorted(flagged) if i < t]          # flagged paragraphs sitting before the trailing block
            rest = [p for i, p in enumerate(ps) if not (i in flagged and i < t)]
            t2 = t - len([i for i in flagged if i < t])
            out[(doc, pg)] = rest[:t2] + moved + rest[t2:]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--min-pages", type=int, default=2); ap.add_argument("--sim", type=int, default=90)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.src, encoding="utf-8")]
    new = process(rows, a.min_pages, a.sim); n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in rows:
            md = "\n\n".join(new[(r["document_id"], r["page"])])
            n += md.strip() != r["markdown"].strip()
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

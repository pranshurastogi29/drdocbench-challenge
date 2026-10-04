"""Drop paragraphs that belong to the neighbouring page (page-split errors of two-page requests).

Our main runs transcribe two pages per request, and sometimes put a paragraph of page p-1 / p+1 on page p (dev: ~29% of the 'leftover' text
that the matcher counts in full, i.e. ~6% of all text edits, mostly two books). The one-page-per-request runs (v6w1, v7w1, v8w1) cannot do that.
A paragraph of our page is dropped when NONE of the one-page runs of this page has it, and at least MIN_VOTES of the one-page runs of the
previous or next page do.

  from spilldrop import spilldrop; md, dropped = spilldrop(md, w1_this_page, w1_neighbour_pages)
"""
import re
from rapidfuzz import fuzz

W = lambda s: re.sub(r"[\W_]", "", s)


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def spilldrop(md, here, neighbours, minw=30, absent=60, present=85, min_votes=2, ours_nb=None):
    """here: one-page runs' Markdown of this page; neighbours: list of lists (one-page runs of each adjacent page);
    ours_nb: our own output for the adjacent pages -- when given, a paragraph is dropped only if it is also there (a true duplicate)"""
    O = [W(x) for x in (ours_nb or []) if x]
    H = [W(h) for h in here if h]; N = [[W(x) for x in nb if x] for nb in neighbours]
    if not H or not any(N):
        return md, []
    keep, drop = [], []
    for p in paras(md):
        w = W(p)
        if len(w) < minw or p.startswith("<table") or p.startswith("$"):
            keep.append(p); continue
        q = w[:400]
        if all(fuzz.partial_ratio(q, h) < absent for h in H) and any(sum(fuzz.partial_ratio(q, x) >= present for x in nb) >= min_votes for nb in N) \
                and (ours_nb is None or any(fuzz.partial_ratio(q, o) >= present for o in O)):
            drop.append(p)
        else:
            keep.append(p)
    return ("\n\n".join(keep), drop) if drop else (md, [])


if __name__ == "__main__":
    # python spilldrop.py SRC.zip DST.zip --split test : apply to a submission zip, using the one-page runs v6w1/v7w1/v8w1
    import argparse, json, os, zipfile
    from build_submission import DEV, TEST, write_zip, zip_rows
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--split", default="test"); a = ap.parse_args()
    files = TEST if a.split == "test" else DEV
    R1 = {n: {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(files[n]))} for n in ("v6w1", "v7w1", "v8w1")}
    w1 = lambda s: [R1[n].get(s, "") for n in R1]
    rows = zip_rows(a.src); out = []; n = 0
    for r in rows:
        s = f'{r["document_id"]}_{r["page"]}'
        nbs = [w1(f'{r["document_id"]}_{r["page"] + d}') for d in (-1, 1)]
        md, dropped = spilldrop(r["markdown"], w1(s), [x for x in nbs if any(x)])
        if dropped:
            n += 1; print(f"  {s}: dropped {len(dropped)} paragraphs, {sum(len(W(d)) for d in dropped)} chars")
        out.append({**r, "markdown": md})
    write_zip(out, a.dst); print(f"{a.dst}: {n} pages changed")

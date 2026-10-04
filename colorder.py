"""Column-major reordering of our body paragraphs using PaddleOCR-VL block boxes (geometry only; Paddle's own reading order is NOT used).
Each body paragraph is located in Paddle's text blocks (fuzzy match) to get a box. The page is cut into horizontal bands by full-width blocks
(wider than WIDE of the page); inside a band, blocks are ordered left column top-to-bottom, then right column. Paragraphs that cannot be located
stay attached to the paragraph before them. Furniture tail (last paragraphs that Paddle labels header/footer/number), tables and formulas keep their place.
Applies only when a band has >= MINCOL located blocks in each of two columns and our current order differs from column-major.
  python colorder.py SRC DST --split dev|test [--wide 0.6] [--mincol 1]
"""
import argparse, json, os, re
from rapidfuzz import fuzz

ROOT = os.path.dirname(os.path.abspath(__file__))
W = lambda s: re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s or "").lower())
SKIPLAB = {"header", "footer", "number", "header_image", "footer_image", "image", "chart", "table", "display_formula", "formula_number", "seal"}


def paddle_blocks(stem):
    f = os.path.join(ROOT, "kaggle", "results", "paddle", "out", stem, f"{stem}_res.json")
    if not os.path.exists(f): return None, []
    j = json.load(open(f))
    return j["width"], [(W(b.get("block_content")), b["block_bbox"]) for b in j["parsing_res_list"] if b["block_label"] not in SKIPLAB and W(b.get("block_content"))]


def special(p):
    return (p.startswith("$") and p.endswith("$")) or p.startswith("<table") or p.startswith("![")


def reorder(md, stem, wide=0.6, mincol=1):
    Wd, blocks = paddle_blocks(stem)
    if not blocks: return md
    paras = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    body = [i for i, p in enumerate(paras) if not special(p)]
    loc = {}
    for i in body:
        w = W(paras[i])
        if len(w) < 15: continue
        best, bb = 0, None
        for t, box in blocks:
            s = fuzz.partial_ratio(w[:120], t) if len(w) >= 15 else 0
            if s > best: best, bb = s, box
        if bb is not None and best >= 85: loc[i] = bb
    if len(loc) < 3: return md
    # units: a located paragraph plus the unlocated ones that follow it (kept together)
    units, cur = [], None
    for i in body:
        if i in loc or cur is None:
            cur = [i]; units.append(cur)
        else:
            cur.append(i)
    if units and units[0][0] not in loc: return md
    def wide_(u): b = loc[u[0]]; return (b[2] - b[0]) > wide * Wd
    # bands separated by wide units, in our current order
    bands, band = [], []
    for u in units:
        if wide_(u):
            if band: bands.append(band)
            bands.append([u]); band = []
        else:
            band.append(u)
    if band: bands.append(band)
    new = []; changed = False
    for band in bands:
        if len(band) < 2: new.extend(band); continue
        mid = Wd / 2
        left = [u for u in band if (loc[u[0]][0] + loc[u[0]][2]) / 2 < mid]; right = [u for u in band if u not in left]
        if len(left) < mincol or len(right) < mincol: new.extend(band); continue
        cm = sorted(left, key=lambda u: loc[u[0]][1]) + sorted(right, key=lambda u: loc[u[0]][1])
        if cm != band: changed = True
        new.extend(cm)
    if not changed: return md
    order = [i for u in new for i in u]
    bset = set(body); it = iter(order)
    out = [paras[next(it)] if i in bset else p for i, p in enumerate(paras)]
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--split", default="dev")
    ap.add_argument("--wide", type=float, default=0.6); ap.add_argument("--mincol", type=int, default=1)
    a = ap.parse_args(); n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            md = reorder(r["markdown"], f'{r["document_id"]}_{r["page"]}', a.wide, a.mincol)
            n += md != "\n\n".join(p.strip() for p in re.split(r"\n\s*\n", r["markdown"].strip()) if p.strip())
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages reordered")

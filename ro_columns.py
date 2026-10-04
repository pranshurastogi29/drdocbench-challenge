"""Column convention of the dev reference vs our output, band by band.
A page is cut into horizontal bands by full-width blocks (>= 60% of page width). Inside a band, narrow text blocks are assigned to columns by
x-centre clustering. A band is 'column-major' if the reference reads every block of a column before the next column, 'row-major' if it
interleaves by height. For our output (MBR base5 pick, processed), the same test on the paired blocks (matched to layout blocks by text).
Also: where do full-width blocks (titles, captions spanning) and the band order fall.
  python ro_columns.py
"""
import collections, glob, json, os, re, sys, statistics as st
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from rapidfuzz import fuzz
from common import gt_markdown
from sel_lab import BASE5, pick_mbr

W_ = lambda s: re.sub(r"[\W_]", "", (s or "").lower())
FUR = {"header", "footer", "page_number"}


def box(b):
    p = b["poly"]; xs, ys = p[0::2], p[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def page_layout(stem):
    doc, pg = stem.rsplit("_", 1)
    f = glob.glob(os.path.join(ROOT, "data/dev/*", doc, "json", f"{doc}_page_{pg}.json"))
    j = json.load(open(f[0])) if f else []
    if not j: return None
    x = j[0]
    return x["page_info"], [dict(cat=b["category_type"], order=b.get("order"), box=box(b), w=W_(b.get("text"))) for b in x["layout_dets"] if not b.get("ignore")]


def bands(B, W):
    """list of bands; each band = list of narrow body blocks with a column index"""
    body = sorted([b for b in B if b["order"] is not None and b["cat"] not in FUR and b["cat"] not in ("figure", "table", "equation_isolated")], key=lambda b: b["box"][1])
    full = [b for b in body if b["box"][2] - b["box"][0] >= 0.6 * W]
    cuts = sorted([b["box"][1] for b in full]) + [1e9]
    out, prev = [], -1
    for c in cuts:
        nb = [b for b in body if b["box"][2] - b["box"][0] < 0.6 * W and prev <= (b["box"][1] + b["box"][3]) / 2 < c]
        prev = c
        if len(nb) < 2: continue
        xs = sorted((b["box"][0] + b["box"][2]) / 2 for b in nb)
        gaps = [(xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)]
        splits = sorted(xs[i] + g / 2 for g, i in gaps if g > 0.15 * W)
        if not splits: continue
        for b in nb: b["col"] = sum((b["box"][0] + b["box"][2]) / 2 > s for s in splits)
        out.append(nb)
    return out


def classify(band, rank):
    """rank: block id -> order position (reference or ours). Returns column-major / row-major / mixed"""
    seq = sorted([b for b in band if id(b) in rank], key=lambda b: rank[id(b)])
    if len(seq) < 3 or len({b["col"] for b in seq}) < 2: return None
    cols = [b["col"] for b in seq]
    runs = sum(1 for i in range(1, len(cols)) if cols[i] != cols[i - 1]) + 1
    if runs == len({*cols}) and cols == sorted(cols): return "column-major"
    ys = [b["box"][1] for b in seq]
    if all(ys[i] <= ys[i + 1] + 15 for i in range(len(ys) - 1)): return "row-major (by height)"
    return "mixed"


def job(a):
    k, v = a; L = page_layout(k)
    if not L: return k, None
    info, B = L; W = info["width"]
    bs = bands(B, W)
    if not bs: return k, (info["page_attribute"].get("layout"), [], [])
    ref = {id(b): b["order"] for band in bs for b in band}
    # ours: position of each layout block in our page text (best fuzzy partner paragraph)
    md = v["proc"][pick_mbr(v, BASE5)]
    P = [W_(p) for p in re.split(r"\n\s*\n", md) if p.strip()]
    ours = {}
    for band in bs:
        for b in band:
            if len(b["w"]) < 8: continue
            sc = [(fuzz.partial_ratio(b["w"][:150], p) if p else 0, i) for i, p in enumerate(P)]
            s, i = max(sc) if sc else (0, None)
            if s >= 85: ours[id(b)] = i + 0.001 * (P[i].find(b["w"][:20]) if P[i].find(b["w"][:20]) >= 0 else 0)
    return k, (info["page_attribute"].get("layout"), [classify(band, ref) for band in bs], [classify(band, ours) for band in bs])


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11) as P: R = [r for r in P.map(job, sorted(C.items()), chunksize=4) if r[1]]
    ref = collections.Counter(); both = collections.Counter(); lay = collections.defaultdict(collections.Counter)
    for k, (layout, rc, oc) in R:
        for r, o in zip(rc, oc):
            if r: ref[r] += 1; lay[layout][r] += 1
            if r and o: both[(r, o)] += 1
    print("reference, multi-column bands:", dict(ref))
    print("by page layout:", {k: dict(v) for k, v in lay.items()})
    print("reference vs ours (same band):")
    for (r, o), n in sorted(both.items(), key=lambda x: -x[1]): print(f"   ref {r:22s} ours {o:22s} {n}")


def show(k, v):
    info, B = page_layout(k); bs = bands(B, info["width"])
    md = v["proc"][pick_mbr(v, BASE5)]; P = [W_(p) for p in re.split(r"\n\s*\n", md) if p.strip()]
    for band in bs:
        ref = {id(b): b["order"] for b in band}
        if classify(band, ref) != "column-major": continue
        rows = []
        for b in sorted(band, key=lambda b: b["order"]):
            sc = [(fuzz.partial_ratio(b["w"][:150], p) if p else 0, i) for i, p in enumerate(P)] if len(b["w"]) >= 8 else []
            s, i = max(sc) if sc else (0, None)
            rows.append((b["order"], b["col"], int(b["box"][1]), b["cat"], i if s >= 85 else None, b["w"][:40]))
        print("  band:"); [print(f"    ref#{r[0]:3d} col{r[1]} y{r[2]:5d} {r[3]:15s} ours-para {r[4]!s:5s} {r[5]}") for r in rows]


if __name__ == "__main__" and len(sys.argv) > 1:
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json")))
    for k in sys.argv[1:]:
        print("==", k, page_layout(k)[0]["page_attribute"].get("layout")); show(k, C[k])

"""How often (dev) (A) the reference splits a paragraph at a column break and we join it; (B) a caption / figure note sits inside the column
flow in the reference while we move it. Uses ro_columns.py bands; our page = MBR base5 pick, processed.
  python ro_colbreak.py
"""
import collections, json, os, re, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
import ro_columns as R
from sel_lab import BASE5, pick_mbr


def where(b, P):
    if len(b["w"]) < 8: return None
    head, tail = b["w"][:40], b["w"][-40:]
    for i, p in enumerate(P):
        if head in p or (len(head) >= 20 and fuzz.partial_ratio(head, p) >= 92): return i
    return None


def job(a):
    k, v = a; L = R.page_layout(k)
    if not L: return k, None
    info, B = L; bs = R.bands(B, info["width"])
    md = v["proc"][pick_mbr(v, BASE5)]; P = [R.W_(p) for p in re.split(r"\n\s*\n", md) if p.strip()]
    out = collections.Counter(); ex = []
    for band in bs:
        if R.classify(band, {id(b): b["order"] for b in band}) != "column-major": continue
        seq = sorted(band, key=lambda b: b["order"])
        for x, y in zip(seq, seq[1:]):
            if x["col"] != y["col"] and x["cat"] == y["cat"] == "text_block":
                cont = bool(y["w"]) and (y["w"][0].islower())
                out["column break between text blocks"] += 1; out["...next block starts lower-case (continuation)"] += cont
                i, j = where(x, P), where(y, P)
                if i is not None and i == j:
                    out["...we JOIN them into one paragraph"] += 1; ex.append(k)
                elif i is not None and j is not None: out["...we keep them apart"] += 1
        for b in seq:
            if b["cat"] in ("figure_caption", "figure_footnote", "table_caption"):
                prev = [z for z in seq if z["order"] < b["order"] and z["col"] == b["col"] and z["cat"] == "text_block"]
                nxt = [z for z in seq if z["order"] > b["order"] and z["col"] == b["col"] and z["cat"] == "text_block"]
                i = where(b, P); ip = where(prev[-1], P) if prev else None; inx = where(nxt[0], P) if nxt else None
                if i is None or (ip is None and inx is None): continue
                out["caption inside a column, located in ours"] += 1
                ok = (ip is None or ip < i) and (inx is None or i < inx)
                out["...ours keeps it between the same text blocks" if ok else "...ours MOVES it"] += 1
    return k, (out, ex)


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11) as P: res = [r for r in P.map(job, sorted(C.items()), chunksize=4) if r[1]]
    tot = collections.Counter(); ex = []
    for k, (o, e) in res: tot.update(o); ex += e
    for kk, vv in tot.items(): print(f"  {kk:55s} {vv}")
    print("  pages with a joined column break:", len(set(ex)), sorted(set(ex))[:8])

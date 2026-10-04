"""How much of the text error is the matcher's 'leftover' record: when every reference block is paired, ALL our unpaired blocks are joined
into one record that counts in full (scorer/utils/match_quick.py convert_final_matches); when any reference block is unpaired they are free.
  python extras_share.py   (dev, MBR base5 pick, processed)
"""
import json, os, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from sel_lab import BASE5, pick_mbr


def job(a):
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    md = v["proc"][pick_mbr(v, BASE5)]
    g = mbr.md_tex_filter(gt).get("text_all") or []; p = mbr.md_tex_filter(md).get("text_all") or []
    recs = mbr.match(g, p, "text", "x"); ed = den = xe = 0; xtext = ""
    for r in recs:
        a_ = r.get("norm_gt") or ""; b = r.get("norm_pred") or ""
        if a_ or b:
            e = mbr.Lev(b, a_); ed += e; den += max(len(a_), len(b))
            if not a_: xe += e; xtext = (r.get("pred") or "")[:160]
    return k, v["subject"], ed, den, xe, xtext


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = P.map(job, sorted(C.items()), chunksize=4)
    E = sum(r[2] for r in R); D = sum(r[3] for r in R); X = sum(r[4] for r in R)
    print(f"dev Text_ED (pooled) {E/D:.4f}; leftover-record edits {X} = {X/E:.1%} of all edits, on {sum(r[4] > 0 for r in R)} pages; without them Text_ED would be {(E-X)/(D-X):.4f}")
    for r in sorted(R, key=lambda r: -r[4])[:15]:
        print(f"  {r[4]:5d} edits  {r[1][:16]:16s} {r[0][:8]}..{r[0][-4:]}  {r[5]!r}")


def classify(a):
    """split each leftover block by where its text is in the reference: in a reference table / in reference text / nowhere"""
    import re
    from rapidfuzz import fuzz
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    md = v["proc"][pick_mbr(v, BASE5)]
    g = mbr.md_tex_filter(gt).get("text_all") or []; p = mbr.md_tex_filter(md).get("text_all") or []
    recs = mbr.match(g, p, "text", "x")
    W = lambda s: re.sub(r"[\W_]", "", s)
    tables = W(" ".join(re.findall(r"<table.*?</table>", gt, re.S)))
    tables = W(re.sub(r"<[^>]+>", " ", " ".join(re.findall(r"<table.*?</table>", gt, re.S))))
    textonly = W(re.sub(r"<table.*?</table>", " ", gt, flags=re.S))
    out = []
    for r in recs:
        if r.get("norm_gt"): continue
        for i in (r["pred_idx"] if isinstance(r["pred_idx"], list) else [r["pred_idx"]]):
            if i == "": continue
            w = W(p[i].get("content") or p[i].get("text") or "") if isinstance(p[i], dict) else W(str(p[i]))
            if len(w) < 4: continue
            pt = fuzz.partial_ratio(w[:400], tables) if tables else 0; px = fuzz.partial_ratio(w[:400], textonly)
            out.append((len(w), "in ref table" if pt >= 85 and pt >= px else "in ref text" if px >= 85 else "not in ref", v["subject"], w[:80]))
    return out


if __name__ == "__main__":
    import collections
    with Pool(11, initializer=mbr._init) as P: O = [x for o in P.map(classify, sorted(C.items()), chunksize=4) for x in o]
    tot = sum(x[0] for x in O); cnt = collections.Counter()
    for x in O: cnt[x[1]] += x[0]
    print(f"\nleftover blocks {len(O)}, {tot} chars:", ", ".join(f"{c} {n/tot:.0%}" for c, n in cnt.most_common()))
    by = collections.defaultdict(collections.Counter)
    for x in O: by[x[1]][x[2]] += x[0]
    for c in by: print(f"  {c}: top subjects", by[c].most_common(6))
    for c in ("not in ref", "in ref text"):
        print(f"  examples {c}:"); [print("    ", x[2][:14], repr(x[3])) for x in sorted([x for x in O if x[1] == c], key=lambda x: -x[0])[:8]]


def neighbour(a):
    """for 'not in ref' leftover text: is it in the reference of the previous / next page of the same book (page-split error)?"""
    import re, glob
    from rapidfuzz import fuzz
    k, v = a; doc, pg = k.rsplit("_", 1); pg = int(pg); gt = gt_markdown("dev", v["subject"], doc, pg)
    md = v["proc"][pick_mbr(v, BASE5)]
    g = mbr.md_tex_filter(gt).get("text_all") or []; p = mbr.md_tex_filter(md).get("text_all") or []
    recs = mbr.match(g, p, "text", "x")
    W = lambda s: re.sub(r"[\W_]", "", s); full = W(re.sub(r"<[^>]+>", " ", gt))
    nb = {d: W(re.sub(r"<[^>]+>", " ", gt_markdown("dev", v["subject"], doc, pg + d))) for d in (-2, -1, 1, 2)}
    out = []
    for r in recs:
        if r.get("norm_gt"): continue
        for i in (r["pred_idx"] if isinstance(r["pred_idx"], list) else [r["pred_idx"]]):
            if i == "": continue
            w = W(p[i].get("content") or p[i].get("text") or "") if isinstance(p[i], dict) else W(str(p[i]))
            if len(w) < 4 or fuzz.partial_ratio(w[:400], full) >= 85: continue
            where = next((f"page {d:+d}" for d in (-1, 1, -2, 2) if nb[d] and fuzz.partial_ratio(w[:400], nb[d]) >= 85), "nowhere")
            out.append((len(w), where, v["subject"], k))
    return out


if __name__ == "__main__":
    with Pool(11, initializer=mbr._init) as P: O = [x for o in P.map(neighbour, sorted(C.items()), chunksize=4) for x in o]
    tot = sum(x[0] for x in O); cnt = collections.Counter()
    for x in O: cnt[x[1]] += x[0]
    print(f"\n'not in ref' leftover chars {tot}:", ", ".join(f"{c} {n/tot:.0%}" for c, n in cnt.most_common()))
    pg = collections.defaultdict(collections.Counter)
    for x in O: pg[x[1]][x[3][:8] + " " + x[2][:12]] += x[0]
    for c in pg: print(f"  {c}: books", pg[c].most_common(8))

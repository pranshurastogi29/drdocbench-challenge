"""Reading-order loss anatomy of the CURRENT pipeline (stack.py steps; default = the 84.13 text/order pipeline), dev, md2md matcher.
Same accounting as ro_anatomy2.py (LIS: paired blocks outside the longest in-order run are 'displaced', reference blocks without a partner
are 'unpaired'; each block labelled with its layout category from the dev JSON), plus concrete examples of displaced furniture: the
reference order and ours, as category letters (B body text, T title, H header, F footer, N page number, C caption, f footnote, ? unknown).
  python ro_anatomy3.py [--steps ...] [--examples page_number]
"""
import argparse, collections, json, os, re, statistics as st, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from ro_anatomy2 import lis_idx, layout, W
from rapidfuzz import fuzz
LET = {"text_block": "B", "title": "T", "header": "H", "footer": "F", "page_number": "N", "figure_caption": "C", "table_caption": "C",
       "page_footnote": "f", "figure_footnote": "f", "table_footnote": "f", "reference": "R", "equation_caption": "E", "code_txt": "K"}


def job(a):
    import md2md_eval as M
    from common import gt_markdown
    k, subj, md = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    g = M.md_tex_filter(gt).get("text_all") or []; p = M.md_tex_filter(md).get("text_all") or []
    if not g: return k, None
    recs = M.match(g, p, "text", "x", skip_truncated=True)
    L = layout(k); txt = {}
    for r in recs:
        if r["gt_position"] != [""]:
            for gp in r["gt_position"]: txt.setdefault(gp, r.get("gt") or "")
    def cat(gp):
        w = W(txt.get(gp, ""))[:200]
        if not w or not L: return "?"
        best = max(L, key=lambda c: fuzz.partial_ratio(w, c[1][:400]) if c[1] else 0)
        return best[0] if fuzz.partial_ratio(w, best[1][:400]) >= 70 else "?"
    G = sorted(x for x in sum([r["gt_position"] for r in recs if r["gt_position"] != [""]], []) if x)
    matched = sorted([r for r in recs if r["gt_position"] != [""] and r["pred_position"] != ""], key=lambda r: r["pred_position"])
    P = [x for r in matched for x in r["gt_position"] if x]
    if not G: return k, None
    ro = 100 * (1 - M.Lev(G, P) / max(len(G), len(P)))
    keep = lis_idx(P); disp = [P[i] for i in range(len(P)) if i not in keep]; unp = sorted(set(G) - set(P))
    rank = {x: i for i, x in enumerate(G)}; prank = {x: i for i, x in enumerate(P)}
    cats = {x: cat(x) for x in G}
    items = [("displaced", cats[x], "early" if prank[x] < rank[x] else "late") for x in disp] + [("unpaired", cats[x], "") for x in unp]
    share = (100 - ro) / len(items) if items else 0
    seq = lambda xs: "".join(LET.get(cats[x], "?") for x in xs)
    return k, {"ro": ro, "items": [(a_, b, c, share) for a_, b, c in items], "G": seq(G), "P": seq(P), "disp": [cats[x] for x in disp]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--steps", default="sel=mbr8,rules,fm,sd,bv,rv=free,ac"); ap.add_argument("--examples", default="page_number,header")
    a = ap.parse_args()
    import stack, md2md_eval as M
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", a.steps, tmp)
    os.chdir(ROOT)
    with Pool(11, initializer=M.init) as P: R = {k: r for k, r in P.map(job, [(f'{r["document_id"]}_{r["page"]}', r["subject"], r["markdown"]) for r in rows], chunksize=6) if r}
    os.chdir(ROOT); json.dump(R, open(os.path.join(ROOT, "runs", "ro_anatomy3.json"), "w"))
    N = len(R); print(f"{N} pages; mean RO {st.mean(r['ro'] for r in R.values()):.2f}")
    agg = collections.defaultdict(float); cnt = collections.Counter(); dirn = collections.defaultdict(collections.Counter); pages = collections.defaultdict(set)
    for k, r in R.items():
        for kind, c, d, s in r["items"]:
            agg[(kind, c)] += s / N; cnt[(kind, c)] += 1; pages[(kind, c)].add(k)
            if d: dirn[c][d] += 1
    for (kind, c), v in sorted(agg.items(), key=lambda x: -x[1])[:16]:
        print(f"  {kind:10s} {c or '-':16s} {v:6.2f} RO pts  {cnt[(kind, c)]:4d} blocks {len(pages[(kind, c)]):4d} pages  {dict(dirn[c]) if kind == 'displaced' else ''}")
    for want in a.examples.split(","):
        ex = [(k, r) for k, r in R.items() if want in r["disp"]][:14]
        print(f"\nexamples with a displaced {want} (reference order | ours):")
        for k, r in ex: print(f"  {k[:8]} p{k.rsplit('_',1)[1]:>4} RO {r['ro']:5.1f}  {r['G']:<40s} | {r['P']}")

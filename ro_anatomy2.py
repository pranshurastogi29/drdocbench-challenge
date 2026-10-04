"""Reading-order loss anatomy of the current best selection (MBR base5 + rules + furniture merge, dev selection cache).
Per page: the scorer's pairing; our order of paired reference blocks; the longest run already in reference order (LIS); every paired block outside
it is 'displaced', every reference block without a partner is 'unpaired'. Each block is labelled with its reference layout category (dev layout
JSON, matched by text). Loss is shared out per page so that the categories add up to the page's order loss (100 - Reading_Order).
For displaced blocks, also: do we put it too EARLY or too LATE relative to the reference?
  python ro_anatomy2.py   -> runs/ro_anatomy2.json
"""
import bisect, collections, glob, json, os, re, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from rapidfuzz import fuzz
from sel_lab import BASE5, pick_mbr

W = lambda s: re.sub(r"[\W_]", "", (s or "").lower())


def lis_idx(seq):
    tails, tidx, prev = [], [], [-1] * len(seq)
    for i, v in enumerate(seq):
        j = bisect.bisect_left(tails, v)
        if j == len(tails): tails.append(v); tidx.append(i)
        else: tails[j] = v; tidx[j] = i
        prev[i] = tidx[j - 1] if j else -1
    out, i = set(), tidx[-1] if tidx else -1
    while i >= 0: out.add(i); i = prev[i]
    return out


def layout(stem):
    doc, pg = stem.rsplit("_", 1)
    f = glob.glob(os.path.join(ROOT, "data", "dev", "*", doc, "json", f"*_{pg}.json")) or glob.glob(os.path.join(ROOT, "data", "dev", "*", doc, "json", f"*{pg}.json"))
    for x in (json.load(open(f[0])) if f else []):
        if str(x["page_info"]["page_no"]) == pg:
            return [(b.get("category_type"), W(b.get("text") or "")) for b in x["layout_dets"] if b.get("text")]
    return []


def job(a):
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    md = v["proc"][pick_mbr(v, BASE5)]
    g = mbr.md_tex_filter(gt).get("text_all") or []; p = mbr.md_tex_filter(md).get("text_all") or []
    recs = mbr.match(g, p, "text", "x")
    L = layout(k); txt = {}
    for r in recs:
        if r["gt_position"] != [""]:
            parts = r.get("gt") or ""
            for gp in r["gt_position"]: txt.setdefault(gp, parts)
    def cat(gp):
        w = W(txt.get(gp, ""))[:200]
        if not w or not L: return "?"
        best = max(L, key=lambda c: fuzz.partial_ratio(w, c[1][:400]) if c[1] else 0)
        return best[0] if fuzz.partial_ratio(w, best[1][:400]) >= 70 else "?"
    G = sorted(x for x in sum([r["gt_position"] for r in recs if r["gt_position"] != [""]], []) if x)
    matched = sorted([r for r in recs if r["gt_position"] != [""] and r["pred_position"] != ""], key=lambda r: r["pred_position"])
    P = [x for r in matched for x in r["gt_position"] if x]
    if not G: return k, None
    ro = 100 * (1 - mbr.Lev(G, P) / max(len(G), len(P)))
    keep = lis_idx(P); disp = [P[i] for i in range(len(P)) if i not in keep]; unp = sorted(set(G) - set(P))
    rank = {x: i for i, x in enumerate(G)}; prank = {x: i for i, x in enumerate(P)}
    items = [("displaced", x, cat(x), "early" if prank[x] < rank[x] else "late") for x in disp] + [("unpaired", x, cat(x), "") for x in unp]
    loss = 100 - ro; share = loss / len(items) if items else 0
    return k, {"ro": ro, "n": len(G), "items": [(kind, c, d, share) for kind, _, c, d in items], "layout": v["subject"]}


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = {k: r for k, r in P.map(job, sorted(C.items()), chunksize=4) if r}
    os.chdir(ROOT); json.dump(R, open("runs/ro_anatomy2.json", "w"))
    N = len(R); print(f"{N} pages; mean RO {st.mean(r['ro'] for r in R.values()):.2f}; mean loss {st.mean(100 - r['ro'] for r in R.values()):.2f} points")
    agg = collections.defaultdict(float); cnt = collections.Counter(); dirn = collections.defaultdict(collections.Counter); pages = collections.defaultdict(set)
    for k, r in R.items():
        for kind, c, d, s in r["items"]:
            agg[(kind, c)] += s / N; cnt[(kind, c)] += 1; pages[(kind, c)].add(k)
            if d: dirn[c][d] += 1
    print(f"{'kind':10s} {'category':18s} {'RO pts':>7s} {'blocks':>7s} {'pages':>6s}  early/late")
    for (kind, c), v in sorted(agg.items(), key=lambda x: -x[1])[:22]:
        print(f"{kind:10s} {c or '-':18s} {v:7.2f} {cnt[(kind, c)]:7d} {len(pages[(kind, c)]):6d}  {dict(dirn[c]) if kind == 'displaced' else ''}")
    worst = sorted(R.items(), key=lambda x: x[1]["ro"])[:10]
    print("\nworst pages:", [(k[:8] + ".." + k[-4:], round(r["ro"]), r["n"]) for k, r in worst])

"""Dev evaluation of para_fuse.py on the selection cache: skeleton = medoid5 / MBR pick, fused with the other candidates of the pool.
  python para_fuse_eval.py [--minsim 70] [--lenr 0.75]
"""
import argparse, collections, json, os, random, statistics as st, sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from ensemble_lab import gt_score
from common import gt_markdown
from para_fuse import fuse
from sel_lab import BASE5, FREE, U, pick_mbr
from build_submission import medoid


def job(a):
    stem, v, minsim, lenr = a
    doc, pg = stem.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg)); res = {}
    for pn, pool in (("base5", BASE5), ("free11", FREE)):
        for sel in ("medoid5", "mbr"):
            if sel == "medoid5" and pn == "free11": continue
            sk = medoid(v["raw"], BASE5) if sel == "medoid5" else pick_mbr(v, pool)
            md, n = fuse(v["proc"][sk], [v["proc"][o] for o in pool if o != sk], minsim, lenr)
            res[f"{sel} {pn}"] = (v["gt"][sk], gt_score(md, gt) if n else v["gt"][sk], n)
    return stem, res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--minsim", type=int, default=70); ap.add_argument("--lenr", type=float, default=0.75); a = ap.parse_args()
    C = json.load(open(os.path.join(ROOT, "runs", "selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    base = {k: medoid(C[k]["raw"], BASE5) for k in C}
    with Pool(11, initializer=mbr._init) as P:
        R = dict(P.imap_unordered(job, [(k, C[k], a.minsim, a.lenr) for k in sorted(C)], chunksize=4))
    for name in R[next(iter(R))]:
        by = collections.defaultdict(list); bt0 = collections.defaultdict(list); n = 0; tx = []; ro = []
        for k, r in R.items():
            before, after, ch = r[name]; n += ch
            by[k.rsplit("_", 1)[0]].append(U(after) - U(before)); bt0[k.rsplit("_", 1)[0]].append(U(after) - U(C[k]["gt"][base[k]]))
            tx.append(after[0] - before[0]); ro.append(after[1] - before[1])
        books = list(by); rng = random.Random(0)
        m = lambda D, bs: sum(sum(D[x]) for x in bs) / sum(len(D[x]) for x in bs)
        bt = sorted(m(by, rng.choices(books, k=len(books))) for _ in range(2000))
        print(f"{name:14s} fusion gain {m(by, books):+.3f} [{bt[50]:+.3f},{bt[1949]:+.3f}] (text {st.mean(tx):+.2f}, order {st.mean(ro):+.2f}); "
              f"books {sum(st.mean(x) > 0 for x in by.values())}/{sum(st.mean(x) < 0 for x in by.values())}; paragraphs replaced {n}; total vs medoid5 {m(bt0, books):+.2f}")

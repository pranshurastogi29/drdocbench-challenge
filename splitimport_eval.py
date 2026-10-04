"""Full-dev evaluation of splitimport.py: current pipeline page (MBR base5 pick, processed) + splits imported from v10 runs.
  python splitimport_eval.py --runs ab_v10a+v10a_rest[,ab_v10b] [--k 1]       ('+' joins run files covering different windows)
"""
import argparse, collections, json, os, random, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from ab_ro_eval import layout_of, MC
from bvote import bvote
from common import gt_markdown
from ensemble_lab import gt_score
from postprocess import strip_sections
from sel_lab import BASE5, U, pick_mbr


def job(a):
    k, v, srcs, kk = a; pick = pick_mbr(v, BASE5); md = v["proc"][pick]; base = v["gt"][pick]
    new, _, s = bvote(md, srcs, k=kk, do_merge=False, long_only=False)
    if not s: return k, (base, base, 0)
    doc, pg = k.rsplit("_", 1)
    return k, (base, gt_score(new, gt_markdown("dev", v["subject"], doc, int(pg))), s)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--runs", required=True); ap.add_argument("--k", type=int, default=1); a = ap.parse_args()
    S = []
    for grp in a.runs.split(","):
        d = {}
        for n in grp.split("+"):
            d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{n}.jsonl")))})
        S.append(d)
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    keys = [k for k in sorted(C) if all(k in d for d in S)]; lay = layout_of()
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], [d[k] for d in S], a.k) for k in keys], chunksize=4))
    print(f"{len(keys)} of {len(C)} dev pages covered by {a.runs}")
    for grp in ("all", "multi-column", "single/other"):
        by = collections.defaultdict(list); d = []
        for k, (b, n, s) in R.items():
            if grp == "multi-column" and lay.get(k) not in MC or grp == "single/other" and lay.get(k) in MC: continue
            by[k.rsplit("_", 1)[0]].append(U(n) - U(b))
            if s: d.append((U(n) - U(b), n[0] - b[0], n[1] - b[1]))
        if not by: continue
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); N = sum(len(v) for v in by.values())
        print(f"  {grp:13s} {N:4d} pages, {len(d):3d} changed: {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}] (leaderboard units)  better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}  "
              f"text {sum(x[1] for x in d)/N:+.3f} order {sum(x[2] for x in d)/N:+.3f}; books better/worse {sum(sum(v) > 0 for v in by.values())}/{sum(sum(v) < 0 for v in by.values())}")

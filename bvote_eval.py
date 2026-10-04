"""Dev evaluation of bvote.py on the selection cache (skeleton = MBR base5 pick, processed; voters = the other candidates).
  python bvote_eval.py [--split test]
"""
import argparse, collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from bvote import bvote
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, FREE, U, pick_mbr

SET = {}
for pool, ks in (("base5", (2, 3, 4)), ("free11", (4, 5, 6, 7))):
    for k in ks:
        SET[f"split {pool} proc k{k}"] = dict(pool=pool, src="proc", k=k, do_merge=False)
        if pool == "free11" and k in (4, 5): SET[f"split {pool} proc k{k} all-lengths"] = dict(pool=pool, src="proc", k=k, do_merge=False, long_only=False)
SET["split free11 raw k5"] = dict(pool="free11", src="raw", k=5, do_merge=False)


def job(a):
    split, k, v = a; pick = pick_mbr(v, BASE5); md = v["proc"][pick]; res = {}
    gt = gt_markdown("dev", v["subject"], *[k.rsplit("_", 1)[0], int(k.rsplit("_", 1)[1])]) if split == "dev" else None
    cache = {}
    for name, cfg in SET.items():
        cfg = dict(cfg); pool = BASE5 if cfg.pop("pool") == "base5" else FREE; src = cfg.pop("src")
        new, m, s = bvote(md, [v[src][n] for n in pool if n != pick], **cfg)
        if new == md: res[name] = None; continue
        if gt and new not in cache: cache[new] = gt_score(new, gt)
        res[name] = (v["gt"][pick] if gt else None, cache.get(new), m, s)
    return k, res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); a = ap.parse_args()
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    if a.split == "dev": C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(a.split, k, v) for k, v in sorted(C.items())], chunksize=2))
    for name in SET:
        ch = {k: r[name] for k, r in R.items() if r[name]}
        line = f"{name:28s} {len(ch):4d} pages, {sum(r[2] for r in ch.values()):4d} merges, {sum(r[3] for r in ch.values()):4d} splits"
        if a.split == "dev":
            by = collections.defaultdict(list)
            for k in C: by[k.rsplit("_", 1)[0]].append(U(ch[k][1]) - U(ch[k][0]) if k in ch else 0.0)
            bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
            bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000))
            d = [(U(r[1]) - U(r[0]), r[1][0] - r[0][0], r[1][1] - r[0][1]) for r in ch.values()]
            line += (f" | {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}] better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}"
                     f" text {sum(x[1] for x in d)/len(C):+.3f} order {sum(x[2] for x in d)/len(C):+.3f}")
        print(line, flush=True)

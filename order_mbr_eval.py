"""Dev evaluation of order_mbr.py (skeleton = MBR base5 pick, processed; hypotheses and pseudo-references = the other candidates, processed).
  python order_mbr_eval.py [--split test]
"""
import argparse, collections, json, os, random, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from ensemble_lab import gt_score
from order_mbr import order_mbr
from sel_lab import BASE5, FREE, U, pick_mbr

SET = {"base5 m0.5": (BASE5, 0.5), "base5 m1": (BASE5, 1.0), "base5 m2": (BASE5, 2.0), "free11 m1": (FREE, 1.0), "free11 m2": (FREE, 2.0), "free11 m4": (FREE, 4.0)}


def job(a):
    split, k, v = a; pick = pick_mbr(v, BASE5); md = v["proc"][pick]; res = {}
    gt = gt_markdown("dev", v["subject"], *[k.rsplit("_", 1)[0], int(k.rsplit("_", 1)[1])]) if split == "dev" else None
    memo = {}
    def util(p, r):
        if (p, r) not in memo: memo[(p, r)] = mbr.utility(p, r)
        return memo[(p, r)]
    sc = {}
    for name, (pool, margin) in SET.items():
        new, c, g = order_mbr(md, {n: v["proc"][n] for n in pool if n != pick}, util, margin)
        if new == md: res[name] = None; continue
        if gt and new not in sc: sc[new] = gt_score(new, gt)
        res[name] = (v["gt"][pick] if gt else None, sc.get(new), c, g)
    return k, res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); a = ap.parse_args()
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    if a.split == "dev": C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = dict(P.imap_unordered(job, [(a.split, k, v) for k, v in sorted(C.items())], chunksize=2))
    for name in SET:
        ch = {k: r[name] for k, r in R.items() if r[name]}
        line = f"{name:12s} {len(ch):4d} pages reordered"
        if a.split == "dev":
            by = collections.defaultdict(list)
            for k in C: by[k.rsplit("_", 1)[0]].append(U(ch[k][1]) - U(ch[k][0]) if k in ch else 0.0)
            bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
            bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000))
            d = [(U(r[1]) - U(r[0]), r[1][0] - r[0][0], r[1][1] - r[0][1]) for r in ch.values()]
            line += (f" | {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}] better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}"
                     f" text {sum(x[1] for x in d)/len(C):+.3f} order {sum(x[2] for x in d)/len(C):+.3f}")
        print(line, flush=True)

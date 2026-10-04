"""Dev evaluation of artclean.py on the MBR base5 pick (processed). python artclean_eval.py"""
import collections, json, os, random, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from artclean import artclean
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, U, pick_mbr
SET = {"entities": dict(br=False, tags=False), "br": dict(entities=False, tags=False), "tags": dict(entities=False, br=False),
       "sup/sub": dict(entities=False, br=False, tags=False, supsub=True), "all but sup/sub": {}, "all": dict(supsub=True)}


def job(a):
    k, v = a; pick = pick_mbr(v, BASE5); md = v["proc"][pick]; gt = gt_markdown("dev", v["subject"], *[k.rsplit("_", 1)[0], int(k.rsplit("_", 1)[1])]); res = {}
    for name, kw in SET.items():
        new = artclean(md, **kw); res[name] = (v["gt"][pick], gt_score(new, gt)) if new != md else None
    return k, res


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, sorted(C.items()), chunksize=4))
    for name in SET:
        ch = {k: r[name] for k, r in R.items() if r[name]}
        by = collections.defaultdict(list)
        for k in C: by[k.rsplit("_", 1)[0]].append(U(ch[k][1]) - U(ch[k][0]) if k in ch else 0.0)
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [(U(r[1]) - U(r[0]), r[1][0] - r[0][0]) for r in ch.values()]
        print(f"{name:16s} {len(ch):4d} pages | {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}] better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)} text {sum(x[1] for x in d)/len(C):+.3f}")

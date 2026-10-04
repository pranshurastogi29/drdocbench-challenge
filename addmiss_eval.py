"""Dev evaluation of addmiss.py on the selection cache: skeleton = MBR base5 pick (processed), sources = other candidates (+ MinerU).
  python addmiss_eval.py
"""
import collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from addmiss import add_missing
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, FREE, U, pick_mbr

MINERU = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, "runs/mineru_dev.jsonl")))}
SETS = {"base5 k2": (BASE5, False, 2), "base5 k3": (BASE5, False, 3), "base5+mineru k3": (BASE5, True, 3),
        "free11 k3": (FREE, False, 3), "free11 k5": (FREE, False, 5), "free11+mineru k4": (FREE, True, 4)}


def job(a):
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    pick = pick_mbr(v, BASE5); md = v["proc"][pick]; base = v["gt"][pick]; res = {}
    for name, (pool, mu, kk) in SETS.items():
        src = [v["raw"][n] for n in pool if n != pick] + ([MINERU.get(k, "")] if mu else [])
        new, added = add_missing(md, src, k=kk)
        res[name] = (base, gt_score(new, gt) if added else base, len(added))
    return k, res


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, sorted(C.items()), chunksize=4))
    for name in SETS:
        by = collections.defaultdict(list); tx = []; ro = []; pages = 0; paras = 0
        for k, r in R.items():
            b, a, n = r[name]; by[k.rsplit("_", 1)[0]].append(U(a) - U(b)); tx.append(a[0] - b[0]); ro.append(a[1] - b[1]); pages += n > 0; paras += n
        books = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
        bt = sorted(m(rng.choices(books, k=len(books))) for _ in range(2000))
        ch = [x for v_ in by.values() for x in v_ if abs(x) > 1e-9]
        print(f"{name:18s} {m(books):+.3f} [{bt[50]:+.3f},{bt[1949]:+.3f}] text {st.mean(tx):+.3f} order {st.mean(ro):+.3f} | {pages} pages, {paras} paragraphs added; "
              f"pages better/worse {sum(x > 0 for x in ch)}/{sum(x < 0 for x in ch)}", flush=True)

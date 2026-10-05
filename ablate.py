"""Dev ablations of the submission stack (stack.py) under the end2end scorer (e2e_eval.py).
Each variant is compared with the full stack (82.88 on the leaderboard): Text_ED, Reading_Order, formula proxy (1 - formula edit, pages with
reference formulas), and a leaderboard-weighted combination 0.558 text + 0.433 order + 0.054 formula, with a book-clustered bootstrap.
  python ablate.py [--variants name=steps;...]
"""
import argparse, collections, json, os, random, statistics as st, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import e2e_eval as E
import stack

VARIANTS = {"FULL (82.88)": stack.FULL,
            "- ac": "sel=mbr,rules,chan,fm,sd,bv", "- bv": "sel=mbr,rules,chan,fm,sd,ac", "- sd": "sel=mbr,rules,chan,fm,bv,ac",
            "- fm": "sel=mbr,rules,chan,sd,bv,ac", "- chan": "sel=mbr,rules,fm,sd,bv,ac", "- rules": "sel=mbr,chan,fm,sd,bv,ac",
            "medoid instead of MBR": "sel=medoid,rules,chan,fm,sd,bv,ac", "+ si": stack.FULL + ",si"}


def job(a):
    stem, mds = a
    s = E.gt_json("dev", stem)
    return stem, [E.page_scores(stem, md, "dev", s) for md in mds] if s else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--variants"); a = ap.parse_args()
    V = dict(x.split("=", 1) for x in a.variants.split(";")) if a.variants else VARIANTS
    if "FULL (82.88)" not in V: V = {"FULL (82.88)": stack.FULL, **V}
    built = {}
    for name, steps in V.items():
        with tempfile.TemporaryDirectory() as tmp:
            built[name] = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in stack.build("dev", steps, tmp)}
        print(f"built {name}", file=sys.stderr, flush=True)
    names = list(V); keys = sorted(set.intersection(*[set(b) for b in built.values()]))
    with Pool(11, initializer=E.init) as P: R = {k: r for k, r in P.map(job, [(k, [built[n][k] for n in names]) for k in keys], chunksize=4) if r}
    os.chdir(ROOT)
    json.dump({k: {n: r[i] for i, n in enumerate(names)} for k, r in R.items()}, open(os.path.join(ROOT, "runs", "ablate_last.json"), "w"))
    ok = [k for k in R if all(R[k][i] and R[k][i][0] is not None and R[k][i][1] is not None for i in range(len(names)))]
    fk = [k for k in ok if all(R[k][i][3] is not None for i in range(len(names)))]
    def util(k, i):
        t, o, _, f = R[k][i]; return 0.558 * t + 0.433 * o + 0.054 * (f if f is not None else 0)
    print(f"{len(ok)} dev pages (formula pages {len(fk)}); end2end scoring")
    for i, n in enumerate(names):
        t = st.mean(R[k][i][0] for k in ok); o = st.mean(R[k][i][1] for k in ok); f = st.mean(R[k][i][3] for k in fk) if fk else float("nan")
        by = collections.defaultdict(list)
        for k in ok: by[k.rsplit("_", 1)[0]].append(util(k, i) - util(k, 0))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for v in by.values() for x in v if abs(x) > 1e-9]
        print(f"  {n:24s} Text_ED {1 - t/100:.4f}  RO {o:6.2f}  formula {f:6.2f}   vs FULL {m(bk):+.3f} [{bt[50]:+.3f},{bt[1949]:+.3f}]  pages +/- {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}")

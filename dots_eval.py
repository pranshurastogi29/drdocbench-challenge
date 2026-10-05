"""dots-3-note-preview (free reader from the S21 pipeline) vs our runs, scored with the END-TO-END logic (e2e_eval.py) on the pages it covers.
Rows: each single run through our downstream rules; the current pipeline page (MBR base5 pick); MBR with dots as a 6th candidate;
and 'dots on plain pages' routing like S21 (dots page when no table / display formula in either and < 60 paragraphs).
  python dots_eval.py [--run sm_dots]
"""
import argparse, collections, json, os, random, re, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import e2e_eval as E

U = lambda t, o: 0.558 * t + 0.433 * o


def init():
    E.init()
    import mbr; mbr._init(); E.init()


def job(a):
    import mbr
    from ensemble_lab import downstream
    k, v, dots = a
    from sel_lab import BASE5, pick_mbr
    pick = pick_mbr(v, BASE5)
    dproc = downstream(dots, k)
    plain = lambda m: "<table" not in m and "$$" not in m and len([p for p in re.split(r"\n\s*\n", m) if p.strip()]) < 60
    names = BASE5 + ["dots"]; raw = dict(v["raw"]); raw["dots"] = dots
    sc = {}
    for i in names:
        us = [u for j in names if j != i for u in [mbr.utility(raw[i], raw[j])] if u is not None]
        sc[i] = sum(us) / len(us) if us else -1
    p6 = max(names, key=lambda n: (sc[n], n == "v7"))
    pages = {"v7 alone": v["proc"]["v7"], "dots alone": dproc, "current pipeline (MBR base5)": v["proc"][pick],
             "MBR base5 + dots": dproc if p6 == "dots" else v["proc"][p6],
             "dots on plain pages": dproc if plain(v["proc"][pick]) and plain(dproc) else v["proc"][pick]}
    s = E.gt_json("dev", k)
    return k, {n: E.page_scores(k, md, "dev", s) for n, md in pages.items()} if s else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--run", default="sm_dots"); a = ap.parse_args()
    from postprocess import strip_sections
    D = {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{a.run}.jsonl")))}
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json")))
    keys = [k for k in sorted(D) if k in C]
    with Pool(11, initializer=init) as P: R = {k: r for k, r in P.map(job, [(k, C[k], D[k]) for k in keys], chunksize=2) if r}
    os.chdir(ROOT)
    names = list(next(iter(R.values())))
    ok = [k for k in R if all(R[k][n] and R[k][n][0] is not None and R[k][n][1] is not None for n in names)]
    print(f"{len(ok)} dev pages scored (end2end logic); short/empty dots pages: {sum(1 for k in keys if len(D[k]) < 60)}")
    base = "current pipeline (MBR base5)"
    for n in names:
        t = st.mean(R[k][n][0] for k in ok); o = st.mean(R[k][n][1] for k in ok)
        d = [U(*R[k][n][:2]) - U(*R[k][base][:2]) for k in ok]
        by = collections.defaultdict(list)
        for k, x in zip(ok, d): by[k.rsplit("_", 1)[0]].append(x)
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000))
        print(f"  {n:30s} Text_ED {1 - t/100:.4f}  RO {o:6.2f}   vs current {m(bk):+.2f} [{bt[50]:+.2f},{bt[1949]:+.2f}]  pages better/worse {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)}")

"""Side-by-side comparison of every model run on the same dev windows (predict.py --subset 40), on the pages ALL of them cover (md2md).
Rows: our current pipeline (mbr8 stack, from runs/ablate_last.json), the old pipeline (MBR base5), our free model v7 alone, and for each
new model: alone (same downstream rules as our runs) and as an extra MBR candidate next to base5. Gains are leaderboard-weighted
(0.558 text + 0.433 order) vs the mbr8 pipeline, with a book-clustered bootstrap; "w/o top page" drops the single page that gains most.
  python compare_models.py sm_gemini sm_kimi sm_kimi25hf sm_kimi26nt
"""
import collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
import model_smoke_eval as S
from postprocess import strip_sections
from sel_lab import U


def boot(d):
    by = collections.defaultdict(list)
    for k, x in d.items(): by[k.rsplit("_", 1)[0]].append(x)
    bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
    bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); return m(bk), bt[50], bt[1949]


if __name__ == "__main__":
    tags = sys.argv[1:]
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json")))
    A = json.load(open(os.path.join(ROOT, "runs/ablate_last.json")))
    res = {}
    for t in tags:
        D = {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{t}.jsonl")))}
        keys = [k for k in sorted(D) if k in C and all(C[k]["gt"][n] for n in C[k]["gt"])]
        with Pool(11, initializer=mbr._init) as P: res[t] = dict(P.map(S.job, [(k, C[k], D[k]) for k in keys], chunksize=2))
    os.chdir(ROOT)
    common = sorted(set.intersection(*[{k for k, v in r.items() if all(v[n] for n in v if not n.startswith("_"))} for r in res.values()]) & {k for k, v in A.items() if v.get("mbr8 base") and v["mbr8 base"][1] is not None})
    t0 = tags[0]
    rows = {"current pipeline (mbr8)": {k: tuple(A[k]["mbr8 base"][:2]) for k in common},
            "old pipeline (MBR base5)": {k: res[t0][k]["current pipeline (MBR base5)"] for k in common},
            "v7 alone (free model)": {k: res[t0][k]["v7 alone"] for k in common}}
    for t in tags:
        rows[f"{t} alone"] = {k: res[t][k]["new model alone"] for k in common}
        rows[f"{t} as MBR candidate"] = {k: res[t][k]["MBR base5 + new"] for k in common}
    ref = rows["current pipeline (mbr8)"]
    print(f"{len(common)} dev pages covered by every run ({', '.join(tags)}); gains vs the current pipeline (mbr8), leaderboard-weighted")
    print(f"  {'':34s} {'Text_ED':>8s} {'RO':>7s}   {'gain [95% CI]':>22s}  {'better/worse':>12s}  w/o top page")
    for n, r in rows.items():
        d = {k: U(r[k]) - U(ref[k]) for k in common}; m, lo, hi = boot(d)
        top = max(d, key=d.get); rest = {k: v for k, v in d.items() if k != top}
        print(f"  {n:34s} {1 - st.mean(r[k][0] for k in common) / 100:8.4f} {st.mean(r[k][1] for k in common):7.2f}   {m:+6.2f} [{lo:+.2f},{hi:+.2f}]  {sum(x > 0.5 for x in d.values()):5d}/{sum(x < -0.5 for x in d.values()):<5d}  {st.mean(rest.values()):+.2f}")

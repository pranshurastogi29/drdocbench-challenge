"""md2md comparison of a smoke-test run (any model) with our runs on the pages it covers: v7 alone, the new model alone, current pipeline page
(MBR base5), and the new model as an extra MBR candidate. All pages through the same downstream rules.
  python model_smoke_eval.py RUN_TAG [--pages]   (--pages: list the pages where adding the new model as a candidate changes the score)
"""
import collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from ensemble_lab import downstream, gt_score
from postprocess import strip_sections
from sel_lab import BASE5, U, pick_mbr


def job(a):
    k, v, new = a
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    nproc = downstream(new, k); pick = pick_mbr(v, BASE5)
    raw = dict(v["raw"]); raw["new"] = new; names = BASE5 + ["new"]; sc = {}
    for i in names:
        us = [u for j in names if j != i for u in [mbr.utility(raw[i], raw[j])] if u is not None]
        sc[i] = sum(us) / len(us) if us else -1
    p6 = max(names, key=lambda n: (sc[n], n == "v7"))
    return k, {"v7 alone": v["gt"]["v7"], "new model alone": gt_score(nproc, gt), "current pipeline (MBR base5)": v["gt"][pick],
               "MBR base5 + new": gt_score(nproc, gt) if p6 == "new" else v["gt"][p6], "_short": len(new.strip()) < 60}


if __name__ == "__main__":
    tag = sys.argv[1]
    D = {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{tag}.jsonl")))}
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json")))
    keys = [k for k in sorted(D) if k in C and all(C[k]["gt"][n] for n in C[k]["gt"])]
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], D[k]) for k in keys], chunksize=2))
    ok = [k for k in R if all(R[k][n] for n in R[k] if not n.startswith("_"))]
    print(f"{tag}: {len(ok)} dev pages scored (md2md); short/empty pages from the new model: {sum(R[k]['_short'] for k in R)}")
    base = "current pipeline (MBR base5)"
    for n in [x for x in R[ok[0]] if not x.startswith("_")]:
        by = collections.defaultdict(list)
        for k in ok: by[k.rsplit("_", 1)[0]].append(U(R[k][n]) - U(R[k][base]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv]
        print(f"  {n:30s} Text_ED {1 - st.mean(R[k][n][0] for k in ok)/100:.4f}  RO {st.mean(R[k][n][1] for k in ok):6.2f}   vs current {m(bk):+.2f} [{bt[50]:+.2f},{bt[1949]:+.2f}]  pages {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)}")
    if "--pages" in sys.argv:
        for k in ok:
            d = U(R[k]["MBR base5 + new"]) - U(R[k][base])
            if abs(d) > 0.01: print(f"  {k[:8]} p{k.rsplit('_', 1)[1]:>4}  MBR + new {d:+6.2f}  text {R[k][base][0]:.1f} -> {R[k]['MBR base5 + new'][0]:.1f}  order {R[k][base][1]:.1f} -> {R[k]['MBR base5 + new'][1]:.1f}")

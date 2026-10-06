"""Which local scorer reproduces the leaderboard's same-scorer differences? Dev variants of today's/yesterday's test uploads (stack.py), each scored
with md2md (truncated merge ON = our old local scorer, OFF = multipage-style) and the deltas compared with the leaderboard deltas.
  python calib.py
"""
import json, os, sys, tempfile, statistics as st
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import md2md_eval as M
import stack
from common import gt_markdown

V = {"sd_bv_ac": stack.FULL, "fc10t": "sel=medoid,rules,chan=1", "si3k2": stack.FULL + ",si", "pools_am": "sel=mbr,rules,chan=poolsS,fm,sd,bv,am=2,ac"}
LB = {"fc10t": (0.1724, 84.44), "sd_bv_ac": (0.1689, 84.91), "si3k2": (0.1734, 85.39), "pools_am": (0.1727, 84.91)}


def job(a):
    k, subj, mds = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    return k, {n: (M.page_scores(md, gt, True), M.page_scores(md, gt, False)) for n, md in mds.items()}


if __name__ == "__main__":
    B = {}
    for n, steps in V.items():
        with tempfile.TemporaryDirectory() as tmp: B[n] = {f'{r["document_id"]}_{r["page"]}': r for r in stack.build("dev", steps, tmp)}
    keys = sorted(set.intersection(*[set(b) for b in B.values()]))
    with Pool(11, initializer=M.init) as P: R = dict(P.map(job, [(k, B["sd_bv_ac"][k]["subject"], {n: B[n][k]["markdown"] for n in V}) for k in keys], chunksize=4))
    os.chdir(ROOT)
    ok = [k for k in R if all(R[k][n][0] and R[k][n][1] for n in V)]
    for i, lab in ((0, "md2md, truncated merge OFF (skip)"), (1, "md2md, truncated merge ON (our old local)")):
        print(f"== {lab}: {len(ok)} pages")
        T = {n: 1 - st.mean(R[k][n][i][0] for k in ok) / 100 for n in V}
        O = {n: st.mean(R[k][n][i][1] for k in ok if R[k][n][i][1] is not None) for n in V}
        for n in V:
            dt, do = T[n] - T["sd_bv_ac"], O[n] - O["sd_bv_ac"]; lt, lo = LB[n][0] - LB["sd_bv_ac"][0], LB[n][1] - LB["sd_bv_ac"][1]
            print(f"   {n:9s} dev Text_ED {T[n]:.4f} RO {O[n]:6.2f} | vs sd_bv_ac: dev text {dt:+.4f} order {do:+.2f}   leaderboard text {lt:+.4f} order {lo:+.2f}")

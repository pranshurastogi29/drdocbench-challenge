"""The matcher's 3600-cell cliff (scorer/utils/match_quick.py cal_final_match_fast): deal_with_truncated, the step that joins split pieces of
a reference block, runs only when (reference blocks x our blocks) <= 3600. How many pages are over it, and what does it cost them?
  python cliff.py      (dev, MBR base5 pick, processed)
"""
import json, os, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from sel_lab import BASE5, U, pick_mbr


def job(a):
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    pick = pick_mbr(v, BASE5); md = v["proc"][pick]
    ng = len(mbr.md_tex_filter(gt).get("text_all") or []); npr = len(mbr.md_tex_filter(md).get("text_all") or [])
    npad = len(mbr.md_tex_filter(v["proc"]["paddle"]).get("text_all") or [])
    return k, ng, npr, npad, v["gt"][pick], {n: (len(mbr.md_tex_filter(v["proc"][n]).get("text_all") or []), v["gt"][n]) for n in BASE5}


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = P.map(job, sorted(C.items()), chunksize=4)
    over = [r for r in R if r[1] * r[2] > 3600]; near = [r for r in R if 2500 < r[1] * r[2] <= 3600]; under = [r for r in R if r[1] * r[2] <= 2500]
    for name, S in (("over 3600", over), ("2500-3600", near), ("<= 2500", under)):
        if S: print(f"{name:10s} {len(S):4d} pages  text {st.mean(r[4][0] for r in S):5.1f}  order {st.mean(r[4][1] for r in S):5.1f}  ref blocks {st.mean(r[1] for r in S):5.1f}  ours {st.mean(r[2] for r in S):5.1f}")
    print("\npages over the cliff: ref blocks x ours = cells, our text score, and the other candidates' (blocks, text)")
    for r in sorted(over, key=lambda r: r[4][0])[:25]:
        print(f"  {r[0][:8]}..{r[0][-5:]} ref {r[1]:3d} x ours {r[2]:3d} = {r[1]*r[2]:5d}  text {r[4][0]:5.1f}  paddle {r[3]:3d} | " + "  ".join(f"{n}:{b}/{s[0]:.0f}" for n, (b, s) in r[5].items()))
    json.dump([[r[0], r[1], r[2], r[3]] for r in R], open("runs/cliff_dev.json", "w"))

"""Dev: selection with extra references (base5 candidates, base5 + six column-break runs as references) followed by the split import
(>= 2 of v10a/v10b/v11), vs the current pipeline (base5 MBR) followed by the same split import.
  python combo_eval.py
"""
import collections, json, os, random, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from ab_ro_eval import layout_of, MC
from bvote import bvote
from common import gt_markdown
from ensemble_lab import gt_score
from postprocess import strip_sections
from sel_lab import BASE5, U, pick_mbr
import mbr_refs_eval as M


def job(a):
    k, v, extra = a
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    picks = {"current": pick_mbr(v, BASE5), "refs x6": M.job((k, v, extra))[1]["base5+v10 x6"]}
    voters = [extra[n] for n in ("v10a", "v10b", "v11") if n in extra]
    out = {}
    for name, p in picks.items():
        md = v["proc"][p]; new, _, s = bvote(md, voters, k=2, do_merge=False, long_only=False)
        out[name] = v["gt"][p] if not s else gt_score(new, gt)
        out[name + " (no split import)"] = v["gt"][p]
    return k, out


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    E = {}
    for n, files in M.EXTRA.items():
        d = {}
        for f in files: d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{f}.jsonl")))})
        E[n] = d
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], {n: E[n][k] for n in E if k in E[n]}) for k in sorted(C)], chunksize=4))
    lay = layout_of(); ref = "current (no split import)"
    for name in ("current", "refs x6 (no split import)", "refs x6"):
        for grp in ("all", "multi-column", "single/other"):
            by = collections.defaultdict(list)
            for k, r in R.items():
                if grp == "multi-column" and lay.get(k) not in MC or grp == "single/other" and lay.get(k) in MC: continue
                by[k.rsplit("_", 1)[0]].append(U(r[name]) - U(r[ref]))
            bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
            bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for v_ in by.values() for x in v_ if abs(x) > 1e-9]
            print(f"{name:26s} {grp:13s} vs current pipeline {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]  pages better/worse {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}  books {sum(sum(v_) > 0 for v_ in by.values())}/{sum(sum(v_) < 0 for v_ in by.values())}")

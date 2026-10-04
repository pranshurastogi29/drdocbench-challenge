"""Cache for selection experiments: per page, every candidate's raw and processed (final5 rules + furniture merge) Markdown, its score against
the reference (dev only), and the pairwise (text, order) scores between candidates, raw and processed, with the official matching logic.
  python sel_cache.py --split dev|test [--cands v6,v7,...]   -> runs/selcache_<split>.json
"""
import argparse, json, os, sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import DEV, TEST
from common import gt_markdown
from ensemble_lab import downstream, gt_score, FREE
from postprocess import strip_sections


def page(job):
    split, stem, subj, raw = job
    names = list(raw)
    proc = {n: downstream(raw[n], stem) for n in names}
    pw = lambda M: {i: {j: gt_score(M[i], M[j]) for j in names if j != i} for i in names}
    out = {"subject": subj, "raw": raw, "proc": proc, "pw_raw": pw(raw), "pw_proc": pw(proc)}
    if split == "dev":
        doc, pg = stem.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
        out["gt"] = {n: gt_score(proc[n], gt) for n in names}
    return stem, out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--cands", default=",".join(FREE)); ap.add_argument("--workers", type=int, default=11)
    a = ap.parse_args(); files = DEV if a.split == "dev" else TEST; names = a.cands.split(",")
    R = {n: {f'{r["document_id"]}_{r["page"]}': r for r in map(json.loads, open(os.path.join(ROOT, files[n]), encoding="utf-8"))} for n in names}
    stems = sorted(set.intersection(*[set(v) for v in R.values()]))
    jobs = [(a.split, s, R[names[0]][s]["subject"], {n: strip_sections(R[n][s]["markdown"]).strip() for n in names}) for s in stems]
    res = {}
    with Pool(a.workers, initializer=mbr._init) as P:
        for i, (stem, o) in enumerate(P.imap_unordered(page, jobs, chunksize=2), 1):
            res[stem] = o
            if i % 100 == 0: print(i, "/", len(jobs), flush=True)
    os.chdir(ROOT); json.dump(res, open(os.path.join(ROOT, "runs", f"selcache_{a.split}.json"), "w"))
    print(len(res), "pages ->", f"runs/selcache_{a.split}.json")

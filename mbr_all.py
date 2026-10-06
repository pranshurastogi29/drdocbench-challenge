"""MBR over (almost) every full reading we have: candidates and pseudo-references drawn from 17 runs that cover all dev and test pages
(base5, the column-break family v10a/v10b/v11 + their contrast / temperature / shifted-window runs, one-page runs v6w1/v7w1/v8w1, contrast-prompt
runs v6c/v8c, 1200px v7s). Writes runs/mbr_choice_<split>_<name>.json.
  python mbr_all.py --split dev|test --name all17 --cands <comma list>
"""
import argparse, json, os, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from postprocess import strip_sections
from sel_lab import U

RUNS = ["v6", "v7", "v8", "paddle", "v7c", "v10a", "v10b", "v11", "v10ac", "v10at", "v10ao", "v6w1", "v7w1", "v8w1", "v6c", "v8c", "v7s"]


def job(a):
    k, raw, pw, cands = a
    def ut(i, j):
        c = pw.get(i, {}).get(j) if pw else None
        if c is None: c = mbr.gt_like(raw[i], raw[j])
        return U(c) if c else None
    sc = {}
    for i in [c for c in cands if c in raw]:
        xs = [x for j in raw if j != i for x in [ut(i, j)] if x is not None]
        sc[i] = sum(xs) / len(xs) if xs else -1
    return k, max(sc, key=lambda n: (sc[n], n == "v7"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--name", required=True); ap.add_argument("--cands", required=True); a = ap.parse_args()
    import build_submission as bs
    files = bs.DEV if a.split == "dev" else bs.TEST
    R = {n: {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, files[n] if n in files else f"runs/{a.split}_all_{n}.jsonl")))} for n in RUNS}
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    keys = sorted(set.intersection(*[set(v) for v in R.values()]))
    jobs = [(k, {n: R[n][k] for n in RUNS}, C[k]["pw_raw"] if k in C else {}, a.cands.split(",")) for k in keys]
    with Pool(11, initializer=mbr._init) as P: out = dict(P.map(job, jobs, chunksize=2))
    os.chdir(ROOT); json.dump(out, open(f"runs/mbr_choice_{a.split}_{a.name}.json", "w"))
    import collections; print(a.split, a.name, len(out), "pages; picks", collections.Counter(out.values()).most_common(8))

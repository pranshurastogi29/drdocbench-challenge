"""Write MBR choices where the candidates are the base5 runs but the pseudo-references are base5 + the six column-break runs (v10a, v10b, v11,
v10ac, v10at, v10ao): runs/mbr_choice_<split>_refs6.json. Dev evidence (mbr_refs_eval.py): +0.41/page [+0.01,+0.79] vs base5-only references.
  python mbr_refs_choose.py --split dev|test
"""
import argparse, json, os, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from postprocess import strip_sections
from sel_lab import BASE5, U
import mbr_refs_eval as M

TAGS = {"dev": M.EXTRA, "test": {"v10a": ("v10a",), "v10b": ("v10b",), "v11": ("v11",), "v10ac": ("v10ac",), "v10at": ("v10at",), "v10ao": ("v10ao",)}}


def job(a):
    k, v, extra = a
    return k, M.job((k, v, extra))[1]["base5+v10 x6"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); a = ap.parse_args()
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    E = {}
    for n, files in TAGS[a.split].items():
        d = {}
        for f in files: d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/{a.split}_all_{f}.jsonl")))})
        E[n] = d
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], {n: E[n][k] for n in E if k in E[n]}) for k in sorted(C)], chunksize=4))
    os.chdir(ROOT); old = json.load(open(f"runs/mbr_choice_{a.split}.json"))
    json.dump(R, open(f"runs/mbr_choice_{a.split}_refs6.json", "w"))
    print(f"{a.split}: {len(R)} pages, pick differs from the current MBR on {sum(R[k] != old.get(k) for k in R)}")

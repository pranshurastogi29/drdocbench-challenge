"""Fast table-only re-implementation of the md2md TEDS pipeline (scorer's own normalizer, Hungarian matching and TEDS class),
for A/B-testing table post-processing on dev without a full scorer run.

  python table_lab.py runs/dev_all_final5.jsonl          # baseline: should reproduce the scorer's Table_TEDS
As a library:  score(pred_by_page, transform=None) -> (mean TEDS x100, per-table list)
"""
import glob, json, os, re, sys, types
from multiprocessing import Pool
import numpy as np
from scipy.optimize import linear_sum_assignment
ROOT = os.path.dirname(os.path.abspath(__file__))
class _Stub(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return type(n, (), {})
sys.modules["mmeval"] = _Stub("mmeval"); sys.path.insert(0, os.path.join(ROOT, "scorer"))
import Levenshtein
from utils.data_preprocess import normalized_table
from metrics.table_metric import TEDS
TAB = re.compile(r"<table\b.*?</table>", re.S | re.I)
_teds = TEDS(n_jobs=1)
_teds_s = TEDS(structure_only=True, n_jobs=1)


def gt_tables():
    G = {}
    for p in glob.glob(os.path.join(ROOT, "eval_tmp/FINAL5/gt/*.md")):
        t = TAB.findall(open(p, encoding="utf-8").read())
        if t: G[os.path.basename(p)[:-3]] = t
    return G


def _page(args):
    gts, preds = args
    ng = [normalized_table(g)[1] if isinstance(normalized_table(g), tuple) else normalized_table(g) for g in gts]
    ng = [x for x in ng if x]
    npred = [x for x in (normalized_table(p) for p in preds) if x]
    npred = [x[0] if isinstance(x, tuple) else x for x in npred]
    if not ng or not npred: return []
    D = np.array([[0 if not a and not b else Levenshtein.distance(a, b) / max(len(a), len(b)) for b in npred] for a in ng])
    r, c = linear_sum_assignment(D)
    out = {int(i): _teds.evaluate(npred[j], ng[i]) for i, j in zip(r, c)}
    return [out.get(i, 0.0) for i in range(len(ng))]        # unmatched GT tables score 0


def score(pred_by_page, transform=None, G=None, workers=6):
    G = G or gt_tables(); jobs = []
    for page, gts in G.items():
        md = pred_by_page.get(page)
        if md is None: continue
        preds = TAB.findall(md)
        if transform: preds = [transform(p) for p in preds]
        if preds: jobs.append((gts, preds))
    with Pool(workers) as pool: res = pool.map(_page, jobs, chunksize=4)
    flat = [x for r in res for x in r]
    return 100 * float(np.mean(flat)), flat


def load_pred(path):
    return {f"{r['document_id']}_{r['page']}": r["markdown"] for r in map(json.loads, open(path, encoding="utf-8"))}


if __name__ == "__main__":
    G = gt_tables(); print("GT tables:", sum(len(v) for v in G.values()), "on", len(G), "pages")
    m, f = score(load_pred(sys.argv[1]), G=G); print(f"tables scored {len(f)}  mean TEDS {m:.2f}")

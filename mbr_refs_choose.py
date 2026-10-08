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


CANDS = None   # --cands8: candidates base5 + v10a, v10b, v11 (references unchanged)


def job(a):
    k, v, extra, cands, refx, w = (a + ((0.558, 0.433),))[:6] if len(a) == 5 else a
    if not cands: return k, M.job((k, v, extra))[1]["base5+v10 x6"]
    raw = dict(v["raw"]); raw.update(extra); u = {}
    def ut(i, j):
        c = v["pw_raw"].get(i, {}).get(j) if i in v["pw_raw"] else None
        if c is None and i in raw and j in raw: c = mbr.gt_like(raw[i], raw[j])
        return w[0] * c[0] + w[1] * c[1] if c else None
    sc = {}
    for i in [c for c in cands if c in raw]:
        xs = [x for j in BASE5 + list(refx) if j != i for x in [ut(i, j)] if x is not None]
        sc[i] = sum(xs) / len(xs) if xs else -1
    return k, max(sc, key=lambda n: (sc[n], n == "v7"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--cands8", action="store_true")
    ap.add_argument("--kimi", help="run tag of a Kimi-K2.5 run (runs/<split>_all_<tag>.jsonl): an extra candidate AND reference on the pages it covers -> mbr_choice_<split>_c9.json")
    ap.add_argument("--cands", help="comma list of candidates (overrides --cands8)"); ap.add_argument("--wt", default="0.558,0.433", help="utility weights text,order")
    ap.add_argument("--name", help="output suffix: runs/mbr_choice_<split>_<name>.json (use with stack sel=mbrf:<name>)")
    a = ap.parse_args()
    if a.cands8 or a.kimi: CANDS = BASE5 + ["v10a", "v10b", "v11"] + (["kimi25"] if a.kimi else [])
    if a.kimi: TAGS[a.split] = {**TAGS[a.split], "kimi25": (a.kimi,)}
    if a.cands: CANDS = a.cands.split(",")
    W = tuple(float(x) for x in a.wt.split(","))
    TAGS_REF = TAGS[a.split]
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    E = {}
    for n, files in TAGS[a.split].items():
        d = {}
        for f in files: d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/{a.split}_all_{f}.jsonl")))})
        E[n] = d
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], {n: E[n][k] for n in E if k in E[n]}, CANDS, list(TAGS_REF), W) for k in sorted(C)], chunksize=4))
    os.chdir(ROOT); old = json.load(open(f"runs/mbr_choice_{a.split}.json"))
    json.dump(R, open(f"runs/mbr_choice_{a.split}_{a.name or ('c9' if a.kimi else 'c8' if a.cands8 else 'refs6')}.json", "w"))
    if a.kimi: print(f"kimi25 picked on {sum(v == 'kimi25' for v in R.values())} pages; differs from c8 on {sum(R[k] != json.load(open(f'runs/mbr_choice_{a.split}_c8.json')).get(k) for k in R)}")
    print(f"{a.split}: {len(R)} pages, pick differs from the current MBR on {sum(R[k] != old.get(k) for k in R)}")

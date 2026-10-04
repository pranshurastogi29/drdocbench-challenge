"""MBR with extra pseudo-references (dev): the candidates stay the base5 runs (what can be selected is unchanged), but each candidate's
expected score is averaged over MORE references: the other free runs (free11) and the column-break runs (v10a, v10b, v11).
More samples of 'what the reference could look like' = a less noisy estimate of the leaderboard score (test-time augmentation for selection).
Scores use the cached processed pages / reference scores of runs/selcache_dev.json, so the effect is exactly that of a different pick.
  python mbr_refs_eval.py
"""
import collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import medoid
from postprocess import strip_sections
from sel_lab import BASE5, FREE, U

EXTRA = {"v10a": ("ab_v10a", "v10a_rest"), "v10b": ("ab_v10b", "v10b_rest"), "v11": ("ab_v11", "v11_rest")}
REFSETS = {"base5 (current)": BASE5, "free11": FREE, "base5+v10": BASE5 + list(EXTRA), "free11+v10": FREE + list(EXTRA), "v10 only": list(EXTRA)}


def job(a):
    k, v, extra = a
    raw = dict(v["raw"]); raw.update(extra)
    U2 = {}
    def u(i, j):
        if (i, j) not in U2:
            c = v["pw_raw"].get(i, {}).get(j) if i in v["pw_raw"] and j in v["pw_raw"][i] else None
            if c is None and i in raw and j in raw: c = mbr.gt_like(raw[i], raw[j])
            U2[(i, j)] = U(c) if c else None
        return U2[(i, j)]
    out = {}
    for name, refs in REFSETS.items():
        sc = {}
        for i in BASE5:
            us = [x for j in refs if j != i for x in [u(i, j)] if x is not None]
            sc[i] = sum(us) / len(us) if us else -1
        out[name] = max(BASE5, key=lambda n: (sc[n], n == "v7"))
    return k, out


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    E = {}
    for n, files in EXTRA.items():
        d = {}
        for f in files:
            d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{f}.jsonl")))})
        E[n] = d
    jobs = [(k, C[k], {n: E[n][k] for n in E if k in E[n]}) for k in sorted(C)]
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, jobs, chunksize=4))
    base = {k: medoid(C[k]["raw"], BASE5) for k in C}
    cur = {k: R[k]["base5 (current)"] for k in C}
    for name in REFSETS:
        by = collections.defaultdict(list)
        for k in C: by[k.rsplit("_", 1)[0]].append(U(C[k]["gt"][R[k][name]]) - U(C[k]["gt"][cur[k]]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for v in by.values() for x in v if abs(x) > 1e-9]
        vs_med = st.mean(U(C[k]["gt"][R[k][name]]) - U(C[k]["gt"][base[k]]) for k in C)
        print(f"{name:18s} vs current MBR {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]  picks changed {len(d):3d} (better/worse {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}), books {sum(sum(v) > 0 for v in by.values())}/{sum(sum(v) < 0 for v in by.values())};  vs medoid5 {vs_med:+.3f}")

"""Dev: MBR where the column-break runs are also CANDIDATES (not only references). Candidates base5 (+ v10a, v10b, v11), references base5 + six
column-break runs; the picked page goes through the same downstream rules (snap, Paddle tables, furniture merge) and is scored with md2md.
  python mbr_cands_eval.py
"""
import collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from ensemble_lab import downstream, gt_score
from postprocess import strip_sections
from sel_lab import BASE5, U
import mbr_refs_eval as M

REFS = BASE5 + list(M.EXTRA)


def job(a):
    k, v, extra = a
    raw = dict(v["raw"]); raw.update(extra)
    u = {}
    def ut(i, j):
        if (i, j) not in u:
            c = v["pw_raw"].get(i, {}).get(j) if i in v["pw_raw"] else None
            if c is None and i in raw and j in raw: c = mbr.gt_like(raw[i], raw[j])
            u[(i, j)] = U(c) if c else None
        return u[(i, j)]
    out = {}
    for name, cands in (("mbr6 (base5 candidates)", BASE5), ("+ v10a,v10b,v11 candidates", BASE5 + ["v10a", "v10b", "v11"]), ("+ v10a candidate", BASE5 + ["v10a"])):
        sc = {}
        for i in cands:
            if i not in raw: continue
            xs = [x for j in REFS if j != i for x in [ut(i, j)] if x is not None]
            sc[i] = sum(xs) / len(xs) if xs else -1
        p = max(sc, key=lambda n: (sc[n], n == "v7"))
        out[name] = (p, v["gt"][p] if p in v["gt"] else None)
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    for name, (p, g) in list(out.items()):
        if g is None: out[name] = (p, gt_score(downstream(raw[p], k), gt))
    return k, out


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    E = {}
    for n, files in M.EXTRA.items():
        d = {}
        for f in files: d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{f}.jsonl")))})
        E[n] = d
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], {n: E[n][k] for n in E if k in E[n]}) for k in sorted(C)], chunksize=4))
    names = list(next(iter(R.values()))); base = names[0]
    for n in names:
        ok = [k for k in R if R[k][n][1] and R[k][base][1]]
        by = collections.defaultdict(list)
        for k in ok: by[k.rsplit("_", 1)[0]].append(U(R[k][n][1]) - U(R[k][base][1]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv if abs(x) > 1e-9]
        picks = collections.Counter(R[k][n][0] for k in ok)
        print(f"{n:30s} text {st.mean(R[k][n][1][0] for k in ok):.2f} order {st.mean(R[k][n][1][1] for k in ok):.2f}  vs mbr6 {m(bk):+.3f} [{bt[50]:+.3f},{bt[1949]:+.3f}] pages {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}  picks {dict(picks.most_common(4))}")

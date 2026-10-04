"""Evaluate the reading-order prompt A/B (run_ab_ro.sh): v7 (fresh) vs v10a vs v10b on the same dev windows.
Each run's page goes through the same downstream rules as the pipeline (snap, Paddle tables, furniture merge) and is scored with the official
text / reading-order logic. Reported per group (multi-column pages / control pages): mean text, order, leaderboard utility; paired difference
vs v7 with a book-clustered bootstrap. Also: how often each run still joins a paragraph across a reference column break (did the model follow).
Ensemble view: MBR over the base5 pool with v7 replaced by the new run (v6, v8, paddle, v7c from the archived full-dev runs).
  python ab_ro_eval.py [--runs ab_v7,ab_v10a,ab_v10b]
"""
import argparse, collections, glob, json, os, random, re, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import DEV
from common import gt_markdown
from ensemble_lab import downstream, gt_score
from sel_lab import U
from postprocess import strip_sections

MC = {"double_column", "1andmore_column", "three_column"}


def layout_of():
    lay = {}
    for f in glob.glob(os.path.join(ROOT, "data/dev/*/*/json/*.json")):
        j = json.load(open(f))
        if j: pi = j[0]["page_info"]; lay[f'{pi["page_name"]}_{pi["page_no"]}'] = pi["page_attribute"].get("layout")
    return lay


def joined(k, md):
    """number of reference column breaks (text -> text, column-major band) that this page joins into one paragraph"""
    import ro_columns as R
    from ro_colbreak import where
    L = R.page_layout(k)
    if not L: return 0, 0
    info, B = L; P = [R.W_(p) for p in re.split(r"\n\s*\n", md) if p.strip()]; n = j = 0
    for band in R.bands(B, info["width"]):
        if R.classify(band, {id(b): b["order"] for b in band}) != "column-major": continue
        seq = sorted(band, key=lambda b: b["order"])
        for x, y in zip(seq, seq[1:]):
            if x["col"] != y["col"] and x["cat"] == y["cat"] == "text_block":
                a, b = where(x, P), where(y, P)
                if a is not None and b is not None: n += 1; j += a == b
    return n, j


def job(a):
    k, subj, cands, base = a
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    proc = {n: downstream(md, k) for n, md in cands.items()}
    out = {n: (gt_score(proc[n], gt), joined(k, proc[n])) for n in proc}
    # ensemble: MBR over base5 with v7 replaced by each run
    from sel_lab import pick_mbr
    ens = {}
    for n in cands:
        pool = dict(base); pool["v7"] = cands[n]
        names = list(pool)
        sc = {}
        for i in names:
            us = [u for j in names if j != i for u in [mbr.utility(pool[i], pool[j])] if u is not None]
            sc[i] = sum(us) / len(us) if us else -1
        best = max(names, key=lambda x: (sc[x], x == "v7"))
        ens[n] = gt_score(downstream(pool[best], k), gt)
    return k, out, ens


if __name__ == "__main__" and "--import-only" not in sys.argv:
    ap = argparse.ArgumentParser(); ap.add_argument("--runs", default="ab_v7,ab_v10a,ab_v10b"); ap.add_argument("--import", dest="imp", action="store_true"); a = ap.parse_args()
    runs = a.runs.split(","); lay = layout_of()
    R = {n: {f'{r["document_id"]}_{r["page"]}': r for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{n}.jsonl")))} for n in runs}
    B = {n: {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, DEV[n])))} for n in ("v6", "v8", "paddle", "v7c")}
    keys = sorted(set.intersection(*[set(v) for v in R.values()]) & set.intersection(*[set(v) for v in B.values()]))
    jobs = [(k, R[runs[0]][k]["subject"], {n: strip_sections(R[n][k]["markdown"]).strip() for n in runs}, {n: B[n][k] for n in B}) for k in keys]
    with Pool(11, initializer=mbr._init) as P: res = [r for r in P.map(job, jobs, chunksize=2)]
    res = [(k, o, e) for k, o, e in res if all(o[n][0] for n in runs)]
    print(f"{len(res)} pages scored ({sum(lay.get(k) in MC for k, _, _ in res)} multi-column)")
    for view in ("single run", "ensemble (MBR base5, v7 slot replaced)"):
        print(f"\n== {view}")
        for grp, sel in (("multi-column", lambda k: lay.get(k) in MC), ("control", lambda k: lay.get(k) not in MC), ("all", lambda k: True)):
            S = [(k, o if view == "single run" else {n: (e[n], None) for n in e}) for k, o, e in res if sel(k)]
            if not S: continue
            print(f"  {grp} ({len(S)} pages)")
            for n in runs:
                t = st.mean(x[n][0][0] for _, x in S); r = st.mean(x[n][0][1] for _, x in S)
                line = f"    {n:9s} text {t:6.2f} order {r:6.2f} utility {st.mean(U(x[n][0]) for _, x in S):6.2f}"
                if n != runs[0]:
                    by = collections.defaultdict(list)
                    for k, x in S: by[k.rsplit("_", 1)[0]].append(U(x[n][0]) - U(x[runs[0]][0]))
                    bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
                    bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000))
                    d = [v for vs in by.values() for v in vs]
                    line += f"   vs {runs[0]}: {m(bk):+.2f} [{bt[50]:+.2f},{bt[1949]:+.2f}] pages better/worse {sum(v > 0.5 for v in d)}/{sum(v < -0.5 for v in d)}"
                if view == "single run":
                    jn = sum(x[n][1][0] for _, x in S); jj = sum(x[n][1][1] for _, x in S)
                    line += f" | column breaks joined {jj}/{jn}"
                print(line)


def imp(a):
    """current pipeline page (MBR base5 pick, processed) + paragraph splits imported from the new-prompt runs (bvote, split-only)"""
    from bvote import bvote
    from sel_lab import pick_mbr, BASE5
    k, v, srcs = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    pick = pick_mbr(v, BASE5); md = v["proc"][pick]; base = v["gt"][pick]; out = {}
    for name, (src, kk, lo) in {"CONTROL v7 k1": (["ab_v7"], 1, False), "v10a k1": (["ab_v10a"], 1, False), "v10b k1": (["ab_v10b"], 1, False), "v10a+v10b k2": (["ab_v10a", "ab_v10b"], 2, False),
                               "v10a+v10b k1": (["ab_v10a", "ab_v10b"], 1, False), "v10a+v10b k2 long": (["ab_v10a", "ab_v10b"], 2, True)}.items():
        new, _, s = bvote(md, [srcs[x] for x in src if x in srcs], k=kk, do_merge=False, long_only=lo)
        out[name] = (base, gt_score(new, gt) if s else base, s)
    return k, out


if __name__ == "__main__" and ("--import" in sys.argv or "--import-only" in sys.argv):
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json")))
    S = {n: {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{n}.jsonl")))} for n in ("ab_v7", "ab_v10a", "ab_v10b")}
    keys = [k for k in sorted(C) if all(C[k]["gt"][n] for n in C[k]["gt"]) and all(k in S[n] for n in S)]
    lay = layout_of()
    with Pool(11, initializer=mbr._init) as P: res = dict(P.map(imp, [(k, C[k], {n: S[n][k] for n in S}) for k in keys], chunksize=2))
    print(f"\n== split import into the current pipeline page ({len(keys)} pages, {sum(lay.get(k) in MC for k in keys)} multi-column)")
    for name, grp in [(n, g) for n in next(iter(res.values())) for g in ("all", "multi", "control")]:
        by = collections.defaultdict(list); d = []
        for k, r in res.items():
            if grp == "multi" and lay.get(k) not in MC or grp == "control" and lay.get(k) in MC: continue
            b, a2, s = r[name]; by[k.rsplit("_", 1)[0]].append(U(a2) - U(b))
            if s: d.append((U(a2) - U(b), a2[0] - b[0], a2[1] - b[1]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000))
        print(f"   {name:20s} {grp:8s} {len(d):3d} pages changed  {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]  better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}  "
              f"text {sum(x[1] for x in d)/max(1, sum(len(v) for v in by.values())):+.3f} order {sum(x[2] for x in d)/max(1, sum(len(v) for v in by.values())):+.3f}")

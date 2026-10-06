"""Can a new model's better reading be used without its paragraph order? (dev, smoke-test pages of RUN_TAG, md2md)
Skeleton = the current pipeline page (MBR base5 pick, processed); each body paragraph is located in the new model's processed page (best
fuzzy match on normalised text, similar length) and replaced by the new model's version; split, order, tables, formulas and furniture stay ours.
  python fuse_eval.py RUN_TAG
"""
import collections, json, os, random, re, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from rapidfuzz import fuzz
from common import gt_markdown
from ensemble_lab import downstream, gt_score
from para_fuse import paras, skip, W, HEAD
from postprocess import strip_sections
from sel_lab import BASE5, U, pick_mbr


def prefer(skel, new, minsim=70, lenr=0.75, minw=8):
    O = [(HEAD.sub("", q), W(HEAD.sub("", q))) for q in paras(new) if not skip(q)]
    out = []; ch = 0
    for p in paras(skel):
        if skip(p): out.append(p); continue
        m = HEAD.match(p); pre = m.group(1) if m else ""; body = p[len(pre):]; w = W(body)
        if len(w) < minw: out.append(p); continue
        best, bq = 0, None
        for q, wq in O:
            if not wq or min(len(w), len(wq)) / max(len(w), len(wq)) < lenr: continue
            s = fuzz.ratio(w, wq)
            if s > best: best, bq = s, q
        if bq is not None and best >= minsim and bq != body: out.append(pre + bq); ch += 1
        else: out.append(p)
    return "\n\n".join(out), ch


def job(a):
    k, v, new = a
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    pick = pick_mbr(v, BASE5); skel = v["proc"][pick]; nproc = downstream(new, k)
    r = {"current pipeline": v["gt"][pick], "new model alone": gt_score(nproc, gt)}
    for name, kw in (("fuse sim>=70", {}), ("fuse sim>=85", {"minsim": 85}), ("fuse sim>=50", {"minsim": 50, "lenr": 0.6})):
        f, ch = prefer(skel, nproc, **kw); r[name] = gt_score(f, gt); r["_ch " + name] = ch
    return k, r


if __name__ == "__main__":
    tag = sys.argv[1]
    D = {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{tag}.jsonl")))}
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json")))
    keys = [k for k in sorted(D) if k in C and all(C[k]["gt"][n] for n in C[k]["gt"]) and len(D[k]) >= 60]
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(k, C[k], D[k]) for k in keys], chunksize=2))
    ok = [k for k in R if all(R[k][n] for n in R[k] if not n.startswith("_"))]
    print(f"{tag}: {len(ok)} dev pages (new model's short/empty pages excluded)")
    base = "current pipeline"
    for n in [x for x in R[ok[0]] if not x.startswith("_")]:
        by = collections.defaultdict(list)
        for k in ok: by[k.rsplit("_", 1)[0]].append(U(R[k][n]) - U(R[k][base]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv]
        ch = sum(R[k].get("_ch " + n, 0) for k in ok)
        print(f"  {n:18s} Text_ED {1 - st.mean(R[k][n][0] for k in ok) / 100:.4f}  RO {st.mean(R[k][n][1] for k in ok):6.2f}  vs current {m(bk):+.2f} [{bt[50]:+.2f},{bt[1949]:+.2f}]  pages {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)}" + (f"  paragraphs replaced {ch}" if ch else ""))

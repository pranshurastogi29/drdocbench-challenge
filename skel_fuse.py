"""D2: parser skeleton for the books where our runs disagree (dev; test G2 = the 8 highest-disagreement books, Text_ED 0.203, RO 80.7).
Our page keeps its text and order; its paragraph boundaries are replaced by a layout parser's (bvote with that parser as the only voter,
k=1, merges and splits, any length): PaddleOCR-VL (runs/paddle_dev.jsonl) or the MinerU pipeline (~/Downloads/mineru_results).
Gate: per-book run disagreement as build_probes.py computes it (100 - mean pairwise fuzz ratio of v6/v7/v8/v7c, first 4000 chars).
Prints md2md text / order / leaderboard-weighted gain vs our page for all books and for the high-disagreement books, book-bootstrapped.
  python skel_fuse.py [--steps sel=mbr8,rules,fm,sd,bv,ac]
"""
import argparse, collections, itertools, json, os, random, re, statistics as st, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
import md2md_eval as M
from bvote import bvote
from common import gt_markdown
MINERU = os.path.expanduser("~/Downloads/mineru_results")
U = lambda r: 0.558 * r[0] + 0.433 * r[1]


def mineru(stem):
    f = os.path.join(MINERU, stem, "auto", stem + ".md")
    return re.sub(r"!\[[^\]]*\]\([^)]*\)", "", open(f, encoding="utf-8").read()) if os.path.exists(f) else None


def variants(md, paddle, mine):
    out = {"ours": md}
    for name, src in (("paddle", paddle), ("mineru", mine)):
        if not src: continue
        out[f"{name} split+merge"] = bvote(md, [src], k=1, do_merge=True, long_only=False)[0]
        out[f"{name} split only"] = bvote(md, [src], k=1, do_merge=False, long_only=False)[0]
        out[f"{name} merge only"] = bvote(md, [src], k=1, do_merge=True, do_split=False, long_only=False)[0]
    return out


def job(a):
    stem, subj, md, paddle = a
    doc, pg = stem.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    V = variants(md, paddle, mineru(stem)); res = {}
    for n, m in V.items():
        s = M.page_scores(m, gt, True)
        if s and s[1] is not None: res[n] = s
    return stem, res


def boot(by, n=2000):
    bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / max(1, sum(len(by[q]) for q in bs))
    bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(n)); return m(bk), bt[int(n * 0.025)], bt[int(n * 0.975)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--steps", default="sel=mbr8,rules,fm,sd,bv,ac"); a = ap.parse_args()
    import stack
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", a.steps, tmp)
    os.chdir(ROOT)
    rd = lambda p: {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, p)))}
    pad = rd("runs/paddle_dev.jsonl"); cand = [rd(p) for p in ("runs/dev_all_full_bunny.jsonl", "runs/dev_all_v7_final.jsonl", "runs/dev_all_v8_final.jsonl", "runs/dev_all_v7c_final.jsonl")]
    w = lambda s: re.sub(r"\W", "", (s or "").lower())[:4000]
    pages = collections.defaultdict(list)
    for r in rows: pages[r["document_id"]].append(f'{r["document_id"]}_{r["page"]}')
    dis = {d: 100 - st.mean(st.mean(fuzz.ratio(w(x.get(k)), w(y.get(k))) for x, y in itertools.combinations(cand, 2)) for k in ks) for d, ks in pages.items()}
    with Pool(11, initializer=M.init) as P: R = dict(P.map(job, [(f'{r["document_id"]}_{r["page"]}', r["subject"], r["markdown"], pad.get(f'{r["document_id"]}_{r["page"]}')) for r in rows], chunksize=4))
    os.chdir(ROOT)
    order = sorted(dis, key=lambda d: -dis[d]); top8 = set(order[:8]); topq = set(order[:len(order) // 4])
    names = sorted({n for v in R.values() for n in v if n != "ours"})
    print(f"{len(R)} dev pages, {len(dis)} books; disagreement top-8 books: " + ", ".join(f"{d[:8]}({dis[d]:.0f})" for d in order[:8]))
    for label, books in (("all books", set(dis)), ("top quartile disagreement", topq), ("top 8 disagreement (G2 analogue)", top8)):
        print(f"  {label}:")
        for n in names:
            by = collections.defaultdict(list); dt = []; do = []
            for k, v in R.items():
                if k.rsplit("_", 1)[0] not in books or "ours" not in v or n not in v: continue
                by[k.rsplit("_", 1)[0]].append(U(v[n]) - U(v["ours"])); dt.append(v[n][0] - v["ours"][0]); do.append(v[n][1] - v["ours"][1])
            if not dt: continue
            m, lo, hi = boot(by); d = [x for xs in by.values() for x in xs]
            print(f"    {n:20s} gain {m:+.2f} [{lo:+.2f},{hi:+.2f}]  text {st.mean(dt):+.2f}  order {st.mean(do):+.2f}  pages {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)} of {len(d)}")
    json.dump({"dis": dis, "R": R}, open(os.path.join(ROOT, "runs", "skel_fuse_dev.json"), "w"))

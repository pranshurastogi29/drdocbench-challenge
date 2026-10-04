"""Dev: split-snap cut at the midpoint (final5) vs moved to the nearest whitespace (snap.py ws=True); MBR base5 pick, full downstream rules.
  python snapws_eval.py [--split test]   (test: count changed pages)
"""
import argparse, collections, json, os, random, re, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import para, MAX_ADD
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, U, pick_mbr


def downstream(md, stem, ws):
    from snap import snap
    from tablefix import fix
    from furnmerge import merge_tail
    import paddle_ingest
    s = snap(md, stem, mode="split", ws=ws)
    if para(s) - para(md) > MAX_ADD: s = md
    s, _ = fix(s, stem, replace=False)
    try: fur = [re.sub(r"[\W_]", "", t.lower()) for _, t in paddle_ingest.furniture(stem)]
    except Exception: fur = []
    return merge_tail(s, 2, 60, fur)


def job(a):
    split, k, v = a; md = v["raw"][pick_mbr(v, BASE5)]
    old = v["proc"][pick_mbr(v, BASE5)]; new = downstream(md, k, True)
    if new == old: return k, None
    if split != "dev": return k, (None, None)
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    return k, (v["gt"][pick_mbr(v, BASE5)], gt_score(new, gt))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); a = ap.parse_args()
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    if a.split == "dev": C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, [(a.split, k, v) for k, v in sorted(C.items())], chunksize=4))
    ch = {k: r for k, r in R.items() if r}
    print(f"{a.split}: {len(ch)} pages changed")
    if a.split == "dev":
        by = collections.defaultdict(list)
        for k in C: by[k.rsplit("_", 1)[0]].append(U(ch[k][1]) - U(ch[k][0]) if k in ch else 0.0)
        books = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
        bt = sorted(m(rng.choices(books, k=len(books))) for _ in range(2000))
        d = [(U(r[1]) - U(r[0]), r[1][0] - r[0][0], r[1][1] - r[0][1]) for r in ch.values()]
        print(f"  {m(books):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]; changed pages better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}; "
              f"text {sum(x[1] for x in d)/len(C):+.3f} order {sum(x[2] for x in d)/len(C):+.3f} (per page, all pages)")

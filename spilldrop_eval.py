"""Dev evaluation of spilldrop.py: skeleton = MBR base5 pick (processed, selection cache), one-page runs v6w1/v7w1/v8w1 of the page and its neighbours.
  python spilldrop_eval.py [--split test]   (test: only counts what would change)
"""
import argparse, collections, json, os, random, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import DEV, TEST
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, U, pick_mbr
from spilldrop import spilldrop

W1 = ("v6w1", "v7w1", "v8w1")
SETTINGS = {"default": {}, "dup-guard": {"dup": True}, "votes3": {"min_votes": 3}, "strict": {"absent": 50, "present": 90}}


def job(a):
    split, k, v, here, nbs, onb = a; doc, pg = k.rsplit("_", 1)
    md = v["proc"][pick_mbr(v, BASE5)]; res = {}
    gt = gt_markdown("dev", v["subject"], doc, int(pg)) if split == "dev" else None
    base = gt_score(md, gt) if gt else None
    for name, kw in SETTINGS.items():
        kw = dict(kw); dup = kw.pop("dup", False)
        new, dropped = spilldrop(md, here, nbs, ours_nb=onb if dup else None, **kw)
        res[name] = (base, gt_score(new, gt) if (gt and dropped) else base, len(dropped), sum(len(d) for d in dropped), dropped[:2])
    return k, res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); a = ap.parse_args()
    C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
    if a.split == "dev": C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    files = DEV if a.split == "dev" else TEST
    R1 = {n: {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, files[n])))} for n in W1}
    def w1(stem): return [R1[n].get(stem, "") for n in W1]
    jobs = []
    for k, v in sorted(C.items()):
        doc, pg = k.rsplit("_", 1); pg = int(pg)
        onb = [C[f"{doc}_{pg + d}"]["proc"][pick_mbr(C[f"{doc}_{pg + d}"], BASE5)] for d in (-1, 1) if f"{doc}_{pg + d}" in C]
        jobs.append((a.split, k, v, w1(k), [w1(f"{doc}_{pg + d}") for d in (-1, 1) if any(w1(f"{doc}_{pg + d}"))], onb))
    with Pool(11, initializer=mbr._init) as P: R = dict(P.map(job, jobs, chunksize=4))
    for name in SETTINGS:
        ch = {k: r[name] for k, r in R.items() if r[name][2]}
        print(f"{name:8s}: {len(ch)} pages changed, {sum(r[2] for r in ch.values())} paragraphs / {sum(r[3] for r in ch.values())} chars dropped", end="")
        if a.split == "dev":
            by = collections.defaultdict(list)
            for k, r in R.items(): by[k.rsplit("_", 1)[0]].append(U(r[name][1]) - U(r[name][0]))
            books = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
            bt = sorted(m(rng.choices(books, k=len(books))) for _ in range(2000))
            d = [U(r[1]) - U(r[0]) for r in ch.values()]
            print(f"; {m(books):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]; changed pages better/worse {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}; "
                  f"text {st.mean(r[name][1][0] - r[name][0][0] for r in R.values()):+.3f} order {st.mean(r[name][1][1] - r[name][0][1] for r in R.values()):+.3f}")
            for k, r in sorted(ch.items(), key=lambda x: U(x[1][1]) - U(x[1][0]))[:3]:
                print(f"     worst {k[:8]}..{k[-5:]} {U(r[1]) - U(r[0]):+.1f}: {r[4][0][:100]!r}")
        else:
            print(); [print(f"     {k[:8]}..{k[-5:]}: {r[4][0][:110]!r}") for k, r in list(ch.items())[:8]]

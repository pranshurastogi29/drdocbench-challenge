"""Upper bound of the column-break rule (dev): split our paragraph exactly where the reference starts the next column's block, when we joined them.
  python ro_colbreak_oracle.py
"""
import collections, json, os, random, re, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
import ro_columns as R
from ro_colbreak import where
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, U, pick_mbr


def job(a):
    k, v = a; L = R.page_layout(k)
    if not L: return k, None
    info, B = L; bs = R.bands(B, info["width"])
    md = v["proc"][pick_mbr(v, BASE5)]; raw = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    P = [R.W_(p) for p in raw]; cuts = collections.defaultdict(list)
    for band in bs:
        if R.classify(band, {id(b): b["order"] for b in band}) != "column-major": continue
        seq = sorted(band, key=lambda b: b["order"])
        for x, y in zip(seq, seq[1:]):
            if x["col"] != y["col"] and x["cat"] == y["cat"] == "text_block":
                i, j = where(x, P), where(y, P)
                if i is not None and i == j: cuts[i].append(y["w"][:25])
    if not cuts: return k, None
    out = []
    for i, p in enumerate(raw):
        if i not in cuts: out.append(p); continue
        low = p.lower(); pieces = [p]
        for head in cuts[i]:
            q = pieces[-1]; ql = q.lower()
            # locate head (normalised) in the original string
            norm, idx = zip(*[(c, n) for n, c in enumerate(ql) if re.match(r"[^\W_]", c)]) if re.search(r"[^\W_]", ql) else ((), ())
            s = "".join(norm).find(head)
            if s > 0:
                cut = idx[s]
                while cut > 0 and not q[cut - 1].isspace(): cut -= 1
                if cut > 0: pieces[-1:] = [q[:cut].strip(), q[cut:].strip()]
        out.extend(x for x in pieces if x)
    new = "\n\n".join(out)
    if new == "\n\n".join(raw): return k, None
    gt = gt_markdown("dev", v["subject"], *[k.rsplit("_", 1)[0], int(k.rsplit("_", 1)[1])])
    return k, (v["gt"][pick_mbr(v, BASE5)], gt_score(new, gt))


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: res = dict(P.map(job, sorted(C.items()), chunksize=4))
    ch = {k: r for k, r in res.items() if r}
    by = collections.defaultdict(list)
    for k in C: by[k.rsplit("_", 1)[0]].append(U(ch[k][1]) - U(ch[k][0]) if k in ch else 0.0)
    bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
    bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [(U(r[1]) - U(r[0]), r[1][0] - r[0][0], r[1][1] - r[0][1]) for r in ch.values()]
    print(f"oracle column-break splits: {len(ch)} pages; {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}] (leaderboard units); better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}; "
          f"text {sum(x[1] for x in d)/len(C):+.3f} order {sum(x[2] for x in d)/len(C):+.3f} per page")

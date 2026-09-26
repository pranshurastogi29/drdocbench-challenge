"""Paired per-page comparison of two scored md2md runs (scorer/result/drdoc_<name>_*.json).
  python compare_runs.py NAME_A NAME_B      -> B minus A, positive = B better
"""
import bisect, collections, glob, json, random, statistics as st, sys
from reading_order import norm
res = "scorer/result/drdoc_%s_%s.json"


def load(name):
    t = json.load(open(res % (name, "text_block_per_page_edit")))
    r = json.load(open(res % (name, "reading_order_per_page_edit")))
    tb = collections.defaultdict(list)
    for k, v in json.load(open(res % (name, "table_per_table_TEDS"))).items():
        tb[k.rsplit("_[", 1)[0]].append(100 * v["TEDS"])
    P = {}
    for k in set(t) | set(r):
        comps = [100 * (1 - x[k]) for x in (t, r) if k in x]
        if k in tb:
            comps.append(st.mean(tb[k]))
        P[k] = dict(overall=st.mean(comps), text=100 * (1 - t[k]) if k in t else None,
                    order=100 * (1 - r[k]) if k in r else None, teds=st.mean(tb[k]) if k in tb else None)
    return P


def lis_keep(seq):
    tails, idx, prev = [], [], [-1] * len(seq)
    for i, v in enumerate(seq):
        j = bisect.bisect_left(tails, v)
        if j == len(tails):
            tails.append(v); idx.append(i)
        else:
            tails[j] = v; idx[j] = i
        prev[i] = idx[j - 1] if j else -1
    keep, i = set(), (idx[-1] if idx else -1)
    while i >= 0:
        keep.add(i); i = prev[i]
    return keep


def header_stats(name):
    by = collections.defaultdict(list)
    for x in json.load(open(res % (name, "text_block_result"))):
        by[x["img_id"]].append(x)
    tot = disp = top = 0
    for img, items in by.items():
        doc, pg = img.rsplit("_", 1)[0], int(img.rsplit("_", 1)[1][:-4]); rec = None
        for p in glob.glob(f"data/dev/*/{doc}/json/{doc}_page_{pg}.json"):
            rec = json.load(open(p))
        if not rec or not rec[0]:
            continue
        hdr = {norm(b.get("text") or "")[:25] for b in rec[0]["layout_dets"]
               if b["category_type"] == "header" and len(norm(b.get("text") or "")) >= 8}
        gi = sorted([x for x in items if x["gt"] != ""], key=lambda x: x["gt_position"][0] if isinstance(x["gt_position"], list) and x["gt_position"] else 0)
        m = [x for x in gi if x["pred"] != "" and x["pred_position"] != ""]
        if len(m) < 3 or not hdr:
            continue
        keep = lis_keep([x["pred_position"] for x in m]); mx = max(y["pred_position"] for y in m)
        for i, x in enumerate(m):
            if norm(x["gt"])[:25] in hdr:
                tot += 1
                if i not in keep:
                    disp += 1; top += x["pred_position"] / max(1, mx) < 0.34
    return tot, disp, top


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    A, B = load(a), load(b); keys = sorted(set(A) & set(B))
    print(f"pages scored in both: {len(keys)}  ({b} minus {a}; positive = {b} better)\n")
    for f in ("overall", "text", "order", "teds"):
        d = [B[k][f] - A[k][f] for k in keys if A[k][f] is not None and B[k][f] is not None]
        rng = random.Random(0); bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(5000))
        print(f"  {f:8s} n={len(d):4d}  mean {st.mean(d):+6.2f}  95% CI [{bs[125]:+.2f}, {bs[4874]:+.2f}]  {b} better on {sum(x > 1 for x in d)}, worse on {sum(x < -1 for x in d)}")
    for name, P in ((a, A), (b, B)):
        print(f"  mean overall {name}: {st.mean(P[k]['overall'] for k in keys):.2f}")
    d = [B[k]["overall"] - A[k]["overall"] for k in keys]; g = sorted(d, reverse=True)
    print(f"\nlargest gains {[round(x) for x in g[:4]]}, largest losses {[round(x) for x in sorted(d)[:4]]}; top 10 pages = {sum(g[:10]):.0f} of {sum(d):.0f} total points gained")
    for n in (a, b):
        t, dd, tp = header_stats(n)
        print(f"{n}: header paragraphs out of order {dd}/{t} ({100*dd/t:.0f}%), placed at top of our output: {tp}")

"""Which blocks are out of order? For each page the scorer's GT block order vs ours; the moved blocks are the ones outside the longest
common ordered subsequence. Classify them by what they are (text from text_block_result, joined via the GT order id)."""
import bisect, collections, json, re, statistics as st, sys
RUN = sys.argv[1] if len(sys.argv) > 1 else "DEVR_final7t"
res = lambda n: json.load(open(f"scorer/result/drdoc_{RUN}_{n}.json"))
RO = res("reading_order_result"); TB = res("text_block_result")
txt = collections.defaultdict(dict)
for e in TB:
    for gi, pos, in zip(e["gt_idx"], e["gt_position"]):
        if gi != "": txt[e["img_id"]][pos] = (e["gt"], e.get("gt_category_type"))
def lis_keep(seq):
    """indices of a longest increasing subsequence"""
    tails, idx, prev = [], [], [-1] * len(seq)
    for i, v in enumerate(seq):
        j = bisect.bisect_left(tails, v)
        if j == len(tails): tails.append(v); idx.append(i)
        else: tails[j] = v; idx[j] = i
        prev[i] = idx[j - 1] if j else -1
    out, i = set(), idx[-1] if idx else -1
    while i >= 0: out.add(i); i = prev[i]
    return out
cls = collections.Counter(); tot = 0; ex = collections.defaultdict(list); pos_c = collections.Counter(); dist = []
for e in RO:
    g, p = e["gt"], e["pred"]
    if g == p or not g: continue
    rank = {v: i for i, v in enumerate(g)}
    try: seq = [rank[v] for v in p]
    except KeyError: continue
    keep = lis_keep(seq); moved = [p[i] for i in range(len(p)) if i not in keep]
    for m in moved:
        t = txt[e["img_id"]].get(m, ("", ""))[0]; s = re.sub(r"\s+", " ", t).strip(); n = len(s); tot += 1
        r = rank[m]; where = "first third of page order" if r < len(g) / 3 else "last third" if r >= 2 * len(g) / 3 else "middle"
        pos_c[where] += 1
        if n == 0: k = "text not found"
        elif n <= 4 or re.fullmatch(r"[\divxlc\W]+", s.lower() or "x"): k = "page number / tiny (<=4 chars or numeric)"
        elif n <= 40 and (s.isupper() or re.match(r"^(chapter|section|part|unit|figure|table|fig\.)\b", s.lower())): k = "short heading / caption / label (<=40 chars)"
        elif n <= 40: k = "short line (<=40 chars)"
        elif n <= 200: k = "medium paragraph (41-200 chars)"
        else: k = "long paragraph (>200 chars)"
        cls[k] += 1; ex[k].append(s[:70])
        dist.append(abs(seq.index(rank[m]) - rank[m]) if rank[m] in seq else 0)
print(f"{len(RO)} pages; blocks displaced (outside longest correct ordered run): {tot}")
for k, v in cls.most_common(): print(f"  {k:46s} {v:5d} ({100*v/tot:4.1f}%)   e.g. {ex[k][:3]}")
print("  where the displaced blocks sit in the GT order:", {k: f"{100*v/tot:.0f}%" for k, v in pos_c.items()})
print("  median displacement (positions):", st.median(dist), " share moved by >=3 positions:", f"{100*sum(d>=3 for d in dist)/len(dist):.0f}%")
per = collections.Counter(); 
for e in RO:
    g, p = e["gt"], e["pred"]
    if g == p or not g: continue
    rank = {v: i for i, v in enumerate(g)}
    try: seq = [rank[v] for v in p]
    except KeyError: continue
    per[len(seq) - len(lis_keep(seq))] += 1
print("  pages by number of displaced blocks:", dict(sorted(per.items())[:8]))

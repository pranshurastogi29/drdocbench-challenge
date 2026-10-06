"""Our dev error broken down by the page / block attributes the Dr.DocBench paper (arXiv 2606.01393) reports on: language, layout,
special issues (colorful background, fuzzy scan, tables), rotated text blocks, data source, challenge type, merge_list (flattened TOC) blocks.
Uses the per-page md2md scores of the last ablation (runs/ablate_last.json; FULL = the 82.88 stack, mbr8 = the best dev selection).
For each group: pages, mean Text_ED, mean order edit, and the group's share of the total Text_ED / order loss (leaderboard averages pages).
  python paper_breakdown.py
"""
import collections, glob, json, os
ROOT = os.path.dirname(os.path.abspath(__file__))


def attrs(stem):
    doc, pg = stem.rsplit("_", 1)
    f = glob.glob(os.path.join(ROOT, "data", "dev", "*", doc, "json", f"{doc}_page_{pg}.json"))
    if not f: return None
    j = json.load(open(f[0]))
    if not j: return None
    x = j[0]; pa = x["page_info"].get("page_attribute", {})
    L = lambda v: v if isinstance(v, list) else [v]
    g = {"language": ["+".join(L(pa.get("language")))], "layout": L(pa.get("layout")), "issue": L(pa.get("special_issue") or ["none"]),
         "data_source": L(pa.get("data_source")), "challenge": L(pa.get("challenge_type"))}
    tb = [d for d in x.get("layout_dets", []) if d.get("category_type") in ("text_block", "title", "reference", "code_txt")]
    n = sum(len(d.get("text") or "") for d in tb) or 1
    r = sum(len(d.get("text") or "") for d in tb if (d.get("attribute") or {}).get("text_rotate") not in (None, "normal"))
    g["rotated text"] = ["none" if r == 0 else "<25% of chars" if r / n < 0.25 else ">=25% of chars"]
    g["merge_list"] = ["yes" if any(d.get("merge_list") for d in x.get("layout_dets", [])) else "no"]
    return g


if __name__ == "__main__":
    S = json.load(open(os.path.join(ROOT, "runs", "ablate_last.json")))
    for var in ("FULL (82.88)", "mbr8"):
        P = {k: (1 - v[var][0] / 100, 1 - v[var][1] / 100) for k, v in S.items() if v.get(var) and v[var][0] is not None and v[var][1] is not None}
        A = {k: attrs(k) for k in P}; A = {k: a for k, a in A.items() if a}
        N = len(A); T = sum(P[k][0] for k in A); O = sum(P[k][1] for k in A)
        print(f"\n=== {var}: {N} dev pages, Text_ED {T / N:.4f}, order edit {O / N:.4f}")
        for dim in ("language", "layout", "issue", "rotated text", "data_source", "challenge", "merge_list"):
            G = collections.defaultdict(list)
            for k, a in A.items():
                for v in a[dim]: G[v].append(k)
            print(f"  {dim}:")
            for v, ks in sorted(G.items(), key=lambda kv: -sum(P[k][0] for k in kv[1])):
                t = sum(P[k][0] for k in ks); o = sum(P[k][1] for k in ks)
                print(f"    {str(v):22s} {len(ks):4d} pages  Text_ED {t / len(ks):.3f} ({t / T:4.0%} of loss)  order {o / len(ks):.3f} ({o / O:4.0%})")

"""Merge crop-pass tables (table_crops.py) into page predictions and score with table_lab.

  python table_merge.py runs/dev_all_final5.jsonl runs/tables_dev_t1.jsonl
Modes: replace = swap our best-matching table for the crop's (if cell text similar >= THR), else append the crop's table;
       add = only append crop tables that match none of ours (what tablefix does with Paddle's own tables);
       crop_only = pages keep only crop tables (upper bound of trusting the crop pass).
"""
import collections, json, re, statistics as st, sys
from rapidfuzz import fuzz
from postprocess import postprocess  # noqa: F401  (kept for parity with the pipeline)
from reading_order import norm
from table_lab import TAB, gt_tables, load_pred, score
from variants import tables_variant

cellnorm = lambda h: norm(re.sub(r"<[^>]+>", " ", h))
THR = 55


def load_crops(path):
    C = collections.defaultdict(list)
    for r in map(json.loads, open(path, encoding="utf-8")):
        m = TAB.search(r["html"] or "")
        if m: C[r["stem"]].append((r["idx"], tables_variant(m.group(0))))
    return C


def merge(md, crops, mode):
    ours = TAB.findall(md)
    if mode == "crop_only":
        return TAB.sub("", md).rstrip() + "\n\n" + "\n\n".join(t for _, t in sorted(crops)) if crops else md
    used, out, extra = set(), md, []
    for _, ct in sorted(crops):
        cn = cellnorm(ct)
        best, bs = None, 0
        for i, o in enumerate(ours):
            if i in used: continue
            s = fuzz.ratio(cn[:1500], cellnorm(o)[:1500])
            if s > bs: best, bs = i, s
        if best is not None and bs >= THR:
            used.add(best)
            if mode == "replace": out = out.replace(ours[best], ct, 1)
        else:
            extra.append(ct)
    return out.rstrip() + ("\n\n" + "\n\n".join(extra) if extra else "")


def owners(G, P):
    o = []
    for page, g in G.items():
        if page in P and TAB.findall(P[page]): o += [page.split("_")[0][:8]] * len(g)
    return o


if __name__ == "__main__":
    G = gt_tables(); P = load_pred(sys.argv[1]); C = load_crops(sys.argv[2])
    def report(name, PP):
        m, flat = score(PP, G=G); ow = owners(G, PP)
        assert len(ow) == len(flat), (len(ow), len(flat))
        c18 = [f for o, f in zip(ow, flat) if o == "c18d05a4"]; rest = [f for o, f in zip(ow, flat) if o != "c18d05a4"]
        print(f"{name:14s} all {m:6.2f} (n={len(flat)})   c18d05a4 {100*st.mean(c18):6.2f} (n={len(c18)})   other docs {100*st.mean(rest):6.2f} (n={len(rest)})", flush=True)
    report("baseline", P)
    for mode in ("replace", "add", "crop_only"):
        report(mode, {k: (merge(v, C[k], mode) if k in C else v) for k, v in P.items()})

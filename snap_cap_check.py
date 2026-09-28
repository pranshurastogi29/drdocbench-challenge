"""How often does build_submission's MAX_ADD=9 cap discard a real split, and does it concentrate on the top-loss pages?"""
import json, re, sys
from snap import snap
from compare_runs import load
para = lambda m: len([p for p in re.split(r"\n\s*\n", m.strip()) if p.strip()])
P = {f"{x['document_id']}_{x['page']}": x["markdown"] for x in map(json.loads, open("runs/dev_all_final5.jsonl", encoding="utf-8"))}
S = load("FINAL5")
rows = []
for stem, md in P.items():
    s = snap(md, stem, mode="split")
    add = para(s) - para(md)
    if add > 0:
        rows.append((add, stem))
rows.sort(reverse=True)
print(f"{sum(1 for a,_ in rows if a>0)} pages get a real split; {sum(1 for a,_ in rows if a>9)} exceed MAX_ADD=9 and are discarded")
for a, stem in rows[:20]:
    k = stem + ".jpg"; ov = S[k]["overall"] if k in S and S[k]["overall"] is not None else None
    print(f"  +{a:3d} paras  {stem[:8]}_{stem.split('_')[1]:6s}  overall {ov}")

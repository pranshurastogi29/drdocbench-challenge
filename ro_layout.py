"""Order loss of the current best (MBR base5 + rules, dev) by the reference's page layout label and special issues, and where displaced body
text sits (block background = sidebars / boxes, column). Uses runs/ro_anatomy2.json (ro_anatomy2.py) for the per-page order score.
  python ro_layout.py
"""
import collections, glob, json, statistics as st
R = json.load(open("runs/ro_anatomy2.json"))
info = {}
for f in glob.glob("data/dev/*/*/json/*.json"):
    j = json.load(open(f))
    if j:
        pi = j[0]["page_info"]; info[f'{pi["page_name"]}_{pi["page_no"]}'] = (pi["page_attribute"].get("layout"), tuple(pi["page_attribute"].get("special_issue") or []),
                                                                             collections.Counter(b.get("attribute", {}).get("text_background") for b in j[0]["layout_dets"] if b.get("category_type") == "text_block"))
N = len(R); by = collections.defaultdict(list); sp = collections.defaultdict(list)
for k, r in R.items():
    lay, iss, bg = info.get(k, ("?", (), {}))
    by[lay].append(100 - r["ro"])
    for i in iss or ("none",): sp[i].append(100 - r["ro"])
    by["(has non-white text background)" if any(b not in ("white", None) for b in bg) else "(all text on white)"].append(100 - r["ro"])
print(f"{N} dev pages; total order loss {sum(100 - r['ro'] for r in R.values())/N:.2f} points/page")
print(f"{'layout':34s} {'pages':>5s} {'mean loss':>9s} {'share of total loss':>20s}")
tot = sum(100 - r["ro"] for r in R.values())
for k, v in sorted(by.items(), key=lambda x: -sum(x[1])): print(f"{str(k):34s} {len(v):5d} {st.mean(v):9.1f} {sum(v)/tot:19.0%}")
print("\nspecial issues:")
for k, v in sorted(sp.items(), key=lambda x: -sum(x[1])): print(f"  {str(k):32s} {len(v):5d} {st.mean(v):9.1f} {sum(v)/tot:19.0%}")

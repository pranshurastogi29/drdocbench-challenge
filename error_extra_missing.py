"""Which pages/paragraphs make up the 'extra predicted' and 'reference not matched' text edits (official scorer result, dev)."""
import collections, json, re, sys
RUN = sys.argv[1] if len(sys.argv) > 1 else "DEVR_final7t"
TB = json.load(open(f"scorer/result/drdoc_{RUN}_text_block_result.json"))
one = lambda s: re.sub(r"\s+", " ", s)[:110]
for label, sel in (("EXTRA predicted (not in reference)", lambda e: e["gt"] == "" and e["pred"] != ""), ("MISSING (reference paragraph not matched)", lambda e: e["pred"] == "" and e["gt"] != "")):
    by = collections.defaultdict(list)
    for e in TB:
        if sel(e): by[e["img_id"]].append(e)
    tot = sum(e["Edit_num"] for v in by.values() for e in v)
    ranked = sorted(by.items(), key=lambda kv: -sum(e["Edit_num"] for e in kv[1]))
    for n in (5, 20, 50):
        print(f"{label}: top {n} pages hold {100*sum(e['Edit_num'] for _, v in ranked[:n] for e in v)/tot:.0f}% of {tot} chars ({len(by)} pages affected)")
    for k, v in ranked[:14]:
        big = max(v, key=lambda e: e["Edit_num"]); txt = big["pred"] if label.startswith("EXTRA") else big["gt"]
        print(f"   {k[:8]}_{k.split('_')[1]:6s} {sum(e['Edit_num'] for e in v):6d} chars in {len(v):3d} paras | biggest: {one(txt)!r}")
    print()

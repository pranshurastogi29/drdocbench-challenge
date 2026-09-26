import collections, glob, json, re, sys
RUN = "DEVR_final7t"; subj = {}
for p in glob.glob("data/dev/*/*/images/page_*.jpg"): subj[p.split("/")[3]] = p.split("/")[2]
TB = json.load(open(f"scorer/result/drdoc_{RUN}_text_block_result.json"))
one = lambda s: re.sub(r"\s+", " ", s)[:120]
for s in sys.argv[1:]:
    ex, ms = [], []
    for e in TB:
        if subj[e["img_id"].split("_")[0]] != s: continue
        if e["gt"] == "" and e["pred"]: ex.append((e["Edit_num"], e["img_id"], e["pred"]))
        elif e["pred"] == "" and e["gt"]: ms.append((e["Edit_num"], e["img_id"], e["gt"]))
    print(f"##### {s}: extra {sum(x[0] for x in ex)} chars in {len(ex)} paras | missing {sum(x[0] for x in ms)} chars in {len(ms)} paras")
    for lab, L in (("EXTRA  (we output, reference omits)", ex), ("MISSING (reference has, we omit)", ms)):
        for n, k, t in sorted(L, reverse=True)[:5]: print(f"  {lab[:5]} {n:5d} {k[:8]}_{k.split('_')[1]:6s} {one(t)!r}")

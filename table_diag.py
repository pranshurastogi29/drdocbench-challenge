"""Diagnose table-structure loss on dev: GT vs predicted table dimensions/spans for a scored run.
  python table_diag.py FINAL5 runs/dev_all_final5.jsonl
"""
import collections, glob, json, re, statistics as st, sys
name, pred_file = sys.argv[1], sys.argv[2]
r = json.load(open(f"scorer/result/drdoc_{name}_table_per_table_TEDS.json"))
def dims(h):
    rows = re.findall(r"<tr\b.*?</tr>", h, re.S | re.I)
    cols = [len(re.findall(r"<t[dh]\b", x, re.I)) for x in rows]
    return len(rows), max(cols) if cols else 0, len(re.findall(r"(?:col|row)span", h, re.I))
gt = {}
for p in glob.glob("data/dev/*/*/json/*.json"):
    recs = json.load(open(p, encoding="utf-8"))
    if not recs: continue
    doc = p.split("/")[3]; pg = re.search(r"page_(\d+)", p).group(1); i = 0
    for b in recs[0]["layout_dets"]:
        if b["category_type"] == "table":
            gt[f"{doc}_{pg}.jpg_[{i}]"] = b.get("html") or ""; i += 1
pred = {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(pred_file, encoding="utf-8"))}
c = collections.Counter(); ex = []
for k, v in r.items():
    if k not in gt: c["nogt"] += 1; continue
    page, idx = k.rsplit("_[", 1); idx = int(idx[:-1]); pt = re.findall(r"<table\b.*?</table>", pred.get(page, ""), re.S | re.I)
    if idx >= len(pt): c["nopred"] += 1; continue
    g, p = dims(gt[k]), dims(pt[idx])
    c["n"] += 1; c["rows_eq"] += g[0] == p[0]; c["cols_eq"] += g[1] == p[1]; c["gt_span"] += g[2] > 0; c["pred_span"] += p[2] > 0
    c["gt_span_pred_none"] += g[2] > 0 and p[2] == 0
    ex.append((v["TEDS"], v["TEDS_structure_only"], g, p, k))
print(dict(c))
for grp, f in (("gt has spans", lambda e: e[2][2] > 0), ("gt no spans", lambda e: e[2][2] == 0)):
    s = [e for e in ex if f(e)]
    print(f"{grp}: n={len(s)} TEDS {100*st.mean(e[0] for e in s):.1f} struct {100*st.mean(e[1] for e in s):.1f}")
ex.sort()
for e in [x for x in ex if .3 <= x[0] < .9][:: max(1, len(ex) // 14)][:14]:
    print(f"TEDS {e[0]:.2f} struct {e[1]:.2f} gt(rows,cols,spans)={e[2]} pred={e[3]} {e[4][:34]}")

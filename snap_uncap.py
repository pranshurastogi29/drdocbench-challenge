"""Test build_submission's split-snap without the MAX_ADD cap, or with alternative caps, on final5's dev output."""
import json, re, sys
from snap import snap
para = lambda m: len([p for p in re.split(r"\n\s*\n", m.strip()) if p.strip()])
rows = [json.loads(l) for l in open("runs/dev_all_final5.jsonl", encoding="utf-8")]
def build(cap):
    out = []
    for r in rows:
        stem = f"{r['document_id']}_{r['page']}"; md = r["markdown"]
        s = snap(md, stem, mode="split")
        if cap is not None and para(s) - para(md) > cap: s = md
        out.append({**r, "markdown": s})
    return out
for cap, tag in ((9, "cap9_baseline"), (None, "uncapped"), (20, "cap20")):
    rows2 = build(cap)
    with open(f"runs/dev_all_snap_{tag}.jsonl", "w", encoding="utf-8") as f:
        for r in rows2: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(tag, "written")

"""How many test pages would a raised MAX_ADD affect (no GT available, count new-paragraph size only)."""
import json, re
from snap import snap
para = lambda m: len([p for p in re.split(r"\n\s*\n", m.strip()) if p.strip()])
rows = [json.loads(l) for l in open("submissions_predictions_placeholder.jsonl", encoding="utf-8")] if False else None
import zipfile
rows = [json.loads(l) for l in zipfile.ZipFile("submissions/submission_final5.zip").open("predictions.jsonl")]
adds = []
for r in rows:
    stem = f"{r['document_id']}_{r['page']}"; md = r["markdown"]
    s = snap(md, stem, mode="split")
    a = para(s) - para(md)
    if a > 0: adds.append((a, stem))
adds.sort(reverse=True)
print(f"{len(rows)} test pages; {sum(1 for a,_ in adds if a>0)} get a real split; discarded by cap9: {sum(1 for a,_ in adds if a>9)}; newly enabled by cap20 (10-20): {sum(1 for a,_ in adds if 10<=a<=20)}; still discarded by cap20 (>20): {sum(1 for a,_ in adds if a>20)}")
for a, stem in adds[:15]: print(f"  +{a:3d}  {stem}")

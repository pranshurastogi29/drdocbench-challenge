"""Detect page misalignment: our page k text matches the reference of page k+-1 better than the reference of page k (dev)."""
import glob, json, re, sys, collections
from rapidfuzz import fuzz
RUN = "DEVR_final7t"
nz = lambda s: re.sub(r"[^a-z0-9]+", " ", re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", s.lower())).strip()[:5000]
pred = {}; 
for r in map(json.loads, open("runs/dev_all_rebuilt_final7t.jsonl", encoding="utf-8")): pred[(r["document_id"], r["page"])] = nz(r["markdown"])
gt = {}
for p in glob.glob(f"eval_tmp/{RUN}/gt/*.md"):
    stem = p.split("/")[-1][:-3]; d, pg = stem.rsplit("_", 1); gt[(d, int(pg))] = nz(open(p, encoding="utf-8").read())
def sim(a, b):
    if not a and not b: return 100.0
    return fuzz.ratio(a, b)
rows = []
for (d, pg), t in pred.items():
    if (d, pg) not in gt: continue
    own = sim(t, gt[(d, pg)]); nb = [(sim(t, gt[(d, pg + o)]), o) for o in (-1, 1, -2, 2) if (d, pg + o) in gt]
    best = max(nb) if nb else (0, 0)
    rows.append((d, pg, own, best[0], best[1], len(t), len(gt[(d, pg)])))
bad = [r for r in rows if r[3] > r[2] + 15 and r[3] > 50]
print(f"pages {len(rows)}; misaligned (a neighbour's reference matches better by >15 and >50): {len(bad)}")
by = collections.Counter(r[0][:8] for r in bad); print("by doc:", dict(by.most_common(10)))
print("offsets:", dict(collections.Counter(r[4] for r in bad)))
for r in sorted(bad, key=lambda r: -(r[3] - r[2]))[:14]: print(f"  {r[0][:8]}_{r[1]:4d} own {r[2]:5.1f}  matches neighbour {r[4]:+d} at {r[3]:5.1f}   lens ours {r[5]} gt {r[6]}")
json.dump([r[:5] for r in bad], open("runs/misaligned_dev.json", "w"))

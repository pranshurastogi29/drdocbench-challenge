"""Size the page-boundary spill inside 2-page windows (dev): window text is right but split at the wrong place."""
import glob, json, re, collections
from rapidfuzz import fuzz
from common import list_pages, windows
RUN = "DEVR_final7t"
nz = lambda s: re.sub(r"[^a-z0-9]+", " ", re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", s.lower())).strip()
pred = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open("runs/dev_all_rebuilt_final7t.jsonl", encoding="utf-8"))}
gt = {}
for p in glob.glob(f"eval_tmp/{RUN}/gt/*.md"):
    d, pg = p.split("/")[-1][:-3].rsplit("_", 1); gt[(d, int(pg))] = open(p, encoding="utf-8").read()
nA = nB = 0; rows = []
for (subj, doc), pages in list_pages("dev").items():
    for w in windows(pages, 2):
        if len(w) < 2: continue
        (a, _), (b, _) = w
        if (doc, a) not in gt or (doc, b) not in gt: continue
        pa, pb, ga, gb = nz(pred[(doc, a)]), nz(pred[(doc, b)]), nz(gt[(doc, a)]), nz(gt[(doc, b)])
        if len(ga) + len(gb) < 400: continue
        own = (fuzz.ratio(pa, ga) + fuzz.ratio(pb, gb)) / 2
        both = fuzz.ratio(pa + " " + pb, ga + " " + gb)
        # length imbalance: how many chars sit on the wrong page
        moved = abs(len(pa) - len(ga))
        rows.append((doc, a, b, own, both, moved, len(pa), len(ga), len(pb), len(gb)))
sp = [r for r in rows if r[4] - r[3] >= 12 and r[5] > 0.2 * max(r[7], 1) and r[5] > 300]
print(f"windows with 2 pages and reference text: {len(rows)}; spill-type windows (window text ok but split wrong): {len(sp)}")
print("by doc:", dict(collections.Counter(r[0][:8] for r in sp).most_common(8)))
for r in sorted(sp, key=lambda r: -(r[4] - r[3]))[:12]:
    print(f"  {r[0][:8]} p{r[1]}-{r[2]}  page-wise sim {r[3]:5.1f} -> window sim {r[4]:5.1f}   ours {r[6]}|{r[8]}  gt {r[7]}|{r[9]}")
json.dump([r[:3] for r in sp], open("runs/spill_windows_dev.json", "w"))

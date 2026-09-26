"""Offline test of a subject prior: pick among the 6 LLM candidate runs by length (longest / shortest) instead of the medoid.
Per-page official scores of each candidate run (pre-snap). Leave-one-document-out: the strategy for a doc is the one that is best on the
OTHER dev docs of the same subject (medoid if it has none)."""
import collections, glob, json, re, statistics as st
from rapidfuzz import fuzz
from compare_runs import load
NAMES = {"v6": "FINAL_v6", "v7": "FINAL_v7", "v8": "FINAL_v8", "v6c": "FINAL_v6c", "v7c": "FINAL_v7C", "v8c": "FINAL_v8c", "paddle": "PADDLE"}
FILES = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl", "paddle": "runs/paddle_dev.jsonl",
         "v6c": "runs/dev_all_v6c_final.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl", "v8c": "runs/dev_all_v8c_final.jsonl"}
S = {n: load(x) for n, x in NAMES.items()}
T = {n: {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(f, encoding="utf-8"))} for n, f in FILES.items()}
subj = {}
for p in glob.glob("data/dev/*/*/images/page_*.jpg"): subj[p.split("/")[3]] = p.split("/")[2]
ks = sorted(set.intersection(*[set(v) for v in S.values()])); nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]
alnum = lambda s: len(re.sub(r"[\W_]+", "", s)); LLM = ["v6", "v7", "v8", "v6c", "v7c", "v8c"]
def medoid(k, names):
    sc = {n: sum(fuzz.ratio(nz(T[n][k]), nz(T[m][k])) for m in names if m != n) for n in names}; return max(names, key=lambda n: (sc[n], n == "v7"))
def choose(k, strat):
    if strat == "medoid": return medoid(k, list(NAMES))
    L = sorted(LLM, key=lambda n: alnum(T[n][k]))
    return L[-1] if strat == "longest" else L[0] if strat == "shortest" else L[len(L) // 2]     # 'median' length
STR = ["medoid", "longest", "shortest", "median"]
sc = {s: {k: S[choose(k, s)][k]["overall"] for k in ks} for s in STR}
print("overall (pre-snap, 950 pages):", {s: round(st.mean(sc[s].values()), 2) for s in STR})
bydoc = collections.defaultdict(list)
for k in ks: bydoc[k.split("_")[0]].append(k)
docs_of = collections.defaultdict(list)
for d in bydoc: docs_of[subj[d]].append(d)
tot = collections.Counter(); n = 0; diffs = []
for d, pages in bydoc.items():
    sibs = [x for x in docs_of[subj[d]] if x != d]
    if sibs:
        best = max(STR, key=lambda s: st.mean(sc[s][k] for x in sibs for k in bydoc[x]))
    else: best = "medoid"
    for k in pages: diffs.append(sc[best][k] - sc["medoid"][k]); 
    tot["with_sibling_docs"] += bool(sibs) * len(pages); tot["changed_strategy"] += (best != "medoid") * len(pages)
print(f"leave-one-doc-out subject strategy vs medoid: mean {st.mean(diffs):+.3f} over all pages; pages using a non-medoid strategy: {tot['changed_strategy']} (of {tot['with_sibling_docs']} with sibling docs)")
ch = [x for x in diffs if x != 0]
if ch: print(f"   on the pages where the strategy differed: mean {st.mean(ch):+.2f} (n={len(ch)}), better on {sum(x>0.5 for x in ch)}, worse on {sum(x<-0.5 for x in ch)}")
print("best fixed strategy per subject on ALL dev docs (in-sample, optimistic):")
for s, ds in sorted(docs_of.items()):
    pg = [k for d in ds for k in bydoc[d]]
    if len(ds) >= 2: print(f"   {s:24s} docs {len(ds)} pages {len(pg):3d}  " + "  ".join(f"{t} {st.mean(sc[t][k] for k in pg):5.1f}" for t in STR))

import json, re, glob, random, statistics as st, collections, numpy as np
from PIL import Image
from rapidfuzz import fuzz
from compare_runs import load
A, B = load("FINAL_v7"), load("FINAL_v7C")
keys = sorted(set(A) & set(B))
# per-page contrast (SD of pixel values), same measure as the dev-vs-test comparison
con = {}
for p in glob.glob("data/dev/*/*/images/page_*.jpg"):
    doc = p.split("/")[3]; pg = int(p.split("page_")[1][:-4])
    im = Image.open(p).convert("L"); w, h = im.size; s = 800 / max(w, h)
    con[f"{doc}_{pg}.jpg"] = float(np.asarray(im.resize((max(1, int(w * s)), max(1, int(h * s)))), dtype=float).std())
rng = random.Random(0)
def ci(d):
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(4000)); return f"{st.mean(d):+.2f} [{bs[100]:+.2f}, {bs[3899]:+.2f}]"
print(f"pages scored in both: {len(keys)}; contrast SD dev median {st.median(con.values()):.1f} (test median was 25.8)")
groups = {"contrast SD < 25": lambda c: c < 25, "25 <= SD < 35": lambda c: 25 <= c < 35, "SD >= 35": lambda c: c >= 35, "ALL pages": lambda c: True}
for comp in ("overall", "text", "order"):
    print(f"\n{comp}: v7 + contrast preprocessing minus v7   (paired, 95% CI)")
    for name, f in groups.items():
        d = [B[k][comp] - A[k][comp] for k in keys if f(con.get(k, 99)) and A[k][comp] is not None and B[k][comp] is not None]
        if len(d) > 5: print(f"  {name:16s} pages {len(d):4d}  {ci(d)}   better on {sum(x>1 for x in d)}, worse on {sum(x<-1 for x in d)}")
# as an extra candidate in the medoid ensemble
S = {"v6": load("FINAL_v6"), "v7": A, "v8": load("FINAL_v8"), "paddle": load("PADDLE"), "v7c": B}
F = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl", "paddle": "runs/paddle_dev.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl"}
T = {n: {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(f))} for n, f in F.items()}
ks = sorted(set.intersection(*[set(S[n]) for n in S])); nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]
def med(names, k):
    sc = {n: sum(fuzz.ratio(nz(T[n][k]), nz(T[m][k])) for m in names if m != n) for n in names}; return max(names, key=lambda n: (sc[n], n == "v7"))
print("\nmedoid ensembles (mean overall, paired vs the 4-candidate ensemble):")
base = None
for names in (["v6", "v7", "v8", "paddle"], ["v6", "v7", "v8", "paddle", "v7c"], ["v7c", "v8", "paddle"], ["v6", "v7c", "v8", "paddle"]):
    ch = [med(names, k) for k in ks]; sc = [S[c][k]["overall"] for c, k in zip(ch, ks)]
    if base is None: base = sc
    print(f"  {'+'.join(names):28s} {st.mean(sc):6.2f}   vs 4-cand {ci([a - b for a, b in zip(sc, base)]) if sc is not base else '':>26s}   picks {dict(collections.Counter(ch))}")

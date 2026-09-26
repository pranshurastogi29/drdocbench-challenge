"""Compare a smoke-test run against our existing runs on the SAME pages (official per-page scores), and as an extra ensemble vote."""
import json, re, statistics as st, sys, random
from rapidfuzz import fuzz
from compare_runs import load
tag, name = sys.argv[1], sys.argv[2]
X = load(name); keys = sorted(k for k in X if X[k]["overall"] is not None)
ref = {"v6": "FINAL_v6", "v7": "FINAL_v7", "v8": "FINAL_v8", "v6c": "FINAL_v6c", "v7c": "FINAL_v7C", "v8c": "FINAL_v8c", "paddle": "PADDLE"}
R = {n: load(x) for n, x in ref.items()}; keys = [k for k in keys if all(k in R[n] and R[n][k]["overall"] is not None for n in R)]
print(f"{tag}: {len(keys)} pages scored in every run")
rng = random.Random(0)
def ci(d):
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(3000)); return f"{st.mean(d):+.2f} [{bs[75]:+.2f}, {bs[2924]:+.2f}]"
print(f"  {tag:8s} overall {st.mean(X[k]['overall'] for k in keys):5.2f}  text {st.mean(X[k]['text'] for k in keys if X[k]['text'] is not None):5.2f}  order {st.mean(X[k]['order'] for k in keys if X[k]['order'] is not None):5.2f}")
for n in R:
    d = [X[k]["overall"] - R[n][k]["overall"] for k in keys]
    print(f"  {n:8s} overall {st.mean(R[n][k]['overall'] for k in keys):5.2f}   {tag} minus {n}: {ci(d)}")
# medoid ensemble with and without the new run as an extra vote (pre-snap, these pages only)
F = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl", "paddle": "runs/paddle_dev.jsonl", "v6c": "runs/dev_all_v6c_final.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl", "v8c": "runs/dev_all_v8c_final.jsonl"}
T = {n: {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(f, encoding="utf-8"))} for n, f in F.items()}
T[tag] = {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(f"runs/dev_all_{tag}.jsonl", encoding="utf-8"))}
S = dict(R); S[tag] = X; nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]
def med(names, k):
    sc = {n: sum(fuzz.ratio(nz(T[n][k]), nz(T[m][k])) for m in names if m != n) for n in names}; return max(names, key=lambda n: (sc[n], n == "v7"))
base = list(F); plus = base + [tag]
a = [S[med(base, k)][k]["overall"] for k in keys]; b = [S[med(plus, k)][k]["overall"] for k in keys]
print(f"  7-candidate medoid {st.mean(a):5.2f}  |  + {tag} as 8th vote {st.mean(b):5.2f}   difference {ci([y - x for x, y in zip(a, b)])}   ({tag} picked on {sum(med(plus,k)==tag for k in keys)} pages)")

"""Does a Flash vote lift the 7-candidate medoid? Full dev, official per-page scores (pre-snap); pages Flash lacks use the base candidates."""
import collections, json, random, re, statistics as st
from rapidfuzz import fuzz
from compare_runs import load
NAMES = {"v6": "FINAL_v6", "v7": "FINAL_v7", "v8": "FINAL_v8", "paddle": "PADDLE", "v6c": "FINAL_v6c", "v7c": "FINAL_v7C", "v8c": "FINAL_v8c", "flash": "FINAL_flash"}
FILES = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl", "paddle": "runs/paddle_dev.jsonl",
         "v6c": "runs/dev_all_v6c_final.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl", "v8c": "runs/dev_all_v8c_final.jsonl", "flash": "runs/dev_all_flash_final.jsonl"}
S = {n: load(x) for n, x in NAMES.items()}
T = {n: {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(f, encoding="utf-8"))} for n, f in FILES.items()}
base = ["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"]
ks = sorted(k for k in S["v7"] if all(k in S[n] and S[n][k]["overall"] is not None for n in base))
nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]; rng = random.Random(0)
def ci(d):
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(4000)); return f"{st.mean(d):+.2f} [{bs[100]:+.2f}, {bs[3899]:+.2f}]"
def med(names, k):
    names = [n for n in names if k in T[n] and k in S[n] and S[n][k]["overall"] is not None or (n in base and k in T[n])]
    sc = {n: sum(fuzz.ratio(nz(T[n][k]), nz(T[m][k])) for m in names if m != n) for n in names}; return max(names, key=lambda n: (sc[n], n == "v7"))
def score(k, n): return S[n][k]["overall"] if k in S[n] and S[n][k]["overall"] is not None else None
res = {}
for label, names in (("7 candidates (final7 pool)", base), ("+ flash", base + ["flash"]), ("flash replaces paddle", [n for n in base if n != "paddle"] + ["flash"]), ("6 LLM runs only (no paddle, no flash)", [n for n in base if n != "paddle"])):
    ch = {k: med(names, k) for k in ks}
    sc = {k: (score(k, ch[k]) if score(k, ch[k]) is not None else S["v7"][k]["overall"]) for k in ks}   # a chosen run whose page was not scored falls back to v7's score
    res[label] = sc
b = res["7 candidates (final7 pool)"]
print(f"{len(ks)} pages; flash has output on {sum(k in T['flash'] for k in ks)}")
for label, sc in res.items():
    d = [sc[k] - b[k] for k in ks]; picks = None
    print(f"  {label:38s} {st.mean(sc.values()):6.2f}   vs final7 pool {ci(d) if any(d) else '   0.00':>24s}")
ch = {k: med(base + ["flash"], k) for k in ks}; print("  picks with flash:", dict(collections.Counter(ch.values())))

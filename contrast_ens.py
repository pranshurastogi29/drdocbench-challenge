"""Medoid ensembles that include the contrast-processed candidates (dev, official per-page scores, pre-snap).

  python contrast_ens.py     -> paired vs the 5-candidate ensemble that was submitted as final5 (leaderboard 78.66)
"""
import collections, json, random, re, statistics as st
from rapidfuzz import fuzz
from compare_runs import load

NAMES = {"v6": "FINAL_v6", "v7": "FINAL_v7", "v8": "FINAL_v8", "paddle": "PADDLE",
         "v6c": "FINAL_v6c", "v7c": "FINAL_v7C", "v8c": "FINAL_v8c"}
FILES = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl",
         "paddle": "runs/paddle_dev.jsonl", "v6c": "runs/dev_all_v6c_final.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl",
         "v8c": "runs/dev_all_v8c_final.jsonl"}
S = {n: load(x) for n, x in NAMES.items()}
T = {n: {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(f, encoding="utf-8"))} for n, f in FILES.items()}
ks = sorted(set.intersection(*[set(v) for v in S.values()]))
nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]
rng = random.Random(0)


def ci(d):
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(4000))
    return f"{st.mean(d):+.2f} [{bs[100]:+.2f}, {bs[3899]:+.2f}]"


def med(names, k):
    sc = {n: sum(fuzz.ratio(nz(T[n][k]), nz(T[m][k])) for m in names if m != n) for n in names}
    return max(names, key=lambda n: (sc[n], n == "v7"))


SETS = [["v6", "v7", "v8", "paddle", "v7c"],            # final5 (submitted)
        ["v6", "v7", "v8", "paddle"],
        ["v6c", "v7c", "v8c", "paddle"],
        ["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"],
        ["v6", "v7", "v8", "v6c", "v7c", "v8c"],
        ["v6c", "v7c", "v8c", "paddle", "v7"],
        ["v6", "v6c", "v7c", "v8c", "paddle"],
        ["v6c", "v8c", "paddle", "v7c", "v7", "v8"]]
if __name__ == "__main__":
    print(f"pages scored in every candidate: {len(ks)}")
    base = None
    for names in SETS:
        ch = [med(names, k) for k in ks]
        sc = [S[c][k]["overall"] for c, k in zip(ch, ks)]
        base = base or sc
        print(f"{'+'.join(names):36s} {st.mean(sc):6.2f}  vs final5 {ci([a - b for a, b in zip(sc, base)]):>24s}  picks {dict(collections.Counter(ch))}")

"""Re-read the last ablation (runs/ablate_last.json) against any of its variants instead of the 82.88 stack:
text, order and leaderboard-weighted text+order gain (0.558 text + 0.433 order) per variant, book-clustered bootstrap, pages better/worse.
  python ablate_vs.py "mbr8 base"
"""
import collections, json, os, random, statistics as st, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(ROOT, "runs", "ablate_last.json"))); ref = sys.argv[1]
names = list(next(iter(S.values())))
ok = [k for k, v in S.items() if all(v.get(n) and v[n][0] is not None and v[n][1] is not None for n in names)]
U = lambda r: 0.558 * r[0] + 0.433 * r[1]
print(f"{len(ok)} dev pages; reference variant: {ref}")
for n in names:
    by = collections.defaultdict(list)
    for k in ok: by[k.rsplit("_", 1)[0]].append(U(S[k][n]) - U(S[k][ref]))
    bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
    bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv]
    t = st.mean(S[k][n][0] for k in ok); o = st.mean(S[k][n][1] for k in ok)
    print(f"  {n:16s} Text_ED {1 - t / 100:.4f}  RO {o:6.2f}  vs {ref}: {m(bk):+.3f} [{bt[50]:+.3f},{bt[1949]:+.3f}]  pages {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)}")

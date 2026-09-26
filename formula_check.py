"""Formula-convention test: compare a run against v7 on the pages whose reference has display 'formulas'.
  python formula_check.py FINAL_v9      (uses the official scorer's display_formula results + per-page components)"""
import json, re, sys, random, statistics as st, collections
from compare_runs import load
res = "scorer/result/drdoc_%s_%s.json"
new = sys.argv[1]; old = "FINAL_v7"
fix = lambda k: k if k.endswith(".jpg") else k + ".jpg"
def fed(n): return {fix(k): v for k, v in json.load(open(res % (n, "display_formula_per_page_edit"))).items()}
def ents(n):
    d = collections.defaultdict(list)
    for x in json.load(open(res % (n, "display_formula_result"))): d[fix(x["img_id"])].append(x)
    return d
A, B = fed(old), fed(new); common = sorted(set(A) & set(B))
wrap = lambda g: bool(re.match(r"\$\s*\\text(bf|it)\{", g.strip()))
EA, EB = ents(old), ents(new)
wp = [k for k in common if any(e["gt"] and wrap(e["gt"]) for e in EA[k])]
rp = [k for k in common if k not in wp]
print(f"pages whose reference has a display formula: {len(common)}  (\\textbf/\\textit wrapper pages: {len(wp)}, real-math pages: {len(rp)})")
for label, ks in (("wrapper pages", wp), ("real-math pages", rp), ("all formula pages", common)):
    a = [A[k] for k in ks]; b = [B[k] for k in ks]
    print(f"  {label:18s} mean formula edit  v7 {st.mean(a):.3f} -> {new} {st.mean(b):.3f}   pages matched (edit<0.5): {sum(x<0.5 for x in a)} -> {sum(x<0.5 for x in b)}   pages with nothing matched: {sum(x>=0.99 for x in a)} -> {sum(x>=0.99 for x in b)}")
# leaderboard-style overall with a formula component, proxy CDM = 100*(1-edit) on formula pages
SA, SB = load(old), load(new); keys = sorted(set(SA) & set(SB))
def adj(S, F, k):
    comps = [c for c in (S[k]["text"], S[k]["order"], S[k]["teds"]) if c is not None]
    if k in F: comps.append(100 * (1 - F[k]))
    return sum(comps) / len(comps)
d0 = [SB[k]["overall"] - SA[k]["overall"] for k in keys]
d1 = [adj(SB, B, k) - adj(SA, A, k) for k in keys]
rng = random.Random(0)
def ci(d):
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(5000)); return f"{st.mean(d):+.2f} [{bs[125]:+.2f}, {bs[4874]:+.2f}]"
print(f"\npaired overall, WITHOUT formula component ({new} minus v7, {len(keys)} pages): {ci(d0)}")
print(f"paired overall, WITH proxy formula component (100*(1-edit) on formula pages):  {ci(d1)}")
print(f"  mean overall with proxy formula component: v7 {st.mean(adj(SA, A, k) for k in keys):.2f}  {new} {st.mean(adj(SB, B, k) for k in keys):.2f}")
for c in ("text", "order"):
    d = [SB[k][c] - SA[k][c] for k in keys if SA[k][c] is not None and SB[k][c] is not None]; print(f"  {c:6s} component paired: {ci(d)}")

import json, re, random, statistics as st, collections, numpy as np
from rapidfuzz import fuzz
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from compare_runs import load
from difficulty import page_features, FEATS, nz
from postprocess import strip_sections

names = ["v6", "v7", "v8", "paddle"]
def medoid(texts):
    sc = {n: sum(fuzz.ratio(nz(texts[n]), nz(texts[m])) for m in names if m != n) for n in names}
    return max(names, key=lambda n: (sc[n], n == "v7"))
def rd(p, key):
    return {key(r): r for r in map(json.loads, open(p))}
# ---------------- dev
S = {"v6": load("FINAL_v6"), "v7": load("FINAL_v7"), "v8": load("FINAL_v8"), "paddle": load("PADDLE")}
DF = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl", "paddle": "runs/paddle_dev.jsonl"}
D = {n: rd(f, lambda r: f"{r['document_id']}_{r['page']}.jpg") for n, f in DF.items()}
keys = sorted(set.intersection(*[set(S[n]) for n in S]))
X, y, g = [], [], []
for k in keys:
    stem = k[:-4]; texts = {n: D[n][k]["markdown"] for n in names}; pk = medoid(texts)
    f = page_features(stem, texts, pk, texts["paddle"]); X.append([f[c] for c in FEATS]); y.append(S[pk][k]["overall"]); g.append(stem.rsplit("_", 1)[0])
X, y, g = np.array(X), np.array(y), np.array(g)
# ---------------- test
TF = {"v6": "runs/test_all_v6.jsonl", "v7": "runs/test_all_v7_clean.jsonl", "v8": "runs/test_all_v8.jsonl", "paddle": "runs/paddle_test.jsonl"}
Tt = {n: rd(f, lambda r: (r["document_id"], r["page"])) for n, f in TF.items()}
Xt, tdoc, blank = [], [], []
for k in Tt["v7"]:
    stem = f"{k[0]}_{k[1]}"; texts = {n: strip_sections(Tt[n][k]["markdown"]).strip() for n in names}; pk = medoid(texts)
    f = page_features(stem, texts, pk, texts["paddle"]); Xt.append([f[c] for c in FEATS]); tdoc.append(k[0]); blank.append(not texts[pk] and not texts["paddle"])
Xt, tdoc, blank = np.array(Xt), np.array(tdoc), np.array(blank)
print(f"dev pages {len(y)} in {len(set(g))} docs | test pages {len(Xt)} in {len(set(tdoc))} docs | test pages blank in candidate AND paddle: {blank.sum()}")
# ---------------- feature distributions
print("\nfeature means   dev     test")
for i, c in enumerate(FEATS):
    if c in ("agree", "sim_paddle", "len_ratio", "paras", "paddle_blocks", "p_table", "p_image", "img_area", "has_table", "empty", "paddle_empty", "min_sim"):
        print(f"  {c:14s} {X[:, i].mean():7.2f} {Xt[~blank][:, i].mean():7.2f}")
# ---------------- grouped CV
mk = lambda: GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=0.04, subsample=0.8, random_state=0)
oof = np.zeros(len(y))
for tr, te in GroupKFold(n_splits=6).split(X, y, g):
    oof[te] = mk().fit(X[tr], y[tr]).predict(X[te])
r = np.corrcoef(oof, y)[0, 1]; base = np.mean((y - y.mean()) ** 2); mse = np.mean((y - oof) ** 2)
print(f"\nheld-out-document CV: page-level corr {r:.2f}, R^2 {1 - mse / base:.2f}; mean predicted {oof.mean():.2f} vs actual {y.mean():.2f}")
docs = sorted(set(g)); am = np.array([y[g == d].mean() for d in docs]); pm = np.array([oof[g == d].mean() for d in docs])
print(f"document-level corr (predicted vs actual doc mean): {np.corrcoef(am, pm)[0, 1]:.2f}; doc-level RMSE {np.sqrt(np.mean((am - pm) ** 2)):.1f} (a naive constant guess has RMSE {am.std():.1f})")
# ---------------- predict test
pred = np.mean([mk().set_params(random_state=s).fit(X, y).predict(Xt) for s in range(5)], axis=0)
print(f"\nPREDICTED test mean overall for the 4-candidate ensemble: {pred[~blank].mean():.1f}   (dev actual {y.mean():.1f}; dev CV-predicted {oof.mean():.1f})")
# uncertainty: bootstrap 34-document sets from dev out-of-fold residuals (model error) + doc sampling
rng = random.Random(0); res = {d: (y[g == d] - oof[g == d]) for d in docs}
sims = []
for _ in range(5000):
    pick = rng.choices(docs, k=34); r_ = np.concatenate([res[d] for d in pick]); sims.append(r_.mean())
sims = sorted(sims); print(f"prediction error over a random 34-doc set (from held-out residuals): 5th {sims[250]:+.1f}, 95th {sims[4750]:+.1f} points")
# per-document view of test
td = {d: pred[(tdoc == d) & ~blank].mean() for d in sorted(set(tdoc)) if ((tdoc == d) & ~blank).any()}
v = sorted(td.values()); print(f"test docs: predicted per-doc mean: min {v[0]:.0f}, median {v[len(v)//2]:.0f}, max {v[-1]:.0f} (dev docs actual: min {am.min():.0f}, median {np.median(am):.0f}, max {am.max():.0f})")
json.dump({"pred_mean": float(pred[~blank].mean()), "dev_mean": float(y.mean())}, open("runs/predicted_test.json", "w"))

"""Selection experiments on runs/selcache_dev.json (sel_cache.py): how close can a label-free selector get to the oracle?
Every learned selector is cross-validated by book (GroupKFold): the pages it is scored on come from books it never saw.
Score unit = leaderboard units per page: 0.558 * text + 0.433 * order (both 0-100).
  python sel_lab.py
"""
import collections, json, os, random, re, statistics as st, sys
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from build_submission import medoid
BASE5 = ["v6", "v7", "v8", "paddle", "v7c"]
FREE = BASE5 + ["v6c", "v8c", "v7s", "v6w1", "v7w1", "v8w1"]
U = lambda t: 0.558 * t[0] + 0.433 * t[1]
SEGF = False
NW = lambda s: len(re.sub(r"[\W_]", "", s))


def load():
    C = json.load(open(os.path.join(ROOT, "runs", "selcache_dev.json")))
    return {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}


def mbr_scores(v, pool, key="pw_raw", wt=(0.558, 0.433), refw=None, agg=st.mean):
    out = {}
    for i in pool:
        us = [(wt[0] * v[key][i][j][0] + wt[1] * v[key][i][j][1], (refw or {}).get(j, 1.0)) for j in pool if j != i and v[key][i][j]]
        out[i] = sum(u * w for u, w in us) / sum(w for _, w in us) if agg is st.mean and us else (agg([u for u, _ in us]) if us else -1)
    return out


def pick_mbr(v, pool, **kw):
    s = mbr_scores(v, pool, **kw); return max(pool, key=lambda n: (s[n], n == "v7"))


def features(v, pool):
    """one row per candidate; only label-free quantities"""
    rows = []
    L = {n: NW(v["raw"][n]) for n in pool}; P = {n: len([p for p in re.split(r"\n\s*\n", v["proc"][n]) if p.strip()]) for n in pool}
    medL = st.median(L.values()) or 1; medP = st.median(P.values()) or 1
    sr = mbr_scores(v, pool, "pw_raw"); sp = mbr_scores(v, pool, "pw_proc")
    st_ = mbr_scores(v, pool, "pw_proc", wt=(1, 0)); so = mbr_scores(v, pool, "pw_proc", wt=(0, 1))
    asref = {i: st.mean([U(v["pw_proc"][j][i]) for j in pool if j != i and v["pw_proc"][j][i]] or [0]) for i in pool}
    rk = {n: r for r, n in enumerate(sorted(pool, key=lambda n: -sp[n]))}
    pagemean = st.mean(sp.values())
    for n in pool:
        f = [sr[n], sp[n], st_[n], so[n], asref[n], sp[n] - pagemean, rk[n], L[n] / medL, P[n] / medP, L[n], P[n], pagemean,
             U(v["pw_proc"][n]["paddle"]) if n != "paddle" and v["pw_proc"][n].get("paddle") else -1,
             v["raw"][n].count("<table"), v["raw"][n].count("$"), v["raw"][n].count("\n") / max(1, P[n])]
        if SEGF:   # segmentation: relative to Paddle's image-layout blocks, and how list-like (short one-line paragraphs) the page is written
            ps = [q for q in re.split(r"\n\s*\n", v["proc"][n]) if q.strip()]
            f += [P[n] / max(1, P["paddle"]) if "paddle" in P else 1, np.log((P[n] + 1) / (P.get("paddle", P[n]) + 1)),
                  sum(1 for q in ps if "\n" not in q.strip() and NW(q) < 60) / max(1, len(ps)), P[n] / max(1, min(P.values())), P[n] / max(1, max(P.values()))]
        f += [1.0 if n == m else 0.0 for m in pool]
        rows.append(f)
    return np.array(rows)


def evaluate(C, picks, base):
    """picks/base: {stem: candidate}; book-clustered bootstrap of the per-page gain"""
    by = collections.defaultdict(list)
    for k in picks:
        by[k.rsplit("_", 1)[0]].append(U(C[k]["gt"][picks[k]]) - U(C[k]["gt"][base[k]]))
    books = list(by); rng = random.Random(0)
    m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
    bt = sorted(m(rng.choices(books, k=len(books))) for _ in range(2000))
    return m(books), bt[50], bt[1949], sum(st.mean(x) > 0 for x in by.values()), sum(st.mean(x) < 0 for x in by.values())


def learned(C, pool, model="hgb", target="rel", folds=5, seed=0):
    from sklearn.model_selection import GroupKFold
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    keys = sorted(C); groups = [k.rsplit("_", 1)[0] for k in keys]
    X = {k: features(C[k], pool) for k in keys}
    Y = {}
    for k in keys:
        y = np.array([U(C[k]["gt"][n]) for n in pool]); Y[k] = y - y.mean() if target == "rel" else y
    picks = {}
    for tr, te in GroupKFold(folds).split(keys, groups=groups):
        Xtr = np.vstack([X[keys[i]] for i in tr]); ytr = np.concatenate([Y[keys[i]] for i in tr])
        m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0, random_state=seed) if model == "hgb" else Ridge(1.0)
        m.fit(Xtr, ytr)
        for i in te:
            k = keys[i]; p = m.predict(X[k]); picks[k] = pool[int(np.argmax(p))]
    return picks


def weighted_mbr_cv(C, pool, folds=5):
    """per-reference weights (how much each run is trusted as a pseudo-reference), fit by coordinate search on training books"""
    from sklearn.model_selection import GroupKFold
    keys = sorted(C); groups = [k.rsplit("_", 1)[0] for k in keys]; picks = {}; grid = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
    A = {k: np.array([[U(C[k]["pw_proc"][i][j]) if i != j and C[k]["pw_proc"][i][j] else 0.0 for j in pool] for i in pool]) for k in keys}
    G = {k: np.array([U(C[k]["gt"][n]) for n in pool]) for k in keys}
    def choose(k, w):
        den = w.sum() - w
        sc = np.where(den > 0, (A[k] @ w) / np.where(den > 0, den, 1), -1)
        return int(np.argmax(sc))
    for tr, te in GroupKFold(folds).split(keys, groups=groups):
        trk = [keys[i] for i in tr]; w = np.ones(len(pool))
        score = lambda w: sum(G[k][choose(k, w)] for k in trk)
        best = score(w)
        for _ in range(2):
            for n in range(len(pool)):
                for g in grid:
                    w2 = w.copy(); w2[n] = g
                    if w2.sum() == 0: continue
                    s_ = score(w2)
                    if s_ > best + 1e-9: best, w = s_, w2
        for i in te: picks[keys[i]] = pool[choose(keys[i], w)]
    return picks, dict(zip(pool, w.tolist()))


if __name__ == "__main__":
    C = load(); keys = sorted(C)
    print(f"{len(keys)} dev pages, {len({k.rsplit('_', 1)[0] for k in keys})} books (unit: leaderboard points per page, 0.558 text + 0.433 order)")
    base = {k: medoid(C[k]["raw"], BASE5) for k in keys}
    mean = lambda P: st.mean(U(C[k]["gt"][P[k]]) for k in keys)
    rows = []
    def rep(name, P):
        g, lo, hi, b, w = evaluate(C, P, base); rows.append((name, mean(P), g, lo, hi, b, w))
        print(f"{name:40s} {mean(P):6.2f}  vs medoid5 {g:+5.2f} [{lo:+.2f},{hi:+.2f}]  books {b}/{w}", flush=True)
    rep("medoid5 (final5)", base)
    for pn, pool in (("base5", BASE5), ("free11", FREE)):
        rep(f"oracle {pn}", {k: max(pool, key=lambda n: U(C[k]["gt"][n])) for k in keys})
        rep(f"mbr raw {pn} (final5m)", {k: pick_mbr(C[k], pool) for k in keys})
        rep(f"mbr processed {pn}", {k: pick_mbr(C[k], pool, key="pw_proc") for k in keys})
        rep(f"mbr processed {pn}, median", {k: pick_mbr(C[k], pool, key="pw_proc", agg=st.median) for k in keys})
        for wt in ((1, 0), (0, 1), (0.558, 0.866)):
            rep(f"mbr processed {pn}, weights {wt}", {k: pick_mbr(C[k], pool, key="pw_proc", wt=wt) for k in keys})
        P, w = weighted_mbr_cv(C, pool); rep(f"weighted mbr {pn} (CV)", P); print("    last-fold weights", w)
        for model in ("ridge", "hgb"):
            rep(f"learned {model} {pn} (CV by book)", learned(C, pool, model))

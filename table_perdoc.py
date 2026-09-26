import collections, statistics as st, sys
from table_lab import gt_tables, load_pred, score, TAB
if __name__ == "__main__":
    G = gt_tables(); P = load_pred(sys.argv[1])
    m, flat = score(P, G=G)
    owner = []
    for page, g in G.items():
        if page in P and TAB.findall(P[page]): owner += [page.split("_")[0][:8]] * len(g)
    d = collections.defaultdict(list)
    for o, f in zip(owner, flat): d[o].append(f)
    tot = sum(1 - f for f in flat)
    print("mean", round(m, 2), "n", len(flat), "docs", len(d), "owner-len", len(owner))
    for o, v in sorted(d.items(), key=lambda kv: -sum(1 - x for x in kv[1]))[:8]:
        print(f"{o} tables {len(v):3d} TEDS {100*st.mean(v):5.1f} share of loss {sum(1-x for x in v)/tot:.2f}")

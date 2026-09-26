"""Per-table paired comparison of table variants against the final5 baseline, with bootstrap CI (dev)."""
import random, statistics as st, sys
from table_lab import gt_tables, load_pred, score
from table_merge import load_crops, merge
from table_vote import vote_page
APPEND = True
if __name__ == "__main__":
    import os; APPEND = {'1': True, '0': False, 'place': 'place'}[os.environ.get('APPEND','1')]
    G = gt_tables(); P = load_pred("runs/dev_all_final5.jsonl")
    _, base = score(P, G=G)
    sets = []
    for f in sys.argv[1:]:
        C = load_crops(f); sets.append({s: {i: t for i, t in v} for s, v in C.items()})
    stems = set().union(*[set(s) for s in sets])
    rng = random.Random(0)
    def ci(d):
        bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(4000)); return f"{100*st.mean(d):+.2f} [{100*bs[100]:+.2f}, {100*bs[3899]:+.2f}]"
    for name, idx, pad in [("t1 alone", [0], False), ("t2 alone", [1], False), ("t1+t2+paddle", [0, 1], True)] + ([("t1+t2+t3+paddle", [0, 1, 2], True), ("t1+t3+paddle", [0, 2], True), ("t1+t2+t3", [0, 1, 2], False)] if len(sets) > 2 else []):
        cs = [sets[i] for i in idx]
        PP = {k: (vote_page(k, v, [s.get(k, {}) for s in cs], {}, pad, APPEND) if k in stems else v) for k, v in P.items()}
        m, flat = score(PP, G=G)
        print(f"{name:18s} {m:6.2f}   paired vs baseline {ci([a - b for a, b in zip(flat, base)])}", flush=True)

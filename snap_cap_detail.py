from compare_runs import load
A, B = load("DEVR_final5"), load("SNAP_cap20")
d = [(B[k]["overall"] - A[k]["overall"], k, A[k]["overall"], B[k]["overall"]) for k in A if k in B and A[k]["overall"] is not None and B[k]["overall"] is not None]
d = [x for x in d if abs(x[0]) > 0.05]
d.sort()
for delta, k, a, b in d:
    print(f"  {delta:+7.1f}  {k[:8]}_{k.split('_')[1]:6s}  {a:6.1f} -> {b:6.1f}")

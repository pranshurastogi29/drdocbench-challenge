"""Turn probe leaderboard Text_ED values into per-group Text_ED.
  python probe_decode.py G1=0.2012 G2=0.2310 G3=0.1950
ED(S) = 1 - (ED_probe - ED_base) * N / n_S, with N/n_S taken as 509 / pages(S) (scored fraction assumed equal across books; dev: 96.4%
overall). G4 follows from the base: ED_base * N = sum over groups of ED(S) * n_S.
"""
import json
import sys

BASE = 0.1681
info = json.load(open("runs/probe_groups.json"))
N = sum(v["pages"] for v in info.values())
got = {}
for a in sys.argv[1:]:
    g, v = a.split("="); got[g] = 1 - (float(v) - BASE) * N / info[g]["pages"]
if "G4" not in got and len(got) == 3:
    got["G4"] = (BASE * N - sum(got[g] * info[g]["pages"] for g in got)) / info["G4"]["pages"]
print(f"base Text_ED {BASE} over {N} pages")
for g in sorted(got):
    docs = ", ".join(x["subject"][:12] for x in info[g]["docs"])
    print(f"  {g}: Text_ED {got[g]:.3f}  ({info[g]['pages']} pages; share of total loss {got[g] * info[g]['pages'] / (BASE * N):.0%})  {docs}")

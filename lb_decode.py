"""Decode any leaderboard A/B: the per-changed-page effect of a variant upload against its base upload (generalises ab_decode.py,
which is tied to final5_wd and the probe groups). The leaderboard averages pages, so a change confined to n_S of the 509 pages moves
each metric by (its change on those pages) * n_S / 509:
  dText_ED(S) = (ED_var - ED_base) * 509 / n_S,   dRO(S) = (RO_var - RO_base) * 509 / n_S
(assumes the changed pages are scored like the rest; leaderboard resolution 0.0001 Text_ED and 0.01 RO).
Also checks the fitted overall formula 0.558 Text + 0.433 RO + 0.054 CDM + 0.006 TEDS - 3.9 against the actual overall delta.
  python lb_decode.py --base "0.1689,71.86,76.54,84.91,83.53" --var "0.1650,71.86,76.54,85.40,83.95" --pages submissions/x.pages.json|N
  (values in leaderboard order: Text_ED, Table_TEDS, Formula_CDM, Reading_Order, Overall)
"""
import argparse, json

F = lambda ed, teds, cdm, ro: 0.558 * 100 * (1 - ed) + 0.433 * ro + 0.054 * cdm + 0.006 * teds - 3.9

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--var", required=True); ap.add_argument("--pages", required=True); a = ap.parse_args()
    b = [float(x) for x in a.base.split(",")]; v = [float(x) for x in a.var.split(",")]
    n = int(a.pages) if a.pages.isdigit() else len(json.load(open(a.pages))["changed"])
    d = [y - x for x, y in zip(b, v)]; k = 509 / n
    pred = F(v[0], v[1], v[2], v[3]) - F(b[0], b[1], b[2], b[3])
    print(f"{n} changed pages (x{k:.1f} scale)")
    print(f"  leaderboard deltas: Text_ED {d[0]:+.4f}  TEDS {d[1]:+.2f}  CDM {d[2]:+.2f}  RO {d[3]:+.2f}  Overall {d[4]:+.2f}")
    print(f"  on the changed pages: Text_ED {d[0] * k:+.4f} (text points {-100 * d[0] * k:+.2f})  RO {d[3] * k:+.2f}  (resolution +-{0.0001 * k:.4f} / +-{0.01 * k:.2f})")
    print(f"  overall: formula predicts {pred:+.2f}, actual {d[4]:+.2f}, residual {d[4] - pred:+.2f}" + ("  <- check: evaluation change?" if abs(d[4] - pred) > 0.1 else ""))
    print(f"  split: text {0.558 * -100 * d[0]:+.2f}, order {0.433 * d[3]:+.2f}, CDM {0.054 * d[2]:+.2f}, TEDS {0.006 * d[1]:+.2f}")

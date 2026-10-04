"""Decode a per-group A/B upload (ab_group.py): final5_wd with ONE probe group's pages replaced.
  python ab_decode.py G2 --text-ed 0.xxxx --order xx.xx [--overall xx.xx]
Group baselines come from the blanking probes (probe_G*.zip): ED_G = 1 - (ED_probe - 0.1681) * 509 / n_G ;  RO_G = (82.85 - RO_probe) * 509 / n_G.
New group value = baseline + (new overall metric - final5_wd metric) * 509 / n_G  (all other pages are unchanged).
"""
import argparse, json
BASE = {"text": 0.1681, "order": 82.85, "overall": 81.59}
PROBE = {"G1": (0.3568, None), "G2": (0.3560, 63.82), "G3": (0.3901, None)}      # blanked-group probes: (Text_ED, Reading_Order)
ap = argparse.ArgumentParser(); ap.add_argument("group"); ap.add_argument("--text-ed", type=float, required=True)
ap.add_argument("--order", type=float, required=True); ap.add_argument("--overall", type=float)
a = ap.parse_args()
info = json.load(open("runs/probe_groups.json"))[a.group]; n = info["pages"]; N = 509
ed0 = 1 - (PROBE[a.group][0] - BASE["text"]) * N / n
ro0 = (BASE["order"] - PROBE[a.group][1]) * N / n if PROBE[a.group][1] else None
ed1 = ed0 + (a.text_ed - BASE["text"]) * N / n
print(f"{a.group} ({n} pages): Text_ED {ed0:.3f} -> {ed1:.3f}  ({ed1 - ed0:+.3f}; precision about +-{0.0001 * N / n:.4f})")
if ro0 is not None:
    ro1 = ro0 + (a.order - BASE["order"]) * N / n
    print(f"{a.group}: Reading_Order {ro0:.1f} -> {ro1:.1f}  ({ro1 - ro0:+.1f})")
print(f"whole-test effect: Text_ED {a.text_ed - BASE['text']:+.4f}, Reading_Order {a.order - BASE['order']:+.2f}" + (f", Overall {a.overall - BASE['overall']:+.2f}" if a.overall else ""))
gain = -0.558 * 100 * (a.text_ed - BASE["text"]) + 0.433 * (a.order - BASE["order"])
print(f"formula-predicted Overall change from text + order: {gain:+.2f}")

"""Dev check of the position signal: do paragraphs the scorer leaves unmatched ("extra") sit inside picture regions, and matched ones
outside? Prints separation for reference figure boxes (upper bound), Paddle picture boxes, and captioned Paddle pictures, then writes
dev files that drop Paddle-absent paragraphs by each position rule, for scoring.

  python picpos_eval.py
"""
import json
import os

from rapidfuzz import fuzz

from paradrop import labels, paras, wn
from picpos import ocr, page_positions

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    lab = labels("DEVR_final5")
    src = {f'{r["document_id"]}_{r["page"]}': r for r in map(json.loads, open(os.path.join(ROOT, "runs/dev_all_rebuilt_final5.jsonl")))}
    pad = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, "runs/paddle_dev.jsonl")))}
    O = ocr(); rows = []
    for stem, r in src.items():
        if stem not in O or O[stem]["split"] != "dev":
            continue
        P = paras(r["markdown"]); pos = page_positions(r["markdown"], stem); p = wn(pad.get(stem, ""))
        ex, ma = lab.get(stem, ("", ""))
        for i, d in pos.items():
            w = wn(P[i]); pm = fuzz.partial_ratio(w[:200], p) if p else 0
            t = "extra" if (w in ex and w not in ma) else "matched" if (w in ma and w not in ex) else "ambig"
            rows.append(dict(stem=stem, i=i, pm=pm, label=t, chars=len(w), **d))
    cand = [x for x in rows if x["pm"] < 60]
    print(f"located paragraphs {len(rows)}; Paddle-absent (pm<60) {len(cand)}: "
          f"extra {sum(x['label'] == 'extra' for x in cand)}, matched {sum(x['label'] == 'matched' for x in cand)}, ambig {sum(x['label'] == 'ambig' for x in cand)}")
    for key in ("in_gt_fig", "in_pic", "in_capped_pic"):
        print(f"\n{key}:")
        for th in (0.3, 0.5, 0.7, 0.9):
            sel = [x for x in cand if (x[key] or 0) >= th]
            e = sum(x["label"] == "extra" for x in sel); m = sum(x["label"] == "matched" for x in sel)
            ce = sum(x["chars"] for x in sel if x["label"] == "extra"); cm = sum(x["chars"] for x in sel if x["label"] == "matched")
            print(f"  >= {th}: selected {len(sel)}  extra {e} ({ce} ch)  matched {m} ({cm} ch)  precision {e / max(e + m, 1):.2f}")
    json.dump(rows, open(os.path.join(ROOT, "runs/picpos_dev_rows.json"), "w"))
    # dev files to score: drop Paddle-absent paragraphs located inside picture regions
    for key, th, name in (("in_pic", 0.5, "pp_pic50"), ("in_capped_pic", 0.5, "pp_cap50"), ("in_gt_fig", 0.5, "pp_gt50")):
        dropset = {(x["stem"], x["i"]) for x in cand if (x[key] or 0) >= th}
        n = 0
        with open(os.path.join(ROOT, f"runs/dev_all_{name}.jsonl"), "w") as f:
            for stem, r in src.items():
                P = paras(r["markdown"]); keep = [q for i, q in enumerate(P) if (stem, i) not in dropset]
                md = "\n\n".join(keep) if keep else r["markdown"]; n += md != r["markdown"]
                f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
        print(f"runs/dev_all_{name}.jsonl: {n} pages changed")


if __name__ == "__main__":
    main()

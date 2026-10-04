"""Import paragraph splits from the column-break prompt runs (v10a / v10b) into a submission zip.

The reference ends a paragraph where it crosses a column break (its layout boxes are per column); our runs join the two halves, which costs
the second half twice (unpaired + inserted) and an order slot. Prompt v10a/v10b tells the model to split there. Swapping the v10 runs into the
ensemble does not carry the gain (the other candidates still join), so here the current page is kept and only the split points are imported:
a boundary of a v10 page (end of one paragraph + start of the next, 25 normalised chars each side) that falls inside one of our paragraphs
splits it at the start of that word (bvote.py, split-only). Text and order of our page are otherwise untouched.
Dev A/B (ab_ro_eval.py --import-only): v10a k1 +1.10/page [+0.34,+1.81] on 160 pages (13 better / 2 worse); the same import from a fresh v7
run (control) +0.04.
  python splitimport.py SRC.zip DST.zip --runs runs/test_all_v10a.jsonl[,runs/test_all_v10b.jsonl] [--k 1]
"""
import argparse, json, os, re, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from bvote import bvote
from postprocess import strip_sections

if __name__ == "__main__":
    from build_submission import write_zip, zip_rows
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--runs", required=True); ap.add_argument("--k", type=int, default=1)
    a = ap.parse_args()
    S = [{f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(f))} for f in a.runs.split(",")]
    out = []; n = sp_tot = 0; missing = 0
    for r in zip_rows(a.src):
        s = f'{r["document_id"]}_{r["page"]}'; md = r["markdown"]
        src = [x[s] for x in S if s in x]; missing += not src
        if src:
            new, _, sp = bvote(md, src, k=a.k, do_merge=False, long_only=False)
            if sp: md = new; n += 1; sp_tot += sp
        out.append({**r, "markdown": md})
    W = lambda t: re.sub(r"\s", "", t)
    assert all(W(x["markdown"]) == W(y["markdown"]) for x, y in zip(zip_rows(a.src), out)), "characters changed"
    write_zip(out, a.dst)
    print(f"{a.dst}: {n} pages changed, {sp_tot} paragraph splits imported; pages without a v10 run: {missing}")

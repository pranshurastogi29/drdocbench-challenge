"""Where is the text error under the END-TO-END scoring? (dev, a stack variant built by stack.py; default = the 82.88 stack)
Text_ED counts reference text_block / title / reference / code_txt blocks (headers, footers, page numbers, captions, footnotes and equation
captions take part in the pairing but are not scored) plus reference formulas that our text paired with, plus our leftover blocks.
Each scored record is one of: paired (both sides), MISSING (reference text, nothing of ours), EXTRA (our text, no reference block).
Page-level Text_ED = sum edits / sum max-lengths; the leaderboard averages pages, so each page's share is its edits / its length / N pages.
  python e2e_text_anatomy.py [--steps sel=mbr,rules,chan=1,fm,sd,bv,ac]
"""
import argparse, collections, json, os, re, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import e2e_eval as E
import stack


def job(a):
    import io, contextlib
    stem, md = a
    s = E.gt_json("dev", stem)
    if not s: return stem, None
    with contextlib.redirect_stdout(io.StringIO()):
        text, formula, _, _, order = E._DS.process_get_matched_elements(s, md, stem + ".jpg", 0)
    items = list(text) + [it for it in formula if it.get("pred_category_type") not in ("equation_inline", "equation_isolated", "")]
    rec = []
    for it in items:
        g = it.get("norm_gt") or it.get("gt") or ""; p = it.get("norm_pred") or it.get("pred") or ""   # the official metric's fallback
        if not (g or p): continue
        kind = "EXTRA" if it.get("gt_idx") in ([""], "") else "MISSING" if it.get("pred_idx") in ([""], "") else "paired"
        rec.append((kind, it.get("gt_category_type") or "-", E.Lev(p, g), max(len(p), len(g)), (it.get("gt") or "")[:80], (it.get("pred") or "")[:80]))
    pi = s["page_info"]["page_attribute"]
    return stem, {"rec": rec, "subject": s["page_info"]["page_attribute"].get("subject") or stem, "layout": pi.get("layout"), "issues": pi.get("special_issue") or []}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--steps", default=stack.FULL); a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", a.steps, tmp)
    with Pool(11, initializer=E.init) as P: R = {k: v for k, v in P.map(job, [(f'{r["document_id"]}_{r["page"]}', r["markdown"]) for r in rows], chunksize=4) if v and v["rec"]}
    os.chdir(ROOT)
    N = len(R); share = collections.Counter(); cat = collections.Counter(); page_ed = {}
    for k, v in R.items():
        den = sum(r[3] for r in v["rec"]) or 1
        page_ed[k] = sum(r[2] for r in v["rec"]) / den
        for kind, c, e, l, g, p in v["rec"]:
            share[kind] += e / den / N; cat[(kind, c)] += e / den / N
    tot = sum(share.values())
    print(f"{N} dev pages; Text_ED {tot:.4f} = " + ", ".join(f"{k} {v:.4f} ({v/tot:.0%})" for k, v in share.most_common()))
    print("by kind x reference category:")
    for (kind, c), v in cat.most_common(12): print(f"   {kind:8s} {c:18s} {v:.4f} ({v/tot:.0%})")
    # concentration
    s = sorted(page_ed.values(), reverse=True)
    for q in (0.02, 0.05, 0.1, 0.2): print(f"   worst {q:.0%} of pages hold {sum(s[:int(N*q)])/sum(s):.0%} of the text error")
    by = collections.defaultdict(list)
    for k, v in R.items(): by[v["layout"]].append(page_ed[k])
    print("by layout:", {k: (len(v), round(sum(v) / len(v), 3), f"{sum(v)/sum(s):.0%}") for k, v in by.items()})
    iss = collections.defaultdict(list)
    for k, v in R.items():
        for i in v["issues"] or ["none"]: iss[i].append(page_ed[k])
    print("by special issue:", {k: (len(v), round(sum(v) / len(v), 3)) for k, v in sorted(iss.items(), key=lambda x: -sum(x[1]))[:6]})
    json.dump({k: {"ed": page_ed[k], "rec": v["rec"], "layout": v["layout"]} for k, v in R.items()}, open(os.path.join(ROOT, "runs", "e2e_text_anatomy.json"), "w"))

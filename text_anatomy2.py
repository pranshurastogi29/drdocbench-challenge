"""Where is the dev text error of the current pipeline (84.13 stack), under the official md2md matcher? Each scored record is
  paired   : a reference block (or several, folded) with our block(s);  edits split into letter / digit / underscore / case-only
  missing  : reference text with nothing of ours (counted in full)
  extra    : our text with no reference block (counted when every reference block is paired: joined into one record)
Page Text_ED = sum edits / sum max-lengths; the leaderboard averages pages, so each record's share = its edits / page length / N pages.
Also: the share held by the worst pages, and by page attributes of the dev layout JSON.
  python text_anatomy2.py [--steps ...]
"""
import argparse, collections, json, os, re, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)


def job(a):
    import md2md_eval as M
    import Levenshtein
    from common import gt_markdown
    k, subj, md = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    g = M.md_tex_filter(gt).get("text_all") or []; p = M.md_tex_filter(md).get("text_all") or []
    if not g: return k, None
    recs = M.match(g, p, "text", "x", skip_truncated=True); out = []
    for r in recs:
        a_ = r.get("norm_gt") or r.get("gt") or ""; b = r.get("norm_pred") or r.get("pred") or ""
        if not (a_ or b): continue
        e = Levenshtein.distance(b, a_); L = max(len(a_), len(b))
        kind = "extra" if r.get("gt_idx") in ([""], "") or not a_ else "missing" if r.get("pred_idx") in ([""], "") or not b else "paired"
        sub = collections.Counter()
        if kind == "paired" and e:
            ci = Levenshtein.distance(b.lower(), a_.lower()); sub["case"] += e - ci
            for op, i, j in Levenshtein.editops(b.lower(), a_.lower()):
                ch = a_[j] if op != "delete" and j < len(a_) else (b[i] if i < len(b) else "")
                sub["underscore" if ch == "_" else "digit" if ch.isdigit() else "letter"] += 1
        out.append((kind, e, L, dict(sub), (r.get("gt") or "")[:60], (r.get("pred") or "")[:60]))
    return k, out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--steps", default="sel=mbr8,rules,fm,sd,bv,rv=free,ac"); a = ap.parse_args()
    import stack, md2md_eval as M
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", a.steps, tmp)
    os.chdir(ROOT)
    with Pool(11, initializer=M.init) as P: R = {k: v for k, v in P.map(job, [(f'{r["document_id"]}_{r["page"]}', r["subject"], r["markdown"]) for r in rows], chunksize=6) if v}
    os.chdir(ROOT)
    N = len(R); share = collections.Counter(); subs = collections.Counter(); page_ed = {}
    for k, recs in R.items():
        den = sum(x[2] for x in recs) or 1; page_ed[k] = sum(x[1] for x in recs) / den
        for kind, e, L, sub, _, _ in recs:
            share[kind] += e / den / N
            for s, n in sub.items(): subs[s] += n / den / N
    tot = sum(share.values())
    print(f"{N} dev pages with reference text; Text_ED {tot:.4f}")
    for kind, v in share.most_common(): print(f"  {kind:8s} {v:.4f} ({v / tot:.0%})")
    ps = share["paired"]
    print("  inside paired records: " + ", ".join(f"{s} {v:.4f} ({v / tot:.0%})" for s, v in subs.most_common()))
    s = sorted(page_ed.values(), reverse=True)
    for q in (0.02, 0.05, 0.1, 0.2): print(f"  worst {q:.0%} of pages hold {sum(s[:int(N * q)]) / sum(s):.0%} of the text error")
    print(f"  pages with Text_ED > 0.5: {sum(x > 0.5 for x in s)}; their share {sum(x for x in s if x > 0.5) / sum(s):.0%}; if they were at the median ({s[len(s)//2]:.3f}) Text_ED would be {(sum(s) - sum(x - s[len(s)//2] for x in s if x > 0.5)) / N:.4f}")
    json.dump({k: {"ed": page_ed[k], "recs": R[k]} for k in R}, open(os.path.join(ROOT, "runs", "text_anatomy2.json"), "w"))

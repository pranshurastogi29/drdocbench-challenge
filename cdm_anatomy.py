"""Where are formula (CDM) points lost? Dev, 82.88 stack (stack.py FULL), md2md formula matching as md2md_dataset does.
Each reference display formula (Markdown references) is classified -- textit / textbf / bi wrapper of one line, multi-line wrapper (array of
wrapped lines), wrapper containing math, real math -- and scored by its matched prediction (1 - normalised edit). Prints the mean per kind,
the share of the total formula error, and the worst-matched examples.
  python cdm_anatomy.py
"""
import collections, json, os, re, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import md2md_eval as M
import stack
from common import gt_markdown


def kind(g):
    g = g.strip()
    if "\\begin{array}" in g: return "multi-line wrapper" if re.search(r"\\text(it|bf)", g) else "array math"
    if re.fullmatch(r"\$*\s*\\textbf\{\\textit\{[^{}]*\}\}\s*\$*", g): return "bold-italic wrapper"
    if re.fullmatch(r"\$*\s*\\textit\{[^{}]*\}\s*\$*", g): return "italic wrapper"
    if re.fullmatch(r"\$*\s*\\textbf\{[^{}]*\}\s*\$*", g): return "bold wrapper"
    if re.search(r"\\text(it|bf)\{", g): return "wrapper with math/markup"
    return "real math"


def job(a):
    stem, subj, md = a
    doc, pg = stem.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    g = M.md_tex_filter(gt).get("equation_isolated") or []
    if not g: return stem, []
    p = M.md_tex_filter(md).get("equation_isolated") or []
    recs = [r for r in M.match(g, p, "formula", "x") if r.get("gt_idx") != [""] and r.get("gt_category_type") != "equation_inline"]
    out = []
    for r in recs:
        a_ = r.get("norm_gt") or r.get("gt") or ""; b = r.get("norm_pred") or r.get("pred") or ""
        if a_ or b: out.append((kind(r.get("gt") or ""), M.Lev(b, a_), max(len(a_), len(b)), (r.get("gt") or "")[:90], (r.get("pred") or "")[:70]))
    return stem, out


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", sys.argv[1] if len(sys.argv) > 1 else stack.FULL, tmp)
    with Pool(11, initializer=M.init) as P: R = dict(P.map(job, [(f'{r["document_id"]}_{r["page"]}', r["subject"], r["markdown"]) for r in rows], chunksize=4))
    os.chdir(ROOT)
    allr = [x for v in R.values() for x in v]; E = sum(x[1] for x in allr); L = sum(x[2] for x in allr)
    print(f"{len(allr)} reference formulas on {sum(1 for v in R.values() if v)} dev pages; pooled formula score {100 * (1 - E / L):.1f}")
    by = collections.defaultdict(list)
    for x in allr: by[x[0]].append(x)
    for k, v in sorted(by.items(), key=lambda kv: -sum(x[1] for x in kv[1])):
        e = sum(x[1] for x in v); l = sum(x[2] for x in v)
        print(f"  {k:26s} {len(v):4d} formulas  score {100 * (1 - e / l):5.1f}  share of formula error {e / E:.0%}  unmatched (score<10) {sum(1 for x in v if x[2] and x[1] / x[2] > 0.9)}")
    print("worst wrapper matches (reference | ours):")
    w = sorted([x for x in allr if "wrapper" in x[0] and x[2] > 0], key=lambda x: -x[1] / x[2])[:12]
    for x in w: print(f"   {x[1] / x[2]:.2f} {x[0]:20s} {x[3]!r} | {x[4]!r}")

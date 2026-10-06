"""Dev scoring with the md2md logic (Markdown references, formulas matched apart from text) with or without the matcher's truncated-merge
step (skip_truncated=True is what scorer/dataset/multipage_md2md_dataset.py uses). Text_ED = mean over pages; RO = 1 - mean page order edit.
Leaderboard evidence (2026-10-06): removing 68k formula copies left Reading_Order at exactly 84.91 and CDM fell 65.8 -> 12.5, so formulas do not
take part in the leaderboard's text/order matching and CDM is scored on the Markdown references (md2md-like), not the end2end JSON pipeline.
  from md2md_eval import page_scores  (worker initialised with md2md_eval.init)
"""
import os, sys, types
ROOT = os.path.dirname(os.path.abspath(__file__))


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        return type(name, (), {})


def init():
    global md_tex_filter, match, Lev
    sys.modules["mmeval"] = _Stub("mmeval"); sys.path.insert(0, os.path.join(ROOT, "scorer")); os.chdir(os.path.join(ROOT, "scorer"))
    from utils.extract import md_tex_filter
    from utils.match_quick import match_gt2pred_quick as match
    import Levenshtein; Lev = Levenshtein.distance


def page_scores(pred_md, gt_md, skip=True):
    g = md_tex_filter(gt_md).get("text_all") or []; p = md_tex_filter(pred_md).get("text_all") or []
    if not g: return None
    recs = match(g, p, "text", "x", skip_truncated=skip); n = d = 0
    for r in recs:
        a = r.get("norm_gt") or r.get("gt") or ""; b = r.get("norm_pred") or r.get("pred") or ""
        if a or b: n += Lev(b, a); d += max(len(a), len(b))
    text = 100 * (1 - n / d) if d else 100.0
    m = [(r["gt_position"], r["pred_position"]) for r in recs if r["gt_position"] != [""] and r["pred_position"] != ""]
    G = sorted(x for x in sum([r["gt_position"] for r in recs if r["gt_position"] != [""]], []) if x)
    P = [x for x in sum([a_ for a_, _ in sorted(m, key=lambda t: t[1])], []) if x]
    if not (G or P): return text, None
    return text, 100 * (1 - Lev(G, P) / max(len(G), len(P)))


def formula_score(pred_md, gt_md):
    """formula proxy (stands in for CDM): reference display formulas (Markdown references, incl. $\\textit{..}$ wrappers) matched to our formula
    blocks as md2md_dataset does; 100 * (1 - edit/len) pooled over the page. None when the reference page has no display formula."""
    g = md_tex_filter(gt_md).get("equation_isolated") or []
    if not g: return None
    p = md_tex_filter(pred_md).get("equation_isolated") or []
    recs = match(g, p, "formula", "x")
    recs = [r for r in recs if r.get("gt_idx") != [""] and r.get("gt_category_type") != "equation_inline"]
    from utils.data_preprocess import normalized_formula
    scores = []
    for r in recs:   # CDM averages per reference formula, so does this proxy: 1 - normalised edit, both sides normalised the scorer's way
        a = normalized_formula(r.get("gt") or ""); b = normalized_formula(r.get("pred") or "") if r.get("pred") else ""
        scores.append(1 - Lev(b, a) / max(len(a), len(b), 1))
    return (100 * sum(scores) / len(scores), len(scores)) if scores else None

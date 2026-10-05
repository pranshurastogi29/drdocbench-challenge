"""Dev scoring with the official END-TO-END pipeline (scorer/dataset/end2end_dataset.py), which the leaderboard appears to use
(its multipage_end2end config): the reference is the per-page layout JSON, ALL our blocks except tables (text, display and inline formulas)
are matched in one pool against the reference's text-like + display-formula blocks, and Text_ED / Reading_Order then IGNORE reference
headers, footers, page numbers, page footnotes, captions, figure/table footnotes, equation captions and code. A reference formula matched by
one of our text blocks is scored as text. Text_ED = mean over pages of (edits / length); Reading_Order = 1 - mean over pages of order edit.

Evidence that the leaderboard scores this way and not like md2md: final5_fc6t -> final5_fc10t added only formula-channel copies, which leave
md2md text blocks unchanged (4 of 509 pages differ, trivially), yet the leaderboard moved Text_ED +0.0043 and Reading_Order +1.59.

  python e2e_eval.py RUN.jsonl [RUN2.jsonl ...] [--name NAME]   -> per-page scores in runs/e2e_<name>.json and a summary
  from e2e_eval import page_scores  (in a worker initialised with e2e_eval.init)
"""
import argparse, glob, json, os, sys, types
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.abspath(__file__))
_DS = None


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        return type(name, (), {})


def init():
    global _DS, Lev
    sys.modules["mmeval"] = _Stub("mmeval"); sys.path.insert(0, os.path.join(ROOT, "scorer")); os.chdir(os.path.join(ROOT, "scorer"))
    from dataset.end2end_dataset import End2EndDataset
    import Levenshtein; Lev = Levenshtein.distance
    _DS = End2EndDataset.__new__(End2EndDataset); _DS.match_method = "quick_match"
    import loguru; loguru.logger.remove()


def gt_json(split, stem):
    doc, pg = stem.rsplit("_", 1)
    f = glob.glob(os.path.join(ROOT, "data", split, "*", doc, "json", f"{doc}_page_{pg}.json"))
    if not f: return None
    j = json.load(open(f[0]))
    if not j: return None
    x = j[0]; ids = {d.get("anno_id") for d in x.get("layout_dets", [])}
    # as multipage_end2end_dataset does: keep only relations whose two blocks exist on the page
    rel = [r for r in (x.get("extra") or {}).get("relation", []) if r.get("source_anno_id") in ids and r.get("target_anno_id") in ids]
    x["extra"] = {**(x.get("extra") or {}), "relation": rel}
    return x


def page_scores(stem, md, split="dev", sample=None):
    """(text_score 0-100 or None, order_score 0-100 or None, n_text_items) for one page, official end2end logic"""
    import io, contextlib
    sample = sample or gt_json(split, stem)
    if not sample: return None
    with contextlib.redirect_stdout(io.StringIO()):
        text, formula, _, _, order = _DS.process_get_matched_elements(sample, md, stem + ".jpg", 0)
    # reference formulas matched by our TEXT blocks are scored as text (get_matched_elements)
    items = list(text)
    for it in formula:
        if it.get("pred_category_type") not in ("equation_inline", "equation_isolated", ""):
            from pylatexenc.latex2text import LatexNodes2Text
            from utils.data_preprocess import clean_string
            g = it.get("gt") or ""
            try: g = LatexNodes2Text().latex_to_text(g)
            except Exception: pass
            items.append({**it, "norm_gt": clean_string(g)})
    num = den = 0
    for it in items:
        g = it.get("norm_gt") or it.get("gt") or ""; p = it.get("norm_pred") or it.get("pred") or ""
        if len(g) or len(p): num += Lev(p, g); den += max(len(p), len(g))
    t = 100 * (1 - num / den) if den else None
    o = 100 * (1 - order["edit"]) if order else None
    # formula proxy (stands in for CDM): reference formulas matched by our formula blocks (or unmatched), 1 - edit distance on the normalised strings
    fn = fd = 0
    for it in formula:
        if it.get("pred_category_type") in ("equation_inline", "equation_isolated", ""):
            g = it.get("norm_gt") or it.get("gt") or ""; p = it.get("norm_pred") or it.get("pred") or ""
            if len(g) or len(p): fn += Lev(p, g); fd += max(len(p), len(g))
    f = 100 * (1 - fn / fd) if fd else None
    return t, o, len(items), f


def _job(a):
    stem, mds, split = a
    s = gt_json(split, stem)
    return stem, [page_scores(stem, md, split, s) if s else None for md in mds]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("runs", nargs="+"); ap.add_argument("--split", default="dev"); ap.add_argument("--name"); a = ap.parse_args()
    from postprocess import strip_sections
    R = [{f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(f))} for f in a.runs]
    keys = sorted(set.intersection(*[set(x) for x in R]))
    with Pool(11, initializer=init) as P: out = dict(P.map(_job, [(k, [x[k] for x in R], a.split) for k in keys], chunksize=4))
    os.chdir(ROOT)
    for i, f in enumerate(a.runs):
        T = [v[i][0] for v in out.values() if v[i] and v[i][0] is not None]; O = [v[i][1] for v in out.values() if v[i] and v[i][1] is not None]
        print(f"{os.path.basename(f):45s} pages {len(T):4d}  Text_ED {1 - sum(T)/len(T)/100:.4f}  Reading_Order {sum(O)/len(O):.2f}  (order pages {len(O)})")
    if a.name: json.dump(out, open(os.path.join(ROOT, "runs", f"e2e_{a.name}.json"), "w"))

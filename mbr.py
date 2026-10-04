"""Minimum-Bayes-risk candidate selection with the official metric.
For each page, every candidate is scored against every other candidate with the scorer's own Markdown splitting (md_tex_filter) and pairing
(match_gt2pred_quick); utility = 0.558 * Text(100*(1-ED)) + 0.433 * Reading_Order, the leaderboard's own weights. The candidate with the highest
mean utility against the others is chosen: the one whose text, paragraphs and order would score best if the reference looked like the other runs.
  python mbr.py --split dev|test     -> runs/mbr_choice_<split>.json  {stem: candidate}
"""
import argparse, json, os, sys, types
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.abspath(__file__))


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        return type(name, (), {})


def _init():
    sys.modules["mmeval"] = _Stub("mmeval"); sys.path.insert(0, os.path.join(ROOT, "scorer")); os.chdir(os.path.join(ROOT, "scorer"))
    global md_tex_filter, match, Lev
    from utils.extract import md_tex_filter
    from utils.match_quick import match_gt2pred_quick as match
    import Levenshtein; Lev = Levenshtein.distance


def utility(pred_md, ref_md):
    gt = md_tex_filter(ref_md).get("text_all") or []; pr = md_tex_filter(pred_md).get("text_all") or []
    if not gt: return None
    recs = match(gt, pr, "text", "x")
    ed_num = ed_den = 0
    for r in recs:
        g = r.get("norm_gt") or r.get("gt") or ""; p = r.get("norm_pred") or r.get("pred") or ""
        if g or p: ed_num += Lev(p, g); ed_den += max(len(p), len(g))
    text = 100 * (1 - ed_num / ed_den) if ed_den else 100.0
    matched = [(r["gt_position"], r["pred_position"]) for r in recs if r["gt_position"] != [""] and r["pred_position"] != ""]
    gt_all = [r["gt_position"] for r in recs if r["gt_position"] != [""]]
    g = sorted(x for x in sum(gt_all, []) if x); p = [x for x in sum([a for a, _ in sorted(matched, key=lambda m: m[1])], []) if x]
    if not g and not p: return 0.558 * text / 0.558 * 0.558 + 0.433 * 100   # no order data: neutral order
    ro = 100 * (1 - Lev(g, p) / max(len(g), len(p)))
    return 0.558 * text + 0.433 * ro


def gt_like(pred_md, ref_md):
    """(text, order) of pred_md scored against ref_md as if it were the reference (official splitting and pairing)"""
    gt = md_tex_filter(ref_md).get("text_all") or []; pr = md_tex_filter(pred_md).get("text_all") or []
    if not gt: return None
    recs = match(gt, pr, "text", "x"); n = d = 0
    for r in recs:
        g = r.get("norm_gt") or r.get("gt") or ""; p = r.get("norm_pred") or r.get("pred") or ""
        if g or p: n += Lev(p, g); d += max(len(p), len(g))
    text = 100 * (1 - n / d) if d else 100.0
    m = [(r["gt_position"], r["pred_position"]) for r in recs if r["gt_position"] != [""] and r["pred_position"] != ""]
    G = sorted(x for x in sum([r["gt_position"] for r in recs if r["gt_position"] != [""]], []) if x)
    P = [x for x in sum([a for a, _ in sorted(m, key=lambda t: t[1])], []) if x]
    if not (G or P): return None
    return text, 100 * (1 - Lev(G, P) / max(len(G), len(P)))


def choose(job):
    stem, cands = job
    names = [n for n, md in cands.items() if md.strip()]
    if len(names) < 3: return stem, None, {}
    sc = {}
    for i in names:
        us = [u for j in names if j != i for u in [utility(cands[i], cands[j])] if u is not None]
        sc[i] = sum(us) / len(us) if us else -1
    best = max(names, key=lambda n: (sc[n], n == "v7"))
    return stem, best, sc


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cands", default="v6,v7,v8,paddle,v7c")
    a = ap.parse_args()
    sys.path.insert(0, ROOT)
    from postprocess import strip_sections
    import build_submission as bs
    files = (bs.DEV if a.split == "dev" else bs.TEST)
    C = {n: {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, files[n]), encoding="utf-8"))} for n in a.cands.split(",")}
    stems = sorted(set.intersection(*[set(v) for v in C.values()]))
    jobs = [(s, {n: C[n][s] for n in C}) for s in stems]
    out, scores = {}, {}
    with Pool(a.workers, initializer=_init) as pool:
        for i, (stem, best, sc) in enumerate(pool.imap_unordered(choose, jobs, chunksize=4), 1):
            if best: out[stem] = best; scores[stem] = sc
            if i % 100 == 0: print(i, "/", len(jobs), flush=True)
    json.dump(out, open(os.path.join(ROOT, "runs", f"mbr_choice_{a.split}.json"), "w"))
    json.dump(scores, open(os.path.join(ROOT, "runs", f"mbr_scores_{a.split}.json"), "w"))
    import collections; print("choices:", collections.Counter(out.values()).most_common())

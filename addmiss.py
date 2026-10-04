"""Add paragraphs our chosen page lacks but other sources agree on (picture text, small print a run skipped).

Page selection keeps one run's page; text that run skipped (labels in a figure, a caption, small print) is lost even when the other runs and
Paddle/MinerU read it. A paragraph of a source is 'missing' when nothing in our page matches it (partial fuzzy match on scorer-normalised
text < MISS); it is added when at least K sources have it (matched to each other with >= AGREE), at its place in the source page: after our
paragraph that best matches the source paragraph just before it (else at the end of the body, before trailing furniture).
"""
import re
from rapidfuzz import fuzz

W = lambda s: re.sub(r"[\W_]", "", s)


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def skip(p):
    return p.startswith("<table") or p.startswith("$") or p.startswith("|") or p.startswith("![")


def add_missing(md, sources, k=2, minw=10, miss=60, agree=80, maxw=2000, max_add=6):
    """sources: list of Markdown pages (other runs). Returns (new_md, added paragraphs)"""
    ours = paras(md); ow = W(md); ows = [W(p) for p in ours]
    S = [[(p, W(p)) for p in paras(s) if not skip(p)] for s in sources if s]
    cand = []                                  # (source index, paragraph index, text, words)
    for si, ps in enumerate(S):
        for pi, (p, w) in enumerate(ps):
            if minw <= len(w) <= maxw and fuzz.partial_ratio(w, ow) < miss if len(w) <= len(ow) else minw <= len(w) <= maxw and fuzz.ratio(w, ow) < miss:
                cand.append((si, pi, p, w))
    added, seen = [], []
    for si, pi, p, w in cand:
        if any(fuzz.ratio(w, s) >= agree for s in seen): continue
        votes = 1 + sum(1 for sj, ps in enumerate(S) if sj != si and any(fuzz.ratio(w, w2) >= agree for _, w2 in ps))
        if votes < k: continue
        seen.append(w)
        prev = W(S[si][pi - 1][0]) if pi > 0 else ""
        at = None
        if prev:
            sc = [fuzz.ratio(prev, x) if x else 0 for x in ows]
            if sc and max(sc) >= 70: at = sc.index(max(sc)) + 1
        added.append((at, p))
        if len(added) >= max_add: break
    if not added:
        return md, []
    out = list(ours)
    for at, p in sorted(added, key=lambda x: -(x[0] if x[0] is not None else len(ours))):
        out.insert(at if at is not None else len(out), p)
    return "\n\n".join(out), [p for _, p in added]

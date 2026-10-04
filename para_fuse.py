"""Paragraph-level consensus (ROVER-style) on top of page selection.

Page selection keeps one candidate's whole page, so every typo / dropped word of that run stays even when the other runs read the paragraph
right. Here the selected page is the skeleton (its paragraph split and order are kept, which is what reading order scores); each body
paragraph is located in every other candidate (best fuzzy match on scorer-normalised text, similar length) and replaced by the medoid of
the matched versions: the version closest to all the others. Tables, $-formulas and multi-line (merged furniture) paragraphs are left as they are;
a heading keeps the skeleton's '#' prefix.
"""
import re
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein as L

W = lambda s: re.sub(r"[\W_]", "", s)
HEAD = re.compile(r"^(#+\s*)")


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def skip(p):
    return p.startswith("<table") or p.startswith("$") or "\n" in p or p.startswith("|") or "<" in p


def fuse(skel, others, minsim=70, lenr=0.75, minw=8, mode="medoid"):
    S = paras(skel); O = [[(q, W(HEAD.sub("", q))) for q in paras(o) if not skip(q)] for o in others]
    out = []; changed = 0
    for p in S:
        if skip(p):
            out.append(p); continue
        m = HEAD.match(p); pre = m.group(1) if m else ""; body = p[len(pre):]; w = W(body)
        if len(w) < minw:
            out.append(p); continue
        vers = [(body, w)]
        for cand in O:
            best, bq = 0, None
            for q, wq in cand:
                if not wq or min(len(w), len(wq)) / max(len(w), len(wq)) < lenr: continue
                s = fuzz.ratio(w, wq)
                if s > best: best, bq = s, (HEAD.sub("", q), wq)
            if bq and best >= minsim: vers.append(bq)
        if len(vers) < 3:
            out.append(p); continue
        cost = [sum(L.normalized_distance(a[1], b[1]) for b in vers) for a in vers]
        i = min(range(len(vers)), key=lambda i: (cost[i], i))   # ties keep the skeleton's own version
        if i:
            changed += 1
        out.append(pre + vers[i][0])
    return "\n\n".join(out), changed

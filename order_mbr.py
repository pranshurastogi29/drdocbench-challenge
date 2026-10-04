"""Order-only MBR: keep the chosen page's text and paragraphs, consider re-orderings borrowed from the other candidates.

For each other candidate c, our paragraphs are sorted into c's order (each of ours matched to its best fuzzy partner in c; unmatched paragraphs
ride behind the matched paragraph that precedes them; the trailing furniture block stays last). A hypothesis replaces our order only when it
scores better against the remaining candidates as pseudo-references, with c itself left out (it would vote for its own order), by > MARGIN of
the scorer utility (0.558 text + 0.433 order).
"""
import re
from rapidfuzz import fuzz

N = lambda s: re.sub(r"[\W_]", "", s)


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def borrow_order(ours, theirs, sim=70):
    """ours/theirs: paragraph lists -> our paragraphs in their order (None if too little matches)"""
    T = [N(q)[:300] for q in theirs]
    key, matched = [], 0
    for i, p in enumerate(ours):
        w = N(p)[:300]
        best, bj = 0, None
        if len(w) >= 3:
            for j, t in enumerate(T):
                if t and min(len(w), len(t)) / max(len(w), len(t)) > 0.3:
                    s = fuzz.ratio(w, t)
                    if s > best: best, bj = s, j
        if bj is not None and best >= sim:
            key.append((bj, i)); matched += 1
        else:
            key.append(None)
    if matched < 3 or matched < 0.5 * len(ours): return None
    k2, last = [], (-1, -1)
    for i, k in enumerate(key):           # unmatched: ride behind the previous paragraph
        last = k if k is not None else (last[0], last[1] + 0.001 if isinstance(last[1], float) else i - 0.5)
        k2.append((last[0], i if k is not None else last[1], i))
    # keep the trailing furniture block (multi-line merged tail or last short lines) in place at the end
    tail = len(ours)
    while tail > 0 and ("\n" in ours[tail - 1] and len(N(ours[tail - 1])) <= 120): tail -= 1
    body = sorted(range(tail), key=lambda i: (k2[i][0], k2[i][2]))
    return [ours[i] for i in body] + ours[tail:]


def order_mbr(md, others, utility, margin=1.0):
    """others: {name: md}; utility(pred, ref) -> scorer utility. Returns (md, chosen name or None, gain)"""
    ours = paras(md); best = (0.0, None, md)
    if len(ours) < 3: return md, None, 0.0
    for c, omd in others.items():
        h = borrow_order(ours, paras(omd))
        if not h or h == ours: continue
        hmd = "\n\n".join(h)
        refs = [r for n, r in others.items() if n != c]
        g = [(utility(hmd, r), utility(md, r)) for r in refs]
        g = [x - y for x, y in g if x is not None and y is not None]
        if g:
            gain = sum(g) / len(g)
            if gain > best[0]: best = (gain, c, hmd)
    return (best[2], best[1], best[0]) if best[0] > margin else (md, None, best[0])

"""Table fix: when PaddleOCR-VL sees a table whose content is NOT covered by any <table> in our page output, add Paddle's table
(normalised to the reference's <tbody> style). With replace=True the plain-text paragraphs that merely spell out that table's
cells are removed, since the reference counts them as table content, not as text."""
import re
from rapidfuzz import fuzz
from paddle_ingest import blocks, furniture
from reading_order import norm
from snap import protected
from variants import tables_variant

cell = lambda h: norm(re.sub(r"<[^>]+>", " ", h))


def fix(md, stem, replace=True):
    bl = [b for b in (blocks(stem) or []) if b["block_label"] == "table" and b["block_content"].strip()]
    if not bl:
        return md, 0
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    furn = {norm(t) for _, t in furniture(stem)}
    added = 0
    for b in bl:
        tn = cell(b["block_content"])
        if len(tn) < 10:
            continue
        ours = [cell(p) for p in paras if "<table" in p]
        if any(fuzz.partial_ratio(tn[:150], o) >= 70 or fuzz.partial_ratio(o[:150], tn) >= 70 for o in ours if o):
            continue                                                  # a table with this content is already there
        html = tables_variant(b["block_content"].strip())
        idx = []
        if replace:
            for j, p in enumerate(paras):
                pn = norm(p)
                if protected(p) or len(pn) < 4 or pn in furn or len(pn) > len(tn):
                    continue
                if fuzz.partial_ratio(pn, tn) >= 95:
                    idx.append(j)
            if len(idx) < 2 or sum(len(norm(paras[j])) for j in idx) < 0.3 * len(tn):
                idx = []                                              # not convincingly the same content: only add
        if idx:
            first = idx[0]; paras = [p for j, p in enumerate(paras) if j not in set(idx[1:])]; paras[first] = html
        else:
            # insert after the paragraph that holds the nearest preceding Paddle text block; else at the top
            pos, pn_list = 0, [norm(p) for p in paras]
            allb = blocks(stem) or []; ti = allb.index(b)
            for q in range(ti - 1, -1, -1):
                t = norm(allb[q]["block_content"] or "")
                if len(t) >= 10 and allb[q]["block_label"] not in ("image", "chart", "header", "footer", "number"):
                    best = max(range(len(paras)), key=lambda z: fuzz.partial_ratio(t[:100], pn_list[z])) if paras else None
                    if best is not None and fuzz.partial_ratio(t[:100], pn_list[best]) >= 80:
                        pos = best + 1; break
            paras.insert(pos, html)
        added += 1
    return "\n\n".join(paras), added

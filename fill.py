"""Add text blocks that PaddleOCR-VL read but NONE of our candidate runs contain (v6, v7, v8), at the position implied by Paddle's order."""
import json, re, argparse
from rapidfuzz import fuzz
from paddle_ingest import blocks
from reading_order import norm
from snap import TEXTLIKE, protected

MIN_LEN = 25
ABSENT = 70    # partial_ratio below this against EVERY candidate => the block is missing from all our runs
FOUND = 80     # partial_ratio at/above this => used as an anchor for where to insert


def missing(stem, cands, with_tables=False):
    """[(paddle_index, text, kind)] of Paddle blocks absent from every candidate."""
    bl = blocks(stem) or []; cn = [norm(c) for c in cands]; out = []
    for i, b in enumerate(bl):
        lab = b["block_label"]; txt = (b["block_content"] or "").strip()
        if lab in TEXTLIKE and len(txt) >= MIN_LEN:
            t = norm(txt)
            if t and all(fuzz.partial_ratio(t[:100], c) < ABSENT for c in cn):
                out.append((i, txt, "text"))
        elif with_tables and lab == "table" and txt:
            if all("<table" not in c for c in cands):           # Paddle sees a table, no run has any table on the page
                out.append((i, txt, "table"))
    return out


def insert(md, stem, miss):
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    bl = blocks(stem) or []; pn = [norm(p) for p in paras]
    def anchor(i):                                                 # index of our paragraph that holds the nearest preceding Paddle block
        for j in range(i - 1, -1, -1):
            t = norm(bl[j]["block_content"] or "")
            if len(t) >= 10 and bl[j]["block_label"] in TEXTLIKE:
                best = max(range(len(paras)), key=lambda q: fuzz.partial_ratio(t[:100], pn[q])) if paras else None
                if best is not None and fuzz.partial_ratio(t[:100], pn[best]) >= FOUND: return best
        return -1
    ins = sorted(((anchor(i), i, txt) for i, txt, _ in miss), key=lambda x: (x[0], x[1]))
    out, k = [], 0
    for pos in range(-1, len(paras)):
        if pos >= 0: out.append(paras[pos])
        while k < len(ins) and ins[k][0] == pos:
            out.append(ins[k][2]); k += 1
    return "\n\n".join(out)

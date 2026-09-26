"""Local reading-order proxy.

Ground truth: dev json `layout_dets` blocks that carry an `order` (headers/footers/page numbers/masks have none).
Prediction : locate each block's text inside the predicted Markdown by fuzzy matching, then sort the located blocks
             by position. Score = 1 - normalized Levenshtein distance between the true order and the predicted
             order of the blocks that were found. Blocks that could not be found are excluded from the order
             comparison and reported separately as `found` (coverage), so an omission does not look like a swap.

This mirrors the "(1 - normalized reading-order edit distance)" definition on the challenge page, but it is a
proxy: the official scorer's block matching is not public to me.
"""
import json
import os
import re

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from common import DATA

MIN_CHARS = 10  # shorter blocks ("1", "Figure") match anywhere and make the order ambiguous
MIN_MATCH = 70  # partial_ratio needed to count a block as located

_HTML_TAG = re.compile(r"<[^>]+>")
_MARKUP = re.compile(r"[*_#`>|\\{}$~]|\\\w+")


def norm(s):
    s = _HTML_TAG.sub(" ", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = _MARKUP.sub(" ", s)
    return " ".join(s.lower().split())


def load_page(split, subject, doc, page):
    p = os.path.join(DATA, split, subject, doc, "json", f"{doc}_page_{page}.json")
    if not os.path.exists(p):
        return None
    rec = json.load(open(p, encoding="utf-8"))
    return rec[0] if rec else None


def gt_blocks(page_rec):
    """[(order, category, normalized_text)] for orderable blocks with usable text, sorted by order."""
    out = []
    for b in page_rec["layout_dets"]:
        if b.get("ignore") or "order" not in b:
            continue
        raw = b.get("text") or b.get("html") or ""
        t = norm(raw)
        if len(t) >= MIN_CHARS:
            out.append((b["order"], b["category_type"], t))
    counts = {}
    for _, _, t in out:
        counts[t] = counts.get(t, 0) + 1
    # identical blocks (repeated labels/headers) cannot be told apart by text, so they are excluded
    return sorted(b for b in out if counts[b[2]] == 1)


def locate(blocks, pred_md):
    """Return (found_positions, n_blocks): list of (gt_rank, position_in_pred) for blocks located in pred."""
    hay = norm(pred_md)
    found = []
    for rank, (_, _, t) in enumerate(blocks):
        if not hay:
            break
        needle = t if len(t) <= 400 else t[:400]  # long blocks: match their opening, keeps it fast and stable
        if len(needle) > len(hay):
            continue
        al = fuzz.partial_ratio_alignment(needle, hay)
        if al is not None and al.score >= MIN_MATCH:
            found.append((rank, al.dest_start))
    return found


def score_page(page_rec, pred_md):
    """Return (order_score or None, found_fraction, n_blocks)."""
    blocks = gt_blocks(page_rec)
    if len(blocks) < 2:
        return None, None, len(blocks)
    found = locate(blocks, pred_md)
    frac = len(found) / len(blocks)
    if len(found) < 2:
        return None, frac, len(blocks)
    true_seq = [r for r, _ in found]  # already in GT order
    pred_seq = [r for r, _ in sorted(found, key=lambda x: x[1])]
    return 1 - Levenshtein.normalized_distance(true_seq, pred_seq), frac, len(blocks)

"""Page-level repairs driven by PaddleOCR-VL's independent per-page layout (found in error analysis round 3).

  python repair.py SRC.jsonl DST.jsonl --split dev --rules figdrop,spill [--T 0.4]
figdrop : a page with a large image block (>= T of the page) and long paragraphs that Paddle's own text does not confirm -> those
          paragraphs are transcriptions of text inside the picture, which the reference leaves out: drop them.
spill   : inside a 2-page window, paragraphs whose text belongs (per Paddle) to the other page of the window are moved across
          (the model sometimes puts the page break too early, spilling half a page onto the next one).
"""
import argparse, glob, json, os, re
from PIL import Image
from rapidfuzz import fuzz
from common import DATA, list_pages, windows
from paddle_ingest import blocks
from reading_order import norm

IMG = ("image", "chart", "seal")
FURN = ("header", "footer", "number", "footnote", "aside_text")


def ptext(stem):
    bl = blocks(stem) or []
    return norm(" ".join(re.sub(r"<[^>]+>", " ", b["block_content"] or "") for b in bl if b["block_label"] not in IMG))


def big_image(stem, size, T):
    W, H = size
    return any(b["block_label"] in IMG and (b["block_bbox"][2] - b["block_bbox"][0]) * (b["block_bbox"][3] - b["block_bbox"][1]) >= T * W * H for b in (blocks(stem) or []))


def paras(md): return [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def figdrop(md, stem, size, T=0.4, minlen=80, thr=60, max_ratio=0.4):
    if not big_image(stem, size, T): return md
    ptx = ptext(stem); keep = []
    if len(ptx) > max_ratio * len(norm(md)): return md      # Paddle reads a lot of text outside the picture: our text is probably real
    for p in paras(md):
        n = norm(p)
        if "<table" in p or len(n) < minlen or fuzz.partial_ratio(n[:300], ptx) >= thr: keep.append(p)
    return "\n\n".join(keep)


def spill(mda, mdb, sa, sb, margin=25, minlen=60):
    """Re-assign long paragraphs of a window to the page whose Paddle text contains them (order of the concatenation is kept)."""
    ta, tb = ptext(sa), ptext(sb)
    if len(ta) < 200 or len(tb) < 200: return mda, mdb
    pa, pb = paras(mda), paras(mdb); seq = [(p, 0) for p in pa] + [(p, 1) for p in pb]; out = [[], []]; moved = 0
    for p, side in seq:
        n = norm(p)[:300]
        if len(n) >= minlen and "<table" not in p:
            sca, scb = fuzz.partial_ratio(n, ta), fuzz.partial_ratio(n, tb)
            if side == 0 and scb - sca >= margin: side, moved = 1, moved + 1
            elif side == 1 and sca - scb >= margin: side, moved = 0, moved + 1
        out[side].append(p)
    if not moved: return mda, mdb
    na, nb = "\n\n".join(out[0]), "\n\n".join(out[1])
    L = lambda m: len(norm(m))
    before = abs(L(mda) - len(ta)) + abs(L(mdb) - len(tb)); after = abs(L(na) - len(ta)) + abs(L(nb) - len(tb))
    if after > 0.5 * before or abs(L(na) - L(mda)) < 500: return mda, mdb   # a real spill makes both page lengths agree with Paddle's; duplicates/extras do not
    return na, nb


def reorder(md, stem, min_match=0.7):
    """Re-sequence our body paragraphs by PaddleOCR-VL's block order (its layout model predicts reading order). Furniture and
    unmatched paragraphs keep their slots."""
    bl = [b for b in (blocks(stem) or []) if b["block_label"] not in IMG and b["block_label"] not in FURN and len(norm(b["block_content"] or "")) >= 10]
    ps = paras(md)
    if len(bl) < 3 or len(ps) < 3: return md
    bn = [norm(re.sub(r"<[^>]+>", " ", b["block_content"])) for b in bl]
    slot, key = [], []
    for i, p in enumerate(ps):
        n = norm(re.sub(r"<[^>]+>", " ", p))
        if len(n) < 10: continue
        sc = [fuzz.partial_ratio(n[:200], t[:400]) if len(t) >= len(n[:200]) else fuzz.partial_ratio(t[:200], n) for t in bn]
        j = max(range(len(bl)), key=lambda z: sc[z])
        if sc[j] >= 80: slot.append(i); key.append(j)
    if len(slot) < 3 or len(slot) < min_match * len([p for p in ps if len(norm(p)) >= 10]): return md
    order = sorted(range(len(slot)), key=lambda t: (key[t], slot[t]))
    new = list(ps)
    for dst, t in zip(slot, order): new[dst] = ps[slot[t]]
    return "\n\n".join(new)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--split", default="dev")
    ap.add_argument("--rules", default="figdrop"); ap.add_argument("--T", type=float, default=0.4)
    a = ap.parse_args(); rules = a.rules.split(",")
    rows = {(r["document_id"], r["page"]): r for r in map(json.loads, open(a.src, encoding="utf-8"))}
    size = {}
    for (subj, doc), pages in list_pages(a.split).items():
        for pg, path in pages: size[(doc, pg)] = Image.open(path).size
    changed = {"figdrop": 0, "spill": 0, "reorder": 0}
    if "spill" in rules:
        for (subj, doc), pages in list_pages(a.split).items():
            for w in windows(pages, 2):
                if len(w) < 2: continue
                (pa, _), (pb, _) = w; ka, kb = (doc, pa), (doc, pb)
                if ka in rows and kb in rows:
                    na, nb = spill(rows[ka]["markdown"], rows[kb]["markdown"], f"{doc}_{pa}", f"{doc}_{pb}")
                    if na != rows[ka]["markdown"] or nb != rows[kb]["markdown"]:
                        changed["spill"] += 1; rows[ka] = {**rows[ka], "markdown": na}; rows[kb] = {**rows[kb], "markdown": nb}
    if "figdrop" in rules:
        for k, r in rows.items():
            new = figdrop(r["markdown"], f"{k[0]}_{k[1]}", size[k], a.T)
            if new != r["markdown"]: changed["figdrop"] += 1; rows[k] = {**r, "markdown": new}
    if "reorder" in rules:
        for k, r in rows.items():
            new = reorder(r["markdown"], f"{k[0]}_{k[1]}")
            if new != r["markdown"]: changed["reorder"] += 1; rows[k] = {**r, "markdown": new}
    with open(a.dst, "w", encoding="utf-8") as f:
        for k in sorted(rows): f.write(json.dumps(rows[k], ensure_ascii=False) + "\n")
    print("pages changed:", changed, "->", a.dst)

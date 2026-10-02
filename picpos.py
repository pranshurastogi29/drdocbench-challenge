"""Where on the page does each of our paragraphs sit? Locate it via OCR lines (runs/ocr_lines.jsonl, from ocr_lines.py) and measure how
much of it lies inside picture regions: PaddleOCR-VL image/chart boxes (label-free, usable on test) and, on dev, the reference's own
`figure` boxes (an upper bound for the position signal).

  from picpos import page_positions
"""
import glob
import json
import os

from rapidfuzz import fuzz

from paradrop import KEEP, paras, wn

ROOT = os.path.dirname(os.path.abspath(__file__))
PIC = ("image", "chart", "header_image", "footer_image")
CAP = ("figure_title", "vision_footnote", "chart_title", "figure_caption")
_OCR = None


def ocr():
    global _OCR
    if _OCR is None:
        _OCR = {}
        f = os.path.join(ROOT, "runs", "ocr_lines.jsonl")
        if os.path.exists(f):
            for l in open(f):
                r = json.loads(l); _OCR[r["stem"]] = r
    return _OCR


def paddle_boxes(stem):
    f = os.path.join(ROOT, "kaggle", "results", "paddle", "out", stem, f"{stem}_res.json")
    if not os.path.exists(f):
        return [], []
    j = json.load(open(f)); W, H = j["width"], j["height"]
    nb = lambda b: [b[0] / W, b[1] / H, b[2] / W, b[3] / H]
    L = j.get("parsing_res_list", [])
    return [nb(b["block_bbox"]) for b in L if b["block_label"] in PIC], [nb(b["block_bbox"]) for b in L if b["block_label"] in CAP]


def gt_figures(stem):
    doc, pg = stem.rsplit("_", 1)
    f = glob.glob(os.path.join(ROOT, "data", "dev", "*", doc, "json", f"{doc}_page_{pg}.json"))
    if not f:
        return None
    j = json.load(open(f[0]))
    if not j:
        return []
    W, H = j[0]["page_info"]["width"], j[0]["page_info"]["height"]
    out = []
    for b in j[0]["layout_dets"]:
        if b["category_type"] == "figure":
            xs, ys = b["poly"][0::2], b["poly"][1::2]
            out.append([min(xs) / W, min(ys) / H, max(xs) / W, max(ys) / H])
    return out


def inside(box, regions):
    """Fraction of `box`'s area covered by the union-approximation (max single overlap) of `regions`."""
    a = max(1e-9, (box[2] - box[0]) * (box[3] - box[1]))
    best = 0.0
    for r in regions:
        w = max(0, min(box[2], r[2]) - max(box[0], r[0])); h = max(0, min(box[3], r[3]) - max(box[1], r[1]))
        best = max(best, w * h / a)
    return best


def near_caption(region, caps, gap=0.08):
    """A caption block directly above/below (or inside) the picture region."""
    for c in caps:
        hx = min(region[2], c[2]) - max(region[0], c[0]) > 0
        if hx and (abs(c[1] - region[3]) < gap or abs(region[1] - c[3]) < gap or inside(c, [region]) > 0.5):
            return True
    return False


def page_positions(md, stem):
    """{para_idx: dict(n_lines, in_pic, in_capped_pic, in_gt_fig, pic_frac_big)} for candidate paragraphs of our page."""
    o = ocr().get(stem)
    if not o:
        return {}
    P = paras(md); pics, caps = paddle_boxes(stem); gtf = gt_figures(stem)
    cand = {i: wn(p) for i, p in enumerate(P) if not KEEP.match(p) and len(wn(p)) >= 8}
    assign = {i: [] for i in cand}
    for ln in o["lines"]:
        t = wn(ln["text"])
        if len(t) < 4:
            continue
        best, bi = 0, None
        for i, w in cand.items():
            s = fuzz.partial_ratio(t, w) if len(t) <= len(w) else 0
            if s > best:
                best, bi = s, i
        if bi is not None and best >= 80:
            assign[bi].append(ln["box"])
    capped = [r for r in pics if near_caption(r, caps)]
    out = {}
    for i, boxes in assign.items():
        if not boxes:
            continue
        m = lambda R: sum(inside(b, R) for b in boxes) / len(boxes)
        out[i] = dict(n_lines=len(boxes), in_pic=m(pics), in_capped_pic=m(capped),
                      in_gt_fig=m(gtf) if gtf is not None else None,
                      pic_frac_big=max(((r[2] - r[0]) * (r[3] - r[1]) for r in pics), default=0))
    return out

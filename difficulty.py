"""Label-free page-difficulty features (computable on dev AND test) + a model that predicts the per-page overall score."""
import json, re, csv, collections
from rapidfuzz import fuzz
from paddle_ingest import blocks

nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]
alnum = lambda s: len(re.sub(r"[\W_]+", "", s))
FEATS = ["agree", "sim_paddle", "len_ratio", "paras", "paddle_blocks", "p_text", "p_table", "p_image", "p_formula", "p_furn", "p_title",
         "img_area", "has_table", "empty", "paddle_empty", "log_len", "paras_ratio", "width", "height", "min_sim"]


def page_features(stem, texts, pick_name, paddle_md):
    """texts: {run: markdown} for the candidate runs on this page (incl. 'paddle'); pick_name: chosen run."""
    names = list(texts)
    sims = {(a, b): fuzz.ratio(nz(texts[a]), nz(texts[b])) for i, a in enumerate(names) for b in names[i + 1:]}
    agree = sum(sims.values()) / max(1, len(sims))
    md = texts[pick_name]
    others = [v for (a, b), v in sims.items() if pick_name in (a, b)]
    bl = blocks(stem) or []
    W = H = 1
    lab = collections.Counter(b["block_label"] for b in bl)
    area = 0
    for b in bl:
        x1, y1, x2, y2 = b["block_bbox"]; W = max(W, x2); H = max(H, y2)
        if b["block_label"] in ("image", "chart"): area += max(0, (x2 - x1) * (y2 - y1))
    n = max(1, len(bl))
    paras = len([p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()])
    pm = alnum(paddle_md)
    return {"agree": agree, "sim_paddle": fuzz.ratio(nz(md), nz(paddle_md)), "len_ratio": min(4.0, alnum(md) / max(1, pm)),
            "paras": paras, "paddle_blocks": len(bl),
            "p_text": (lab["text"] + lab["reference_content"] + lab["content"]) / n, "p_table": lab["table"] / n, "p_image": (lab["image"] + lab["chart"]) / n,
            "p_formula": lab["display_formula"] / n, "p_furn": (lab["header"] + lab["footer"] + lab["number"]) / n,
            "p_title": (lab["paragraph_title"] + lab["doc_title"]) / n, "img_area": area / (W * H), "has_table": int("<table" in md),
            "empty": int(not md.strip()), "paddle_empty": int(not bl), "log_len": __import__("math").log1p(alnum(md)),
            "paras_ratio": min(6.0, paras / max(1, len(bl))), "width": W, "height": H, "min_sim": min(others) if others else 100}

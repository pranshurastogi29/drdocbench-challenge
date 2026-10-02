"""Whole-page fallback to PaddleOCR-VL when our vision model transcribed far less text than Paddle found.

Why: a book scanned as sideways two-page spreads (dev Psychology 6acfa608) makes the vision model read only one of the two pages
(2.5k of 5.1k reference characters) while Paddle reads both (5.0k). All four of our model runs miss the same half, so the medoid vote
cannot catch it. Rule: if words(ours) < ratio * words(paddle), emit Paddle's page.

  python pagefallback.py SRC DST --paddle runs/paddle_dev.jsonl --ratio 0.7
"""
import argparse, json, re

W = lambda s: len(re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s)))


def fallback(ours, paddle, ratio=0.7, min_paddle=400):
    p = W(paddle or "")
    return paddle if p >= min_paddle and W(ours) < ratio * p else ours


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--paddle", default="runs/paddle_dev.jsonl")
    ap.add_argument("--ratio", type=float, default=0.7); ap.add_argument("--min-paddle", type=int, default=400)
    a = ap.parse_args()
    pad = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(a.paddle, encoding="utf-8"))}
    n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            m = fallback(r["markdown"], pad.get((r["document_id"], r["page"])), a.ratio, a.min_paddle)
            n += m != r["markdown"]
            f.write(json.dumps({**r, "markdown": m}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

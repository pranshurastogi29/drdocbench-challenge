"""Layout-block snapping: re-segment OUR page Markdown so its paragraph boundaries follow PaddleOCR-VL's layout blocks.
Our text, our reading order and our wording are kept; only blank-line boundaries move.
  - a paragraph that contains two or more Paddle text blocks is SPLIT between them
  - consecutive paragraphs that together make up one Paddle block are MERGED
Tables, display math and code fences are never touched.

  python snap.py runs/dev_all_v7_final.jsonl runs/dev_all_v7_snap.jsonl [--gate 2]
"""
import argparse
import json
import re

from rapidfuzz import fuzz

from paddle_ingest import blocks

TEXTLIKE = {"text", "paragraph_title", "doc_title", "figure_title", "vision_footnote", "reference_content", "content", "abstract"}
MIN_LEN = 20
THRESH = 88


def low(s):  # lower-case without changing string length, so alignment offsets stay valid
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in s)


def block_texts(stem):
    bl = blocks(stem) or []
    return [re.sub(r"\s+", " ", b["block_content"]).strip() for b in bl if b["block_label"] in TEXTLIKE and len(b["block_content"].strip()) >= MIN_LEN]


def protected(p):
    return "<table" in p or p.lstrip().startswith(("$$", "```")) or p.lstrip().startswith("![")


def find_span(needle, hay):
    """Best (score, start, end) of `needle` inside `hay`; long needles are anchored on their first and last 100 chars."""
    n, h = low(needle), low(hay)
    if len(n) <= 220:
        al = fuzz.partial_ratio_alignment(n, h)
        return (al.score, al.dest_start, al.dest_end) if al else (0, 0, 0)
    a = fuzz.partial_ratio_alignment(n[:100], h); b = fuzz.partial_ratio_alignment(n[-100:], h)
    if not a or not b or min(a.score, b.score) < 90 or b.dest_end <= a.dest_start:
        return (0, 0, 0)
    return (min(a.score, b.score), a.dest_start, b.dest_end)


def snap(md, stem, mode="both"):
    btxt = block_texts(stem)
    paras = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    if not btxt or len(paras) < 1:
        return md
    # ---- merges: a block that is not inside any single paragraph but is inside two or three consecutive ones
    for _ in range(4 if mode in ("both", "merge") else 0):
        changed = False
        for t in btxt:
            if any(not protected(p) and find_span(t, p)[0] >= THRESH and (find_span(t, p)[2] - find_span(t, p)[1]) >= 0.85 * len(t) for p in paras):
                continue                                             # already lives in one paragraph
            for width in (2, 3):
                done = False
                for j in range(len(paras) - width + 1):
                    grp = paras[j:j + width]
                    if any(protected(p) for p in grp):
                        continue
                    joined = "\n".join(grp)
                    sc, s, e = find_span(t, joined)
                    first_end = len(grp[0])
                    if sc >= THRESH and s < first_end - 5 and e > first_end + 1 and (e - s) >= 0.85 * len(t):   # the block really straddles the boundary
                        paras[j:j + width] = [" ".join(x.strip() for x in grp)]
                        changed = done = True
                        break
                if done:
                    break
        if not changed:
            break
    # ---- splits: a paragraph holding two or more blocks
    out = []
    for p in paras:
        if protected(p):
            out.append(p); continue
        spans = []
        for t in btxt:
            sc, s, e = find_span(t, p)
            if sc >= THRESH and (e - s) >= 0.85 * len(t) and (e - s) < 0.97 * len(p):
                spans.append((s, e))
        spans.sort(); keep = []
        for s, e in spans:                                            # drop overlapping spans
            if not keep or s >= keep[-1][1] - 2:
                keep.append((s, e))
        if len(keep) < 2 or mode == "merge":
            out.append(p); continue
        cuts = [0] + [(keep[i][1] + keep[i + 1][0]) // 2 for i in range(len(keep) - 1)] + [len(p)]
        pieces = [p[cuts[i]:cuts[i + 1]].strip() for i in range(len(cuts) - 1)]
        out.extend(x for x in pieces if x)
    return "\n\n".join(out)


def n_paddle(stem):
    return len([b for b in (blocks(stem) or []) if b["block_label"] not in ("image", "chart", "header_image", "footer_image", "seal", "header", "footer", "number")])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--gate", type=int, default=0); ap.add_argument("--mode", default="both", choices=["both", "split", "merge"])
    a = ap.parse_args(); n = ch = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for line in open(a.src, encoding="utf-8"):
            r = json.loads(line); stem = f"{r['document_id']}_{r['page']}"; md = r["markdown"]
            do = True
            if a.gate:
                O = len([p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]); do = abs(O - n_paddle(stem)) >= a.gate
            new = snap(md, stem, a.mode) if do else md
            n += 1; ch += new != md; r["markdown"] = new; f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{n} pages, {ch} changed -> {a.dst}")

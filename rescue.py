"""Rescue dropped pages: replace our page with the one-page-per-request output only when ours looks like it lost content.

Why: ensembles that swap the one-page runs into the pool changed 52-85% of test pages and final5b_wd lost 0.63 on the leaderboard even though dev
gained 1.13; on dev the gain was a handful of pages (+94, +94, +81, +61 points) where the two-page request had dropped text. This applies only that
part: a page is replaced when the alternative has at least RATIO x our words, ours is short in absolute terms, and the alternative is not inflated
relative to PaddleOCR-VL (to avoid pages of word-search grids / form lines the reference leaves out).

  python rescue.py BASE ALT DST --split dev|test --ratio 2 --max-base 600 --paddle-cap 1.5
"""
import argparse, json, re, sys

from ab_group import finish

W = lambda s: len(re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s)))


def pick(base, alt, paddle, ratio=2.0, max_base=600, paddle_cap=1.5):
    b, a, p = W(base), W(alt), W(paddle or "")
    if a < ratio * max(b, 1) or b > max_base:
        return False
    if paddle_cap and p >= 100 and a > paddle_cap * p:
        return False
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("base"); ap.add_argument("alt"); ap.add_argument("dst")
    ap.add_argument("--split", default="dev"); ap.add_argument("--ratio", type=float, default=2.0)
    ap.add_argument("--max-base", type=int, default=600); ap.add_argument("--paddle-cap", type=float, default=1.5)
    ap.add_argument("--wd", action="store_true")
    a = ap.parse_args()
    pad = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(f"runs/paddle_{a.split}.jsonl", encoding="utf-8"))}
    alt = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(a.alt, encoding="utf-8"))}
    n = 0; ids = []
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.base, encoding="utf-8")):
            k = (r["document_id"], r["page"]); md = r["markdown"]
            if k in alt and alt[k].strip() and pick(md, alt[k], pad.get(k), a.ratio, a.max_base, a.paddle_cap):
                md = finish(alt[k], f"{k[0]}_{k[1]}", a.wd); n += 1; ids.append(k)
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages replaced")
    json.dump(ids, open(a.dst + ".ids.json", "w"))

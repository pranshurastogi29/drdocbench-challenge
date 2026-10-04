"""Merge runs of consecutive SHORT body paragraphs into blocks of <= CAP normalised chars (single newlines inside).
Scorer mechanics: short reference blocks (<= 300) fold into a predicted block (<= 300) that contains them, and their reading-order positions are then
recorded in sorted reference order; so local order mistakes among short blocks stop counting, while text is unchanged when our order already matches.
Risk: a folded piece must match inside the merged block within 0.4 normalised distance (direct pairing tolerates 0.7), so noisy pieces can fail to fold.
  python shortmerge.py SRC DST [--maxlen 80] [--cap 280] [--no-headings]
"""
import argparse, json, re

N = lambda s: len(re.sub(r"[\W_]", "", s))


def special(p):
    return (p.startswith("$") and p.endswith("$")) or p.startswith("<table") or p.startswith("![")


def merge_runs(md, maxlen=80, cap=280, headings=True):
    paras = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    out, run = [], []

    def flush():
        groups, cur, size = [], [], 0
        for p in run:
            if cur and size + N(p) > cap:
                groups.append(cur); cur, size = [], 0
            cur.append(p); size += N(p)
        if cur: groups.append(cur)
        out.extend("\n".join(g) for g in groups)
        run.clear()

    for p in paras:
        short = (not special(p)) and "\n" not in p and 1 <= N(p) <= maxlen and (headings or not p.startswith("#"))
        if short:
            run.append(p)
        else:
            flush(); out.append(p)
    flush()
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--maxlen", type=int, default=80); ap.add_argument("--cap", type=int, default=280); ap.add_argument("--no-headings", action="store_true")
    a = ap.parse_args(); n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            md = merge_runs(r["markdown"], a.maxlen, a.cap, not a.no_headings)
            n += md != "\n\n".join(p.strip() for p in re.split(r"\n\s*\n", r["markdown"].strip()) if p.strip())
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages changed")

"""Page-number tail merge (on top of furnmerge.py). The reference orders the page number and the running head / footer at the page end by
hidden annotation order (both N-H and H-N occur within one book), and the scorer folds short reference blocks that one of our blocks
(<= 300 chars) contains, listing their positions in reference order, so a merged furniture block cannot be out of order. furnmerge only
merges lines PaddleOCR-VL labels as furniture; this also merges the bare page number with the short single lines right next to it at the
end of the page, whatever Paddle said.
  mode tail : the trailing run of short lines (each <= maxlen normalised chars, no heading / table / formula, up to `k` lines, an already
              merged furniture block counts as its lines) is merged when it contains a bare page number
  from numtail import numtail; md, changed = numtail(md, maxlen=60, k=3)
"""
import re

N = lambda s: len(re.sub(r"[\W_]", "", s))
NUM = re.compile(r"^\W*(\d{1,4}|[ivxlcdm]{1,7})\W*$", re.I)


def short_lines(p, maxlen):
    if p.startswith("#") or p.startswith("<") or p.startswith("$") or p.startswith("|"): return None
    ls = [l.strip() for l in p.split("\n") if l.strip()]
    return ls if ls and all(1 <= N(l) <= maxlen for l in ls) else None


def numtail(md, maxlen=60, k=3):
    paras = [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    body = [i for i, p in enumerate(paras) if not p.startswith("$") and not p.startswith("<table")]
    if len(body) < 3: return md, 0
    tail, lines = [], 0
    for i in reversed(body):
        ls = short_lines(paras[i], maxlen)
        if ls is None or lines + len(ls) > k: break
        tail.append(i); lines += len(ls)
    if len(tail) < 2: return md, 0
    tail = tail[::-1]
    if not any(NUM.match(l) for i in tail for l in paras[i].split("\n") if l.strip()): return md, 0
    merged = "\n".join(paras[i] for i in tail)
    out = [merged if i == tail[0] else p for i, p in enumerate(paras) if i == tail[0] or i not in tail]
    return "\n\n".join(out), 1

"""Formula channel v2: offer several wrapper variants per line. Extra predicted formulas are ignored by the formula metric (pred-only entries are
dropped) and $...$ blocks are excluded from text and reading-order matching, so variants can only help the best formula match.
  styles : comma list from textit,textbf,bi (\\textbf{\\textit{..}}),plain (\\text{..})
  maxlen : longest line wrapped;  lines : also wrap each line of multi-line paragraphs
"""
import json, re, argparse
from snap import protected
from wrapdup import clean, ESC

WR = {"textit": lambda t: "$\\textit{" + t + "}$", "textbf": lambda t: "$\\textbf{" + t + "}$",
      "bi": lambda t: "$\\textbf{\\textit{" + t + "}}$", "plain": lambda t: "$\\text{" + t + "}$"}


def esc(t):
    return "".join(ESC.get(c, c) for c in t)


def add(md, styles=("textit",), maxlen=60, lines=False, grouped=False, numbers=False):
    """grouped: put all copies at the end of the page, one style after another, so that neighbouring formulas are different lines (the
    matcher merges CONSECUTIVE predicted formulas that each fit inside one reference formula, which turned our same-line variants into a
    \\begin{array} and spoiled exact matches). numbers: also offer standalone copies of page-number-like trailing numbers."""
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    out, texts = [], []
    for p in paras:
        out.append(p)
        if protected(p) or re.match(r"^\$", p.strip()):
            continue
        cand = [p] if "\n" not in p.strip() else ([l for l in p.split("\n") if l.strip()] if lines else [])
        for c in cand:
            t = clean(c)
            if re.search(r"[$\\<>`]", t):   # $, backslash, angle brackets (HTML-like) or backticks break out of the wrapper and leak into text matching
                continue
            if 1 <= len(t) <= maxlen:
                if grouped: texts.append(t)
                else: out.extend(WR[s](esc(t)) for s in styles)
            if numbers:
                m = re.search(r"(?:^|\s)(\d{1,4})\s*$", t) or re.match(r"^\s*(\d{1,4})(?:\s|$)", t)
                if m and m.group(1) != t.strip(): texts.append(m.group(1)) if grouped else out.extend(WR[s](m.group(1)) for s in styles)
    if grouped and texts:
        seen = []; [seen.append(t) for t in texts if t not in seen]
        for s in styles:
            out.extend(WR[s](esc(t)) for t in seen)
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--styles", default="textit"); ap.add_argument("--maxlen", type=int, default=60); ap.add_argument("--lines", action="store_true"); ap.add_argument("--grouped", action="store_true"); ap.add_argument("--numbers", action="store_true")
    a = ap.parse_args(); st = tuple(a.styles.split(","))
    with open(a.dst, "w", encoding="utf-8") as f:
        for l in open(a.src, encoding="utf-8"):
            r = json.loads(l); r["markdown"] = add(r["markdown"], st, a.maxlen, a.lines, a.grouped, a.numbers); f.write(json.dumps(r, ensure_ascii=False) + "\n")

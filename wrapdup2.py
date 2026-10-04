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


def add(md, styles=("textit",), maxlen=60, lines=False):
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    out = []
    for p in paras:
        out.append(p)
        if protected(p) or re.match(r"^\$", p.strip()):
            continue
        cand = [p] if "\n" not in p.strip() else ([l for l in p.split("\n") if l.strip()] if lines else [])
        for c in cand:
            t = clean(c)
            if 1 <= len(t) <= maxlen:
                out.extend(WR[s](esc(t)) for s in styles)
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--styles", default="textit"); ap.add_argument("--maxlen", type=int, default=60); ap.add_argument("--lines", action="store_true")
    a = ap.parse_args(); st = tuple(a.styles.split(","))
    with open(a.dst, "w", encoding="utf-8") as f:
        for l in open(a.src, encoding="utf-8"):
            r = json.loads(l); r["markdown"] = add(r["markdown"], st, a.maxlen, a.lines); f.write(json.dumps(r, ensure_ascii=False) + "\n")

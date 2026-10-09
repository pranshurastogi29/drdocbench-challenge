"""Formula channel v3: wrapper versions the references use that the v2 channel (wrapdup2.py, chan=1W4) does not offer yet.
  multi   : a whole multi-line paragraph as ONE formula (lists, addresses, verse: the references wrap such blocks whole, e.g.
            $\\underline{\\textit{1 round lettuce ... }}$), lines joined by a space (LaTeX renders a newline as a space)
  windows : 2..`maxw` consecutive short single-line paragraphs (each <= `maxline` chars) as ONE formula (the reference keeps as one block
            lines our model wrote as separate paragraphs)
  nested  : single lines and paragraphs in nested styles: \\underline{\\textit{}}, \\textit{\\underline{}}, \\textbf{\\underline{}},
            \\underline{} without \\text
All appended at the page end, grouped by style (consecutive formulas are different texts), deduplicated against each other. Extra
predicted formulas are ignored by the formula metric and $...$ blocks are excluded from text and reading-order matching.
  python wrapdup3.py SRC DST [--multi textit,textbf,plain,ul,uit,itu] [--windows ...] [--nested uit,itu,bu,u0] [--maxw 4] [--maxline 80]
"""
import argparse, json, re
from snap import protected
from wrapdup import clean, ESC

STY = {"textit": ("\\textit{", "}"), "textbf": ("\\textbf{", "}"), "bi": ("\\textbf{\\textit{", "}}"), "plain": ("\\text{", "}"),
       "ul": ("\\underline{\\text{", "}}"), "uit": ("\\underline{\\textit{", "}}"), "itu": ("\\textit{\\underline{", "}}"),
       "bu": ("\\textbf{\\underline{", "}}"), "u0": ("\\underline{", "}"), "sc": ("\\textsc{", "}")}
BAD = re.compile(r"[$\\<>`]")
esc = lambda t: "".join(ESC.get(c, c) for c in t)
wrap = lambda s, t: "$" + STY[s][0] + esc(t) + STY[s][1] + "$"


def add(md, multi=(), windows=(), nested=(), maxw=4, maxline=80):
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    body = [p for p in paras if not (protected(p) or p.strip().startswith("$") or p.strip().startswith("<"))]
    M, Wn, S = [], [], []
    run = []
    def flush():
        for n in range(2, maxw + 1):
            for i in range(len(run) - n + 1): Wn.append(" ".join(run[i:i + n]))
        run.clear()
    for p in body:
        lines = [clean(l) for l in p.split("\n") if l.strip()]
        lines = [l for l in lines if l and not BAD.search(l)]
        if not lines: flush(); continue
        if len(lines) > 1:
            flush(); M.append(" ".join(lines)); S.extend(lines)
        else:
            S.append(lines[0])
            if len(lines[0]) <= maxline: run.append(lines[0])
            else: flush()
    flush()
    S.extend(M)
    out, seen = list(paras), set()
    for styles, texts in ((multi, M), (windows, Wn), (nested, S)):
        for s in styles:
            for t in texts:
                f = wrap(s, t)
                if f not in seen: seen.add(f); out.append(f)
    return "\n\n".join(out), len(seen)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--multi", default="textit,textbf,plain,ul,uit,itu"); ap.add_argument("--windows", default="textit,textbf,plain,ul")
    ap.add_argument("--nested", default="uit,itu,bu,u0"); ap.add_argument("--maxw", type=int, default=4); ap.add_argument("--maxline", type=int, default=80)
    a = ap.parse_args(); sp = lambda x: tuple(s for s in x.split(",") if s)
    n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for l in open(a.src, encoding="utf-8"):
            r = json.loads(l); r["markdown"], k = add(r["markdown"], sp(a.multi), sp(a.windows), sp(a.nested), a.maxw, a.maxline); n += k
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} formula copies added")

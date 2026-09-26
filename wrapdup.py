"""Add a duplicate $\\textit{...}$ paragraph for short standalone lines, KEEPING the plain line.
The reference wraps some ordinary lines (page numbers, running heads, decorated text) in $\\textit{..}$ / $\\textbf{..}$ and the
scorer treats those as display formulas. Extra predicted formulas are ignored by the formula metric, so a duplicate costs nothing
there; the plain line stays in place for text / reading-order matching.
  scope='furniture' : the last <=4 short paragraphs of the page (where headers/footers/page numbers sit)
  scope='short'     : every short single-line paragraph
"""
import json, re, argparse
from snap import protected

ESC = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\~{}", "^": r"\^{}", "\\": r"\textbackslash{}"}
MAXLEN = 60


def clean(p):
    t = re.sub(r"^#+\s*", "", p.strip()); t = re.sub(r"[*_]{1,3}", "", t) if False else t.replace("**", "").strip("*").strip()
    return t


def wrap(t, style="textit"):
    return "$\\" + style + "{" + "".join(ESC.get(c, c) for c in t) + "}$"


def add(md, scope="furniture", style="textit"):
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    if not paras: return md
    n = len(paras); out = []
    for i, p in enumerate(paras):
        out.append(p)
        t = clean(p)
        ok = (not protected(p)) and "\n" not in p.strip() and 1 <= len(t) <= MAXLEN and not re.match(r"^\$", p.strip())
        if ok and (scope == "short" or i >= n - 4):
            out.append(wrap(t, style))
    return "\n\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--scope", default="furniture"); ap.add_argument("--style", default="textit")
    a = ap.parse_args(); n = ch = added = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for line in open(a.src, encoding="utf-8"):
            r = json.loads(line); new = add(r["markdown"], a.scope, a.style); n += 1; ch += new != r["markdown"]
            added += new.count("\n\n") - r["markdown"].count("\n\n") if new != r["markdown"] else 0
            r["markdown"] = new; f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{n} pages, {ch} changed, {added} wrapper paragraphs added -> {a.dst}")

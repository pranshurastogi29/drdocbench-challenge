"""Styled lines in the references' own LaTeX convention, IN PLACE (no copies): a paragraph that is entirely italic / bold / bold-italic in our
Markdown (*x*, **x**, ***x***) is written once as $\\textit{x}$ / $\\textbf{x}$ / $\\textbf{\\textit{x}}$ instead, the form the test
references use for styled lines (the formula copies showed test references are rich in such wrappers). Multi-line paragraphs whose every
line is styled become one such formula per line (the matcher joins consecutive formulas that fit inside one reference formula).
Headings, tables, formulas, lists and partly styled paragraphs are left alone; nothing is duplicated.
  from inplace import convert; md, n = convert(md)
"""
import re
from snap import protected
from wrapdup import clean
from wrapdup2 import WR, esc

STYLED = [("bi", re.compile(r"^\*\*\*(?!\*)(.+?)(?<!\*)\*\*\*$")), ("textbf", re.compile(r"^\*\*(?!\*)(.+?)(?<!\*)\*\*$")),
          ("textit", re.compile(r"^\*(?!\*)(.+?)(?<!\*)\*$")), ("textit", re.compile(r"^_(?!_)(.+?)(?<!_)_$"))]


def wrap_line(line, maxlen=10 ** 6):
    s = line.strip()
    for style, rx in STYLED:
        m = rx.match(s)
        if m:
            t = clean(m.group(1)).strip()
            if t and len(t) <= maxlen and not re.search(r"[$\\<>`*]", t): return WR[style](esc(t))
            return None
    return None


def convert(md, maxlen=10 ** 6):
    out, n = [], 0
    for p in re.split(r"\n\s*\n", md.strip()):
        q = p.strip()
        if not q or protected(q) or q.startswith("#") or q.startswith("$") or q.startswith("<") or re.match(r"^([-*+]|\d+[.)])\s", q):
            out.append(p); continue
        lines = [l for l in q.split("\n") if l.strip()]
        w = [wrap_line(l, maxlen) for l in lines]
        if all(w): out.extend(w); n += len(w)
        else: out.append(p)
    return "\n\n".join(out), n

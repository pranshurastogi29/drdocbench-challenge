"""Symbol channel for the formula score: the Markdown references write many page symbols as their own small formulas (\\bullet, \\dotfill,
^*, ^\\circ, \\copyright, \\frac{1}{2}, roman numerals, shapes, superscript footnote numbers, blanks) -- 2,200 of the 2,768 dev reference
formulas. CDM averages over reference formulas and our unmatched formulas are dropped, while formulas never enter text / order matching,
so one formula copy per symbol occurrence on our page, in the reference's LaTeX, can only add matches.
  from symchan import add_symbols; md = add_symbols(md)
"""
import re

SYM = {"•": r"\bullet", "●": r"\bullet", "▪": r"\blacksquare", "■": r"\blacksquare", "□": r"\square", "☐": r"\square", "◆": r"\blacklozenge",
       "◇": r"\diamond", "♦": r"\blacklozenge", "▶": r"\triangleright", "►": r"\triangleright", "▸": r"\triangleright", "▷": r"\triangleright",
       "★": r"\bigstar", "☆": r"\star", "©": r"\copyright", "°": r"^\circ", "×": r"\times", "½": r"\frac{1}{2}", "¼": r"\frac{1}{4}",
       "¾": r"\frac{3}{4}", "⅓": r"\frac{1}{3}", "⅔": r"\frac{2}{3}", "⅛": r"\frac{1}{8}", "✓": r"\checkmark", "✔": r"\checkmark", "†": r"^\dagger",
       "‡": r"^\ddagger", "§": r"\S", "¶": r"\P", "±": r"\pm", "÷": r"\div", "→": r"\rightarrow", "←": r"\leftarrow", "↑": r"\uparrow",
       "↓": r"\downarrow", "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx", "∞": r"\infty", "α": r"\alpha", "β": r"\beta", "γ": r"\gamma",
       "δ": r"\delta", "μ": r"\mu", "π": r"\pi", "σ": r"\sigma", "Ω": r"\Omega", "Γ": r"\Gamma", "Δ": r"\Delta", "θ": r"\theta", "λ": r"\lambda"}
SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
ROMAN = re.compile(r"(?<![A-Za-z])(I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV|XX)(?![A-Za-z])")


def symbols(md, roman=True, cap=60):
    out = []
    text = re.sub(r"<table.*?</table>", " ", md, flags=re.S)
    text = "\n\n".join(p for p in re.split(r"\n\s*\n", text) if not p.strip().startswith("$") and not p.strip().startswith("\\["))
    for ch, tex in SYM.items(): out += [tex] * min(text.count(ch), cap)
    out += [r"\bullet"] * min(len(re.findall(r"(?m)^\s*[-*+]\s+\S", text)), cap)                       # markdown bullet list items
    out += [r"\dotfill"] * min(len(re.findall(r"\.{4,}|(?:\. ){3,}\.|…{2,}", text)), cap)            # dot leaders
    out += [r"\underline{\hspace{1em}}"] * min(len(re.findall(r"_{4,}", text)), cap)                 # blanks
    stars = len(re.findall(r"(?<=\w)\*(?!\*)|(?<!\*)\*(?=\s)", text)); out += [r"^*"] * min(stars, cap) + ["*"] * min(stars, cap)
    for m in re.findall(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", text): d = m.translate(SUP); out.append("^" + (d if len(d) == 1 else "{" + d + "}"))
    for m in re.findall(r"<sup>\s*([0-9a-z*]{1,3})\s*</sup>|\^\{?([0-9]{1,3})\}?", text):
        d = m[0] or m[1]; out.append("^" + (d if len(d) == 1 else "{" + d + "}"))
    if roman:
        for m in ROMAN.findall(text)[:cap]: out.append(r"\mathrm{" + m + "}")
    return out


def add_symbols(md, roman=True):
    s = symbols(md, roman)
    return md.rstrip() + ("\n\n" + "\n\n".join(f"${t}$" for t in s) if s else "")

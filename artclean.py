"""Markup artifacts in our text paragraphs that the scorer counts as letters: HTML entities (&quot; -> 'quot'), <br> ('br'), inline tags
(<strong>, <em>, <span ...>: 'strong', 'em', 'span'), <sup>/<sub>. The scorer keeps only \\w (and CJK) after a LaTeX-to-Unicode pass, so these
add or remove characters. Tables, $-formulas and code fences are left alone (scored as tables/formulas, or not at all).
"""
import html, re

TAGS = re.compile(r"</?(?:strong|em|b|i|u|span|font|small|big|mark|s|strike|del|ins|center|p|div)(?:\s[^>]*)?>", re.I)


def clean_para(p, entities=True, br=True, tags=True, supsub=False):
    if p.startswith("<table") or p.startswith("$") or p.startswith("```") or p.startswith("|"):
        return p
    if br: p = re.sub(r"\s*<br\s*/?>\s*", "\n", p)
    if tags: p = TAGS.sub("", p)
    if supsub: p = re.sub(r"</?su[pb]>", "", p)
    if entities and "&" in p: p = html.unescape(p).replace("\xa0", " ")
    return p


def artclean(md, **kw):
    ps = re.split(r"(\n\s*\n)", md)
    return "".join(clean_para(x, **kw) if i % 2 == 0 else x for i, x in enumerate(ps))


CJK = re.compile(r"[　-〿一-鿿＀-￯]+")


def cjk_glitch(md, max_share=0.05):
    """the free model sometimes drops a few Chinese words into an English page; remove CJK runs when they are < max_share of the page's letters"""
    letters = len(re.sub(r"[^\w]", "", md)); cjk = sum(len(m) for m in CJK.findall(md))
    if not cjk or cjk > max_share * max(1, letters): return md
    ps = re.split(r"(\n\s*\n)", md)
    return "".join(CJK.sub("", x) if i % 2 == 0 and not x.startswith("<table") and not x.startswith("$") else x for i, x in enumerate(ps))


if __name__ == "__main__":
    # python artclean.py SRC.zip DST.zip : entities/<br>/inline tags/<sup>,<sub> outside tables and formulas + CJK glitch runs on English pages
    import argparse, os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_submission import write_zip, zip_rows
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); a = ap.parse_args()
    N = lambda s: len(re.sub(r"[^\w一-鿿]", "", s))
    out = []; n = 0
    for r in zip_rows(a.src):
        md = cjk_glitch(artclean(r["markdown"], supsub=True))
        if md != r["markdown"]:
            n += 1; print(f'  {r["document_id"][:8]}_{r["page"]}: normalised chars {N(r["markdown"])} -> {N(md)}')
        out.append({**r, "markdown": md})
    write_zip(out, a.dst); print(f"{a.dst}: {n} pages changed")

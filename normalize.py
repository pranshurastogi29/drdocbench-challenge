"""Convention fixes learned from the reference Markdown (dev):
  quotes  : reference is ~96% straight double quotes, ~79% straight apostrophes -> curly -> straight; en dash -> hyphen
  heads   : reference uses only a single '#'  -> '##', '###' -> '#'
  titles  : PaddleOCR-VL title blocks -> make the matching paragraph start with '# '
"""
import re
from rapidfuzz import fuzz
from paddle_ingest import blocks
from reading_order import norm
from snap import protected

QMAP = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "„": '"', "–": "-"}
TRANS = str.maketrans(QMAP)


def quotes(md): return md.translate(TRANS)
def heads(md): return re.sub(r"(?m)^#{2,}[ \t]+", "# ", md)


def titles(md, stem):
    tt = [norm(b["block_content"]) for b in (blocks(stem) or []) if b["block_label"] in ("doc_title", "paragraph_title") and b["block_content"].strip()]
    tt = [t for t in tt if len(t) >= 3]
    if not tt: return md
    out = []
    for p in re.split(r"\n\s*\n", md.strip()):
        if p.strip() and not protected(p) and not p.lstrip().startswith("#") and "\n" not in p.strip():
            n = norm(p)
            if n and any(fuzz.ratio(n, t) >= 90 for t in tt): p = "# " + p.strip()
        out.append(p)
    return "\n\n".join(out)

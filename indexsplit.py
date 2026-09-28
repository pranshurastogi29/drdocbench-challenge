"""Split back-of-book index paragraphs: the model already puts one entry per single-newline LINE inside a paragraph, but the
reference wants each entry as its own blank-line-separated paragraph. Detected purely from the text (no Paddle dependency): a
paragraph whose internal lines mostly end in a page-number list (`, 123`, `123-45`, `123, 145-46;`) or a "See ..." cross-reference.

  python indexsplit.py runs/dev_all_final5.jsonl runs/dev_indexsplit.jsonl
"""
import json, re, sys

PAGENUM = re.compile(r"(?:,\s*\d{1,4}(?:[–\-]\d{1,4})?|[–\-]\d{1,4})+\s*;?\s*$")
SEEREF = re.compile(r"\bsee(?:\s+also)?\b[^.;]{0,60}$", re.I)


def is_entry_line(line):
    s = line.strip()
    if len(s) < 45:      # short author/citation-index entries ("Name, 125") are a different book convention: reference
        return False      # keeps many of those merged in one paragraph, so only split genuinely long index entries
    return bool(PAGENUM.search(s) or SEEREF.search(s))


def split_index(md):
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    out = []
    for p in paras:
        if "<table" in p or p.lstrip().startswith(("$$", "```", "![")):
            out.append(p); continue
        lines = p.split("\n")
        if len(lines) < 2:
            out.append(p); continue
        hits = sum(is_entry_line(l) for l in lines)
        if hits >= 2 and hits >= 0.6 * len(lines):     # most lines in this paragraph look like index entries
            out.extend(l.strip() for l in lines if l.strip())
        else:
            out.append(p)
    return "\n\n".join(out)


if __name__ == "__main__":
    n = tot = 0
    with open(sys.argv[2], "w", encoding="utf-8") as fo:
        for l in open(sys.argv[1], encoding="utf-8"):
            r = json.loads(l); new = split_index(r["markdown"]); tot += 1; n += new != r["markdown"]
            fo.write(json.dumps({**r, "markdown": new}, ensure_ascii=False) + "\n")
    print(f"{n} of {tot} pages changed -> {sys.argv[2]}")

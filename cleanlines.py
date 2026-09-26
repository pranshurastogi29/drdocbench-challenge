"""Drop standalone paragraphs that are only rule characters (____, ----, ....., ====): 0 in the dev reference, 73 in our output.
  python cleanlines.py SRC.jsonl DST.jsonl
"""
import json, re, sys
RULE = re.compile(r"[\s_\-.=*~•·]{4,}")


def clean(md):
    keep = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip() and not (RULE.fullmatch(p.strip()) and not re.fullmatch(r"[\s*]*", p.strip()))]
    return "\n\n".join(keep)


if __name__ == "__main__":
    n = tot = 0
    with open(sys.argv[2], "w", encoding="utf-8") as fo:
        for l in open(sys.argv[1], encoding="utf-8"):
            r = json.loads(l); new = clean(r["markdown"]); tot += 1; n += new != r["markdown"]
            fo.write(json.dumps({**r, "markdown": new}, ensure_ascii=False) + "\n")
    print(f"{n} of {tot} pages changed -> {sys.argv[2]}")

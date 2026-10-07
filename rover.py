"""Word-level consensus (ROVER) inside each paragraph of the selected page.
The selected page stays the skeleton: its paragraph split, order, tables, formulas and multi-line paragraphs are kept. Each body paragraph is
located in every other run (best fuzzy match on scorer-normalised text, similar length, as para_fuse.py does); every located version is
word-aligned to the skeleton paragraph (difflib on the scorer-visible characters of each word), and each word position takes the version that
a strict majority of ALL versions (skeleton included) agree on: a substitution, a deletion, or an insertion in the gap before it.
Where no strict majority exists the skeleton's word stays. Only the scorer-visible characters decide the vote; the surface form is the one
most of the winning voters wrote.
  from rover import rover; md, changed = rover(page_md, [other_run_md, ...])
"""
import collections, re
from difflib import SequenceMatcher
from rapidfuzz import fuzz
import Levenshtein
from para_fuse import paras, skip, W, HEAD

K = lambda t: re.sub(r"[\W_]", "", t)
MAXGAP = 1                                    # longer insertions / deletions are segmentation differences, not word errors
SIM = 0.75                                    # word substitutions: normalised similarity of the two spellings
similar = lambda a, b: 1 - Levenshtein.distance(a.lower(), b.lower()) / max(len(a), len(b)) >= SIM
MATH = re.compile(r"\$|\\\(|\\\[")


def vote_para(S, versions):
    """S: skeleton words; versions: list of word lists. Returns (new words, number of changed positions)."""
    n = 1 + len(versions); need = n // 2 + 1
    sub = [collections.Counter({K(w): 1}) for w in S]; surf = [collections.defaultdict(collections.Counter) for _ in S]
    for i, w in enumerate(S): surf[i][K(w)][w] += 1
    ins = [collections.Counter() for _ in range(len(S) + 1)]
    for O in versions:
        sm = SequenceMatcher(None, [K(w) for w in S], [K(w) for w in O], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            edge = i1 == 0 or i2 == len(S)          # a version that starts or ends elsewhere (paragraph split differently) abstains there
            if tag == "equal":
                for d in range(i2 - i1): sub[i1 + d][K(S[i1 + d])] += 1; surf[i1 + d][K(S[i1 + d])][O[j1 + d]] += 1
            elif tag == "replace" and i2 - i1 == j2 - j1:
                for d in range(i2 - i1): k = K(O[j1 + d]); sub[i1 + d][k] += 1; surf[i1 + d][k][O[j1 + d]] += 1
            elif tag == "delete" and not edge and i2 - i1 <= MAXGAP:
                for i in range(i1, i2): sub[i][None] += 1
            elif tag == "insert" and not edge and j2 - j1 <= MAXGAP:
                ins[i1][tuple(O[j1:j2])] += 1
    out, ch = [], 0
    for i in range(len(S) + 1):
        if ins[i]:
            t, c = ins[i].most_common(1)[0]
            if c >= need: out.extend(t); ch += 1
        if i == len(S): break
        k, c = sub[i].most_common(1)[0]
        if (c >= need and k != K(S[i]) and K(S[i]) and (k is None or (k.lower() != K(S[i]).lower() and similar(k, K(S[i]))))):
            # never vote on punctuation-only words or on case alone (small caps: the selected page's casing stays); a substitution must
            # be a near-spelling of the word (an OCR slip), never a different word (that means the voters matched another paragraph)
            ch += 1
            if k is None: continue
            out.append(surf[i][k].most_common(1)[0][0])
        else:
            out.append(S[i])
    return out, ch


def rover(skel, others, minsim=90, lenr=0.85, minw=8, minv=2):
    O = [[(HEAD.sub("", q), W(HEAD.sub("", q))) for q in paras(o) if not skip(q)] for o in others if o]
    out = []; changed = 0
    for p in paras(skel):
        if skip(p) or MATH.search(p): out.append(p); continue   # inline math: whitespace tokens would cut formulas apart
        m = HEAD.match(p); pre = m.group(1) if m else ""; body = p[len(pre):]; w = W(body)
        if len(w) < minw: out.append(p); continue
        vers = []
        for cand in O:
            best, bq = 0, None
            for q, wq in cand:
                if not wq or min(len(w), len(wq)) / max(len(w), len(wq)) < lenr: continue
                s = fuzz.ratio(w, wq)
                if s > best: best, bq = s, q
            if bq is not None and best >= minsim: vers.append(bq.split())
        if len(vers) < minv: out.append(p); continue
        new, ch = vote_para(body.split(), vers)
        if ch: changed += ch; out.append(pre + " ".join(new))
        else: out.append(p)
    return "\n\n".join(out), changed

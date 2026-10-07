"""Word-level consensus (ROVER) inside each paragraph of the selected page, gated by independent evidence.
The selected page stays the skeleton: its paragraph split, order, tables, formulas, casing and multi-line paragraphs are kept. Each body
paragraph is located in every other run (near-identical match on scorer-normalised text, similar length); every located version is
word-aligned to the skeleton paragraph (difflib on the scorer-visible characters of each word), and a word position may change only when
  1. a strict majority of ALL versions (skeleton included) agree on the change, AND
  2. the change is a near-spelling of the word (an OCR slip, not a different word: that would mean the voters matched another paragraph),
     never a case-only change (small caps) and never on punctuation-only tokens, AND
  3. evidence outside our model family confirms it. Our runs share one model, so their majority is often a shared error (just -> jut,
     1973 -> 1979). A change passes when an independent engine on the same page (PaddleOCR-VL, MinerU pipeline) has the new word and
     not the old one, or when it turns a non-word into a dictionary word (oozhed -> oozed; no digits). Insertions and deletions (one
     word at most, never at the paragraph edges) need the independent engines: inserted word present there, deleted word absent there
     and not a dictionary word.
  from rover import rover; md, changed = rover(page_md, [other_run_md, ...], indep=[paddle_md, mineru_md])
"""
import collections, functools, re
from difflib import SequenceMatcher
from rapidfuzz import fuzz
import Levenshtein
from para_fuse import paras, skip, W, HEAD

K = lambda t: re.sub(r"[\W_]", "", t)
MAXGAP = 1                                    # longer insertions / deletions are segmentation differences, not word errors
SIM = 0.75                                    # word substitutions: normalised similarity of the two spellings
similar = lambda a, b: 1 - Levenshtein.distance(a.lower(), b.lower()) / max(len(a), len(b)) >= SIM
MATH = re.compile(r"\$|\\\(|\\\[")


@functools.lru_cache(1)
def dictionary():
    try: return {w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8", errors="ignore")}
    except OSError: return set()


def indep_words(texts):
    """lower-cased word keys of the independent engines' pages (whole whitespace tokens and their \\w+ pieces)"""
    c = collections.Counter()
    for t in texts or []:
        for tok in (t or "").split():
            k = K(tok).lower()
            if k: c[k] += 1
            for piece in re.findall(r"[^\W_]+", tok.lower()):
                if piece != k: c[piece] += 1
    return c


def make_gate(ind):
    D = dictionary()
    def gate(old, new):
        ko = K(old).lower() if old else ""; kn = K(new).lower() if new else ""
        if old and new:                                            # substitution
            if ind and ind[kn] > 0 and ind[ko] == 0: return True
            return not any(ch.isdigit() for ch in ko + kn) and ko not in D and kn in D and ind[ko] == 0
        if new:                                                    # insertion
            return bool(ind) and kn != "" and ind[kn] > 0
        return bool(ind) and ind[ko] == 0 and ko not in D          # deletion
    return gate


def vote_para(S, versions, gate=lambda old, new: True):
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
            if c >= need and K("".join(t)) and gate(None, t[0]): out.extend(t); ch += 1
        if i == len(S): break
        k, c = sub[i].most_common(1)[0]; ks = K(S[i])
        if c >= need and k != ks and ks and (k is None or (k.lower() != ks.lower() and similar(k, ks))):
            new = None if k is None else surf[i][k].most_common(1)[0][0]
            if gate(S[i], new):
                ch += 1
                if new is not None: out.append(new)
                continue
        out.append(S[i])
    return out, ch


def rover(skel, others, indep=None, minsim=90, lenr=0.85, minw=8, minv=2):
    gate = make_gate(indep_words(indep)) if indep is not None else (lambda old, new: True)   # indep=None: majority vote only
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
        new, ch = vote_para(body.split(), vers, gate)
        if ch: changed += ch; out.append(pre + " ".join(new))
        else: out.append(p)
    return "\n\n".join(out), changed

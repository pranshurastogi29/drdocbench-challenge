"""Paragraph-boundary voting: keep our page's text and order, change only blank-line boundaries where most other candidates disagree.

Scorer mechanics: short blocks (<= 300 normalised chars) are robust to boundary mistakes (deal_with_truncated rejoins our pieces of a short
reference block; unpaired short reference blocks fold into a short block of ours), long ones are not: a long reference paragraph we split, or
two we join, costs the boundary text twice (once missing in the pair, once as an unpaired block). Page selection keeps one run's boundaries;
here every boundary is voted on by the other runs:
  MERGE  P_i | P_i+1 when >= K candidates have the end of P_i and the start of P_i+1 inside ONE paragraph
  SPLIT  inside P_i where >= K candidates end a paragraph and start the next one at the same place
Only boundaries touching a long block (> LONG chars on either side of the decision) are changed unless long_only=False.
"""
import re
from rapidfuzz import fuzz

N = lambda s: re.sub(r"[\W_]", "", s)


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def protected(p):
    return p.startswith("<table") or p.startswith("$") or p.startswith("|") or p.startswith("#") or p.startswith("![") or "<" in p


def norm_map(p):
    """normalised string and, for each normalised char, its index in p"""
    idx = [i for i, c in enumerate(p) if re.match(r"[^\W_]", c)]
    return "".join(p[i] for i in idx), idx


def bvote(md, others, k=3, ctx=25, long_only=True, LONG=300, do_merge=True, do_split=True):
    P = paras(md); O = [[N(q) for q in paras(o)] for o in others if o]
    if len(O) < k: return md, 0, 0
    J = ["".join(c) for c in O]          # whole candidate text, no boundaries
    merges = splits = 0
    # ---- merges
    if do_merge:
        out = [P[0]] if P else []
        for p in P[1:]:
            a, b = N(out[-1]), N(p)
            if (not protected(out[-1]) and not protected(p) and len(a) >= ctx and len(b) >= ctx and "\n" not in out[-1] + p
                    and (not long_only or len(a) + len(b) > LONG)):
                key = a[-ctx:] + b[:ctx]
                votes = sum(any(key in q for q in c) for c in O)      # end of ours and start of next inside one candidate paragraph
                if votes >= k:
                    out[-1] = out[-1] + " " + p; merges += 1; continue
            out.append(p)
        P = out
    # ---- splits
    if do_split:
        out = []
        for p in P:
            n, idx = norm_map(p)
            if protected(p) or len(n) < 2 * ctx or (long_only and len(n) <= LONG):
                out.append(p); continue
            cuts = {}
            for c in O:
                for q1, q2 in zip(c, c[1:]):
                    if len(q1) < ctx or len(q2) < ctx: continue
                    key = q1[-ctx:] + q2[:ctx]
                    j = n.find(key)
                    if j > 0 and ctx <= j + ctx <= len(n) - ctx:
                        pos = j + ctx; cuts.setdefault(pos, set()).add(id(c))
            good = sorted(pos for pos, s in cuts.items() if len(s) >= k)
            if not good:
                out.append(p); continue
            last = 0; pieces = []
            for pos in good:
                i = idx[pos]                    # original index of the first char of the second piece
                while i > 0 and not p[i - 1].isspace() and i > last: i -= 1   # back to the start of that word
                if i <= last: continue
                pieces.append(p[last:i].strip()); last = i
            pieces.append(p[last:].strip())
            pieces = [x for x in pieces if x]
            splits += len(pieces) - 1; out.extend(pieces)
        P = out
    return "\n\n".join(P), merges, splits


if __name__ == "__main__":
    # python bvote.py SRC.zip DST.zip : split-only boundary vote (k=5 of the 10 other free candidates, long blocks only) on a test submission zip.
    # Voters: processed candidates from runs/selcache_test.json (sel_cache.py); skeleton candidate = runs/mbr_choice_test.json.
    import argparse, json, os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_submission import write_zip, zip_rows
    from sel_lab import FREE
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--k", type=int, default=5); a = ap.parse_args()
    C = json.load(open("runs/selcache_test.json")); pick = json.load(open("runs/mbr_choice_test.json"))
    out = []; n = 0
    for r in zip_rows(a.src):
        s = f'{r["document_id"]}_{r["page"]}'; md = r["markdown"]
        if s in C and s in pick:
            new, _, sp = bvote(md, [C[s]["proc"][c] for c in FREE if c != pick[s]], k=a.k, do_merge=False)
            if sp:
                md = new; n += 1; print(f"  {s}: {sp} split(s)")
        out.append({**r, "markdown": md})
    write_zip(out, a.dst); print(f"{a.dst}: {n} pages changed")

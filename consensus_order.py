"""Reorder a page's paragraphs by the consensus position across the candidate runs.

The ensemble keeps one candidate's text per page (medoid). Reading order is half of the leaderboard score (Overall ~ 0.56 Text +
0.43 Reading_Order), and one run's ordering mistakes (a displaced header, a swapped column) are not seen by a text-agreement vote.
Here each paragraph of the chosen page is located in every other candidate (best fuzzy match), its relative position (share of the page's
characters before it) is read off, and the paragraph is moved to the median of those positions when the median differs from where it
is now by more than DELTA. Text is never changed, only order.

  python consensus_order.py SRC DST [--delta 0.1] [--min-votes 2] [--sim 75] [--split dev|test]
"""
import argparse
import json
import re
import statistics as st

from rapidfuzz import fuzz

CANDS = {"dev": ["runs/dev_all_full_bunny.jsonl", "runs/dev_all_v7_final.jsonl", "runs/dev_all_v8_final.jsonl", "runs/dev_all_v7c_final.jsonl"],
         "test": ["runs/test_all_v6.jsonl", "runs/test_all_v7.jsonl", "runs/test_all_v8.jsonl", "runs/test_all_v7c_test.jsonl"]}


def wn(s):
    return re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s).lower())


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def positions(P):
    """share of the page's (normalised) characters that precede each paragraph"""
    L = [max(1, len(wn(p))) for p in P]; tot = sum(L); out, acc = [], 0
    for l in L:
        out.append(acc / tot); acc += l
    return out


def reorder(base_md, cand_mds, delta=0.1, min_votes=2, sim=75):
    B = paras(base_md)
    if len(B) < 3:
        return base_md
    own = positions(B); keys = [wn(p)[:200] for p in B]
    votes = [[] for _ in B]
    for md in cand_mds:
        C = paras(md)
        if not C:
            continue
        cp = positions(C); ck = [wn(p)[:200] for p in C]
        for i, k in enumerate(keys):
            if len(k) < 4:
                continue
            best, bj = 0, None
            for j, k2 in enumerate(ck):
                s = fuzz.ratio(k, k2)
                if s > best:
                    best, bj = s, j
            if bj is not None and best >= sim:
                votes[i].append(cp[bj])
    new = []
    for i in range(len(B)):
        if len(votes[i]) >= min_votes:
            med = st.median(votes[i] + [own[i]])
            new.append(med if abs(med - own[i]) > delta else own[i])
        else:
            new.append(own[i])
    order = sorted(range(len(B)), key=lambda i: (new[i], i))
    return "\n\n".join(B[i] for i in order)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--split", default="dev")
    ap.add_argument("--delta", type=float, default=0.1); ap.add_argument("--min-votes", type=int, default=2); ap.add_argument("--sim", type=int, default=75)
    a = ap.parse_args()
    C = [{(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(f, encoding="utf-8"))} for f in CANDS[a.split]]
    n = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            k = (r["document_id"], r["page"])
            md = reorder(r["markdown"], [c[k] for c in C if k in c], a.delta, a.min_votes, a.sim)
            n += md.strip() != paras and md.strip() != "\n\n".join(paras(r["markdown"]))
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages reordered")

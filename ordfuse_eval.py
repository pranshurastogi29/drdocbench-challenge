"""Our page in ANOTHER model's reading order (dev): our paragraphs (text, split, tables, formulas untouched) are re-sorted by where their text
sits in the other model's page (rapidfuzz partial alignment on normalised text); paragraphs that cannot be located keep their place after
the previous one; the furniture tail (merged by furnmerge, at the end of our page) stays last. Tests whether a model with better order on
dev (sol-6.1: RO 87.6 vs the free model's 84.1) can lend its order without its text.
  python ordfuse_eval.py --src live_sol61 [--min 70]
"""
import argparse, collections, json, os, random, re, statistics as st, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
N = lambda s: re.sub(r"[\W_]", "", s.lower())


def paras(md): return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def reorder_by(ours, other, mn=70):
    O = N(other); P = paras(ours)
    if not O or len(P) < 3: return ours
    tail = len(P)
    while tail > 0 and len(N(P[tail - 1])) <= 60 and tail > len(P) - 3: tail -= 1   # keep the short tail (furniture) last
    pos = []; last = -1.0
    for i, p in enumerate(P[:tail]):
        w = N(p)
        if len(w) >= 8 and not p.startswith("$") and not p.startswith("<table"):
            al = fuzz.partial_ratio_alignment(w[:200], O)
            if al and al.score >= mn: last = al.dest_start + i * 1e-6; pos.append(last); continue
        last = last + 1e-3; pos.append(last)
    body = [p for _, p in sorted(zip(pos, P[:tail]), key=lambda t: t[0])]
    return "\n\n".join(body + P[tail:])


def job(a):
    import md2md_eval as M
    from common import gt_markdown
    k, subj, vs = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    return k, {n: M.page_scores(md, gt, True) for n, md in vs.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default="live_sol61"); ap.add_argument("--min", type=int, default=70); a = ap.parse_args()
    import stack, md2md_eval as M
    from postprocess import strip_sections
    with tempfile.TemporaryDirectory() as tmp: rows = {f'{r["document_id"]}_{r["page"]}': r for r in stack.build("dev", "sel=mbr8,rules,fm,sd,bv,rv=free,ac", tmp)}
    os.chdir(ROOT)
    S_ = {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{a.src}.jsonl")))}
    V = {k: (rows[k]["subject"], {"ours (mbr8)": rows[k]["markdown"], f"ours in {a.src} order": reorder_by(rows[k]["markdown"], s, a.min), f"{a.src} alone": s})
         for k, s in S_.items() if k in rows and len(s) > 60}
    with Pool(11, initializer=M.init) as P: S = dict(P.map(job, [(k, s, v) for k, (s, v) in V.items()]))
    os.chdir(ROOT)
    ok = [k for k, v in S.items() if all(x and x[1] is not None for x in v.values())]
    U = lambda x: 0.558 * x[0] + 0.433 * x[1]; base = "ours (mbr8)"
    print(f"{len(ok)} dev pages ({a.src})")
    for n in S[ok[0]]:
        by = collections.defaultdict(list)
        for k in ok: by[k.rsplit("_", 1)[0]].append(U(S[k][n]) - U(S[k][base]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv]
        print(f"  {n:28s} Text_ED {1 - st.mean(S[k][n][0] for k in ok) / 100:.4f}  RO {st.mean(S[k][n][1] for k in ok):6.2f}  vs ours {m(bk):+.2f} [{bt[50]:+.2f},{bt[1949]:+.2f}]  pages {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)}")

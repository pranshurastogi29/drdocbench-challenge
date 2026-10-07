"""Kimi's page in OUR reading order (dev). Kimi-K2.5 alone has much better Text_ED than our pipeline on its 53 dev pages (0.0614 vs 0.0857)
but worse order (85.2 vs 88.5); swapping its wording into our paragraphs gave nothing, so its text gain is in segmentation / content.
Here Kimi's page keeps its paragraphs and text, and its paragraphs are re-sorted by where their text sits in our mbr8 page:
each Kimi paragraph is located in our page's normalised text (rapidfuzz partial alignment), and sorted by that offset; paragraphs that
cannot be located (score < MIN) keep their place right after the paragraph before them.
  python reorder_eval.py [--kimi sm_kimi] [--min 60]
"""
import argparse, collections, json, os, random, re, statistics as st, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
N = lambda s: re.sub(r"[\W_]", "", s.lower())


def paras(md): return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def reorder(new, ours, mn=60):
    O = N(ours); P = paras(new); pos = []; last = -1.0
    for i, p in enumerate(P):
        w = N(p)
        if len(w) >= 4 and O:
            al = fuzz.partial_ratio_alignment(w[:300], O)
            if al and al.score >= mn: last = al.dest_start + i * 1e-6; pos.append(last); continue
        last = last + 1e-3; pos.append(last)          # not found: stays right after the previous paragraph
    return "\n\n".join(p for _, p in sorted(zip(pos, P), key=lambda t: t[0]))


def job(a):
    import md2md_eval as M
    from common import gt_markdown
    k, subj, vs = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    return k, {n: M.page_scores(md, gt, True) for n, md in vs.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--kimi", default="sm_kimi"); ap.add_argument("--min", type=int, default=60); a = ap.parse_args()
    import stack
    from ensemble_lab import downstream
    import mbr
    from postprocess import strip_sections
    with tempfile.TemporaryDirectory() as tmp: rows = {f'{r["document_id"]}_{r["page"]}': r for r in stack.build("dev", "sel=mbr8,rules,fm,sd,bv,ac", tmp)}
    os.chdir(ROOT)
    K = {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/dev_all_{a.kimi}.jsonl")))}
    mbr._init()
    V = {}
    for k, km in K.items():
        if k not in rows or len(km) < 60: continue
        ours = rows[k]["markdown"]; kp = downstream(km, k)
        V[k] = (rows[k]["subject"], {"ours (mbr8)": ours, "kimi alone": kp, "kimi in our order": reorder(kp, ours, a.min)})
    os.chdir(ROOT)
    with Pool(11, initializer=__import__("md2md_eval").init) as P: S = dict(P.map(job, [(k, s, v) for k, (s, v) in V.items()]))
    os.chdir(ROOT)
    ok = [k for k, v in S.items() if all(x and x[1] is not None for x in v.values())]
    U = lambda x: 0.558 * x[0] + 0.433 * x[1]; base = "ours (mbr8)"
    print(f"{len(ok)} dev pages ({a.kimi})")
    for n in S[ok[0]]:
        by = collections.defaultdict(list)
        for k in ok: by[k.rsplit("_", 1)[0]].append(U(S[k][n]) - U(S[k][base]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv]
        print(f"  {n:20s} Text_ED {1 - st.mean(S[k][n][0] for k in ok) / 100:.4f}  RO {st.mean(S[k][n][1] for k in ok):6.2f}  vs ours {m(bk):+.2f} [{bt[50]:+.2f},{bt[1949]:+.2f}]  pages {sum(x > 0.5 for x in d)}/{sum(x < -0.5 for x in d)}")

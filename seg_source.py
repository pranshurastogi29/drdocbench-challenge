"""Whose paragraph boundaries does the reference follow? (Dr.DocBench paper, Sec. 3.3: annotation starts from parser-generated pre-labels that
annotators correct, so the reference's block segmentation may inherit a parser's layout blocks.)
Dev: for each reference text block (scorer extraction, >= 30 normalised chars) that a source reproduces somewhere on the page (coverage:
partial match >= 90), is it also ONE block of that source (whole-block match >= 90)? segmentation agreement = exact / covered.
Sources: our free-model runs (v7, v10a), PaddleOCR-VL, MinerU pipeline (~/Downloads/mineru_results), the 82.88 stack's pick.
  python seg_source.py
"""
import collections, json, os, re, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
from common import gt_markdown
import md2md_eval as M
MINERU = os.path.expanduser("~/Downloads/mineru_results")
N = lambda s: re.sub(r"[\W_]+", "", (s or "").lower())


def blocks(md):
    md = re.sub(r"<<<(BODY|FURNITURE)>>>", "\n\n", md or "")
    return [N(r.get("content") or "") for r in M.md_tex_filter(md).get("text_all") or []]


def job(a):
    stem, subj, srcs = a
    doc, pg = stem.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    G = [g for g in blocks(gt) if len(g) >= 30]
    if not G: return stem, None
    out = {}
    for name, md in srcs.items():
        if md is None: continue
        B = [b for b in blocks(md) if b]; page = "".join(B)
        cov = ex = 0
        for g in G:
            if fuzz.partial_ratio(g, page) >= 90:
                cov += 1
                if any(fuzz.ratio(g, b) >= 90 for b in B): ex += 1
        out[name] = (len(G), cov, ex)
    return stem, out


if __name__ == "__main__":
    import stack
    R = lambda p: {f'{r["document_id"]}_{r["page"]}': r for r in stack.rows_of(os.path.join(ROOT, p))}
    src = {"v7": R("runs/dev_all_v7_final.jsonl"), "v10a": R("runs/dev_all_v10a_full.jsonl"), "paddle": R("runs/paddle_dev.jsonl")}
    with tempfile.TemporaryDirectory() as tmp: src["stack"] = {f'{r["document_id"]}_{r["page"]}': r for r in stack.build("dev", stack.FULL, tmp)}
    os.chdir(ROOT)
    def mineru(stem):
        f = os.path.join(MINERU, stem, "auto", stem + ".md")
        return open(f, encoding="utf-8").read() if os.path.exists(f) else None
    keys = sorted(src["v7"])
    jobs = [(k, src["v7"][k]["subject"], {**{n: (s[k]["markdown"] if k in s else None) for n, s in src.items()}, "mineru": mineru(k)}) for k in keys]
    with Pool(11, initializer=M.init) as P: res = {k: v for k, v in P.map(job, jobs, chunksize=4) if v}
    os.chdir(ROOT)
    both = [k for k, v in res.items() if "mineru" in v]
    print(f"{len(res)} dev pages with reference text blocks; {len(both)} also have MinerU output")
    for name in ("stack", "v7", "v10a", "paddle", "mineru"):
        ks = [k for k in both if name in res[k]]
        g, c, e = (sum(res[k][name][i] for k in ks) for i in range(3))
        print(f"  {name:7s} ref blocks {g:5d}  covered {c / g:5.1%}  one-block {e / g:5.1%}  segmentation agreement {e / max(c, 1):5.1%}")
    # per book: where does a parser's segmentation beat ours?
    book = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for k in both:
        for n, (g, c, e) in res[k].items(): book[k.rsplit("_", 1)[0][:8]][n][0] += c; book[k.rsplit("_", 1)[0][:8]][n][1] += e
    print("books where mineru/paddle segmentation agreement beats the stack by >= 10 points:")
    for b, d in sorted(book.items()):
        s = d["stack"][1] / max(d["stack"][0], 1)
        for n in ("mineru", "paddle"):
            v = d[n][1] / max(d[n][0], 1)
            if d[n][0] >= 10 and v - s >= 0.10: print(f"   {b} {n:6s} {v:.0%} vs stack {s:.0%} ({d[n][0]} covered blocks)")
    json.dump(res, open(os.path.join(ROOT, "runs", "seg_source.json"), "w"))

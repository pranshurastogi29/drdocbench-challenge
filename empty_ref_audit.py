"""Pages whose Markdown reference has NO text blocks: the official md2md matcher (utils/match_quick.py: `if not norm_gt_lines`) scores every
predicted text block there as edit 1, so the page's Text_ED is 1.0 and it still counts in the page average; with no text of ours the page
drops out of the text average. Our dev evaluation (md2md_eval.page_scores) skipped these pages, so this loss was never measured.
  python empty_ref_audit.py [--steps ...]
"""
import argparse, json, os, re, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import md2md_eval as M
from common import gt_markdown


def job(a):
    k, subj, md = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    g = M.md_tex_filter(gt).get("text_all") or []; p = M.md_tex_filter(md).get("text_all") or []
    return k, len(g), len(p), sum(len(re.sub(r"[\W_]", "", x.get("content") or "")) for x in p), len(re.sub(r"[\W_]", "", gt))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--steps", default="sel=mbr8,rules,fm,sd,bv,rv=free,ac"); a = ap.parse_args()
    import stack
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", a.steps, tmp)
    os.chdir(ROOT)
    with Pool(11, initializer=M.init) as P: R = P.map(job, [(f'{r["document_id"]}_{r["page"]}', r["subject"], r["markdown"]) for r in rows], chunksize=8)
    os.chdir(ROOT)
    empty = [x for x in R if x[1] == 0]
    hit = [x for x in empty if x[2] > 0]
    print(f"{len(R)} dev pages; reference with no text blocks: {len(empty)}; of those we write text on {len(hit)} (each scores Text_ED 1.0)")
    for k, ng, npb, nch, gtch in sorted(hit, key=lambda x: -x[3]): print(f"   {k[:8]} p{k.rsplit('_',1)[1]:>4}  our blocks {npb:3d}, our chars {nch:5d}, reference chars (any) {gtch}")
    json.dump({"empty": [x[0] for x in empty], "hit": [x[0] for x in hit]}, open(os.path.join(ROOT, "runs", "empty_ref_dev.json"), "w"))

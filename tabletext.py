"""Text that sits on the wrong side of the table/text divide (dev, MBR base5 pick, processed). Tables are scored only by TEDS (weight 0.006);
text inside a <table> is invisible to Text_ED. (a) reference text blocks whose text is only inside OUR tables (counted missing);
(b) our text paragraphs whose text is only inside the REFERENCE's tables (counted extra when every reference block is paired).
  python tabletext.py
"""
import json, os, re, sys, collections
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
from common import gt_markdown
from sel_lab import BASE5, pick_mbr
W = lambda s: re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s))
TB = re.compile(r"<table.*?</table>", re.S)


def job(a):
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg)); md = v["proc"][pick_mbr(v, BASE5)]
    ot = W(" ".join(TB.findall(md))); ox = W(TB.sub(" ", md)); gtt = W(" ".join(TB.findall(gt))); gx = W(TB.sub(" ", gt))
    a_ = b_ = 0; tot = len(gx)
    for p in re.split(r"\n\s*\n", TB.sub("\n\n", gt)):
        w = W(p)[:300]
        if len(w) >= 10 and ot and fuzz.partial_ratio(w, ot) >= 90 and fuzz.partial_ratio(w, ox) < 70: a_ += len(W(p))
    for p in re.split(r"\n\s*\n", TB.sub("\n\n", md)):
        w = W(p)[:300]
        if len(w) >= 10 and gtt and fuzz.partial_ratio(w, gtt) >= 90 and fuzz.partial_ratio(w, gx) < 70: b_ += len(W(p))
    return k, v["subject"], tot, a_, b_


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11) as P: R = P.map(job, sorted(C.items()), chunksize=4)
    T = sum(r[2] for r in R); A = sum(r[3] for r in R); B = sum(r[4] for r in R)
    print(f"reference text chars {T}; (a) ref text only in OUR tables: {A} ({A/T:.2%}) on {sum(r[3] > 0 for r in R)} pages; (b) our text only in REF tables: {B} ({B/T:.2%}) on {sum(r[4] > 0 for r in R)} pages")
    print("  (a) by subject:", collections.Counter({r[1]: r[3] for r in R if r[3]}).most_common(6))
    print("  (b) by subject:", collections.Counter({r[1]: r[4] for r in R if r[4]}).most_common(6))

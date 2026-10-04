"""Omission sizing (dev): reference blocks our chosen page (MBR base5, processed) leaves unpaired or badly paired, and whether any other
source read that text: the other free candidates, Paddle, MinerU. Weighted by reference characters (scorer-normalised).
  python omit_sources.py   -> runs/omit_sources.json (per missed block: stem, text, which sources have it)
"""
import collections, json, os, re, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from common import gt_markdown
from rapidfuzz import fuzz
from sel_lab import BASE5, FREE, pick_mbr

W = lambda s: re.sub(r"[\W_]", "", s)
MINERU = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, "runs/mineru_dev.jsonl")))}


def job(a):
    k, v = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg))
    pick = pick_mbr(v, BASE5); md = v["proc"][pick]
    g = mbr.md_tex_filter(gt).get("text_all") or []; p = mbr.md_tex_filter(md).get("text_all") or []
    recs = mbr.match(g, p, "text", "x"); out = []; tot = 0
    for r in recs:
        ng = r.get("norm_gt") or ""; npr = r.get("norm_pred") or ""
        if not ng: continue
        tot += len(ng)
        ed = mbr.Lev(ng, npr) / max(len(ng), len(npr))
        if ed < 0.5 or len(ng) < 4: continue
        srcs = {n: W(v["raw"][n]) for n in FREE if n != pick}; srcs["mineru"] = W(MINERU.get(k, ""))
        have = [n for n, s in srcs.items() if s and fuzz.partial_ratio(ng, s) >= 85] if len(ng) <= 2000 else []
        inpick = fuzz.partial_ratio(ng, W(md)) >= 85 if len(ng) <= 2000 else False
        out.append({"stem": k, "subject": v["subject"], "gt": ng[:300], "len": len(ng), "ed": round(ed, 2), "pred": npr[:120], "in_pick": inpick, "have": have})
    return k, tot, out


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = P.map(job, sorted(C.items()), chunksize=4)
    os.chdir(ROOT)
    tot = sum(t for _, t, _ in R); miss = [b for _, _, o in R for b in o]
    json.dump(miss, open("runs/omit_sources.json", "w"))
    L = lambda bs: sum(b["len"] for b in bs)
    print(f"reference chars {tot}; in blocks our page pairs badly (ED >= 0.5): {L(miss)} ({L(miss)/tot:.1%}) in {len(miss)} blocks on {len({b['stem'] for b in miss})} pages")
    a = [b for b in miss if b["in_pick"]]; print(f"  text IS in our page (segmentation / pairing): {L(a)/tot:.1%}")
    b_ = [b for b in miss if not b["in_pick"]]; print(f"  text NOT in our page: {L(b_)/tot:.1%}")
    c = [b for b in b_ if b["have"]]; print(f"    ...but some other source read it: {L(c)/tot:.1%} ({len(c)} blocks, {len({b['stem'] for b in c})} pages)")
    cnt = collections.Counter(n for b in c for n in b["have"]); print("      sources:", cnt.most_common())
    one = collections.Counter(b["have"][0] for b in c if len(b["have"]) == 1); print("      only source:", one.most_common())
    print(f"    ...nobody read it: {L([b for b in b_ if not b['have']])/tot:.1%}")

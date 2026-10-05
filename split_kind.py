"""What kind of paragraph break did the split import add? Each imported break is located in PaddleOCR-VL's layout blocks:
  column  : the text before and after the break lie in two different Paddle blocks side by side (different columns)
  block   : two different Paddle blocks in the same column (a new region below)
  inside  : both sides inside ONE Paddle block (list entries, lines of an index / table of cases)
  ?       : not found in Paddle's text
Dev: gain of the changed pages by kind (pages with one kind only); test: composition.
  python split_kind.py
"""
import collections, json, os, re, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr, paddle_ingest
from bvote import bvote, paras
from build_submission import zip_rows
from common import gt_markdown
from ensemble_lab import gt_score
from postprocess import strip_sections
from sel_lab import BASE5, U, pick_mbr
W = lambda s: re.sub(r"[\W_]", "", s.lower())


def kinds(stem, old, new):
    bl = [b for b in (paddle_ingest.blocks(stem) or []) if b.get("block_content")]
    B = [(W(b["block_content"]), b["block_bbox"]) for b in bl]
    out = []
    po = set(paras(old)); pn = paras(new)
    for i in range(len(pn) - 1):
        a, b = pn[i], pn[i + 1]
        if a in po and b in po: continue
        if a in po and b not in po and i + 2 < len(pn) and False: continue
        ta, hb = W(a)[-30:], W(b)[:30]
        if not ta or not hb: continue
        ia = [j for j, (t, _) in enumerate(B) if ta in t]; ib = [j for j, (t, _) in enumerate(B) if hb in t]
        if not ia or not ib: out.append("?"); continue
        if set(ia) & set(ib): out.append("inside"); continue
        A, Bb = B[ia[0]][1], B[ib[0]][1]
        side = A[2] <= Bb[0] + 5 or Bb[2] <= A[0] + 5
        out.append("column" if side else "block")
    return out


def dev_job(a):
    k, v, voters = a; pick = pick_mbr(v, BASE5); md = v["proc"][pick]
    new, _, s = bvote(md, voters, k=2, do_merge=False, long_only=False)
    if not s: return k, None
    doc, pg = k.rsplit("_", 1); g = gt_score(new, gt_markdown("dev", v["subject"], doc, int(pg)))
    return k, (kinds(k, md, new), U(g) - U(v["gt"][pick]))


if __name__ == "__main__":
    load = lambda tags: {k: v for t in tags for k, v in {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(f"runs/dev_all_{t}.jsonl"))}.items()}
    V = [load(("ab_v10a", "v10a_rest")), load(("ab_v10b", "v10b_rest")), load(("ab_v11", "v11_rest"))]
    C = json.load(open("runs/selcache_dev.json")); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: R = {k: r for k, r in P.map(dev_job, [(k, C[k], [d[k] for d in V if k in d]) for k in sorted(C)], chunksize=4) if r}
    os.chdir(ROOT)
    cnt = collections.Counter(x for ks, _ in R.values() for x in ks); print("DEV imported breaks by kind:", dict(cnt))
    by = collections.defaultdict(list)
    for k, (ks, d) in R.items(): by[ks[0] if len(set(ks)) == 1 else "mixed"].append(d)
    for kk, v in by.items(): print(f"   pages with only '{kk}' breaks: {len(v):3d}, sum of gains {sum(v):+7.1f} leaderboard points, mean {sum(v)/len(v):+.2f}, better/worse {sum(x > 0 for x in v)}/{sum(x < 0 for x in v)}")
    a = {(r["document_id"], r["page"]): r["markdown"] for r in zip_rows("submissions/submission_final5m_fc10t_fm_sd_bv_ac.zip")}
    t = collections.Counter(); pk = collections.Counter()
    for r in zip_rows("submissions/submission_final5m_fc10t_fm_sd_bv_ac_si3k2.zip"):
        o = a[(r["document_id"], r["page"])]
        if o == r["markdown"]: continue
        ks = kinds(f'{r["document_id"]}_{r["page"]}', o, r["markdown"]); t.update(ks); pk[ks[0] if len(set(ks)) == 1 else "mixed"] += 1
    print("TEST imported breaks by kind:", dict(t)); print("   test pages by kind:", dict(pk))


def filtered(stem, old, new, allow):
    """keep only the imported breaks whose kind is in allow; rejoin the others (with a space: the scorer ignores whitespace)"""
    pn = paras(new); po = set(paras(old)); ks = kinds_list(stem, old, new)
    out = [pn[0]] if pn else []
    for i in range(1, len(pn)):
        kind = ks.get(i - 1)
        if kind is not None and kind not in allow: out[-1] = out[-1] + " " + pn[i]
        else: out.append(pn[i])
    return "\n\n".join(out)


def kinds_list(stem, old, new):
    """{index of the paragraph before an imported break: kind}"""
    bl = [b for b in (paddle_ingest.blocks(stem) or []) if b.get("block_content")]
    B = [(W(b["block_content"]), b["block_bbox"]) for b in bl]
    pn = paras(new); po = paras(old); res = {}
    # imported breaks: consecutive new paragraphs whose concatenation lies inside one old paragraph
    oj = [W(p) for p in po]
    for i in range(len(pn) - 1):
        a, b = pn[i], pn[i + 1]
        j = W(a)[-40:] + W(b)[:40]
        if not any(j in o for o in oj): continue
        ta, hb = W(a)[-30:], W(b)[:30]
        ia = [x for x, (t, _) in enumerate(B) if ta and ta in t]; ib = [x for x, (t, _) in enumerate(B) if hb and hb in t]
        if not ia or not ib: res[i] = "?"
        elif set(ia) & set(ib): res[i] = "inside"
        else:
            A, Bb = B[ia[0]][1], B[ib[0]][1]
            res[i] = "column" if (A[2] <= Bb[0] + 5 or Bb[2] <= A[0] + 5) else "block"
    return res


def kind_job(a):
    k, v, voters = a; pick = pick_mbr(v, BASE5); md = v["proc"][pick]
    new, _, s = bvote(md, voters, k=2, do_merge=False, long_only=False)
    if not s: return k, None
    doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", v["subject"], doc, int(pg)); base = U(v["gt"][pick]); out = {}
    for name, allow in (("column only", {"column"}), ("block only", {"block"}), ("inside only", {"inside"}), ("unlocated only", {"?"}),
                        ("column+block", {"column", "block"}), ("all but inside", {"column", "block", "?"}), ("all", {"column", "block", "inside", "?"})):
        f = filtered(k, md, new, allow)
        out[name] = U(gt_score(f, gt)) - base if f != md else 0.0
    return k, out


if __name__ == "__main__" and "--by-kind" in sys.argv:
    with Pool(11, initializer=mbr._init) as P: R2 = {k: r for k, r in P.map(kind_job, [(k, C[k], [d[k] for d in V if k in d]) for k in sorted(C)], chunksize=4) if r}
    import random
    for name in next(iter(R2.values())):
        by = collections.defaultdict(list)
        for k in C: by[k.rsplit("_", 1)[0]].append(R2[k][name] if k in R2 else 0.0)
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv if abs(x) > 1e-9]
        print(f"  DEV {name:16s} {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]  pages better/worse {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}")

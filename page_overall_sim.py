"""Per-page Overall as the leaderboard defines it (paper Sec. 4.2: mean of the available component scores per page, pages averaged), on dev:
  text  (100 * (1 - page Text_ED))  available when the reference has text blocks   (multipage_md2md_dataset: `if gt_data.get('text_all')`)
  order (100 * (1 - order edit))     same pages
  formula (proxy: 1 - normalised edit, per reference formula)  available when the reference has display formulas (our side may be empty)
  table (TEDS, page mean)            available only when the reference AND our page both have a table (`if gt ... and pred ...`)
Variants: the stack as is, and with our tables removed (tables only count where we output one).
  python page_overall_sim.py [--steps sel=mbr8,rules,fm,sd,bv,rv=free,ac]
"""
import argparse, collections, json, os, random, re, statistics as st, sys, tempfile
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
TAB = re.compile(r"<table\b.*?</table>", re.S | re.I)


def comps(a):
    import md2md_eval as M
    from common import gt_markdown
    import table_lab as T
    k, subj, md = a; doc, pg = k.rsplit("_", 1); gt = gt_markdown("dev", subj, doc, int(pg))
    c = {}
    s = M.page_scores(md, gt, True)
    if s: c["text"] = s[0]; c["order"] = s[1] if s[1] is not None else None
    f = M.formula_score(md, gt)
    if f: c["formula"] = f[0]
    g, p = TAB.findall(gt), TAB.findall(md)
    if g and p:
        r = T._page((g, p))
        if r: c["table"] = 100 * sum(r) / len(r)
    return k, {x: y for x, y in c.items() if y is not None}


def overall(pages):
    v = [sum(c.values()) / len(c) for c in pages.values() if c]
    return sum(v) / len(v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--steps", default="sel=mbr8,rules,fm,sd,bv,rv=free,ac"); a = ap.parse_args()
    import stack, md2md_eval as M
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build("dev", a.steps, tmp)
    os.chdir(ROOT)
    V = {"as is": {f'{r["document_id"]}_{r["page"]}': (r["subject"], r["markdown"]) for r in rows}}
    V["tables removed"] = {k: (s, TAB.sub("", md)) for k, (s, md) in V["as is"].items()}
    res = {}
    for n, d in V.items():
        with Pool(11, initializer=M.init) as P: res[n] = dict(P.map(comps, [(k, s, md) for k, (s, md) in d.items()], chunksize=8))
        os.chdir(ROOT)
    base = res["as is"]
    for n, R in res.items():
        cnt = collections.Counter(x for c in R.values() for x in c)
        mean = {x: st.mean(c[x] for c in R.values() if x in c) for x in cnt}
        print(f"{n:15s} Overall {overall(R):.3f}  " + "  ".join(f"{x} {mean[x]:.2f} ({cnt[x]} pages)" for x in ("text", "order", "formula", "table") if x in cnt))
    tp = [k for k, c in base.items() if "table" in c]
    d = [(sum(res['tables removed'][k].values()) / len(res['tables removed'][k]) - sum(base[k].values()) / len(base[k])) for k in tp if res['tables removed'][k]]
    print(f"pages with a scored table: {len(tp)}; per-page change when our tables are removed: mean {st.mean(d):+.2f}, better on {sum(x > 0 for x in d)}, worse on {sum(x < 0 for x in d)}")
    lo = [base[k]["table"] for k in tp]; print(f"TEDS on those pages: median {st.median(lo):.1f}; below the page's text/order mean on {sum(base[k]['table'] < (base[k]['text'] + base[k].get('order', base[k]['text'])) / 2 for k in tp)}")

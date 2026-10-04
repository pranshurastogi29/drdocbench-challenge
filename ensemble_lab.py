"""Consensus lab: every candidate run, every selector, the same rule stack, scored on dev with the official text / reading-order logic.

Per page, every candidate (free-model prompts, Paddle, and the paid models where they ran) goes through the same downstream rules as final5
(Paddle split-snap, cap 9 new paragraphs; Paddle tables where none; furniture merge --max-tail 2 --maxlen 60 --paddle-check), then is scored
against the reference. Selectors:
  medoid5        final5's text-similarity medoid over v6,v7,v8,paddle,v7c
  mbr:<pool>     mbr.py's metric-utility consensus (0.558 text + 0.433 order between candidates) over a pool
  oracle:<pool>  best candidate per page by the reference (a ceiling, not achievable)
Formulas and tables are not scored here: they ride free channels (formula_pool.py, table_pool.py) that never touch text / reading order.

  python ensemble_lab.py                -> full dev, free pools
  python ensemble_lab.py --sample       -> the 48-window sample, pools with the paid models (pages every run covers)
"""
import argparse, collections, json, os, random, re, statistics as st, sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import DEV, medoid, para, MAX_ADD
from common import gt_markdown
from postprocess import strip_sections

PAID = {"sol61": "runs/dev_all_live_sol61.jsonl", "solpro": "runs/dev_all_bt_sol48.jsonl", "glm": "runs/dev_all_bt_glm48.jsonl",
        "deepseek": "runs/dev_all_bt_deepseek48.jsonl", "mimo": "runs/dev_all_bt_mimo48.jsonl"}
BASE5 = ["v6", "v7", "v8", "paddle", "v7c"]
FREE = BASE5 + ["v6c", "v8c", "v7s", "v6w1", "v7w1", "v8w1"]   # the free runs that cover all of dev (v7cw1, v7sw1, v5w1, v7tw1 cover 376-400 pages)


def downstream(md, stem):
    from snap import snap
    from tablefix import fix
    from furnmerge import merge_tail
    import paddle_ingest
    s = snap(md, stem, mode="split")
    if para(s) - para(md) > MAX_ADD: s = md
    s, _ = fix(s, stem, replace=False)
    try: fur = [re.sub(r"[\W_]", "", t.lower()) for _, t in paddle_ingest.furniture(stem)]
    except Exception: fur = []
    return merge_tail(s, 2, 60, fur)


def gt_score(pred, gt):
    g = mbr.md_tex_filter(gt).get("text_all") or []; p = mbr.md_tex_filter(pred).get("text_all") or []
    if not g: return None
    recs = mbr.match(g, p, "text", "x"); n = d = 0
    for r in recs:
        a = r.get("norm_gt") or r.get("gt") or ""; b = r.get("norm_pred") or r.get("pred") or ""
        if a or b: n += mbr.Lev(b, a); d += max(len(a), len(b))
    text = 100 * (1 - n / d) if d else 100.0
    m = [(r["gt_position"], r["pred_position"]) for r in recs if r["gt_position"] != [""] and r["pred_position"] != ""]
    G = sorted(x for x in sum([r["gt_position"] for r in recs if r["gt_position"] != [""]], []) if x)
    P = [x for x in sum([a for a, _ in sorted(m, key=lambda t: t[1])], []) if x]
    if not (G or P): return None
    return text, 100 * (1 - mbr.Lev(G, P) / max(len(G), len(P)))


def mbr_pick(raw, pool):
    names = [n for n in pool if n in raw and raw[n].strip()]
    sc = {}
    for i in names:
        us = [u for j in names if j != i for u in [mbr.utility(raw[i], raw[j])] if u is not None]
        sc[i] = sum(us) / len(us) if us else -1
    return max(names, key=lambda n: (sc[n], n == "v7"))


def page(job):
    stem, subj, raw, pools = job
    doc, pg = stem.rsplit("_", 1)
    gt = gt_markdown("dev", subj, doc, int(pg))
    S = {}
    for n, md in raw.items():
        s = gt_score(downstream(md, stem), gt)
        if s is None: return stem, None, None
        S[n] = s
    picks = {"medoid5": medoid(raw, BASE5)}
    for pn, pool in pools.items():
        picks[f"mbr:{pn}"] = mbr_pick(raw, pool)
        picks[f"oracle:{pn}"] = max(pool, key=lambda n: 0.558 * S[n][0] + 0.433 * S[n][1])
    return stem, S, picks


def ci(xs, seed=0):
    rng = random.Random(seed); b = sorted(st.mean(rng.choices(xs, k=len(xs))) for _ in range(2000)); return b[50], b[1949]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sample", action="store_true"); ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    runs = {n: DEV[n] for n in FREE}
    pools = {"base5": BASE5, "free11": FREE}
    if a.sample:
        runs.update(PAID)
        pools.update({"base5+sol": BASE5 + ["sol61", "solpro"], "free11+sol": FREE + ["sol61", "solpro"], "all16": FREE + list(PAID)})
    R = {n: {f'{r["document_id"]}_{r["page"]}': r for r in map(json.loads, open(os.path.join(ROOT, f), encoding="utf-8"))} for n, f in runs.items()}
    stems = sorted(set.intersection(*[set(v) for v in R.values()]))
    jobs = [(s, R["v7"][s]["subject"], {n: strip_sections(R[n][s]["markdown"]).strip() for n in runs}, pools) for s in stems]
    res = {}
    with Pool(a.workers, initializer=mbr._init) as P:
        for i, (stem, S, picks) in enumerate(P.imap_unordered(page, jobs, chunksize=2), 1):
            if S: res[stem] = (S, picks)
            if i % 100 == 0: print(i, "/", len(jobs), flush=True)
    os.chdir(ROOT)
    keys = sorted(res); book = lambda s: s.rsplit("_", 1)[0]
    U = lambda t: 0.558 * t[0] + 0.433 * t[1]                         # leaderboard weights (text, order); overall shown as their mean
    def row(name, get):
        T = [get(k) for k in keys]; base = [res[k][0][res[k][1]["medoid5"]] for k in keys]
        ov = [(t[0] + t[1]) / 2 for t in T]; d = [(t[0] + t[1]) / 2 - (b[0] + b[1]) / 2 for t, b in zip(T, base)]
        lo, hi = ci(d) if any(d) else (0, 0)
        return f"{name:22s} overall {st.mean(ov):5.2f}  text {st.mean(t[0] for t in T):5.2f}  order {st.mean(t[1] for t in T):5.2f}  vs medoid5 {st.mean(d):+5.2f} [{lo:+.2f},{hi:+.2f}]  better/worse {sum(x > .5 for x in d)}/{sum(x < -.5 for x in d)}"
    out = [f"{'sample (paid models included)' if a.sample else 'full dev'}: {len(keys)} pages, {len({book(k) for k in keys})} books; every row has the same downstream rules + furniture merge", "", "== single models =="]
    singles = sorted(runs, key=lambda n: -st.mean(sum(res[k][0][n]) / 2 for k in keys))
    out += [row(n, lambda k, n=n: res[k][0][n]) for n in singles]
    out += ["", "== selectors =="]
    for sel in ["medoid5"] + [f"{t}:{p}" for p in pools for t in ("mbr", "oracle")]:
        out.append(row(sel, lambda k, sel=sel: res[k][0][res[k][1][sel]]))
    out += ["", "== what each consensus picks (pages) =="]
    for sel in ["medoid5"] + [f"mbr:{p}" for p in pools]:
        out.append(f"{sel:22s} " + ", ".join(f"{n} {c}" for n, c in collections.Counter(res[k][1][sel] for k in keys).most_common()))
    txt = "\n".join(out); print(txt)
    dst = os.path.join(ROOT, "runs", f"ensemble_lab_{'sample' if a.sample else 'dev'}.txt"); open(dst, "w").write(txt + "\n")
    json.dump({k: {"scores": res[k][0], "picks": res[k][1]} for k in keys}, open(dst.replace(".txt", ".json"), "w"))

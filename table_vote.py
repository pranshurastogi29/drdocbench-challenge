"""Table-level medoid vote. Per PaddleOCR-VL table block, candidates = crop-pass transcriptions + Paddle's own table + the best-matching
table of each page-level candidate run; the medoid (highest summed similarity to the others, similarity = ratio of the scorer-normalised
table strings, so structure and cell text both count) replaces our table on the page (or is appended when ours has none).

  python table_vote.py dev runs/tables_dev_t1.jsonl runs/tables_dev_t2.jsonl
"""
import collections, json, re, statistics as st, sys
from rapidfuzz import fuzz
from paddle_ingest import blocks
from table_lab import TAB, gt_tables, load_pred, normalized_table
from reading_order import norm
from table_merge import THR, cellnorm, load_crops, owners
from table_lab import score
from variants import tables_variant

DEV = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl",
       "v6c": "runs/dev_all_v6c_final.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl", "v8c": "runs/dev_all_v8c_final.jsonl"}
nt = lambda h: normalized_table(h) if isinstance(normalized_table(h), str) else normalized_table(h)[1]


def best_match(target_norm, tables, used):
    best, bs = None, 0
    for i, o in enumerate(tables):
        if i in used: continue
        s = fuzz.ratio(target_norm[:1500], cellnorm(o)[:1500])
        if s > bs: best, bs = i, s
    return (best, bs) if best is not None and bs >= THR else (None, 0)


def medoid(cands):
    ns = [nt(c) for c in cands]
    sc = [sum(fuzz.ratio(ns[i], ns[j]) for j in range(len(ns)) if j != i) for i in range(len(ns))]
    return max(range(len(cands)), key=lambda i: (sc[i], -i))       # ties -> earlier candidate (crop passes come first)


def place(md, stem, b, html):
    """Insert html after the paragraph that holds the nearest preceding Paddle text block (else at the top): same rule as tablefix.fix."""
    from snap import protected  # noqa: F401
    paras = [p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    allb = blocks(stem) or []; ti = allb.index(b); pn_list = [norm(p) for p in paras]; pos = 0
    for q in range(ti - 1, -1, -1):
        t = norm(allb[q]["block_content"] or "")
        if len(t) >= 10 and allb[q]["block_label"] not in ("image", "chart", "header", "footer", "number"):
            best = max(range(len(paras)), key=lambda z: fuzz.partial_ratio(t[:100], pn_list[z])) if paras else None
            if best is not None and fuzz.partial_ratio(t[:100], pn_list[best]) >= 80:
                pos = best + 1; break
    paras.insert(pos, html)
    return "\n\n".join(paras)


def vote_page(stem, base_md, crop_sets, page_cands, use_paddle=True, append=True):
    tb = [b for b in (blocks(stem) or []) if b["block_label"] == "table"]
    ours = TAB.findall(base_md); used_ours = set(); used_pc = {n: set() for n in page_cands}; out, extra = base_md, []
    for i, b in enumerate(tb):
        cs = [c[i] for c in crop_sets if i in c]
        if not cs: continue
        cands = list(cs)
        if use_paddle and b["block_content"].strip() and "<table" in b["block_content"].lower():
            cands.append(tables_variant(TAB.search(b["block_content"]).group(0)) if TAB.search(b["block_content"]) else b["block_content"])
        ref = cellnorm(cs[0])
        for n, pmd in page_cands.items():
            pt = TAB.findall(pmd.get(stem, ""))
            j, _ = best_match(ref, pt, used_pc[n])
            if j is not None: used_pc[n].add(j); cands.append(pt[j])
        pick = cands[medoid(cands)]
        j, _ = best_match(ref, ours, used_ours)
        if j is not None: used_ours.add(j); out = out.replace(ours[j], pick, 1)
        else: extra.append((b, pick))
    if not append: return out
    if append == "place":
        for b, pick in extra: out = place(out, stem, b, pick)
        return out
    return out.rstrip() + ("\n\n" + "\n\n".join(p for _, p in extra) if extra else "")


if __name__ == "__main__":
    split = sys.argv[1]; files = sys.argv[2:]
    G = gt_tables(); P = load_pred("runs/dev_all_final5.jsonl")
    sets = []
    for f in files:
        C = load_crops(f); sets.append({s: {i: t for i, t in v} for s, v in C.items()})
    stems = set().union(*[set(s) for s in sets])
    PC = {n: load_pred(p) for n, p in DEV.items()}
    def run(name, cs, pcn, paddle=True):
        PP = {k: (vote_page(k, v, [s.get(k, {}) for s in cs], {n: PC[n] for n in pcn}, paddle) if k in stems else v) for k, v in P.items()}
        m, flat = score(PP, G=G); ow = owners(G, PP)
        c18 = [f for o, f in zip(ow, flat) if o == "c18d05a4"]; rest = [f for o, f in zip(ow, flat) if o != "c18d05a4"]
        print(f"{name:34s} all {m:6.2f}   c18 {100*st.mean(c18):6.2f}   other {100*st.mean(rest):6.2f}", flush=True)
    run("crop1 only (=replace)", sets[:1], [], False)
    run("crop1 + paddle", sets[:1], [], True)
    run("crop1 + paddle + 6 page cands", sets[:1], list(DEV), True)
    if len(sets) > 1:
        run("crop1+crop2", sets, [], False)
        run("crop1+crop2 + paddle", sets, [], True)
        run("crop1+crop2 + paddle + 6 pages", sets, list(DEV), True)
        run("crop1+crop2 + 6 pages", sets, list(DEV), False)

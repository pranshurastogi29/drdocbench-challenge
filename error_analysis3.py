"""Error analysis round 3 on a scored run (official scorer result files). Default: DEVR_final7t (final7t rebuilt on dev).
  python error_analysis3.py [RUN_NAME]   -> printed report (also saved to runs/error_analysis3.txt by the shell)
"""
import collections, glob, json, os, re, statistics as st, sys
import Levenshtein
from compare_runs import load
RUN = sys.argv[1] if len(sys.argv) > 1 else "DEVR_final7t"
res = lambda n: json.load(open(f"scorer/result/drdoc_{RUN}_{n}.json"))
P = load(RUN); keys = sorted(k for k in P if P[k]["overall"] is not None); N = len(keys)
subject = {}
for p in glob.glob("data/dev/*/*/images/page_*.jpg"):
    subject[p.split("/")[3]] = p.split("/")[2]
doc = lambda k: k.split("_")[0]
ov = {k: P[k]["overall"] for k in keys}; lost = sum(100 - v for v in ov.values())
print(f"RUN {RUN}: {N} scored pages, mean overall {st.mean(ov.values()):.2f}, total lost points {lost:.0f}\n")

print("== 1. Score distribution: where the lost points are")
for lo, hi, nm in ((97, 101, ">=97"), (90, 97, "90-97"), (80, 90, "80-90"), (60, 80, "60-80"), (30, 60, "30-60"), (-1, 30, "<30")):
    s = [v for v in ov.values() if lo <= v < hi]
    print(f"  {nm:6s} pages {len(s):4d} ({100*len(s)/N:4.1f}%)  mean {st.mean(s) if s else 0:5.1f}  share of lost points {100*sum(100-x for x in s)/lost:4.1f}%")
comp = collections.Counter()
for k in keys:
    cs = {c: P[k][c] for c in ("text", "order", "teds") if P[k][c] is not None}
    for c, v in cs.items(): comp[c] += (100 - v) / len(cs) * (len(cs) / max(1, len(cs)))  # each component's own loss, weighted by 1/len(cs) of the page overall
tot = sum(comp.values()); print("  component share of lost overall points (page loss split by component):", {c: f"{100*v/tot:.0f}%" for c, v in comp.items()})

print("\n== 2. Text loss by kind (character edits from the scorer's paragraph matching)")
fmt = lambda s: re.sub(r"\s+", " ", re.sub(r"[*_#`>|\\{}$~]|\\[a-zA-Z]+", "", s.replace("\n", " "))).strip().lower()
TB = res("text_block_result"); kind = collections.Counter(); bycat = collections.defaultdict(lambda: collections.Counter())
sub = collections.Counter(); ops = collections.Counter(); nchar = 0
for e in TB:
    en = e.get("Edit_num", 0); ul = e.get("upper_len", 0); cat = e.get("gt_category_type") or "(extra prediction)"
    bycat[cat]["edits"] += en; bycat[cat]["chars"] += ul; bycat[cat]["n"] += 1
    if not en: continue
    g, p = e["gt"], e["pred"]
    if g == "" and p != "": kind["extra predicted paragraph not in reference"] += en; bycat[cat]["extra"] += en
    elif p == "" and g != "": kind["reference paragraph not output / not matched"] += en; bycat[cat]["missing"] += en
    else:
        ng, np_ = e.get("norm_gt", ""), e.get("norm_pred", "")
        real = Levenshtein.distance(fmt(g), fmt(p)); real = min(real, en)
        kind["matched pair: markup/format only"] += en - real; kind["matched pair: real wording/OCR differences"] += real
        bycat[cat]["matched_real"] += real
        for op, i1, i2, j1, j2 in Levenshtein.opcodes(ng, np_):
            if op == "replace" and i2 - i1 == 1 and j2 - j1 == 1: sub[(ng[i1], np_[j1])] += 1; ops["replace"] += 1
            elif op == "replace": ops["replace"] += max(i2 - i1, j2 - j1)
            elif op == "delete": ops["delete (we dropped chars)"] += i2 - i1
            elif op == "insert": ops["insert (we added chars)"] += j2 - j1
tk = sum(kind.values()); 
for k_, v in kind.most_common(): print(f"  {k_:52s} {v:7d} chars  {100*v/tk:5.1f}%")
print("\n  by reference category (share of all text edits | own edit rate | dominant kind):")
for cat, c in sorted(bycat.items(), key=lambda kv: -kv[1]["edits"])[:10]:
    dom = max(("extra", "missing", "matched_real"), key=lambda z: c[z])
    print(f"    {cat:26s} {100*c['edits']/tk:5.1f}% of edits   {100*c['edits']/max(1,c['chars']):5.1f}% of its chars   n={c['n']:5d}   mostly {dom} ({100*c[dom]/max(1,c['edits']):.0f}%)")

print("\n== 3. Character-level errors inside matched paragraphs (real OCR-type differences)")
print("  ops:", {k_: v for k_, v in ops.most_common()})
def cls(c):
    if c.isdigit(): return "digit"
    if c.isalpha(): return "letter" if c.isascii() else "accented/non-ascii letter"
    return "punctuation/symbol"
cc = collections.Counter(); 
for (a, b), n in sub.items(): cc[(cls(a), cls(b))] += n
print("  single-char substitutions by class:", [(f"{a}->{b}", n) for (a, b), n in cc.most_common(6)])
print("  most common substitutions (gt -> ours):", [(f"{a}->{b}", n) for (a, b), n in sub.most_common(14)])

print("\n== 4. Reading order")
RO = res("reading_order_result"); ed = [e["edit"] for e in RO]
print(f"  pages {len(RO)}, mean order loss {100*st.mean(ed):.1f}%; pages with any error {sum(x>0 for x in ed)} ({100*sum(x>0 for x in ed)/len(ed):.0f}%), with >=0.3: {sum(x>=0.3 for x in ed)}")
one = sum(1 for e in RO if 0 < e["Edit_num"] <= 2); print(f"  pages whose whole error is <=2 block moves: {one}; share of the total order loss from pages with edit>=0.3: {100*sum(x for x in ed if x>=0.3)/sum(ed):.0f}%")
byn = collections.defaultdict(list)
for e in RO: byn["<=4 blocks" if e["upper_len"] <= 4 else "5-9" if e["upper_len"] <= 9 else "10-19" if e["upper_len"] < 20 else ">=20"].append(e["edit"])
print("  order loss by number of ordered blocks:", {k_: f"n={len(v)} mean {100*st.mean(v):.1f}%" for k_, v in sorted(byn.items())})
# last-block displacement: is the moved element the trailing furniture/footnote?
mv = collections.Counter()
for e in RO:
    g, p = e["gt"], e["pred"]
    if g == p or not g or not p: continue
    mv["first block differs"] += g[0] != p[0]; mv["last block differs"] += g[-1] != p[-1]; mv["pages with errors"] += 1
print("  pages with errors:", dict(mv))

print("\n== 5. Formulas (reference display formulas, CDM cannot be run locally; edit distance vs our output)")
FM = res("display_formula_result"); n = len(FM); wrap = [e for e in FM if re.match(r"\s*\$*\s*\\text(it|bf)", e["gt"] or "")]
un = [e for e in FM if e["pred"] == ""]
print(f"  reference display formulas {n}: wrapper-style ($\\textit/$\\textbf) {len(wrap)}; real math {n-len(wrap)}; no prediction paired: {len(un)} ({100*len(un)/n:.0f}%)")
rm = [e for e in FM if e not in wrap]; print(f"  real-math formulas: unpaired {sum(e['pred']=='' for e in rm)}/{len(rm)}; mean edit of paired real-math {st.mean([e['edit'] for e in rm if e['pred']!='']) if any(e['pred']!='' for e in rm) else float('nan'):.2f}")

print("\n== 6. Concentration: documents and subjects")
d = collections.defaultdict(list)
for k in keys: d[doc(k)].append(ov[k])
tl = sum(100 - x for v in d.values() for x in v)
print("  worst documents by share of lost points:")
for dk, v in sorted(d.items(), key=lambda kv: -sum(100 - x for x in kv[1]))[:8]:
    print(f"    {dk[:8]} ({subject.get(dk,'?')[:22]:22s}) pages {len(v):3d}  mean {st.mean(v):5.1f}  {100*sum(100-x for x in v)/tl:4.1f}% of loss")
s = collections.defaultdict(list)
for k in keys: s[subject.get(doc(k), "?")].append(ov[k])
print("  by subject:", {a: f"{st.mean(v):.1f} (n={len(v)})" for a, v in sorted(s.items(), key=lambda kv: st.mean(kv[1]))})

print("\n== 7. Worst pages (lowest overall) with the dominant cause")
tb_by = collections.defaultdict(list)
for e in TB: tb_by[e["img_id"]].append(e)
for k in sorted(keys, key=lambda k: ov[k])[:20]:
    ents = tb_by.get(k, []); ex = sum(e["Edit_num"] for e in ents if e["gt"] == ""); ms = sum(e["Edit_num"] for e in ents if e["pred"] == "" and e["gt"] != "")
    mr = sum(e["Edit_num"] for e in ents if e["gt"] and e["pred"]); c = P[k]
    dom = max((("extra text", ex), ("missing text", ms), ("wording", mr)), key=lambda z: z[1])[0]
    print(f"  {ov[k]:5.1f} {k[:8]}_{k.split('_')[1]:8s} text {c['text'] if c['text'] is not None else float('nan'):5.1f} order {c['order'] if c['order'] is not None else float('nan'):5.1f} teds {c['teds'] if c['teds'] is not None else float('nan'):5.1f}  cause: {dom} (extra {ex}, missing {ms}, wording {mr})")

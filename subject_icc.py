"""Is the error *direction* (reference-omits vs we-omit) a property of the subject or of the individual book? Dev, final7t.
Doc-level score d = extra/(extra+missing) edits; intraclass correlation over subjects with >=2 docs (one-way ANOVA ICC)."""
import collections, glob, json, statistics as st, random
RUN = "DEVR_final7t"
subj = {}
for p in glob.glob("data/dev/*/*/images/page_*.jpg"): subj[p.split("/")[3]] = p.split("/")[2]
TB = json.load(open(f"scorer/result/drdoc_{RUN}_text_block_result.json"))
D = collections.defaultdict(lambda: collections.Counter())
for e in TB:
    d = e["img_id"].split("_")[0]; en = e["Edit_num"]
    D[d]["extra" if e["gt"] == "" else "missing" if e["pred"] == "" else "matched"] += en; D[d]["chars"] += e["upper_len"]
def feats(c):
    tot = c["extra"] + c["missing"]
    return (c["extra"] / tot if tot >= 200 else None, (c["extra"] + c["missing"]) / max(1, c["chars"]))
G = collections.defaultdict(list)
for d, c in D.items():
    f = feats(c)
    if f[0] is not None: G[subj[d]].append(f)
for idx, name in ((0, "share of unmatched text that is EXTRA (we add) vs MISSING (we drop)"), (1, "unmatched-text rate (extra+missing edits / reference chars)")):
    groups = [[x[idx] for x in v] for v in G.values() if len(v) >= 2]
    n = sum(len(g) for g in groups); k = len(groups); gm = st.mean(x for g in groups for x in g)
    ssb = sum(len(g) * (st.mean(g) - gm) ** 2 for g in groups); ssw = sum((x - st.mean(g)) ** 2 for g in groups for x in g)
    msb, msw = ssb / (k - 1), ssw / (n - k); n0 = (n - sum(len(g) ** 2 for g in groups) / n) / (k - 1)
    icc = (msb - msw) / (msb + (n0 - 1) * msw)
    # permutation p-value: shuffle doc->subject labels
    allx = [x for g in groups for x in g]; sizes = [len(g) for g in groups]; rng = random.Random(0); hits = 0
    for _ in range(2000):
        rng.shuffle(allx); gg = []; i = 0
        for s in sizes: gg.append(allx[i:i + s]); i += s
        b = sum(len(g) * (st.mean(g) - gm) ** 2 for g in gg); w = sum((x - st.mean(g)) ** 2 for g in gg for x in g)
        hits += (b / (k - 1)) / (w / (n - k)) >= msb / msw
    print(f"{name}\n   {k} subjects with >=2 docs ({n} docs): ICC = {icc:.2f}  (share of between-doc variance that is subject-level); permutation p = {hits/2000:.3f}")

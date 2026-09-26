"""Per-subject error profile on dev (final7t): which loss type dominates, and how the reference formats text (for subject-conditioned prompts)."""
import collections, glob, json, re, statistics as st
from compare_runs import load
RUN = "DEVR_final7t"
P = load(RUN); subj = {}
for p in glob.glob("data/dev/*/*/images/page_*.jpg"): subj[p.split("/")[3]] = p.split("/")[2]
TB = json.load(open(f"scorer/result/drdoc_{RUN}_text_block_result.json")); RO = {e["img_id"]: e["edit"] for e in json.load(open(f"scorer/result/drdoc_{RUN}_reading_order_result.json"))}
S = collections.defaultdict(lambda: collections.Counter()); ov = collections.defaultdict(list); tests = set(p.split("/")[2] for p in glob.glob("data/test/*/*/images/page_*.jpg"))
for k, v in P.items():
    if v["overall"] is not None: ov[subj[k.split("_")[0]]].append(v["overall"])
for e in TB:
    s = subj[e["img_id"].split("_")[0]]; en = e["Edit_num"]
    kind = "extra" if e["gt"] == "" else "missing" if e["pred"] == "" else "matched"
    S[s][kind] += en; S[s]["chars"] += e["upper_len"]
for k, o in RO.items(): S[subj[k.split("_")[0]]]["order_sum"] += o; S[subj[k.split("_")[0]]]["order_n"] += 1
nl = collections.defaultdict(lambda: [0, 0])
for f in glob.glob("eval_tmp/DEVR_final7t/gt/*.md"):
    s = subj[f.split("/")[-1].split("_")[0]]; t = open(f, encoding="utf-8").read()
    paras = [p for p in re.split(r"\n\s*\n", t) if p.strip() and not p.lstrip().startswith(("<table", "![", "$$"))]
    nl[s][0] += sum("\n" in p.strip() for p in paras); nl[s][1] += len(paras)
print(f"{'subject':26s} {'in test':7s} pages overall  order-loss  extra% missing% matched%  refs with in-paragraph newlines")
for s, v in sorted(ov.items(), key=lambda kv: st.mean(kv[1])):
    c = S[s]; tot = max(1, c["extra"] + c["missing"] + c["matched"])
    print(f"{s:26s} {'yes' if s in tests else 'no':7s} {len(v):4d} {st.mean(v):7.1f} {100*c['order_sum']/max(1,c['order_n']):9.1f}%  {100*c['extra']/tot:5.0f}  {100*c['missing']/tot:6.0f}  {100*c['matched']/tot:6.0f}      {100*nl[s][0]/max(1,nl[s][1]):4.0f}%")

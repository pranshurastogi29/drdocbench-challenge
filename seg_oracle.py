"""Upper bound for paragraph segmentation on dev: Text_ED if our text were split exactly at the reference's block boundaries.
Each reference block is located anywhere in our page text (order-free, best fuzzy alignment, non-overlapping), its edit distance to that
span is counted, and our text covered by no block counts as extra. Same per-page aggregation as the official metric:
sum(edits) / sum(max(len_ref, len_ours)).   python seg_oracle.py DEVR_final5 runs/dev_all_rebuilt_final5.jsonl
"""
import json, re, statistics as st, sys
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from common import gt_markdown, list_pages

N = lambda s: re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s))


def blocks(md):
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    out = []
    for b in md.split("\n\n"):
        b = b.strip()
        if not b or (b.startswith("<table") and b.endswith("</table>")) or (b.startswith("$") and b.endswith("$")):
            continue
        if N(b): out.append(N(b))
    return out


def oracle(gtb, ours):
    O = "".join(ours); used = [False] * len(O); edits = 0; upper = 0
    for g in sorted(gtb, key=len, reverse=True):       # long blocks first, they anchor best
        if not O:
            edits += len(g); upper += len(g); continue
        al = fuzz.partial_ratio_alignment(g, O) if len(g) <= len(O) else None
        if al is None or al.score < 50:
            edits += len(g); upper += len(g); continue
        s, e = al.dest_start, al.dest_end
        seg = O[s:e]
        d = Levenshtein.distance(g, seg); edits += d; upper += max(len(g), len(seg))
        for i in range(s, e): used[i] = True
    extra = used.count(False) if O else 0
    return (edits + extra) / max(upper + extra, 1)


if __name__ == "__main__":
    name, ours_file = sys.argv[1], sys.argv[2]
    subj = {d: s for (s, d) in list_pages("dev")}
    E = json.load(open(f"scorer/result/drdoc_{name}_text_block_per_page_edit.json"))
    ours = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(ours_file))}
    act, orc = [], []
    for k, v in E.items():
        stem = k[:-4]; doc, pg = stem.rsplit("_", 1)
        g = blocks(gt_markdown("dev", subj[doc], doc, int(pg))); o = blocks(ours.get(stem, ""))
        if not g and not o: continue
        act.append(v); orc.append(oracle(g, o))
    a, b = st.mean(act), st.mean(orc)
    print(f"pages {len(act)} | actual Text_ED {a:.4f} | perfect-boundary Text_ED {b:.4f} | boundaries cost {a - b:+.4f} ({(a - b) / a:.0%} of total; about {0.558 * 100 * (a - b):.1f} overall points)")
    print(f"pages where perfect boundaries help by > 0.05: {sum(1 for x, y in zip(act, orc) if x - y > 0.05)}; hurt by > 0.05 (alignment noise): {sum(1 for x, y in zip(act, orc) if y - x > 0.05)}")

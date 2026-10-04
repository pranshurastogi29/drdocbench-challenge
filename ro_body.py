"""Body-text reading-order analysis on dev: where our paired blocks sit in a different order from the reference, and what layout pattern explains it.
Each paired reference block is mapped (by text) to its box and its reference `order` in the dev layout JSON; our order is the scorer's pred order.
Per page we compare three orders over the same paired body blocks: reference, ours, and two geometric conventions (column-major: by column then top
to bottom; row-major: top to bottom then left to right)."""
import json, glob, re, collections, statistics as st
from rapidfuzz import fuzz
from scipy.stats import kendalltau
W = lambda s: re.sub(r"[\W_]", "", (s or "").lower())
FUR = {"header", "footer", "page_number"}


def main(name="DEVR_final5"):
    RO = {x["img_id"]: x for x in json.load(open(f"scorer/result/drdoc_{name}_reading_order_result.json"))}
    TB = json.load(open(f"scorer/result/drdoc_{name}_text_block_result.json"))
    pos2txt = collections.defaultdict(dict)
    for x in TB:
        if x["norm_gt"] and isinstance(x["gt_position"], list):
            for gp in x["gt_position"]:
                if gp != "": pos2txt[x["img_id"]][gp] = x["gt"]
    stats = collections.Counter(); per_layout = collections.defaultdict(list); examples = collections.defaultdict(list)
    for f in glob.glob("data/dev/*/*/json/*.json"):
        j = json.load(open(f))
        if not j: continue
        pa = j[0]["page_info"]; img = f"{pa['page_name']}_{pa['page_no']}.jpg"
        if img not in RO: continue
        lay = pa["page_attribute"].get("layout"); Wd = pa["width"]
        dets = [(W(b.get("text")), b) for b in j[0]["layout_dets"] if b["category_type"] not in FUR and W(b.get("text")) and "order" in b]
        pred = RO[img]["pred"]
        rows = []
        for rank, gp in enumerate(pred):          # our order
            t = W(pos2txt[img].get(gp, ""))
            if len(t) < 4: continue
            best, bb = 0, None
            for w, b in dets:
                s = fuzz.ratio(t[:150], w[:150])
                if s > best: best, bb = s, b
            if bb is None or best < 75: continue
            xs, ys = bb["poly"][0::2], bb["poly"][1::2]
            rows.append({"ours": rank, "ref": bb["order"], "x": (min(xs) + max(xs)) / 2 / Wd, "x0": min(xs) / Wd, "y": min(ys), "cat": bb["category_type"]})
        if len(rows) < 4 or len({r["ref"] for r in rows}) < len(rows): continue
        ours = [r["ref"] for r in sorted(rows, key=lambda r: r["ours"])]
        ref = sorted(ours)
        if ours == ref:
            stats["pages in correct order"] += 1; continue
        col = lambda r: 0 if r["x0"] < 0.45 and r["x"] < 0.5 else 1
        colmaj = [r["ref"] for r in sorted(rows, key=lambda r: (col(r), r["y"]))]
        rowmaj = [r["ref"] for r in sorted(rows, key=lambda r: (round(r["y"] / 12), r["x"]))]
        tau_ours = kendalltau(range(len(ours)), ours).correlation
        tau = lambda seq: kendalltau(range(len(seq)), seq).correlation
        stats["pages with order errors"] += 1
        # classify: is OUR order a geometric convention the reference does not follow?
        if ours == rowmaj and ref == colmaj: c = "we read across columns (row-major), reference reads down columns"
        elif ours == colmaj and ref == rowmaj: c = "we read down columns, reference reads across (row-major)"
        else:
            moved = sorted(rows, key=lambda r: r["ours"])
            disp = [r for i, r in enumerate(moved) if abs(sorted(ours).index(r["ref"]) - i) >= 2]
            cats = collections.Counter(r["cat"] for r in disp)
            c = "local swaps / single displaced block" if len(disp) <= 2 else "several blocks in a different order"
            if cats and cats.most_common(1)[0][0] in ("figure_caption", "figure_footnote", "table_caption"): c = "caption / figure note placed differently"
        stats[c] += 1; per_layout[lay].append(c)
        if len(examples[c]) < 3: examples[c].append((img[:6] + "_p" + img[:-4].rsplit("_", 1)[1], lay, round(tau_ours, 2)))
    print(f"pages with >= 4 mapped body blocks: {stats['pages in correct order'] + stats['pages with order errors']} | correct order: {stats['pages in correct order']} | with order errors: {stats['pages with order errors']}\n")
    for k, v in stats.most_common():
        if k.startswith("pages"): continue
        print(f"  {v:>4}  {k}   e.g. {examples[k]}")
    print("\nerror pages by layout:")
    for lay, cs in sorted(per_layout.items(), key=lambda kv: -len(kv[1])):
        print(f"  {str(lay):<16} {len(cs):>4}   {dict(collections.Counter(cs).most_common(3))}")


if __name__ == "__main__":
    main()

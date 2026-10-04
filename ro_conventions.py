"""What ordering conventions does the dev reference follow? (layout JSON: every block's box and its reading-order index)
Questions a prompt could encode:
  captions      : next to their figure/table in the order? before or after it? caption above or below the picture?
  footnotes     : page footnotes last in the body? figure/table footnotes right after their figure/table?
  equation nos. : right after their equation?
  titles        : where a title sits in the order vs. geometry
  columns       : on multi-column pages, column by column (column-major) or across (row-major)? full-width blocks as band breaks?
  pictures      : text blocks inside / overlapping a figure box: order position
  python ro_conventions.py
"""
import collections, glob, json, statistics as st

FUR = {"header", "footer", "page_number"}


def box(b):
    p = b["poly"]; xs, ys = p[0::2], p[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def load():
    for f in sorted(glob.glob("data/dev/*/*/json/*.json")):
        j = json.load(open(f))
        if not j: continue
        x = j[0]; W, H = x["page_info"]["width"], x["page_info"]["height"]
        B = [dict(cat=b["category_type"], order=b.get("order"), box=box(b), text=(b.get("text") or "")[:60]) for b in x["layout_dets"] if not b.get("ignore")]
        yield f, x["page_info"], W, H, B


def main():
    S = collections.Counter(); ex = collections.defaultdict(list)
    col_pages = collections.Counter()
    for f, info, W, H, B in load():
        O = sorted([b for b in B if b["order"] is not None], key=lambda b: b["order"])
        if not O: continue
        idx = {id(b): i for i, b in enumerate(O)}
        body = [b for b in O if b["cat"] not in FUR]
        # ---- captions vs their figure/table
        for cap, tgt in (("figure_caption", "figure"), ("table_caption", "table"), ("figure_footnote", "figure"), ("table_footnote", "table"), ("equation_caption", "equation_isolated")):
            for c in [b for b in O if b["cat"] == cap]:
                cands = [b for b in O if b["cat"] == tgt]
                if not cands: S[(cap, "no target")] += 1; continue
                cx = (c["box"][0] + c["box"][2]) / 2; cy = (c["box"][1] + c["box"][3]) / 2
                t = min(cands, key=lambda b: abs((b["box"][1] + b["box"][3]) / 2 - cy) + abs((b["box"][0] + b["box"][2]) / 2 - cx))
                d = idx[id(c)] - idx[id(t)]
                S[(cap, "order: right after target" if d == 1 else "order: right before target" if d == -1 else "order: later, not adjacent" if d > 1 else "order: earlier, not adjacent")] += 1
                S[(cap, "geometry: below target" if c["box"][1] >= t["box"][3] - 5 else "geometry: above target" if c["box"][3] <= t["box"][1] + 5 else "geometry: beside/overlap")] += 1
                # is the caption placed by its own vertical position among body text? (text blocks above it come before it)
                txt = [b for b in body if b["cat"] in ("text_block", "title") and abs(((b["box"][0] + b["box"][2]) / 2) - cx) < W * 0.35]
                above = [b for b in txt if b["box"][3] <= c["box"][1] + 3]; below = [b for b in txt if b["box"][1] >= c["box"][3] - 3]
                if above or below:
                    ok = all(idx[id(b)] < idx[id(c)] for b in above) and all(idx[id(b)] > idx[id(c)] for b in below)
                    S[(cap, "flow: placed by its vertical position among nearby text" if ok else "flow: NOT by vertical position")] += 1
                    if not ok and len(ex[cap]) < 4: ex[cap].append(f.split("/")[-1])
        # ---- page footnotes
        for c in [b for b in body if b["cat"] == "page_footnote"]:
            S[("page_footnote", "last body block(s)" if all(idx[id(b)] < idx[id(c)] or b["cat"] == "page_footnote" for b in body) else "not last")] += 1
        # ---- titles: does the order follow geometry around them?
        for c in [b for b in body if b["cat"] == "title"]:
            nxt = [b for b in body if idx[id(b)] == idx[id(c)] + 1]
            if nxt:
                n = nxt[0]
                S[("title", "next block is below it" if n["box"][1] >= c["box"][1] - 3 else "next block is ABOVE it")] += 1
        # ---- columns: body text blocks, multi-column if two blocks overlap vertically and sit side by side
        T = [b for b in body if b["cat"] in ("text_block", "title", "figure_caption", "table_caption", "page_footnote") and b["box"][2] - b["box"][0] < 0.6 * W]
        side = [(a, b) for a in T for b in T if a is not b and a["box"][2] <= b["box"][0] + 5 and min(a["box"][3], b["box"][3]) - max(a["box"][1], b["box"][1]) > 10]
        if side:
            cm = rm = 0
            for a, b in side:          # a is left of b, both on the same band
                if idx[id(a)] < idx[id(b)]: cm += 1
                else: rm += 1
            # column-major vs row-major: does a LEFT block lower on the page come before a RIGHT block higher up?
            lowleft_first = sum(1 for a in T for b in T if a["box"][2] <= b["box"][0] + 5 and a["box"][1] > b["box"][3] and idx[id(a)] < idx[id(b)])
            lowleft_after = sum(1 for a in T for b in T if a["box"][2] <= b["box"][0] + 5 and a["box"][1] > b["box"][3] and idx[id(a)] > idx[id(b)])
            col_pages["multi-column pages"] += 1
            col_pages["left-before-right on same band"] += cm; col_pages["right-before-left on same band"] += rm
            col_pages["lower-left before upper-right (column-major)"] += lowleft_first; col_pages["upper-right before lower-left (row-major)"] += lowleft_after
    cur = None
    for (cat, k), v in sorted(S.items()):
        if cat != cur: print(f"\n{cat}"); cur = cat
        print(f"   {k:58s} {v}")
    print("\ncolumns:", dict(col_pages))
    for k, v in ex.items(): print("  examples not by vertical position:", k, v)


if __name__ == "__main__":
    main()

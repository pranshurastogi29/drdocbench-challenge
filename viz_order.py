"""Draw reference vs our reading order on dev pages: each reference block boxed and labelled R<ref rank> / O<our rank>.
Red = we placed it out of order (not in the longest correctly-ordered subsequence), green = in order, grey = reference block we never paired.
  python viz_order.py STEM [STEM ...]   -> viz/<stem>.png"""
import json, glob, re, sys, collections
from PIL import Image, ImageDraw, ImageFont
from rapidfuzz import fuzz
from compare_runs import lis_keep

W = lambda s: re.sub(r"[\W_]", "", (s or "").lower())
import os
NAME = os.environ.get("RUN", "DEVR_final5")   # scored run to draw
RO = {x["img_id"]: x for x in json.load(open(f"scorer/result/drdoc_{NAME}_reading_order_result.json"))}
TB = json.load(open(f"scorer/result/drdoc_{NAME}_text_block_result.json"))
pos2txt = collections.defaultdict(dict)
for x in TB:
    if x["norm_gt"] and isinstance(x["gt_position"], list):
        for gp in x["gt_position"]:
            if gp != "": pos2txt[x["img_id"]][gp] = x["gt"]
try:
    FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    SMALL = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
except Exception:
    FONT = SMALL = ImageFont.load_default()


def draw(stem, note=""):
    img_id = stem + ".jpg"; doc, pg = stem.rsplit("_", 1)
    jf = glob.glob(f"data/dev/*/{doc}/json/{doc}_page_{pg}.json")[0]; imf = glob.glob(f"data/dev/*/{doc}/images/page_{pg}.jpg")[0]
    j = json.load(open(jf))[0]; dets = [(W(b.get("text")), b) for b in j["layout_dets"] if W(b.get("text"))]
    ro = RO[img_id]; g, p = ro["gt"], ro["pred"]
    keep = lis_keep(p); ref_rank = {v: i + 1 for i, v in enumerate(sorted(g))}
    S = 2.0
    im = Image.open(imf).convert("RGB"); im = im.resize((int(im.width * S), int(im.height * S)))
    d = ImageDraw.Draw(im, "RGBA")
    def box(gp):
        t = W(pos2txt[img_id].get(gp, ""))
        best, bb = 0, None
        for w, b in dets:
            s = fuzz.ratio(t[:150], w[:150])
            if s > best: best, bb = s, b
        if bb is None or best < 70: return None, None
        xs, ys = bb["poly"][0::2], bb["poly"][1::2]
        return [min(xs) * S, min(ys) * S, max(xs) * S, max(ys) * S], bb["category_type"]
    paired = set(p)
    for gp in g:                                   # reference blocks we never paired
        if gp in paired: continue
        bb, cat = box(gp)
        if bb: d.rectangle(bb, outline=(120, 120, 120, 255), width=3, fill=(120, 120, 120, 40)); d.text((bb[0] + 4, bb[1] + 2), f"R{ref_rank[gp]} missed", fill=(90, 90, 90), font=SMALL)
    for i, gp in enumerate(p):
        bb, cat = box(gp)
        if not bb: continue
        ok = i in keep; col = (30, 150, 60) if ok else (220, 30, 30)
        d.rectangle(bb, outline=col + (255,), width=4, fill=col + (35,))
        label = f"R{ref_rank.get(gp, '?')} / O{i + 1}" + ("" if ok else "  OUT OF ORDER")
        tw = d.textlength(label, font=FONT)
        d.rectangle([bb[0], bb[1] - 26, bb[0] + tw + 8, bb[1]], fill=col + (230,))
        d.text((bb[0] + 4, bb[1] - 25), label, fill=(255, 255, 255), font=FONT)
    head = Image.new("RGB", (im.width, 90), (255, 255, 255)); hd = ImageDraw.Draw(head)
    score = 100 * (1 - ro["edit"])
    hd.text((10, 8), f"{doc[:8]} page {pg}   reading order {score:.0f}/100   R = reference position, O = our position", fill=(0, 0, 0), font=FONT)
    hd.text((10, 46), note, fill=(60, 60, 60), font=SMALL)
    out = Image.new("RGB", (im.width, im.height + 90), (255, 255, 255)); out.paste(head, (0, 0)); out.paste(im, (0, 90))
    path = f"viz/{stem}{os.environ.get('SUFFIX', '')}.png"; out.save(path); print(path, f"order score {score:.0f}")
    return path


if __name__ == "__main__":
    for a in sys.argv[1:]:
        stem, _, note = a.partition("|"); draw(stem, note)

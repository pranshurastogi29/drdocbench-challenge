import glob, json, re, sys
key, pred_file = sys.argv[1], sys.argv[2]
page, idx = key.rsplit("_[", 1); idx = int(idx[:-1]); doc = page.split("_")[0]; pg = re.search(r"_(\d+)\.jpg", page).group(1)
p = glob.glob(f"data/dev/*/{doc}/json/*_page_{pg}.json")[0]; i = 0
for b in json.load(open(p, encoding="utf-8"))[0]["layout_dets"]:
    if b["category_type"] == "table":
        if i == idx: g = b["html"]
        i += 1
pred = {f"{x['document_id']}_{x['page']}.jpg": x["markdown"] for x in map(json.loads, open(pred_file, encoding="utf-8"))}
pt = re.findall(r"<table\b.*?</table>", pred[page], re.S | re.I)[idx]
sq = lambda h: re.sub(r"\s*\n\s*", "", re.sub(r' style="[^"]*"', "", h))
print("GT  :", sq(g)[:1800]); print("PRED:", sq(pt)[:1800])

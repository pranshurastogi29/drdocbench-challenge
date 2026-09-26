import glob, json, os, collections
from paddle_ingest import OUT
c = collections.Counter(); ex = None
for p in glob.glob(f"{OUT}/*/*_res.json"):
    stem = os.path.basename(os.path.dirname(p)); pl = json.load(open(p))["parsing_res_list"]
    tb = [b for b in pl if b["block_label"] == "table"]
    c["pages"] += 1; c["table_blocks"] += len(tb); c["pages_with_table"] += bool(tb)
    if tb and ex is None: ex = (stem, {k: (v if k != "block_content" else v[:60]) for k, v in tb[0].items()})
print(dict(c)); print(ex); print(OUT)

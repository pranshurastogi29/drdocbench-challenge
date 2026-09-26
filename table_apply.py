"""Apply the table vote to a predictions file (dev or test rows) and write a new jsonl.

  python table_apply.py runs/dev_all_final5.jsonl runs/dev_all_tv.jsonl runs/tables_dev_t1.jsonl runs/tables_dev_t2.jsonl [--no-paddle]
"""
import json, sys
from table_merge import load_crops
from table_vote import vote_page
if __name__ == "__main__":
    src, dst, *files = sys.argv[1:]; paddle = "--no-paddle" not in files; files = [f for f in files if not f.startswith("--")]
    sets = []
    for f in files:
        C = load_crops(f); sets.append({s: {i: t for i, t in v} for s, v in C.items()})
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]; n = 0
    with open(dst, "w", encoding="utf-8") as fo:
        for r in rows:
            k = f"{r['document_id']}_{r['page']}"
            if any(k in s for s in sets):
                new = vote_page(k, r["markdown"], [s.get(k, {}) for s in sets], {}, paddle, "place"); n += new != r["markdown"]; r = {**r, "markdown": new}
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} rows, {n} pages changed -> {dst}")

"""Table pool: append to each page every distinct table that any source produced for it (crop passes, Paddle, MinerU, model runs), in the
reference's HTML style. The table metric drops predicted tables that pair with no reference table, and tables are matched separately from text
and reading order, so extra candidates can only help the best table match (Table_TEDS is worth ~0.006 overall per point: small but free).
  python table_pool.py SRC DST --split dev|test
"""
import argparse, json, re
from variants import tables_variant
from table_merge import load_crops

TAB = re.compile(r"<table\b.*?</table>", re.S | re.I)
RUNS = {"dev": ["runs/dev_all_full_bunny.jsonl", "runs/dev_all_v7_final.jsonl", "runs/dev_all_v8_final.jsonl", "runs/dev_all_v7c_final.jsonl",
                "runs/dev_all_v6_w1.jsonl", "runs/dev_all_v7_w1.jsonl", "runs/dev_all_v8_w1.jsonl", "runs/dev_all_v7_1200.jsonl",
                "runs/paddle_dev.jsonl", "runs/mineru_dev.jsonl"],
        "test": ["runs/test_all_v6.jsonl", "runs/test_all_v7.jsonl", "runs/test_all_v8.jsonl", "runs/test_all_v7c_test.jsonl",
                 "runs/test_all_v6_w1.jsonl", "runs/test_all_v7_w1.jsonl", "runs/test_all_v8_w1.jsonl", "runs/test_all_v7_1200.jsonl",
                 "runs/paddle_test.jsonl", "runs/mineru_test.jsonl"]}
CROPS = {"dev": ["runs/tables_dev_t1.jsonl", "runs/tables_dev_t2.jsonl", "runs/tables_dev_t3.jsonl"],
         "test": ["runs/tables_test_t1.jsonl", "runs/tables_test_t2.jsonl", "runs/tables_test_t3.jsonl"]}
K = lambda t: re.sub(r"\s+", "", t)


def tables(md):
    return [tables_variant(t) for t in TAB.findall(md or "")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--split", default="dev")
    a = ap.parse_args()
    runs = [{f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(f, encoding="utf-8"))} for f in RUNS[a.split]]
    crops = [load_crops(f) for f in CROPS[a.split]]
    n = added = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            stem = f'{r["document_id"]}_{r["page"]}'; md = r["markdown"]
            have = {K(t) for t in TAB.findall(md)}; extra = []
            cands = [t for c in crops for _, t in sorted(c.get(stem, []))] + [t for R in runs for t in tables(R.get(stem, ""))]
            for t in cands:
                if K(t) not in have:
                    have.add(K(t)); extra.append(t)
            if extra:
                md = md.rstrip() + "\n\n" + "\n\n".join(extra); n += 1; added += len(extra)
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages got extra table candidates ({added} added)")

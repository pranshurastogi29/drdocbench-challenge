"""Run the official DrDocBench md2md scorer (scorer/, quick_match) on a predictions jsonl, without CDM.

  python run_md2md_eval.py runs/dev_b_b_v3.jsonl [--name b_v3]

Builds flat gt/pred folders of <doc>_<page>.md (the layout the scorer expects), runs the scorer's own dataset,
matching and metric code unchanged (mmeval, which only the detection tasks use, is stubbed out), and prints the
per-metric results. Only pages present in the predictions file are scored.
"""
import argparse
import glob
import json
import os
import shutil
import sys
import types

ROOT = os.path.dirname(os.path.abspath(__file__))
SCORER = os.path.join(ROOT, "scorer")


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return type(name, (), {})


sys.modules["mmeval"] = _Stub("mmeval")
sys.path.insert(0, SCORER)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pred")
    ap.add_argument("--name")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--match", default="quick_match")
    ap.add_argument("--restrict-to", help="only score pages that also appear in this predictions file (for A/B comparisons)")
    ap.add_argument("-q", "--quiet", action="store_true", help="print only the compact summary")
    args = ap.parse_args()
    name = args.name or os.path.splitext(os.path.basename(args.pred))[0]

    work = os.path.join(ROOT, "eval_tmp", name)
    shutil.rmtree(work, ignore_errors=True)
    gt_dir, pred_dir = os.path.join(work, "gt"), os.path.join(work, "pred")
    os.makedirs(gt_dir)
    os.makedirs(pred_dir)
    n = 0
    keep = None
    if args.restrict_to:
        keep = {(r["document_id"], r["page"]) for r in map(json.loads, open(args.restrict_to, encoding="utf-8"))}
    for line in open(args.pred, encoding="utf-8"):
        r = json.loads(line)
        if keep is not None and (r["document_id"], r["page"]) not in keep:
            continue
        fn = f"{r['document_id']}_{r['page']}.md"
        src = os.path.join(ROOT, "data", args.split, r["subject"], r["document_id"], "mds", fn)
        if not os.path.exists(src):
            continue
        shutil.copy(src, os.path.join(gt_dir, fn))
        open(os.path.join(pred_dir, fn), "w", encoding="utf-8").write(r["markdown"])
        n += 1
    print(f"{n} pages staged in {work}", file=sys.stderr)

    os.chdir(SCORER)  # the scorer writes ./result/ relative to cwd
    os.makedirs("result", exist_ok=True)
    from registry.registry import DATASET_REGISTRY, EVAL_TASK_REGISTRY
    import dataset  # noqa: F401
    import metrics  # noqa: F401
    import task  # noqa: F401

    cfg = {
        "dataset": {
            "dataset_name": "md2md_dataset",
            "ground_truth": {"data_path": gt_dir},
            "prediction": {"data_path": pred_dir},
            "match_method": args.match,
        }
    }
    ds = DATASET_REGISTRY.get("md2md_dataset")(cfg)
    metrics_list = {
        "text_block": {"metric": ["Edit_dist"]},
        "display_formula": {"metric": ["Edit_dist"]},
        "table": {"metric": ["TEDS", "Edit_dist"]},
        "reading_order": {"metric": ["Edit_dist"]},
    }
    if args.quiet:
        real = sys.stdout
        sys.stdout = open(os.devnull, "w")
    EVAL_TASK_REGISTRY.get("end2end_eval")(ds, metrics_list, gt_dir, f"drdoc_{name}")
    if args.quiet:
        sys.stdout = real
    summary(name, n)


def summary(name, n):
    """Leaderboard-style numbers: Text_ED (lower better), Table_TEDS, Reading_Order (higher better), and a per-page
    overall = mean of the components present on each page (text, reading order, table TEDS when the page has tables;
    formulas/CDM not scored locally)."""
    res = os.path.join(SCORER, "result")
    load = lambda f: json.load(open(os.path.join(res, f"drdoc_{name}_{f}.json")))
    m = load("metric_result")
    text_pp, ro_pp = load("text_block_per_page_edit"), load("reading_order_per_page_edit")
    teds = m["table"]["all"].get("TEDS", {}).get("all")
    ro = 1 - m["reading_order"]["all"]["Edit_dist"]["ALL_page_avg"]
    text = sum(text_pp.values()) / len(text_pp)
    tb = {}
    try:
        for key, v in load("table_per_table_TEDS").items():
            tb.setdefault(key.rsplit("_[", 1)[0], []).append(100 * v["TEDS"])
    except FileNotFoundError:
        pass
    pages = {}
    for k in set(text_pp) | set(ro_pp):
        comps = [100 * (1 - v[k]) for v in (text_pp, ro_pp) if k in v]
        if k in tb:
            comps.append(sum(tb[k]) / len(tb[k]))
        pages[k] = sum(comps) / len(comps)
    overall = sum(pages.values()) / len(pages)
    print(f"[{name}] pages={n} scored={len(pages)}  Text_ED={text:.4f}  Table_TEDS={100 * teds:.2f}  Reading_Order={100 * ro:.2f}  "
          f"Overall~={overall:.2f}")


if __name__ == "__main__":
    main()

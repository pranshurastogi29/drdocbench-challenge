"""Rebuild any submission from the archived candidate runs (deterministic: no model calls).

  python build_submission.py final5_wd            -> submissions/rebuilt_final5_wd.zip
  python build_submission.py --verify final5      -> also compares against submissions/submission_final5.zip

Pipelines (each adds one step to the previous):
  medoid4_snap : medoid of v6,v7,v8,paddle -> split-snap to Paddle layout blocks (cap 9 new paragraphs/page)
  best         : + Paddle tables added where no candidate has a table                      (leaderboard 77.39)
  final5       : medoid of v6,v7,v8,paddle,v7c (contrast-processed v7) + the same steps    (leaderboard 78.66)
  final7       : medoid of all 3 plain + 3 contrast-processed prompts + paddle (dev +0.39 vs final5, CI includes 0)
  final7t      : final7 + table vote: medoid of 3 crop-pass transcriptions + Paddle's table replaces our table (dev Table_TEDS 70.0 -> 77.0)
  final8       : final7t + rule-line removal (cleanlines.py); dev overall 85.89
  final5_wd    : + duplicate $\\textit{..}$ copy of every short standalone line (formula channel)
The LLM outputs themselves (runs/test_all_*.jsonl) are archived, not regenerable byte-for-byte.
"""
import argparse, collections, itertools, json, os, re, statistics, sys, zipfile
from rapidfuzz import fuzz
from common import list_pages
from common import DATA  # noqa: F401
from postprocess import strip_sections
from snap import snap
from tablefix import fix
from wrapdup import add as wrapdup
from cleanlines import clean as cleanlines
from repair import figdrop, spill
from indexsplit import split_index
from xdrop import xdrop

ROOT = os.path.dirname(os.path.abspath(__file__))
TEST = {"v6": "runs/test_all_v6.jsonl", "v7": "runs/test_all_v7.jsonl", "v8": "runs/test_all_v8.jsonl",
        "paddle": "runs/paddle_test.jsonl", "v7c": "runs/test_all_v7c_test.jsonl",
        "v6c": "runs/test_all_v6c_test.jsonl", "v8c": "runs/test_all_v8c_test.jsonl", "v7s": "runs/test_all_v7_1200.jsonl",
        "v6w1": "runs/test_all_v6_w1.jsonl", "v7w1": "runs/test_all_v7_w1.jsonl", "v8w1": "runs/test_all_v8_w1.jsonl", "v7cw1": "runs/test_all_v7c_w1.jsonl",
        "v7sw1": "runs/test_all_v7sw1.jsonl", "v5w1": "runs/test_all_v5w1.jsonl", "v7tw1": "runs/test_all_v7tw1.jsonl"}
CFG = {"medoid4_snap": (["v6", "v7", "v8", "paddle"], False, False),
       "best": (["v6", "v7", "v8", "paddle"], True, False),
       "final5": (["v6", "v7", "v8", "paddle", "v7c"], True, False),
       "final5_wd": (["v6", "v7", "v8", "paddle", "v7c"], True, True),
       "final7": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, False),
       "final7_wd": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, True),
       "final7t": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, False, True),
       "final7t_wd": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, True, True),
       "final8": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, False, True, True),
       "final8_wd": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, True, True, True),
       "final9": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, False, True, True, True),
       "final9_wd": (["v6", "v7", "v8", "paddle", "v6c", "v7c", "v8c"], True, True, True, True, True),
       "final5t": (["v6", "v7", "v8", "paddle", "v7c"], True, False, True),
       "final5t_wd": (["v6", "v7", "v8", "paddle", "v7c"], True, True, True),
       "final5i": (["v6", "v7", "v8", "paddle", "v7c"], True, False, False, False, False, True),
       "final5i_wd": (["v6", "v7", "v8", "paddle", "v7c"], True, True, False, False, False, True),
       "final5ti_wd": (["v6", "v7", "v8", "paddle", "v7c"], True, True, True, False, False, True),
       "final5s": (["v6", "v7", "v8", "paddle", "v7c", "v7s"], True, False),
       "final5s_wd": (["v6", "v7", "v8", "paddle", "v7c", "v7s"], True, True),
       "final5a": (["v6", "v7", "v8", "paddle", "v7c", "v7w1"], True, False),
       "final5a_wd": (["v6", "v7", "v8", "paddle", "v7c", "v7w1"], True, True),
       "final5b": (["v6w1", "v7w1", "v8w1", "paddle", "v7c"], True, False),
       "final5b_wd": (["v6w1", "v7w1", "v8w1", "paddle", "v7c"], True, True),
       "final5c": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1"], True, False),
       "final5c_wd": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1"], True, True),
       "final5d": (["v6w1", "v7w1", "v8w1", "paddle", "v7cw1"], True, False),
       "final5d_wd": (["v6w1", "v7w1", "v8w1", "paddle", "v7cw1"], True, True),
       "final5e": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v7sw1"], True, False),
       "final5e_wd": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v7sw1"], True, True),
       "final5f": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v5w1"], True, False),
       "final5f_wd": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v5w1"], True, True),
       "final5g": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v7sw1", "v5w1"], True, False),
       "final5g_wd": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v7sw1", "v5w1"], True, True),
       "final5h": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v7tw1"], True, False),
       "final5h_wd": (["v6", "v7", "v8", "paddle", "v7c", "v6w1", "v7w1", "v8w1", "v7tw1"], True, True),
       "final5x": (["v6", "v7", "v8", "paddle", "v7c"], True, False, False, False, False, False, True),
       "final5x_wd": (["v6", "v7", "v8", "paddle", "v7c"], True, True, False, False, False, False, True)}
DEV = {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl",
       "paddle": "runs/paddle_dev.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl", "v6c": "runs/dev_all_v6c_final.jsonl", "v8c": "runs/dev_all_v8c_final.jsonl", "v7s": "runs/dev_all_v7_1200.jsonl",
       "v6w1": "runs/dev_all_v6_w1.jsonl", "v7w1": "runs/dev_all_v7_w1.jsonl", "v8w1": "runs/dev_all_v8_w1.jsonl", "v7cw1": "runs/dev_all_v7c_w1.jsonl",
       "v7sw1": "runs/dev_all_v7sw1.jsonl", "v5w1": "runs/dev_all_v5w1.jsonl", "v7tw1": "runs/dev_all_v7tw1.jsonl"}
TABLE_CROPS_DEV = ["runs/tables_dev_t1.jsonl", "runs/tables_dev_t2.jsonl", "runs/tables_dev_t3.jsonl"]
SPLIT = "test"      # `--split dev` rebuilds the same pipeline on the dev pages (jsonl out) so it can be scored with the official scorer
TABLE_CROPS = ["runs/tables_test_t1.jsonl", "runs/tables_test_t2.jsonl", "runs/tables_test_t3.jsonl"]
MAX_ADD = 9
para = lambda m: len([p for p in re.split(r"\n\s*\n", m.strip()) if p.strip()])
nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]


def rd(p):
    return {(r["document_id"], r["page"]): r for r in map(json.loads, open(os.path.join(ROOT, p), encoding="utf-8"))}


def medoid(texts, names):
    sc = {n: sum(fuzz.ratio(nz(texts[n]), nz(texts[m])) for m in names if m != n) for n in names}
    return max(names, key=lambda n: (sc[n], n in ("v7", "v7w1")))


def agreement(texts, names):
    w = {n: re.sub(r"\W", "", texts[n].lower())[:4000] for n in names}
    return statistics.mean(fuzz.ratio(w[a], w[b]) for a, b in itertools.combinations(names, 2))


def build(name):
    names, tables, wrap, *rest = CFG[name]; tv = bool(rest and rest[0]); cl = bool(len(rest) > 1 and rest[1]); rp = bool(len(rest) > 2 and rest[2])
    ix = bool(len(rest) > 3 and rest[3]); xd = bool(len(rest) > 4 and rest[4])
    if tv:      # table vote: needs the scorer checkout (its table normaliser) and the crop-pass outputs
        from table_merge import load_crops
        from table_vote import vote_page
        crops = [{st: {i: t for i, t in v} for st, v in load_crops(os.path.join(ROOT, f)).items()} for f in (TABLE_CROPS_DEV if SPLIT == 'dev' else TABLE_CROPS)]
    R = {n: rd((DEV if SPLIT == 'dev' else TEST)[n]) for n in names}
    out = []
    ref = next(iter(R.values()))
    for k in [k for k in ref if all(k in R[n] for n in names)]:
        base = ref[k]
        t = {n: strip_sections(R[n][k]["markdown"]).strip() for n in names}
        md = t[medoid(t, names)]; stem = f"{k[0]}_{k[1]}"
        s = snap(md, stem, mode="split")
        if para(s) - para(md) > MAX_ADD:      # heavy re-splits are a coin flip on dev: leave those pages alone
            s = md
        if ix:
            s = split_index(s)    # back-of-book index paragraphs: one entry per line -> one entry per paragraph (indexsplit.py)
        if tables:
            s, _ = fix(s, stem, replace=False)
        if xd and agreement(t, [n for n in names if n != "paddle"]) < 97:
            # we write >1.3x Paddle's text: drop our paragraphs Paddle lacks entirely (xdrop.py). Skipped when our runs agree
            # near-verbatim: that is legible body text Paddle under-read (a dense street index), not text inside a picture
            s = xdrop(s, t["paddle"], ratio=1.3, match=60, min_keep=4)
        if tv:
            s = vote_page(stem, s, [c.get(stem, {}) for c in crops], {}, True, "place")
        if cl:
            s = cleanlines(s)       # drop standalone ____ / ..... / ---- paragraphs: 0 in the dev reference, 73 in our output
        if wrap:
            s = wrapdup(s, "short")
        out.append({"subject": base["subject"], "document_id": k[0], "page": k[1], "markdown": s})
    out.sort(key=lambda r: (r["subject"], r["document_id"], r["page"]))
    if rp:
        from PIL import Image
        from common import windows as _windows
        by = {(r["document_id"], r["page"]): r for r in out}
        size = {}
        for (subj, doc), pages in list_pages("dev" if SPLIT == "dev" else "test").items():
            for pg, path in pages: size[(doc, pg)] = Image.open(path).size
        for (subj, doc), pages in list_pages("dev" if SPLIT == "dev" else "test").items():
            for w in _windows(pages, 2):
                if len(w) < 2: continue
                (pa, _), (pb, _) = w; ka, kb = (doc, pa), (doc, pb)
                if ka in by and kb in by:
                    na, nb = spill(by[ka]["markdown"], by[kb]["markdown"], f"{doc}_{pa}", f"{doc}_{pb}")
                    by[ka] = {**by[ka], "markdown": na}; by[kb] = {**by[kb], "markdown": nb}
        for k, r in by.items():
            new = figdrop(r["markdown"], f"{k[0]}_{k[1]}", size[k], 0.3)
            by[k] = {**r, "markdown": new}
        out = [by[(r["document_id"], r["page"])] for r in out]
    return out


def write_zip(rows, path):
    tmp = os.path.join(ROOT, "predictions.jsonl")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z: z.write(tmp, "predictions.jsonl")
    os.remove(tmp)


def zip_rows(path):
    return [json.loads(l) for l in zipfile.ZipFile(path).open("predictions.jsonl")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("pipeline", choices=list(CFG)); ap.add_argument("--verify", action="store_true"); ap.add_argument("--split", default="test", choices=["test", "dev"]); ap.add_argument("--partial", action="store_true", help="dev only: candidates cover a sample of pages")
    a = ap.parse_args()
    SPLIT = a.split
    rows = build(a.pipeline)
    want = {(s, d, p) for (s, d), pages in list_pages(a.split).items() for p, _ in pages}
    assert a.partial or {(r["subject"], r["document_id"], r["page"]) for r in rows} == want, "page set differs from the test set"
    if a.split == "dev":
        dst = os.path.join(ROOT, "runs", f"dev_all_rebuilt_{a.pipeline}.jsonl")
        with open(dst, "w", encoding="utf-8") as f:
            for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{a.pipeline} (dev): {len(rows)} rows -> {dst}"); sys.exit()
    dst = os.path.join(ROOT, "submissions", f"rebuilt_{a.pipeline}.zip"); write_zip(rows, dst)
    print(f"{a.pipeline}: {len(rows)} rows -> {dst}")
    if a.verify:
        ref = zip_rows(os.path.join(ROOT, "submissions", f"submission_{a.pipeline}.zip"))
        same = sum(x == y for x, y in zip(rows, ref)); print(f"  identical to the uploaded submission on {same}/{len(ref)} pages")
        sys.exit(0 if same == len(ref) == len(rows) else 1)

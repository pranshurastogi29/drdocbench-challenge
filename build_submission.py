"""Rebuild any submission from the archived candidate runs (deterministic: no model calls).

  python build_submission.py final5_wd            -> submissions/rebuilt_final5_wd.zip
  python build_submission.py --verify final5      -> also compares against submissions/submission_final5.zip

Pipelines (each adds one step to the previous):
  medoid4_snap : medoid of v6,v7,v8,paddle -> split-snap to Paddle layout blocks (cap 9 new paragraphs/page)
  best         : + Paddle tables added where no candidate has a table                      (leaderboard 77.39)
  final5       : medoid of v6,v7,v8,paddle,v7c (contrast-processed v7) + the same steps    (leaderboard 78.66)
  final5_wd    : + duplicate $\\textit{..}$ copy of every short standalone line (formula channel)
The LLM outputs themselves (runs/test_all_*.jsonl) are archived, not regenerable byte-for-byte.
"""
import argparse, collections, json, os, re, sys, zipfile
from rapidfuzz import fuzz
from common import list_pages
from postprocess import strip_sections
from snap import snap
from tablefix import fix
from wrapdup import add as wrapdup

ROOT = os.path.dirname(os.path.abspath(__file__))
TEST = {"v6": "runs/test_all_v6.jsonl", "v7": "runs/test_all_v7.jsonl", "v8": "runs/test_all_v8.jsonl",
        "paddle": "runs/paddle_test.jsonl", "v7c": "runs/test_all_v7c_test.jsonl"}
CFG = {"medoid4_snap": (["v6", "v7", "v8", "paddle"], False, False),
       "best": (["v6", "v7", "v8", "paddle"], True, False),
       "final5": (["v6", "v7", "v8", "paddle", "v7c"], True, False),
       "final5_wd": (["v6", "v7", "v8", "paddle", "v7c"], True, True)}
MAX_ADD = 9
para = lambda m: len([p for p in re.split(r"\n\s*\n", m.strip()) if p.strip()])
nz = lambda s: re.sub(r"\s+", " ", s.lower())[:6000]


def rd(p):
    return {(r["document_id"], r["page"]): r for r in map(json.loads, open(os.path.join(ROOT, p), encoding="utf-8"))}


def medoid(texts, names):
    sc = {n: sum(fuzz.ratio(nz(texts[n]), nz(texts[m])) for m in names if m != n) for n in names}
    return max(names, key=lambda n: (sc[n], n == "v7"))


def build(name):
    names, tables, wrap = CFG[name]
    R = {n: rd(TEST[n]) for n in names}
    out = []
    for k, base in R["v7"].items():
        t = {n: strip_sections(R[n][k]["markdown"]).strip() for n in names}
        md = t[medoid(t, names)]; stem = f"{k[0]}_{k[1]}"
        s = snap(md, stem, mode="split")
        if para(s) - para(md) > MAX_ADD:      # heavy re-splits are a coin flip on dev: leave those pages alone
            s = md
        if tables:
            s, _ = fix(s, stem, replace=False)
        if wrap:
            s = wrapdup(s, "short")
        out.append({"subject": base["subject"], "document_id": k[0], "page": k[1], "markdown": s})
    out.sort(key=lambda r: (r["subject"], r["document_id"], r["page"]))
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
    ap = argparse.ArgumentParser(); ap.add_argument("pipeline", choices=list(CFG)); ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    rows = build(a.pipeline)
    want = {(s, d, p) for (s, d), pages in list_pages("test").items() for p, _ in pages}
    assert {(r["subject"], r["document_id"], r["page"]) for r in rows} == want, "page set differs from the test set"
    dst = os.path.join(ROOT, "submissions", f"rebuilt_{a.pipeline}.zip"); write_zip(rows, dst)
    print(f"{a.pipeline}: {len(rows)} rows -> {dst}")
    if a.verify:
        ref = zip_rows(os.path.join(ROOT, "submissions", f"submission_{a.pipeline}.zip"))
        same = sum(x == y for x, y in zip(rows, ref)); print(f"  identical to the uploaded submission on {same}/{len(ref)} pages")
        sys.exit(0 if same == len(ref) == len(rows) else 1)

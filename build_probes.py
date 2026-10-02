"""Diagnostic probe submissions: final5_wd with whole test books blanked ("." per page, which the scorer treats as an empty page).

Blanking a set S of pages sets each of its scored pages' Text_ED to 1, so from the leaderboard's Text_ED:
    ED(S) = 1 - (ED_probe - ED_base) * N / n_S          (N = scored pages overall, n_S = scored pages in S)
Checked on dev: recovers the blanked set's true Text_ED exactly (0.3107 vs 0.3107). Leaderboard rounding is 4 decimals, i.e. +-0.001
on ED(S) for ~120-page groups. Base = final5_wd (Text_ED 0.1681).

Groups (34 books, 509 pages):
  G1  books whose subject never appears in dev (DRAMA x3, HEALTH&FITNESS x2, JUVENILEFICTION, NATURE, TRAVEL): does the unseen-subject
      hypothesis hold?
  G2  the 8 of the remaining books on which our four runs disagree most (a label-free difficulty proxy)
  G3  every other second remaining book (alternating, by document id)
  G4  the rest -- never uploaded, derived from the known total

  python build_probes.py         -> submissions/probe_G1.zip, probe_G2.zip, probe_G3.zip, runs/probe_groups.json
"""
import itertools
import json
import os
import re
import statistics as st
import zipfile

from rapidfuzz import fuzz

from common import list_pages

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "submissions/submission_final5_wd.zip"
RUNS = ["runs/test_all_v6.jsonl", "runs/test_all_v7.jsonl", "runs/test_all_v8.jsonl", "runs/test_all_v7c_test.jsonl"]


def read(f):
    return {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, f), encoding="utf-8"))}


def main():
    T = list_pages("test"); D = list_pages("dev")
    dev_subjects = {s for (s, _d) in D}
    docs = {d: s for (s, d) in T}
    cand = [read(f) for f in RUNS]
    w = lambda s: re.sub(r"\W", "", s.lower())[:4000]
    dis = {}
    for d in docs:
        ks = [(d, p) for _, p in [(None, p) for p, _ in T[(docs[d], d)]]]
        dis[d] = 100 - st.mean(st.mean(fuzz.ratio(w(a[k]), w(b[k])) for a, b in itertools.combinations(cand, 2)) for k in ks)
    G1 = sorted(d for d, s in docs.items() if s not in dev_subjects)
    rest = sorted((d for d in docs if d not in G1), key=lambda d: -dis[d])
    G2 = sorted(rest[:8]); rest = sorted(rest[8:])
    G3 = rest[::2]; G4 = rest[1::2]
    groups = {"G1": G1, "G2": G2, "G3": G3, "G4": G4}
    assert sorted(sum(groups.values(), [])) == sorted(docs)
    base = [json.loads(l) for l in zipfile.ZipFile(os.path.join(ROOT, BASE)).open("predictions.jsonl")]
    out = {}
    for g in ("G1", "G2", "G3"):
        blank = set(groups[g]); n = 0
        path = os.path.join(ROOT, "submissions", f"probe_{g}.zip")
        tmp = os.path.join(ROOT, "predictions.jsonl")
        with open(tmp, "w", encoding="utf-8") as f:
            for r in base:
                hit = r["document_id"] in blank; n += hit
                f.write(json.dumps({**r, "markdown": "." if hit else r["markdown"]}, ensure_ascii=False) + "\n")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tmp, "predictions.jsonl")
        os.remove(tmp)
        out[g] = n
    info = {g: {"docs": [{"doc": d, "subject": docs[d], "disagreement": round(dis[d], 1)} for d in ds],
                "pages": sum(len(T[(docs[d], d)]) for d in ds)} for g, ds in groups.items()}
    json.dump(info, open(os.path.join(ROOT, "runs", "probe_groups.json"), "w"), indent=1)
    for g, v in info.items():
        print(f"{g}: {len(v['docs'])} books, {v['pages']} pages" + (f"  [zip: {out[g]} pages blanked]" if g in out else "  [derived, not uploaded]"))
        print("    ", ", ".join(f"{x['subject'][:14]}({x['disagreement']})" for x in v["docs"]))


if __name__ == "__main__":
    main()

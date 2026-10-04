"""Per-group A/B on the test set: final5_wd with ONE probe group's pages replaced by another source, everything else identical.

Because the other groups are unchanged, the change in the leaderboard's Text_ED / Reading_Order is entirely that group's, so each upload is a
labelled test of the intervention on exactly those books (probe_decode.py: ED(S) = 1 - (ED_probe - ED_base) * N / n_S; same for order).

  python ab_group.py build --group G2 --src runs/test_all_ab_g2_sol61.jsonl --name ab_g2_sol61
  python ab_group.py devpreview --src runs/dev_all_live_sol61.jsonl          # same finishing steps on the dev pages that source covers
The replacement pages go through the same finishing steps as the ensemble output: split-snap to Paddle blocks (cap 9), Paddle table add,
and (test) the formula-duplicate channel. No candidate vote: the source replaces the page.
"""
import argparse, json, os, re, sys, zipfile

from snap import snap
from tablefix import fix
from wrapdup import add as wrapdup

ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_ADD = 9
para = lambda m: len([p for p in re.split(r"\n\s*\n", m.strip()) if p.strip()])


def finish(md, stem, wd):
    s = snap(md, stem, mode="split")
    if para(s) - para(md) > MAX_ADD:
        s = md
    s, _ = fix(s, stem, replace=False)
    return wrapdup(s, "short") if wd else s


def build(a):
    info = json.load(open(os.path.join(ROOT, "runs", "probe_groups.json")))[a.group]; ids = {x["doc"] for x in info["docs"]}
    base = [json.loads(l) for l in zipfile.ZipFile(os.path.join(ROOT, "submissions", "submission_final5_wd.zip")).open("predictions.jsonl")]
    src = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, a.src), encoding="utf-8"))}
    n = miss = 0; out = []
    for r in base:
        if r["document_id"] in ids:
            k = (r["document_id"], r["page"])
            if k in src and src[k].strip():
                r = {**r, "markdown": finish(src[k], f"{k[0]}_{k[1]}", True)}; n += 1
            else:
                miss += 1      # keep the base page: a page missing from the source must not be blanked
        out.append(r)
    path = os.path.join(ROOT, "submissions", f"submission_{a.name}.zip"); tmp = os.path.join(ROOT, "predictions.jsonl")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in out: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z: z.write(tmp, "predictions.jsonl")
    os.remove(tmp)
    changed = sum(1 for x, y in zip(base, out) if x["markdown"] != y["markdown"])
    outside = sum(1 for x, y in zip(base, out) if x["markdown"] != y["markdown"] and x["document_id"] not in ids)
    print(f"{path}: {len(out)} rows; replaced {n} of {info['pages']} {a.group} pages ({miss} kept from base); pages differing from final5_wd: {changed}; outside {a.group}: {outside}")


def devpreview(a):
    src = [json.loads(l) for l in open(os.path.join(ROOT, a.src), encoding="utf-8")]
    out = os.path.join(ROOT, "runs", "dev_all_abpreview.jsonl")
    base = [json.loads(l) for l in open(os.path.join(ROOT, "runs", "dev_all_rebuilt_final5.jsonl"), encoding="utf-8")]
    S = {(r["document_id"], r["page"]): r["markdown"] for r in src}
    with open(out, "w", encoding="utf-8") as f:
        for r in base:
            k = (r["document_id"], r["page"])
            md = finish(S[k], f"{k[0]}_{k[1]}", False) if k in S and S[k].strip() else r["markdown"]
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    print(f"{out}: {len(S)} source pages substituted into the dev final5 output")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("--group", required=True); b.add_argument("--src", required=True); b.add_argument("--name", required=True)
    d = sp.add_parser("devpreview"); d.add_argument("--src", required=True)
    a = ap.parse_args()
    {"build": build, "devpreview": devpreview}[a.cmd](a)

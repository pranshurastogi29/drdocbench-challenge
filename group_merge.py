"""Page-level merge of finished submission zips (no finishing steps are re-run).
Each --take VARIANT[:RESTRICT] replaces the base's pages with the variant's, on the pages where the variant differs from the base,
optionally restricted to probe groups (runs/probe_groups.json: G1,G2,...) or to book ids (8-char prefixes are enough).
Later --take wins where takes overlap (reported). Writes OUT.zip and OUT.pages.json (changed pages per take, for ab_decode.py).
  python group_merge.py submissions/submission_cdm_max.zip submissions/out.zip --take submissions/submission_cdm_max_mbr8.zip:G1,G2
  python group_merge.py BASE.zip OUT.zip --take A.zip --take B.zip            (combine two changes)
"""
import argparse, json, os, zipfile
ROOT = os.path.dirname(os.path.abspath(__file__))


def load(z):
    with zipfile.ZipFile(z) as f: return [json.loads(l) for l in f.open("predictions.jsonl") if l.strip()]


def books_of(restrict):
    if not restrict: return None
    G = json.load(open(os.path.join(ROOT, "runs", "probe_groups.json")))
    out = set()
    for t in restrict.split(","):
        out |= {d["doc"] for d in G[t]["docs"]} if t in G else {t}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("base"); ap.add_argument("out"); ap.add_argument("--take", action="append", required=True); a = ap.parse_args()
    base = load(a.base); key = lambda r: f'{r["document_id"]}_{r["page"]}'
    cur = {key(r): r["markdown"] for r in base}; orig = dict(cur); owner = {}; report = {}
    for t in a.take:
        path, _, restrict = t.partition(":")
        B = books_of(restrict); v = {key(r): r["markdown"] for r in load(path)}
        assert set(v) == set(cur), f"{path}: page set differs from the base"
        ch = [k for k in v if v[k] != orig[k] and (B is None or any(k.startswith(b) for b in B))]
        over = [k for k in ch if k in owner]
        for k in ch: cur[k] = v[k]; owner[k] = path
        report[t] = sorted(ch)
        print(f"take {os.path.basename(path)}{':' + restrict if restrict else ''}: {len(ch)} pages" + (f" ({len(over)} overlap earlier takes; this take wins)" if over else ""))
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as f:
        f.writestr("predictions.jsonl", "".join(json.dumps({**r, "markdown": cur[key(r)]}, ensure_ascii=False) + "\n" for r in base))
    changed = sorted(k for k in cur if cur[k] != orig[k])
    json.dump({"base": a.base, "takes": report, "changed": changed}, open(a.out.replace(".zip", ".pages.json"), "w"), indent=1)
    print(f"wrote {a.out}: {len(base)} pages, {len(changed)} differ from the base")

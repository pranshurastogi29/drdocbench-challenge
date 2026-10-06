"""Formula pool: append to each page the display formulas that ANY of our candidate runs wrote for it (deduplicated), as extra $-blocks.
The formula metric pairs each reference formula with its best predicted formula and drops unpaired predictions, and $-blocks are excluded from
text and reading-order matching, so extra formula candidates cannot cost anything there.
  python formula_pool.py SRC DST --split dev|test --cands v6,v7,...
"""
import argparse, json, re

FILES = {"dev": {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl", "v7c": "runs/dev_all_v7c_final.jsonl",
                 "paddle": "runs/paddle_dev.jsonl", "v6w1": "runs/dev_all_v6_w1.jsonl", "v7w1": "runs/dev_all_v7_w1.jsonl", "v8w1": "runs/dev_all_v8_w1.jsonl",
                 "v7s": "runs/dev_all_v7_1200.jsonl", "sol61": "runs/dev_all_live_sol61.jsonl",
                 "v10a": ["runs/dev_all_ab_v10a.jsonl", "runs/dev_all_v10a_rest.jsonl"], "v10b": ["runs/dev_all_ab_v10b.jsonl", "runs/dev_all_v10b_rest.jsonl"],
                 "v11": ["runs/dev_all_ab_v11.jsonl", "runs/dev_all_v11_rest.jsonl"], "v10ac": "runs/dev_all_v10ac.jsonl", "v10at": "runs/dev_all_v10at.jsonl",
                 "v10ao": "runs/dev_all_v10ao.jsonl", "mineru": "runs/mineru_dev.jsonl", "v6c": "runs/dev_all_v6c_final.jsonl", "v8c": "runs/dev_all_v8c_final.jsonl",
                 "v7cw1": "runs/dev_all_v7c_w1.jsonl", "v7sw1": "runs/dev_all_v7sw1.jsonl", "v5w1": "runs/dev_all_v5w1.jsonl", "v7tw1": "runs/dev_all_v7tw1.jsonl"},
         "test": {"v6": "runs/test_all_v6.jsonl", "v7": "runs/test_all_v7.jsonl", "v8": "runs/test_all_v8.jsonl", "v7c": "runs/test_all_v7c_test.jsonl",
                  "paddle": "runs/paddle_test.jsonl", "v6w1": "runs/test_all_v6_w1.jsonl", "v7w1": "runs/test_all_v7_w1.jsonl", "v8w1": "runs/test_all_v8_w1.jsonl",
                  "v7s": "runs/test_all_v7_1200.jsonl", "sol61": "runs/test_all_ab_g2_sol61.jsonl",
                  "v10a": "runs/test_all_v10a.jsonl", "v10b": "runs/test_all_v10b.jsonl", "v11": "runs/test_all_v11.jsonl", "v10ac": "runs/test_all_v10ac.jsonl",
                  "v10at": "runs/test_all_v10at.jsonl", "v10ao": "runs/test_all_v10ao.jsonl", "mineru": "runs/mineru_test.jsonl", "v6c": "runs/test_all_v6c_test.jsonl",
                  "v8c": "runs/test_all_v8c_test.jsonl", "v7cw1": "runs/test_all_v7c_w1.jsonl", "v7sw1": "runs/test_all_v7sw1.jsonl", "v5w1": "runs/test_all_v5w1.jsonl", "v7tw1": "runs/test_all_v7tw1.jsonl"}}   # sol61: gpt-6.1-sol-pro, 89 dev / 120 test (G2) pages


INLINE = False   # --inline: also offer each inline $...$ formula (with real math in it) as a display candidate


def formulas(md):
    out = []
    if INLINE:
        for m in re.findall(r"(?<!\$)\$([^$\n]{3,200})\$(?!\$)", md or ""):
            if re.search(r"[\^_=]|\\[a-zA-Z]+", m) and not re.fullmatch(r"\s*\\text(it|bf)\{[^{}]*\}\s*", m): out.append("$$\n" + m.strip() + "\n$$")
    for b in re.split(r"\n\s*\n", md or ""):
        b = b.strip()
        if b.startswith("\\[") and b.endswith("\\]"):
            b = "$$\n" + b[2:-2].strip() + "\n$$"
        if len(b) > 2 and b.startswith("$") and b.endswith("$") and b.replace("$", "").strip():
            out.append(b)
    return out


def pool(md, others, wrap_others=False):
    have = {re.sub(r"\s+", "", f) for f in formulas(md)}; extra = []
    if wrap_others:   # also the wrapper copies (wrapdup2, same settings as ours) of every other run's lines: other spellings/splits of the same lines
        from wrapdup2 import add
        from postprocess import strip_sections
        others = [add(strip_sections(o or ""), ("textit", "textbf", "bi"), 100000, True, True, True) for o in others]
    for o in others:
        for f in formulas(o):
            k = re.sub(r"\s+", "", f)
            if k not in have:
                have.add(k); extra.append(f)
    return md.rstrip() + ("\n\n" + "\n\n".join(extra) if extra else "")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--split", default="dev")
    ap.add_argument("--cands", default="v6,v7,v8,v7c,paddle,v6w1,v7w1,v8w1,v7s,sol61"); ap.add_argument("--wrap-others", action="store_true"); ap.add_argument("--inline", action="store_true")
    a = ap.parse_args(); INLINE = a.inline
    _load = lambda f: [l for ff in (f if isinstance(f, list) else [f]) for l in open(ff, encoding="utf-8")]
    C = [{(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, _load(FILES[a.split][c]))} for c in a.cands.split(",")]
    n = added = 0
    with open(a.dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            k = (r["document_id"], r["page"]); new = pool(r["markdown"], [c.get(k, "") for c in C], a.wrap_others)
            if new != r["markdown"]: n += 1; added += len(formulas(new)) - len(formulas(r["markdown"]))
            f.write(json.dumps({**r, "markdown": new}, ensure_ascii=False) + "\n")
    print(f"{a.dst}: {n} pages got extra formula candidates ({added} added)")

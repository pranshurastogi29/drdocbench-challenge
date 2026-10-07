"""The submission stack as switchable steps, for dev ablations under the end2end scorer (e2e_eval.py) and exact test rebuilds.

Order (= submission_final5m_fc10t_fm_sd_bv_ac.zip, leaderboard 82.88):
  sel   : MBR pick over base5 (runs/mbr_choice_<split>.json) or medoid5         -> raw page
  rules : split-snap to Paddle blocks (cap 9 new paragraphs) + Paddle tables where none (build_submission final5/final5m)
  chan  : formula channel (wrapdup2 textit/textbf/bi, any length, lines, grouped, numbers) + formula pool + sol-6.1 wrapper copies + table pool
  fm    : furniture merge (furnmerge --max-tail 2 --maxlen 60 --paddle-check)
  sd    : spill drop (one-page runs v6w1/v7w1/v8w1)
  bv    : boundary splits (bvote split-only, k=5 of the 10 other free candidates, processed)
  ac    : markup-artifact cleanup (artclean + CJK glitch)
  si    : split import (>= 2 of v10a/v10b/v11)
  python stack.py --split test --verify          (rebuild the 82.88 zip and compare)
  python stack.py --split dev --steps sel=mbr,rules,chan,fm,sd,bv,ac --out runs/dev_stack_full.jsonl
"""
import argparse, json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
PY = os.path.join(ROOT, ".venv/bin/python")
FULL = "sel=mbr,rules,chan,fm,sd,bv,ac"


def rows_of(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def write(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run(*args):
    subprocess.run([PY, *args], cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def base_rows(split, sel, rules):
    """selection (+ rules) via build_submission; without rules: the selected candidate's raw page"""
    import build_submission as bs
    bs.SPLIT = split
    bs.MBR_FILE = {"mbr6": f"mbr_choice_{split}_refs6.json", "mbr8": f"mbr_choice_{split}_c8.json"}.get(sel) or (f"mbr_choice_{split}_{sel[5:]}.json" if sel.startswith("mbrf:") else None)
    if rules:
        rows = bs.build("final5mall" if sel.startswith("mbrf:") else "final5m8" if sel == "mbr8" else "final5m" if sel in ("mbr", "mbr6") else "final5")
    else:
        from postprocess import strip_sections
        files = bs.DEV if split == "dev" else bs.TEST; names = ["v6", "v7", "v8", "paddle", "v7c"]
        R = {n: bs.rd(files[n]) for n in names}; MBR = json.load(open(os.path.join(ROOT, "runs", bs.MBR_FILE or f"mbr_choice_{split}.json")))
        rows = []
        for k in R["v7"]:
            if not all(k in R[n] for n in names): continue
            t = {n: strip_sections(R[n][k]["markdown"]).strip() for n in names}; stem = f"{k[0]}_{k[1]}"
            p = MBR.get(stem) if (sel in ("mbr", "mbr6", "mbr8") or sel.startswith("mbrf:")) and MBR.get(stem) in t else bs.medoid(t, names)
            rows.append({"subject": R["v7"][k]["subject"], "document_id": k[0], "page": k[1], "markdown": t[p]})
        rows.sort(key=lambda r: (r["subject"], r["document_id"], r["page"]))
    return rows


def build(split, steps, tmp):
    st = dict(s.split("=") if "=" in s else (s, "1") for s in steps.split(","))
    rows = base_rows(split, st.get("sel", "mbr"), "rules" in st)
    if st.get("chan", "").startswith("mathu"):   # unwrap our own wrapper-only formula blocks into plain text before the pools are added
        INNER = re.compile(r"\\text(?:bf|it|rm)?\{([^{}$]*)\}")
        WR1 = re.compile(r"^(\$\$?|\\\[)\s*(\\begin\{array\}\{l\}\s*)?((\{?\\text(bf|it|rm)?\{[^{}$]*\}\}?|\\textbf\{\\textit\{[^{}$]*\}\})\s*(\\\\)?\s*)+(\\end\{array\})?\s*(\$\$?|\\\])$", re.S)
        for r in rows:
            ps = re.split(r"\n\s*\n", r["markdown"])
            r["markdown"] = "\n\n".join(" ".join(INNER.findall(x.replace("\\textbf{\\textit{", "\\textit{"))) if WR1.match(x.strip()) and INNER.findall(x) else x for x in ps)
    if "ob" in st:   # order borrow: our paragraphs re-sorted into the order of a column-major run (v10a); text unchanged. ob=all | multi (Paddle multi-column pages only)
        from order_mbr import borrow_order, paras as _paras
        from postprocess import strip_sections
        import paddle_ingest
        tags = {"dev": ("ab_v10a", "v10a_rest"), "test": ("v10a",)}[split]; SRC = {}
        for t in tags: SRC.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/{split}_all_{t}.jsonl")))})
        def multicol(stem):
            bl = [b["block_bbox"] for b in (paddle_ingest.blocks(stem) or []) if b["block_label"] in ("text", "paragraph_title", "content", "reference_content", "abstract")]
            return any(a[2] <= b[0] + 5 and min(a[3], b[3]) - max(a[1], b[1]) > 20 for a in bl for b in bl if a is not b)
        for r in rows:
            stem = f'{r["document_id"]}_{r["page"]}'
            if stem not in SRC or (st["ob"] == "multi" and not multicol(stem)): continue
            ours = _paras(r["markdown"]); h = borrow_order(ours, _paras(SRC[stem]))
            if h and h != ours: r["markdown"] = "\n\n".join(h)
    if "sm" in st:   # snap MERGE pass: join our consecutive paragraphs that together make up one PaddleOCR-VL layout block (end2end references are layout boxes)
        from snap import snap
        for r in rows: r["markdown"] = snap(r["markdown"], f'{r["document_id"]}_{r["page"]}', mode="merge")
    if "lm" in st:   # list merge: runs of >= RUN short paragraphs joined into one block (end2end references keep a list / clue column / bibliography as one layout box)
        from listmerge import merge as lmerge
        run_, ml = {"1": (6, 80), "4": (4, 80), "3": (3, 100), "6": (6, 120)}.get(st["lm"], (6, 80))
        for r in rows: r["markdown"] = lmerge(r["markdown"], min_run=run_, max_len=ml, min_total=300)
    p = os.path.join(tmp, "s0.jsonl"); write(rows, p)
    if "chan" in st:
        v = st["chan"]; v = "pools" if v.startswith("math") else ("1" if v in ("1W", "1W2", "1W3", "1W4") else v); sol = v == "1" or v.endswith("S"); v = v[:-1] if v.endswith("S") else v   # suffix S: also sol-6.1 wrapper copies (G2 pages)
        # 1 = the 82.88 channel; inter = same copies placed right after each line; short = grouped, lines <= 60; wd = textit, <= 60, after each line; pools = no wrapper copies
        wargs = {"1": ["--styles", "textit,textbf,bi", "--maxlen", "100000", "--lines", "--grouped", "--numbers"],
                 "inter": ["--styles", "textit,textbf,bi", "--maxlen", "100000", "--lines", "--numbers"],
                 "short": ["--styles", "textit,textbf,bi", "--maxlen", "60", "--lines", "--grouped", "--numbers"],
                 "wd": ["--styles", "textit", "--maxlen", "60"],
                 "inter1": ["--styles", "textit", "--maxlen", "100000", "--lines", "--numbers"]}.get(v)
        if wargs: run("wrapdup2.py", p, p + ".1", *wargs)
        else: run("formula_pool.py", p, p + ".1", "--split", split, "--cands", "v7")   # no copies: identity pass (pools follow)
        run("formula_pool.py", p + ".1", p + ".2", "--split", split)
        if sol: run("formula_pool.py", p + ".2", p + ".3", "--split", split, "--cands", "sol61", "--wrap-others")   # sol-6.1 wrapper copies
        else: run("formula_pool.py", p + ".2", p + ".3", "--split", split, "--cands", "sol61")
        if st["chan"] in ("1W", "1W2", "1W3", "1W4"):   # also wrapper copies of other runs' lines (more spellings of the reference's italic/bold lines)
            cw = {"1W": "v6,v7,v8,v7c", "1W2": "v6,v7,v8,v7c,v6w1,v7w1,v8w1", "1W3": "v6,v7,v8,v7c,v6w1,v7w1,v8w1,v7s,v10a,v10b,v11,v10ac,v10at,v10ao",
                  "1W4": "v6,v7,v8,v7c,v6w1,v7w1,v8w1,v7s,v10a,v10b,v11,v10ac,v10at,v10ao,v6c,v8c,v7cw1,v7sw1,v5w1,v7tw1,paddle,mineru"}[st["chan"]]
            run("formula_pool.py", p + ".3", p + ".3w", "--split", split, "--cands", cw, "--wrap-others"); os.replace(p + ".3w", p + ".3")
        if st.get("fp"):   # extra formula candidates: fp=new (v10 family + MinerU) | newi (+ inline formulas of every run as display candidates)
            ex = "v10a,v10b,v11,v10ac,v10at,v10ao,mineru"
            if st["fp"] == "newi": run("formula_pool.py", p + ".3", p + ".3f", "--split", split, "--cands", "v6,v7,v8,v7c,paddle,v6w1,v7w1,v8w1,v7s,sol61," + ex, "--inline")
            else: run("formula_pool.py", p + ".3", p + ".3f", "--split", split, "--cands", ex)
            os.replace(p + ".3f", p + ".3")
        if st["chan"] == "1W4":   # our own lines also in plain \\text{} and underlined \\underline{\\text{}} wrappers
            run("wrapdup2.py", p + ".3", p + ".3u", "--styles", "plain,ul", "--maxlen", "100000", "--lines", "--grouped", "--numbers"); os.replace(p + ".3u", p + ".3")
        run("table_pool.py", p + ".3", p + ".4", "--split", split); p = p + ".4"
    if "chan" in st and st["chan"].startswith("math"):   # keep only formula blocks that look like real math; drop wrapper-only ones (\\textbf{..} / \\textit{..} / \\text{..} around plain words)
        rows_ = rows_of(p)
        WRAP = re.compile(r"^(\$\$?|\\\[)\s*(\\begin\{array\}\{l\}\s*)?((\{?\\text(bf|it|rm)?\{[^{}$]*\}\}?|\\textbf\{\\textit\{[^{}$]*\}\})\s*(\\\\)?\s*)+(\\end\{array\})?\s*(\$\$?|\\\])$", re.S)
        MATH = re.compile(r"[\^_=+<>]|\\(frac|sum|int|sqrt|alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|omega|times|cdot|le|ge|neq|infty|partial|mathrm|mathbf|left|right)\b")
        for r in rows_:
            ps = re.split(r"\n\s*\n", r["markdown"])
            keep = [x for x in ps if not ((x.strip().startswith("$") or x.strip().startswith("\\[")) and (WRAP.match(x.strip()) or not MATH.search(x)))]
            r["markdown"] = "\n\n".join(keep)
        write(rows_, p + ".m"); p = p + ".m"
    if "fm" in st:
        ft, fl = ("3", "80") if st["fm"] == "3" else ("2", "60")
        run("furnmerge.py", p, p + ".fm", "--max-tail", ft, "--maxlen", fl, "--paddle-check"); p = p + ".fm"
    rows = rows_of(p)
    if "sd" in st:
        from spilldrop import spilldrop
        import build_submission as bs
        files = bs.TEST if split == "test" else bs.DEV
        R1 = {n: {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, files[n])))} for n in ("v6w1", "v7w1", "v8w1")}
        w1 = lambda s: [R1[n].get(s, "") for n in R1]
        for r in rows:
            nbs = [w1(f'{r["document_id"]}_{r["page"] + d}') for d in (-1, 1)]
            md, dropped = spilldrop(r["markdown"], w1(f'{r["document_id"]}_{r["page"]}'), [x for x in nbs if any(x)])
            r["markdown"] = md
    if "bv" in st:
        from bvote import bvote
        from sel_lab import FREE
        C = json.load(open(os.path.join(ROOT, f"runs/selcache_{split}.json"))); pick = json.load(open(os.path.join(ROOT, "runs", __import__("build_submission").MBR_FILE or f"mbr_choice_{split}.json")))
        for r in rows:
            s = f'{r["document_id"]}_{r["page"]}'
            if s in C and s in pick:
                new, _, sp = bvote(r["markdown"], [C[s]["proc"][c] for c in FREE if c != pick[s]], k=5, do_merge=False)
                if sp: r["markdown"] = new
    if "am" in st:   # add paragraphs our page lacks but >= K other base5 runs have (addmiss.py); end2end drops unpaired text of ours, so extras are free
        from addmiss import add_missing
        from postprocess import strip_sections
        import build_submission as bs
        files = bs.TEST if split == "test" else bs.DEV; names = ["v6", "v7", "v8", "paddle", "v7c"]
        RR = {n: {f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, files[n])))} for n in names}
        pick = json.load(open(os.path.join(ROOT, "runs", __import__("build_submission").MBR_FILE or f"mbr_choice_{split}.json"))); kk = int(st["am"]) if st["am"] != "1" else 2
        for r in rows:
            s_ = f'{r["document_id"]}_{r["page"]}'; pk = pick.get(s_, "v7")
            new, added = add_missing(r["markdown"], [RR[n].get(s_, "") for n in names if n != pk], k=kk)
            if added: r["markdown"] = new
    if "dd" in st:   # de-duplicate: a long paragraph (>= 40 chars) that appears again on the same page is kept once (the model sometimes transcribes a passage twice)
        for r in rows:
            seen, keep = set(), []
            for q in re.split(r"\n\s*\n", r["markdown"]):
                k = q.strip()
                if len(k) >= 40 and not k.startswith("$") and not k.startswith("<table") and k in seen: continue
                seen.add(k); keep.append(q)
            r["markdown"] = "\n\n".join(keep)
    if "ac" in st:
        from artclean import artclean, cjk_glitch
        for r in rows: r["markdown"] = cjk_glitch(artclean(r["markdown"], supsub=True))
    if "sym" in st:   # symbol channel (symchan.py): one formula per symbol occurrence, in the references' LaTeX (\\bullet, \\dotfill, ^\\circ, ...)
        from symchan import add_symbols
        for r in rows: r["markdown"] = add_symbols(r["markdown"], roman=st["sym"] != "noroman")
    if "si" in st:
        from bvote import bvote
        from postprocess import strip_sections
        tags = {"dev": (("ab_v10a", "v10a_rest"), ("ab_v10b", "v10b_rest"), ("ab_v11", "v11_rest")), "test": (("v10a",), ("v10b",), ("v11",))}[split]
        S = []
        for grp in tags:
            d = {}
            for t in grp: d.update({f'{r["document_id"]}_{r["page"]}': strip_sections(r["markdown"]).strip() for r in map(json.loads, open(os.path.join(ROOT, f"runs/{split}_all_{t}.jsonl")))})
            S.append(d)
        for r in rows:
            s = f'{r["document_id"]}_{r["page"]}'; src = [d[s] for d in S if s in d]
            if src:
                new, _, sp = bvote(r["markdown"], src, k=2, do_merge=False, long_only=False)
                if sp and st["si"] == "nl":   # si=nl: keep column / new-region / unlocated breaks, drop breaks inside one layout block (list entries: a dev-only convention)
                    from split_kind import filtered
                    new = filtered(s, r["markdown"], new, {"column", "block", "?"})
                if sp: r["markdown"] = new
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--steps", default=FULL); ap.add_argument("--out"); ap.add_argument("--verify", action="store_true"); ap.add_argument("--compare", help="a submission zip to compare the built pages with")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        rows = build(a.split, a.steps, tmp)
    if a.out: write(rows, a.out); print(f"{a.out}: {len(rows)} pages ({a.steps})")
    if a.verify:
        from build_submission import zip_rows
        ref = {(r["document_id"], r["page"]): r for r in zip_rows(os.path.join(ROOT, "submissions/submission_final5m_fc10t_fm_sd_bv_ac.zip"))}
        same = sum(ref.get((r["document_id"], r["page"])) == r for r in rows)
        print(f"identical to submission_final5m_fc10t_fm_sd_bv_ac.zip (82.88) on {same}/{len(ref)} pages")
    if a.compare:
        from build_submission import zip_rows
        ref = {(r["document_id"], r["page"]): r for r in zip_rows(a.compare)}
        same = sum(ref.get((r["document_id"], r["page"])) == r for r in rows)
        print(f"identical to {os.path.basename(a.compare)} on {same}/{len(ref)} pages")

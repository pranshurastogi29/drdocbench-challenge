"""Drop paragraphs the official scorer would leave unmatched ("extra text"), chosen by a classifier trained on dev.

Why only unmatched paragraphs: the reading-order metric (scorer/dataset/md2md_dataset.py get_order_paired) counts every reference
block, and any of our paragraphs that is matched to a reference block -- however poor its text -- keeps that block in our order. So
removing a matched paragraph costs order (and text), while removing an unmatched one is a pure text gain. Dev labels come from the
scorer's own match records; every feature is label-free, so the model applies to test.

  python paradrop.py cv                       # book-grouped CV on dev: AUC, precision, and OOF-dropped dev files to score
  python paradrop.py apply SRC DST --split test --theta 0.7
"""
import argparse
import glob
import itertools
import json
import os
import re
import statistics as st
import sys

import numpy as np
from rapidfuzz import fuzz

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = {"dev": {"v6": "runs/dev_all_full_bunny.jsonl", "v7": "runs/dev_all_v7_final.jsonl", "v8": "runs/dev_all_v8_final.jsonl",
                "v7c": "runs/dev_all_v7c_final.jsonl", "paddle": "runs/paddle_dev.jsonl"},
        "test": {"v6": "runs/test_all_v6.jsonl", "v7": "runs/test_all_v7.jsonl", "v8": "runs/test_all_v8.jsonl",
                 "v7c": "runs/test_all_v7c_test.jsonl", "paddle": "runs/paddle_test.jsonl"}}
KEEP = re.compile(r"^\s*(<table|<div|\$\$|\$\\|!\[)")
PIC = ("image", "chart", "header_image", "footer_image")
FEATS = ["pm", "pm_full", "ratio", "agree", "sup_mean", "sup_min", "n_sup90", "len", "log_len", "digit", "upper", "alpha",
         "single", "avgtok", "under", "lines", "sentence", "heading", "pos", "n_paras", "pic_area", "n_pic", "n_text_blocks",
         "paddle_len"]


def wn(s):            # comparison form: tags out, lower-case, word characters only
    return re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s).lower())


def paras(md):
    return [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]


def load(split):
    L = lambda f: {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(os.path.join(ROOT, f), encoding="utf-8"))}
    return {k: L(f) for k, f in RUNS[split].items()}


def paddle_layout(stem):
    f = os.path.join(ROOT, "kaggle", "results", "paddle", "out", stem, f"{stem}_res.json")
    if not os.path.exists(f):
        return 0.0, 0, 0
    j = json.load(open(f))
    W, H = j.get("width") or 1, j.get("height") or 1
    pic = [b for b in j.get("parsing_res_list", []) if b["block_label"] in PIC]
    area = sum(max(0, b["block_bbox"][2] - b["block_bbox"][0]) * max(0, b["block_bbox"][3] - b["block_bbox"][1]) for b in pic) / (W * H)
    ntext = sum(b["block_label"] in ("text", "paragraph_title", "reference_content", "aside_text", "content") for b in j.get("parsing_res_list", []))
    return min(area, 1.0), len(pic), ntext


def page_rows(md, stem, R):
    """One feature dict per candidate paragraph of `md` (our output for page `stem`); R = candidate runs for this page."""
    P = paras(md)
    pad = wn(R.get("paddle", ""))
    runs = [wn(R[n]) for n in ("v6", "v7", "v8", "v7c") if n in R]
    agree = st.mean(fuzz.ratio(a[:4000], b[:4000]) for a, b in itertools.combinations(runs, 2)) if len(runs) > 1 else 100.0
    ours = wn(md)
    area, npic, ntext = paddle_layout(stem)
    rows = []
    for i, p in enumerate(P):
        w = wn(p)
        if KEEP.match(p) or len(w) < 8:
            continue
        sup = [fuzz.partial_ratio(w[:200], r) if r else 0 for r in runs]
        toks = re.findall(r"\S+", re.sub(r"[#*_`$]", " ", p))
        letters = [c for c in p if c.isalpha()]
        rows.append(dict(
            idx=i, text=p,
            pm=fuzz.partial_ratio(w[:200], pad) if pad else 0, pm_full=fuzz.partial_ratio(w, pad) if pad and len(w) <= 400 else 0,
            ratio=len(ours) / max(len(pad), 50), agree=agree,
            sup_mean=st.mean(sup) if sup else 0, sup_min=min(sup) if sup else 0, n_sup90=sum(s >= 90 for s in sup),
            len=len(w), log_len=np.log1p(len(w)),
            digit=sum(c.isdigit() for c in p) / max(len(p), 1), upper=sum(c.isupper() for c in letters) / max(len(letters), 1),
            alpha=len(letters) / max(len(p), 1), single=sum(len(t) == 1 for t in toks) / max(len(toks), 1),
            avgtok=st.mean(len(t) for t in toks) if toks else 0, under=p.count("_") / max(len(p), 1), lines=p.count("\n") + 1,
            sentence=float(bool(re.search(r"[a-z]{3,}[.!?]", p))), heading=float(p.lstrip().startswith("#")),
            pos=i / max(len(P) - 1, 1), n_paras=len(P), pic_area=area, n_pic=npic, n_text_blocks=ntext, paddle_len=len(pad)))
    return rows


def labels(name):
    """stem -> (extra_text, matched_text) from the scorer's text-block match records for run `name`."""
    out = {}
    for x in json.load(open(os.path.join(ROOT, "scorer", "result", f"drdoc_{name}_text_block_result.json"))):
        e, m = out.setdefault(x["img_id"][:-4], ([], []))
        (e if not x["norm_gt"] else m).append(re.sub(r"[\W_]", "", x["norm_pred"]).lower())
    return {k: ("|".join(e), "|".join(m)) for k, (e, m) in out.items()}


def dataset(src="runs/dev_all_rebuilt_final5.jsonl", scored="DEVR_final5"):
    R = load("dev"); lab = labels(scored)
    X, y, g, keys = [], [], [], []
    for r in map(json.loads, open(os.path.join(ROOT, src), encoding="utf-8")):
        stem = f'{r["document_id"]}_{r["page"]}'
        if stem not in lab:
            continue
        ex, ma = lab[stem]
        for row in page_rows(r["markdown"], stem, {n: R[n].get(stem, "") for n in R}):
            w = wn(row["text"])
            ie, im = w in ex, w in ma
            if ie == im:            # in both or neither (merged/split by the matcher): ambiguous, not used for training
                continue
            X.append([row[f] for f in FEATS]); y.append(int(ie)); g.append(r["document_id"]); keys.append((stem, row["idx"]))
    return np.array(X, float), np.array(y), np.array(g), keys


def model():
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0)


def drop_file(src, dst, probs, theta):
    """probs: {(stem, para_idx): p_extra}. Writes src with every paragraph whose p_extra >= theta removed."""
    n = 0
    with open(dst, "w", encoding="utf-8") as f:
        for r in map(json.loads, open(src, encoding="utf-8")):
            stem = f'{r["document_id"]}_{r["page"]}'
            P = paras(r["markdown"])
            keep = [p for i, p in enumerate(P) if probs.get((stem, i), 0) < theta]
            md = "\n\n".join(keep) if keep else r["markdown"]
            n += md != r["markdown"]
            f.write(json.dumps({**r, "markdown": md}, ensure_ascii=False) + "\n")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["cv", "apply"])
    ap.add_argument("src", nargs="?"); ap.add_argument("dst", nargs="?")
    ap.add_argument("--split", default="test"); ap.add_argument("--theta", type=float, default=0.7)
    ap.add_argument("--thetas", default="0.5,0.6,0.7,0.8,0.9")
    a = ap.parse_args()
    if a.cmd == "cv":
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import GroupKFold
        X, y, g, keys = dataset()
        print(f"{len(y)} labelled paragraphs, {y.sum()} extra ({y.mean():.1%}), {len(set(g))} books", file=sys.stderr)
        oof = np.zeros(len(y))
        for tr, te in GroupKFold(5).split(X, y, g):
            oof[te] = model().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        print(f"book-grouped CV AUC {roc_auc_score(y, oof):.3f}")
        # OOF probabilities for every candidate paragraph (labelled or not), so the dev files can be scored honestly
        R = load("dev"); probs = {}
        rows_all = []
        for r in map(json.loads, open(os.path.join(ROOT, "runs/dev_all_rebuilt_final5.jsonl"), encoding="utf-8")):
            stem = f'{r["document_id"]}_{r["page"]}'
            for row in page_rows(r["markdown"], stem, {n: R[n].get(stem, "") for n in R}):
                rows_all.append((r["document_id"], stem, row))
        books = sorted(set(g)); fold_of = {}
        for k, (tr, te) in enumerate(GroupKFold(5).split(X, y, g)):
            for b in set(g[te]): fold_of[b] = k
        models = {k: model().fit(X[tr], y[tr]) for k, (tr, te) in enumerate(GroupKFold(5).split(X, y, g))}
        for doc, stem, row in rows_all:
            m = models[fold_of.get(doc, 0)]   # books with no labelled rows were in no fold: any model is out-of-sample for them
            probs[(stem, row["idx"])] = m.predict_proba(np.array([[row[f] for f in FEATS]]))[0, 1]
        for th in map(float, a.thetas.split(",")):
            sel = oof >= th
            prec = y[sel].mean() if sel.any() else float("nan")
            n = drop_file(os.path.join(ROOT, "runs/dev_all_rebuilt_final5.jsonl"), os.path.join(ROOT, f"runs/dev_all_pd{int(th*100)}.jsonl"), probs, th)
            print(f"theta {th}: labelled drops {sel.sum()} precision {prec:.2f} (extra recall {(sel & (y == 1)).sum() / y.sum():.2f}); pages changed {n}")
    else:
        X, y, g, _ = dataset()
        m = model().fit(X, y)
        R = load(a.split); probs = {}
        for r in map(json.loads, open(a.src, encoding="utf-8")):
            stem = f'{r["document_id"]}_{r["page"]}'
            for row in page_rows(r["markdown"], stem, {n: R[n].get(stem, "") for n in R}):
                probs[(stem, row["idx"])] = m.predict_proba(np.array([[row[f] for f in FEATS]]))[0, 1]
        print(f"{a.dst}: {drop_file(a.src, a.dst, probs, a.theta)} pages changed")

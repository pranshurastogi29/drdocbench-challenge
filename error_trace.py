"""Trace every text error of a scored dev run back to a cause (official scorer match records + reference + PaddleOCR-VL as an independent reader).

  python error_trace.py DEVR_final5 runs/dev_all_rebuilt_final5.jsonl
Missing  = reference block the matcher left unpaired: present elsewhere in our page (pairing/segmentation) or absent (dropped);
           absent ones split by whether Paddle read that text (readable, we skipped it) or not (hard / inside a picture).
Extra    = our block with no reference partner: text the reference has elsewhere on the page (duplicate / misgrouped), text Paddle also read
           (real page text the reference leaves out), or text neither has (candidate hallucination).
Matched  = reference block paired with ours but different: character edit operations split into short slips (runs < 15 chars, OCR-like) and long
           runs (>= 15 chars, a chunk of text that moved between paragraphs or is missing/added inside the pair).
"""
import collections, json, re, sys
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

W = lambda s: re.sub(r"[\W_]", "", re.sub(r"<[^>]+>", " ", s or "").lower())


def present(needle, hay):
    n = W(needle)
    if not n or not hay:
        return False
    probes = [n[:120]] + ([n[-120:]] if len(n) > 240 else [])
    return all(fuzz.partial_ratio(p, hay) >= 90 for p in probes)


def runs(ops):
    """lengths of consecutive runs of the same insert/delete op along the strings"""
    out, cur, last = [], 0, None
    for tag, i, j in ops:
        key = (tag, i - (tag == "insert") * 0, j)
        if tag in ("insert", "delete") and last and last[0] == tag and ((tag == "insert" and j == last[2] + 1 and i == last[1]) or (tag == "delete" and i == last[1] + 1 and j == last[2])):
            cur += 1
        else:
            if cur: out.append((last[0], cur))
            cur = 1 if tag in ("insert", "delete") else 0
        last = (tag, i, j)
    if cur and last: out.append((last[0], cur))
    return out


def main(name, ours_file):
    R = json.load(open(f"scorer/result/drdoc_{name}_text_block_result.json"))
    ours = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open(ours_file))}
    pad = {f'{r["document_id"]}_{r["page"]}': r["markdown"] for r in map(json.loads, open("runs/paddle_dev.jsonl"))}
    by = collections.defaultdict(list)
    for x in R: by[x["img_id"][:-4]].append(x)
    M = collections.Counter(); ex = collections.defaultdict(list)
    for page, items in by.items():
        ref_all = "".join(W(x["gt"]) for x in items if x["norm_gt"]); our_all = W(ours.get(page, "")); pad_all = W(pad.get(page, ""))
        for x in items:
            n = x["Edit_num"]
            if not n: continue
            if not x["norm_pred"]:                      # missing reference block
                if present(x["gt"], our_all): c = "missing: in our output, left unpaired"
                elif present(x["gt"], pad_all): c = "missing: dropped (Paddle read it)"
                else: c = "missing: dropped (Paddle did not read it either)"
            elif not x["norm_gt"]:                      # extra block of ours
                if present(x["pred"], ref_all): c = "extra: reference has it elsewhere on the page"
                elif present(x["pred"], pad_all): c = "extra: real page text the reference leaves out"
                else: c = "extra: neither reference nor Paddle has it"
            else:                                       # matched, different
                a, b = W(x["gt"]), W(x["pred"])
                if len(a) * len(b) > 4e7:
                    M["matched: (too long to diff)"] += n; continue
                ops = Levenshtein.editops(a, b)
                sub = sum(1 for o in ops if o[0] == "replace")
                long_ = sum(l for t, l in runs(ops) if l >= 15); short = len(ops) - sub - long_
                tot = max(len(ops), 1)
                M["matched: character slips (substitutions)"] += n * sub / tot
                M["matched: short insert/delete runs (<15 chars)"] += n * short / tot
                M["matched: long chunks inserted/deleted (>=15 chars)"] += n * long_ / tot
                continue
            M[c] += n
            if len(ex[c]) < 4 and len(W(x["pred"] or x["gt"])) >= 25: ex[c].append((page[:6] + "_p" + page.rsplit("_", 1)[1], re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (x["pred"] or x["gt"])))[:60]))
    T = sum(M.values())
    print(f"{name}: {T:,.0f} edit characters on {len(by)} pages\n")
    for k, v in sorted(M.items(), key=lambda kv: (kv[0].split(":")[0], -kv[1])):
        print(f"  {k:<52} {v / T:6.1%}")
    print("\nexamples (page, first 60 chars):")
    for k in ex:
        print(f"  {k}:"); [print(f"     {p}  {t!r}") for p, t in ex[k]]


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

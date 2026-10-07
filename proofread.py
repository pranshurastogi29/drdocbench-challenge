"""Proofreading pass: a second model (Kimi-K2.5 via OpenRouter, pinned host, high reasoning) gets the page image AND our final transcription
of that page and returns it with recognition errors corrected (wrong / missing / extra characters or words), structure untouched.
How the corrections are used (apply()):
  raw    : the proofread page as returned
  gated  : only word-level edits inside the same paragraph that are near-spellings of the word (an OCR slip), never case-only, never on
           punctuation-only tokens; insertions / deletions of one word, not at the paragraph edges
  indep  : gated, and confirmed outside our model family: PaddleOCR-VL or MinerU on the same page has the new word and not the old one,
           or the edit turns a non-word into a dictionary word (rover.make_gate)
  python proofread.py run  --split dev --pages-from runs/dev_all_sm_kimi25hf.jsonl --tag prk   (pages = those of the 40-window dev subset)
  python proofread.py eval --tag prk                                                          (md2md vs the mbr8 stack on those pages)
"""
import argparse, collections, json, os, random, re, statistics as st, sys, tempfile, threading
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from rapidfuzz import fuzz
from para_fuse import paras, skip, W, HEAD
from rover import K, similar, MATH, make_gate, indep_words

PROMPT = """You are proofreading a transcription of the attached page image. The transcription below was made by an OCR system and may contain recognition errors: wrong, missing or extra characters or words.

Compare the transcription with the image and correct ONLY such recognition errors. Keep everything else exactly as it is:
- the same paragraphs in the same order, separated by blank lines as in the transcription (do not merge, split, move, add or drop paragraphs);
- Markdown markup (#, *, tables, LaTeX) and the capitalization style used in the transcription;
- spellings that match the page, even if old-fashioned or unusual;
- text you cannot verify on the image stays as transcribed.

Return the complete corrected transcription and nothing else (no comments, no code fence).

TRANSCRIPTION:
"""


def page_image(split, subject, doc, page):
    return os.path.join(ROOT, "data", split, subject, doc, "images", f"page_{page}.jpg")


def call(client, model, provider, reasoning, img_b64, text):
    r = client.chat.completions.create(
        model=model, max_tokens=32000, temperature=0,
        messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}},
                                               {"type": "text", "text": PROMPT + text}]}],
        extra_body={"reasoning": {"effort": reasoning}, "usage": {"include": True},
                    **({"provider": {"order": provider.split(","), "allow_fallbacks": False}} if provider else {})})
    out = (r.choices[0].message.content or "").strip()
    out = re.sub(r"^```(?:markdown|md)?\s*\n|\n```\s*$", "", out)
    u = r.usage.model_dump() if r.usage else {}
    return out, u.get("cost") or 0.0, (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0


def apply(ours, proof, gate=None):
    """keep our page; take word-level corrections from the proofread page (see module doc). Returns (md, number of edits)."""
    P = [(HEAD.sub("", q), W(HEAD.sub("", q))) for q in paras(proof) if not skip(q)]
    out, n = [], 0
    for p in paras(ours):
        if skip(p) or MATH.search(p): out.append(p); continue
        m = HEAD.match(p); pre = m.group(1) if m else ""; body = p[len(pre):]; w = W(body)
        best, bq = 0, None
        for q, wq in P:
            if wq and min(len(w), len(wq)) / max(len(w), len(wq)) >= 0.85:
                s = fuzz.ratio(w, wq)
                if s > best: best, bq = s, q
        if bq is None or best < 85: out.append(p); continue
        S, O = body.split(), bq.split(); res = []; i0 = 0
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, [K(x) for x in S], [K(x) for x in O], autojunk=False).get_opcodes():
            edge = i1 == 0 or i2 == len(S)
            if tag == "equal": res += S[i1:i2]
            elif tag == "replace" and i2 - i1 == j2 - j1:
                for a, b in zip(S[i1:i2], O[j1:j2]):
                    ka, kb = K(a), K(b)
                    ok = ka and kb and ka != kb and ka.lower() != kb.lower() and similar(ka, kb) and (gate is None or gate(a, b))
                    res.append(b if ok else a); n += bool(ok)
            elif tag == "delete" and not edge and i2 - i1 == 1 and K(S[i1]) and (gate is None or gate(S[i1], None)): n += 1
            elif tag == "insert" and not edge and j2 - j1 == 1 and K(O[j1]) and (gate is None or gate(None, O[j1])): res += S[i1:i2] + O[j1:j2]; n += 1
            else: res += S[i1:i2]
        out.append(pre + " ".join(res) if res != S else p)
    return "\n\n".join(out), n


def score_job(x):
    import md2md_eval as M
    from common import gt_markdown
    k, split, subj, vs = x; doc, pg = k.rsplit("_", 1); gt = gt_markdown(split, subj, doc, int(pg))
    return k, {n: M.page_scores(md, gt, True) for n, md in vs.items()}


def stack_rows(split, steps):
    import stack
    with tempfile.TemporaryDirectory() as tmp: rows = stack.build(split, steps, tmp)
    os.chdir(ROOT); return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "eval"]); ap.add_argument("--split", default="dev")
    ap.add_argument("--pages-from", help="a run jsonl whose pages define the subset (default: all pages)"); ap.add_argument("--tag", default="prk")
    ap.add_argument("--steps", default="sel=mbr8,rules,fm,sd,bv,ac"); ap.add_argument("--model", default="moonshotai/kimi-k2.5")
    ap.add_argument("--provider", default="siliconflow,atlas-cloud"); ap.add_argument("--reasoning", default="high")
    ap.add_argument("--max-side", type=int, default=1600); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--budget", type=float, default=2.0)
    a = ap.parse_args()
    out = os.path.join(ROOT, "runs", f"{a.split}_proofread_{a.tag}.jsonl")
    if a.cmd == "run":
        import openai
        from common import load_env
        from predict import encode
        load_env()
        client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"], max_retries=2, timeout=600)
        rows = stack_rows(a.split, a.steps)
        if a.pages_from: keep = {(r["document_id"], r["page"]) for r in map(json.loads, open(os.path.join(ROOT, a.pages_from)))}; rows = [r for r in rows if (r["document_id"], r["page"]) in keep]
        done = {(r["document_id"], r["page"]) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
        todo = [r for r in rows if (r["document_id"], r["page"]) not in done and r["markdown"].strip()]
        print(f"{len(todo)} pages to proofread -> {out}", file=sys.stderr)
        lock = threading.Lock(); spent = [0.0, 0]
        def one(r):
            if spent[0] > a.budget: return
            try:
                txt, cost, rt = call(client, a.model, a.provider, a.reasoning, encode(page_image(a.split, r["subject"], r["document_id"], r["page"]), a.max_side), r["markdown"])
            except Exception as e:
                print(f"  fail {r['document_id'][:8]} p{r['page']}: {str(e)[:120]}", file=sys.stderr); return
            with lock:
                spent[0] += cost; spent[1] += 1
                with open(out, "a", encoding="utf-8") as f: f.write(json.dumps({**r, "proof": txt, "cost": cost, "reasoning_tokens": rt}, ensure_ascii=False) + "\n")
                print(f"[{spent[1]}/{len(todo)}] ${spent[0]:.3f}", file=sys.stderr, flush=True)
        with ThreadPoolExecutor(a.workers) as ex: list(ex.map(one, todo))
        print(f"spent ${spent[0]:.3f} on {spent[1]} pages", file=sys.stderr)
    else:
        from multiprocessing import Pool
        import md2md_eval as M
        from common import gt_markdown
        R = [json.loads(l) for l in open(out)]
        C = json.load(open(os.path.join(ROOT, f"runs/selcache_{a.split}.json")))
        def mineru(stem):
            f = os.path.expanduser(f"~/Downloads/mineru_results/{stem}/auto/{stem}.md")
            return re.sub(r"!\[[^\]]*\]\([^)]*\)", "", open(f, encoding="utf-8").read()) if os.path.exists(f) else ""
        V = {}; nedits = collections.Counter()
        for r in R:
            k = f'{r["document_id"]}_{r["page"]}'
            gate = make_gate(indep_words([C.get(k, {}).get("proc", {}).get("paddle", ""), mineru(k)]))
            g, n1 = apply(r["markdown"], r["proof"]); gi, n2 = apply(r["markdown"], r["proof"], gate)
            nedits["gated"] += n1; nedits["indep"] += n2
            V[k] = (r["subject"], {"ours (mbr8 stack)": r["markdown"], "proofread raw": r["proof"], "proofread gated": g, "proofread gated+indep": gi})
        with Pool(11, initializer=M.init) as P: S = dict(P.map(score_job, [(k, a.split, subj, vs) for k, (subj, vs) in V.items()]))
        os.chdir(ROOT)
        ok = [k for k, v in S.items() if all(x and x[1] is not None for x in v.values())]
        U = lambda x: 0.558 * x[0] + 0.433 * x[1]; base = "ours (mbr8 stack)"
        print(f"{len(ok)} dev pages; spent ${sum(r.get('cost', 0) for r in R):.2f}; word edits applied: gated {nedits['gated']}, gated+indep {nedits['indep']}")
        for n in S[ok[0]]:
            by = collections.defaultdict(list)
            for k in ok: by[k.rsplit("_", 1)[0]].append(U(S[k][n]) - U(S[k][base]))
            bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[q]) for q in bs) / sum(len(by[q]) for q in bs)
            bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000)); d = [x for vv in by.values() for x in vv]
            print(f"  {n:24s} Text_ED {1 - st.mean(S[k][n][0] for k in ok) / 100:.4f}  RO {st.mean(S[k][n][1] for k in ok):6.2f}  vs ours {m(bk):+.3f} [{bt[50]:+.3f},{bt[1949]:+.3f}]  pages {sum(x > 0.05 for x in d)}/{sum(x < -0.05 for x in d)}")

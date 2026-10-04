"""OpenRouter Batch API driver (half price, asynchronous, 24h window). The batch endpoint rejects base64 images, so pages are referenced
by signed HTTPS URLs of the copies staged by bucket_stage.py (runs/url_map.json, made by sign_urls.py; gitignored: signed URLs are bearer links).

  python batch_or.py prepare --split test --model anthropic/claude-sonnet-5.5 --prompt v7 --variant plain --tag t_sonnet [--subset 4] [--dry]
  python batch_or.py submit  --tag t_sonnet [--chunk 150]
  python batch_or.py poll    --tag t_sonnet
  python batch_or.py collect --tag t_sonnet     -> runs/<split>_all_<tag>.jsonl  (same schema as predict.py; postprocess applied)

Same windows (2 pages per request), prompt files and postprocess as predict.py, so a batch run is directly comparable with the live runs.
Not reproduced from predict.py: its retry-on-short-page loop (a batch cannot re-ask); pages that come back short are reported by `collect`.
Needs OPENROUTER_API_KEY (.env), read by common.load_env and never printed.
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.request

import predict
from common import list_pages, load_env, load_prompt, windows
from postprocess import is_degenerate, postprocess, strip_sections

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://openrouter.ai/api/v1"


def wdir(tag):
    d = os.path.join(ROOT, "runs", f"batch_{tag}"); os.makedirs(d, exist_ok=True); return d


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {method} {path}: {e.read().decode()[:600]}")


def prepare(a):
    manifest = json.load(open(os.path.join(ROOT, "bucket_stage", "manifest.json")))["pages"]
    urls = {} if a.dry else json.load(open(os.path.join(ROOT, "runs", "url_map.json")))
    prompt = load_prompt(a.prompt)
    docs = list_pages(a.split)
    allw = [(s, d, w) for (s, d), pages in docs.items() for w in windows(pages, a.window)]
    if a.group:    # only the books of one probe group (runs/probe_groups.json, written by build_probes.py)
        ids = {x["doc"] for x in json.load(open(os.path.join(ROOT, "runs", "probe_groups.json")))[a.group]["docs"]}
        allw = [w for w in allw if w[1] in ids]
    if a.subset:
        allw = [allw[i] for i in sorted(random.Random(0).sample(range(len(allw)), min(a.subset, len(allw))))]
    reqs, meta = [], {}
    for s, d, win in allw:
        content = []
        for pg, _ in win:
            rel = manifest[f"{d}_{pg}"][a.variant]
            url = f"https://example.invalid/{rel}" if a.dry else urls[rel]
            content += [{"type": "text", "text": f"Page {pg}:"}, {"type": "image_url", "image_url": {"url": url}}]
        content.append({"type": "text", "text": prompt})
        body = {"model": a.model, "max_tokens": a.max_tokens, "temperature": 0.0, "messages": [{"role": "user", "content": content}]}
        if a.reasoning:
            body["reasoning"] = {"effort": a.reasoning}
        cid = f"{d}__{win[0][0]}"
        reqs.append({"custom_id": cid, "body": body}); meta[cid] = {"subject": s, "doc": d, "pages": [p for p, _ in win]}
    wd = wdir(a.tag)
    json.dump({"split": a.split, "model": a.model, "prompt": a.prompt, "variant": a.variant, "requests": reqs, "meta": meta}, open(os.path.join(wd, "prepared.json"), "w"))
    n_img = sum(1 for r in reqs for c in r["body"]["messages"][0]["content"] if c["type"] == "image_url")
    print(f"{len(reqs)} requests, {n_img} images -> {wd}/prepared.json" + ("  [DRY: placeholder URLs, cannot be submitted]" if a.dry else ""))


def submit(a):
    load_env(); wd = wdir(a.tag); P = json.load(open(os.path.join(wd, "prepared.json")))
    if "example.invalid" in json.dumps(P["requests"][0]):
        sys.exit("prepared with --dry (placeholder URLs); re-run prepare with runs/url_map.json")
    ids = json.load(open(os.path.join(wd, "batches.json"))) if os.path.exists(os.path.join(wd, "batches.json")) else []
    done = {c for b in ids for c in b["custom_ids"]}
    todo = [r for r in P["requests"] if r["custom_id"] not in done]
    for i in range(0, len(todo), a.chunk):
        ch = todo[i:i + a.chunk]
        resp = call("POST", "/batches", {"endpoint": "/v1/chat/completions", "model": P["model"], "completion_window": "24h", "requests": ch})
        ids.append({"id": resp["id"], "custom_ids": [r["custom_id"] for r in ch], "status": resp.get("status")})
        json.dump(ids, open(os.path.join(wd, "batches.json"), "w"), indent=1)   # saved after each batch, so a crash never loses an id
        print(f"submitted batch {resp['id']}: {len(ch)} requests, status {resp.get('status')}")


def poll(a):
    load_env(); wd = wdir(a.tag)
    for b in json.load(open(os.path.join(wd, "batches.json"))):
        r = call("GET", f"/batches/{b['id']}")
        print(b["id"], r["status"], r.get("request_counts"), "cost", (r.get("usage") or {}).get("cost"))


def collect(a):
    load_env(); wd = wdir(a.tag); P = json.load(open(os.path.join(wd, "prepared.json")))
    out = os.path.join(ROOT, "runs", f"{P['split']}_all_{a.tag}.jsonl")
    have = {(r["document_id"], r["page"]) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    cost, ok, bad, short, pend, trunc = 0.0, 0, 0, 0, 0, 0
    with open(out, "a", encoding="utf-8") as f:
        for b in json.load(open(os.path.join(wd, "batches.json"))):
            r = call("GET", f"/batches/{b['id']}")
            if r["status"] not in ("completed", "failed", "expired", "cancelled"):
                pend += 1; continue
            cost += (r.get("usage") or {}).get("cost") or 0
            for item in r.get("results") or []:
                m = P["meta"][item["custom_id"]]
                body = ((item.get("response") or {}).get("body")) or {}
                ch0 = (body.get("choices") or [{}])[0]
                text = (ch0.get("message") or {}).get("content") or ""
                trunc += ch0.get("finish_reason") == "length"   # hit max_tokens: the page text is cut off
                if item.get("error") or not text.strip() or is_degenerate(text):
                    bad += 1; print("  failed/degenerate:", item["custom_id"], (item.get("error") or {}).get("message", "")[:120]); continue
                pages = predict.split_pages(text, len(m["pages"]))
                short += sum(len(strip_sections(x).strip()) < predict.SHORT for x in pages)
                for pg, md in zip(m["pages"], pages):
                    if (m["doc"], pg) not in have:
                        f.write(json.dumps({"subject": m["subject"], "document_id": m["doc"], "page": pg, "markdown": postprocess(md)}) + "\n"); ok += 1
    print(f"{out}: wrote {ok} pages; failed/degenerate requests {bad}; short pages {short}; truncated at max_tokens {trunc}; batches still running {pend}; batch cost so far ${cost:.4f}")


def live(a):
    """Same prepared requests, sent synchronously at the live (non-batch) price, for models with no :batch variant.
    Stops submitting once the spend reported by OpenRouter passes --budget."""
    from concurrent.futures import ThreadPoolExecutor
    load_env(); wd = wdir(a.tag); P = json.load(open(os.path.join(wd, "prepared.json")))
    out = os.path.join(ROOT, "runs", f"{P['split']}_all_{a.tag}.jsonl")
    spent = {"cost": 0.0}; stats = {"ok": 0, "bad": 0, "short": 0, "trunc": 0}
    have = {(r["document_id"], r["page"]) for r in map(json.loads, open(out))} if os.path.exists(out) else set()

    def one(r):
        if spent["cost"] >= a.budget:
            return r["custom_id"], None, "budget"
        for attempt in range(3):
            try:
                resp = call("POST", "/chat/completions", {**r["body"], "usage": {"include": True}})
                spent["cost"] += (resp.get("usage") or {}).get("cost") or 0
                return r["custom_id"], resp, None
            except (SystemExit, OSError, ValueError) as e:      # HTTP error from call(), or a dropped connection / bad JSON
                err = str(e)
                if "402" in err or "403" in err: return r["custom_id"], None, err
                time.sleep(5 * (attempt + 1))
        return r["custom_id"], None, "failed after retries"

    todo = [r for r in P["requests"] if not all((P["meta"][r["custom_id"]]["doc"], pg) in have for pg in P["meta"][r["custom_id"]]["pages"])]
    print(f"{len(P['requests']) - len(todo)} windows already done, {len(todo)} to run")
    with open(out, "a", encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as ex:
        for cid, resp, err in ex.map(one, todo):
            m = P["meta"][cid]
            if resp is None:
                stats["bad"] += 1; print("  not run:", cid, (err or "")[:100]); continue
            ch0 = resp["choices"][0]; text = (ch0.get("message") or {}).get("content") or ""
            stats["trunc"] += ch0.get("finish_reason") == "length"
            if not text.strip() or is_degenerate(text):
                stats["bad"] += 1; print("  empty/degenerate:", cid); continue
            pages = predict.split_pages(text, len(m["pages"]))
            stats["short"] += sum(len(strip_sections(x).strip()) < predict.SHORT for x in pages)
            for pg, md in zip(m["pages"], pages):
                if (m["doc"], pg) not in have:
                    f.write(json.dumps({"subject": m["subject"], "document_id": m["doc"], "page": pg, "markdown": postprocess(md)}) + "\n"); stats["ok"] += 1
            f.flush()
    print(f"{out}: wrote {stats['ok']} pages; failed {stats['bad']}; short pages {stats['short']}; truncated {stats['trunc']}; spend ${spent['cost']:.4f} (budget ${a.budget})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--split", default="test", choices=["dev", "test"]); p.add_argument("--model", required=True)
    p.add_argument("--prompt", default="v7"); p.add_argument("--variant", default="plain", choices=["plain", "contrast"]); p.add_argument("--window", type=int, default=2)
    p.add_argument("--reasoning", choices=["low", "medium", "high"]); p.add_argument("--max-tokens", type=int, default=32000); p.add_argument("--subset", type=int); p.add_argument("--group", choices=["G1", "G2", "G3", "G4"])
    p.add_argument("--dry", action="store_true")
    for c in ("prepare", "submit", "poll", "collect", "live"):
        q = p if c == "prepare" else sp.add_parser(c); q.add_argument("--tag", required=True)
        if c == "submit": q.add_argument("--chunk", type=int, default=150)
        if c == "live": q.add_argument("--budget", type=float, default=4.0); q.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    {"prepare": prepare, "submit": submit, "poll": poll, "collect": collect, "live": live}[a.cmd](a)

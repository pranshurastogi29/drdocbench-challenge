"""Generate predictions.jsonl for a split.

  python predict.py --backend oracle --fold a                         # scorer sanity check, no API
  python predict.py --fold a --prompt v0 --tag v0                     # tune on dev fold A
  python predict.py --fold b --prompt v3 --tag v3                     # confirm on held-out fold B
  python predict.py --split test --prompt v3 --tag final              # test images -> submission

Needs OPENROUTER_API_KEY, or HF_TOKEN with --api hf (environment or a .env file next to this script).
Resumable: pages already present in the output file are skipped. Output: runs/<split>_<fold>_<tag>.jsonl
"""
import argparse
import base64
import io
import json
import re
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

from common import PAGE_SEP, fold, gt_markdown, list_pages, load_env, load_prompt, windows as _windows
from postprocess import is_degenerate, postprocess, strip_sections


SHORT = 60  # chars; a page shorter than this triggers a retry


PREPROC = "none"   # set from --preprocess: "contrast" = stretch the histogram before upscaling, mild unsharp mask after


FRAME_SKIP = {"image", "chart", "seal", "header_image", "footer_image"}


def draw_frames(im, path):
    """--preprocess frames: thin red frames around PaddleOCR-VL's layout blocks (no numbers), so the model sees where text regions end"""
    from PIL import ImageDraw
    import paddle_ingest
    m = re.search(r"/([0-9a-f-]{36})/images/page_(\d+)\.", path)
    if not m: return im
    bl = paddle_ingest.blocks(f"{m.group(1)}_{m.group(2)}") or []
    d = ImageDraw.Draw(im)
    for b in bl:
        if b["block_label"] in FRAME_SKIP: continue
        x0, y0, x1, y1 = b["block_bbox"]
        d.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=(230, 0, 0), width=1)
    return im


def encode(path, max_side):
    im = Image.open(path).convert("RGB")
    if PREPROC == "frames":
        im = draw_frames(im, path)
    if PREPROC == "contrast":
        from PIL import ImageOps
        im = ImageOps.autocontrast(im, cutoff=1)
    if max_side and max(im.size) != max_side:  # also upscales: page images are only ~460x740
        s = max_side / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    if PREPROC == "contrast":
        from PIL import ImageFilter
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return base64.standard_b64encode(buf.getvalue()).decode()


def split_pages(text, n):
    parts = [p.strip() for p in text.split(PAGE_SEP)]
    if len(parts) < n:
        parts += [""] * (n - len(parts))
    if len(parts) > n:  # extra separators: fold the surplus into the last page
        parts = parts[: n - 1] + ["\n\n".join(parts[n - 1 :])]
    return parts


class OpenRouter:
    API = {"openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
           "hf": ("https://router.huggingface.co/v1", "HF_TOKEN")}   # Hugging Face Inference Providers (model id "org/Model:provider")

    def __init__(self, model, prompt, max_side, reasoning, temperature, api="openrouter", price=None, no_think=False):
        import openai

        url, env = self.API[api]
        key = os.environ.get(env)
        if not key:
            sys.exit(f"{env} is not set (export it, or put it in .env next to predict.py)")
        self.client = openai.OpenAI(base_url=url, api_key=key, max_retries=2, timeout=240)
        self.model, self.prompt, self.max_side = model, prompt, max_side
        self.price = price  # (USD per M input, USD per M output) for APIs that do not return the cost of a call
        if api == "openrouter":
            self.extra = {"reasoning": {"effort": reasoning}} if reasoning else {}
            self.extra["usage"] = {"include": True}  # ask OpenRouter to return the actual cost of each call
        else:
            self.extra = {"chat_template_kwargs": {"thinking": False}} if no_think else {}   # Kimi K2.x on HF providers: answer without a thinking phase
        self.usage = []  # one dict per API call (retries included), for cost reporting
        self.temperature = temperature

    def __call__(self, win, temperature=None, **_):
        content = []
        for pg, path in win:
            content.append({"type": "text", "text": f"Page {pg}:"})
            content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encode(path, self.max_side)}})
        content.append({"type": "text", "text": self.prompt})
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=32000,
            temperature=self.temperature if temperature is None else temperature,
            messages=[{"role": "user", "content": content}],
            extra_body=self.extra,
        )
        u = resp.usage.model_dump() if resp.usage is not None else {}
        self.usage.append({
            "prompt": u.get("prompt_tokens", 0),
            "completion": u.get("completion_tokens", 0),
            "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0,
            "cost": u.get("cost") if u.get("cost") is not None or not self.price else
                    (u.get("prompt_tokens", 0) * self.price[0] + u.get("completion_tokens", 0) * self.price[1]) / 1e6,
        })
        ch = resp.choices[0]
        text = ch.message.content or ""
        if not text.strip() and PAGE_SEP not in text:  # reasoning ate the budget, or a transient empty answer
            raise RuntimeError(f"empty answer (finish_reason={ch.finish_reason}, tokens={resp.usage.completion_tokens})")
        return text


def report_usage(backend, n_windows, out):
    calls = getattr(backend, "usage", None)
    if not calls:
        return
    tot = {k: sum(c[k] or 0 for c in calls) for k in ("prompt", "completion", "reasoning")}
    costs = [c["cost"] for c in calls if c["cost"] is not None]
    cost = sum(costs) if costs else None
    summary = {"windows": n_windows, "api_calls": len(calls), **tot, "cost_usd": cost}
    if cost is not None and n_windows:
        summary["cost_per_window_usd"] = cost / n_windows
    json.dump(summary, open(out.replace(".jsonl", ".usage.json"), "w"), indent=1)
    print("USAGE", json.dumps(summary), file=sys.stderr)


OFFSET = 0


def windows(pages, n=2):
    """the window grid, shifted by --offset (the first OFFSET pages form their own window)"""
    if OFFSET and n > 1 and len(pages) > OFFSET:
        yield pages[:OFFSET]
        yield from _windows(pages[OFFSET:], n)
    else:
        yield from _windows(pages, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--backend", default="openrouter", choices=["openrouter", "oracle", "empty"])
    ap.add_argument("--model", default="stealth/space-bunny-alpha")
    ap.add_argument("--prompt", default="v0", help="prompts/<name>.txt")
    ap.add_argument("--tag", help="run name (default: prompt name)")
    ap.add_argument("--fold", default="all", choices=["a", "b", "all"], help="dev only: tuning fold / held-out fold")
    ap.add_argument("--window", type=int, default=2)
    ap.add_argument("--offset", type=int, default=0, help="test-time augmentation: shift the window grid (offset 1 -> first page alone, then pairs 2-3, 4-5, ...)")
    ap.add_argument("--max-side", type=int, default=0, help="resize longest side of each page (0 = keep)")
    ap.add_argument("--reasoning", choices=["low", "medium", "high"], help="OpenRouter reasoning effort")
    ap.add_argument("--api", default="openrouter", choices=["openrouter", "hf"], help="hf = Hugging Face Inference Providers (needs HF_TOKEN; model id like moonshotai/Kimi-K2.6:novita)")
    ap.add_argument("--no-think", action="store_true", help="hf only: disable the model's thinking phase (Kimi K2.x: chat_template_kwargs thinking=false)")
    ap.add_argument("--price", help="IN,OUT USD per million tokens, to estimate cost when the API does not report it (e.g. 0.8,3.4)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--no-postprocess", action="store_true")
    ap.add_argument("--preprocess", default="none", choices=["none", "contrast", "frames"], help="image preprocessing before the model call")
    ap.add_argument("--limit-docs", type=int)
    ap.add_argument("--subset", type=int, help="run a fixed random sample of N windows (seeded), for fast A/B comparisons")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--windows", help="JSON file with a list of [document_id, first_page]: run only those windows (fixed A/B sets)")
    args = ap.parse_args()

    load_env()
    global PREPROC, OFFSET
    PREPROC = args.preprocess; OFFSET = args.offset
    os.makedirs("runs", exist_ok=True)
    out = f"runs/{args.split}_{args.fold if args.split == 'dev' else 'all'}_{args.tag or args.prompt}.jsonl"
    docs = list_pages(args.split)
    if args.split == "dev" and args.fold != "all":
        docs = {k: v for k, v in docs.items() if fold(k[1]) == args.fold}
    if args.limit_docs:
        docs = dict(list(docs.items())[: args.limit_docs])

    if args.subset:
        import random

        allw = [(s_, d_, w_) for (s_, d_), pages in docs.items() for w_ in windows(pages, args.window)]
        keep = random.Random(0).sample(range(len(allw)), min(args.subset, len(allw)))
        subset = {(allw[i][1], allw[i][2][0][0]) for i in keep}  # (doc, first page)
    elif args.windows:
        subset = {(d_, p_) for d_, p_ in json.load(open(args.windows))}
    else:
        subset = None

    done = set()
    if os.path.exists(out):
        for line in open(out):
            r = json.loads(line)
            done.add((r["subject"], r["document_id"], r["page"]))

    jobs = []
    for (subject, doc), pages in docs.items():
        for win in windows(pages, args.window):
            if subset is not None and (doc, win[0][0]) not in subset:
                continue
            if all((subject, doc, pg) in done for pg, _ in win):
                continue
            jobs.append((subject, doc, win))
    print(f"{len(docs)} docs, {len(jobs)} windows to run -> {out}", file=sys.stderr)

    if args.backend == "openrouter":
        backend = OpenRouter(args.model, load_prompt(args.prompt), args.max_side, args.reasoning, args.temperature, args.api,
                             tuple(map(float, args.price.split(","))) if args.price else None, args.no_think)
    elif args.backend == "oracle":
        backend = lambda win, split, subject, doc: PAGE_SEP.join(gt_markdown(split, subject, doc, pg) for pg, _ in win)
    else:
        backend = lambda win, **_: PAGE_SEP.join("" for _ in win)

    def run(job):
        subject, doc, win = job
        for attempt in range(3):
            try:
                kw = {"temperature": 0.3 * attempt} if attempt and args.backend == "openrouter" else {}
                text = backend(win, split=args.split, subject=subject, doc=doc, **kw)
                if is_degenerate(text):  # repetition loop: retry, warmer each time
                    raise RuntimeError(f"degenerate output ({len(text)} chars)")
                pages = split_pages(text, len(win))
                if attempt < 2 and any(len(strip_sections(x).strip()) < SHORT for x in pages) and args.backend == "openrouter":
                    # a page came back empty or suspiciously short (often just page furniture, body dropped): usually a
                    # transient failure, so re-ask warmer, up to twice, and keep the answer with the most content
                    for k in (1, 2):
                        alt = split_pages(backend(win, split=args.split, subject=subject, doc=doc, temperature=0.3 * k), len(win))
                        if sum(map(len, alt)) > sum(map(len, pages)):
                            pages = alt
                        if all(len(strip_sections(x).strip()) >= SHORT for x in pages):
                            break
                return job, pages if args.no_postprocess else [postprocess(p) for p in pages]
            except Exception as e:  # noqa: BLE001
                print(f"  retry {doc} {[p for p, _ in win]}: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        return job, None  # not written, so a rerun retries it

    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(run, j) for j in jobs]
        for i, fut in enumerate(as_completed(futures), 1):  # write each window as it finishes
            job, mds = fut.result()
            subject, doc, win = job
            if mds is None:
                print(f"  FAILED {doc} {[p for p, _ in win]}", file=sys.stderr)
                continue
            for (pg, _), md in zip(win, mds):
                f.write(json.dumps({"subject": subject, "document_id": doc, "page": pg, "markdown": md}) + "\n")
            f.flush()
            print(f"[{i}/{len(jobs)}] {time.time() - t0:.0f}s", file=sys.stderr)
    report_usage(backend, len(jobs), out)


if __name__ == "__main__":
    main()

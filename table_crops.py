"""Second pass for tables: crop every PaddleOCR-VL table block from the page image and transcribe it alone with the free model.

  python table_crops.py --split dev --tag t1 [--limit N] [--preprocess contrast]
Output runs/tables_<split>_<tag>.jsonl: {stem, idx, bbox, html}. Resumable. Needs OPENROUTER_API_KEY in .env.
"""
import argparse, base64, glob, io, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageFilter, ImageOps
from common import DATA, load_env, load_prompt
from paddle_ingest import blocks

PAD = 10


def crop_b64(path, bbox, max_side, contrast):
    im = Image.open(path).convert("RGB")
    x0, y0, x1, y1 = bbox
    im = im.crop((max(0, x0 - PAD), max(0, y0 - PAD), min(im.width, x1 + PAD), min(im.height, y1 + PAD)))
    if contrast:
        im = ImageOps.autocontrast(im, cutoff=1)
    s = max_side / max(im.size)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    if contrast:
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=92)
    return base64.standard_b64encode(buf.getvalue()).decode()


def find_image(split, stem):
    doc, pg = stem.rsplit("_", 1)
    hits = glob.glob(os.path.join(DATA, split, "*", doc, "images", f"page_{pg}.jpg"))
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev"); ap.add_argument("--tag", required=True); ap.add_argument("--prompt", default="tbl1")
    ap.add_argument("--model", default="stealth/space-bunny-alpha"); ap.add_argument("--max-side", type=int, default=1600)
    ap.add_argument("--reasoning", default="low"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int); ap.add_argument("--preprocess", default="contrast")
    a = ap.parse_args()
    load_env()
    import openai
    client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"], max_retries=2, timeout=240)
    prompt = load_prompt(a.prompt)
    out = f"runs/tables_{a.split}_{a.tag}.jsonl"
    done = {(r["stem"], r["idx"]) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    jobs = []
    for d in sorted(glob.glob(os.path.join(DATA, a.split, "*", "*"))):
        doc = os.path.basename(d)
        for img in sorted(glob.glob(os.path.join(d, "images", "page_*.jpg"))):
            stem = f"{doc}_{re.search(r'page_(\d+)', img).group(1)}"
            for i, b in enumerate([b for b in (blocks(stem) or []) if b["block_label"] == "table"]):
                if (stem, i) not in done: jobs.append((stem, i, b["block_bbox"], img))
    if a.limit: jobs = jobs[: a.limit]
    print(f"{len(jobs)} table crops to do ({len(done)} already done)", flush=True)

    def run(job):
        stem, i, bbox, img = job
        for attempt in range(3):
            try:
                r = client.chat.completions.create(model=a.model, max_tokens=32000, temperature=0.0, extra_body={"reasoning": {"effort": a.reasoning}, "usage": {"include": True}},
                    messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + crop_b64(img, bbox, a.max_side, a.preprocess == "contrast")}}, {"type": "text", "text": prompt}]}])
                t = r.choices[0].message.content or ""
                if "<table" in t.lower(): return {"stem": stem, "idx": i, "bbox": bbox, "html": t}
            except Exception as e:
                print("  retry", stem, i, str(e)[:100], flush=True); time.sleep(3)
        return {"stem": stem, "idx": i, "bbox": bbox, "html": ""}

    t0 = time.time(); n = 0
    with ThreadPoolExecutor(a.workers) as ex, open(out, "a", encoding="utf-8") as f:
        for fut in as_completed([ex.submit(run, j) for j in jobs]):
            f.write(json.dumps(fut.result(), ensure_ascii=False) + "\n"); f.flush(); n += 1
            if n % 10 == 0 or n == len(jobs): print(f"[{n}/{len(jobs)}] {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

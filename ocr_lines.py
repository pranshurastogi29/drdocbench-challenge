"""Line-level OCR with boxes (RapidOCR / PP-OCR det+rec, CPU) for the pages listed in runs/ocr_jobs.json.
Runs in the separate Python 3.11 env (.venv-ocr) because onnxruntime has no Python 3.14 wheel for this machine.
  .venv-ocr/bin/python ocr_lines.py   -> runs/ocr_lines.jsonl  (boxes normalised to 0-1 by image size; resumable)
"""
import json, os, sys
from multiprocessing import Pool

OUT = "runs/ocr_lines.jsonl"


def work(job):
    import cv2
    from rapidocr_onnxruntime import RapidOCR
    global ENG
    if "ENG" not in globals():
        ENG = RapidOCR()
    im = cv2.imread(job["path"]); H, W = im.shape[:2]
    res, _ = ENG(im)
    lines = [{"box": [min(p[0] for p in b) / W, min(p[1] for p in b) / H, max(p[0] for p in b) / W, max(p[1] for p in b) / H],
              "text": t, "conf": float(c)} for b, t, c in (res or [])]
    return {**job, "w": W, "h": H, "lines": lines}


if __name__ == "__main__":
    jobs = json.load(open("runs/ocr_jobs.json"))
    done = {json.loads(l)["stem"] for l in open(OUT)} if os.path.exists(OUT) else set()
    jobs = [j for j in jobs if j["stem"] not in done]
    print(len(jobs), "pages to OCR", flush=True)
    with open(OUT, "a") as f, Pool(4) as pool:
        for i, r in enumerate(pool.imap_unordered(work, jobs), 1):
            f.write(json.dumps(r) + "\n"); f.flush()
            if i % 20 == 0: print(i, flush=True)

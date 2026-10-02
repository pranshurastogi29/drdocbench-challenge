"""Drive the Kaggle CLI for the PaddleOCR-VL / MinerU jobs. Never reads or prints credentials: the `kaggle` CLI
finds them itself (run `kaggle auth login` once, or save a token to ~/.kaggle/access_token).

  python kaggle/run_kaggle.py --user YOURNAME quota
  python kaggle/run_kaggle.py --user YOURNAME upload                     # private dataset from drdocbench_pages.zip
  python kaggle/run_kaggle.py --user YOURNAME push paddle --limit 20     # smoke test on 20 pages
  python kaggle/run_kaggle.py --user YOURNAME wait paddle
  python kaggle/run_kaggle.py --user YOURNAME fetch paddle               # -> kaggle/results/paddle/
  python kaggle/run_kaggle.py --user YOURNAME push paddle                # full run (no --limit)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KAGGLE = os.path.join(os.path.dirname(sys.executable), "kaggle")
DATASET = "drdoc-pages-v2"
TOOLS = {  # name -> (notebook file, kernel slug)
    "paddle": ("paddleocr_vl.ipynb", "drdoc-paddleocr-vl"),
    "mineru": ("mineru.ipynb", "drdoc-mineru"),
    "mineru2": ("mineru.ipynb", "drdoc-mineru2"),   # chunked, time-budgeted rerun
    "docling": ("docling.ipynb", "drdoc-docling"),
}


def run(*args, check=True):
    print("$ kaggle", " ".join(args), flush=True)
    p = subprocess.run([KAGGLE, *args], capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    shown = "\n".join(l for l in out.splitlines() if not re.search(r"\d+%\||it/s|[kM]B/s", l))
    print(shown[-2500:], flush=True)
    if check and p.returncode:
        sys.exit(f"kaggle exited with {p.returncode}")
    return p.returncode, out


def upload(user):
    d = os.path.join(HERE, "stage", "dataset")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    shutil.copy(os.path.join(HERE, "drdocbench_pages.zip"), d)
    json.dump({"title": DATASET, "id": f"{user}/{DATASET}", "licenses": [{"name": "other"}]},
              open(os.path.join(d, "dataset-metadata.json"), "w"))
    rc, out = run("datasets", "create", "-p", d, check=False)  # private by default
    if rc or "error" in out.lower():
        print("create failed (already exists?) - trying a new version instead")
        run("datasets", "version", "-p", d, "-m", "update", "-r", "zip")


def push(user, tool, limit, accel, only=None):
    nb, slug = TOOLS[tool]
    d = os.path.join(HERE, "stage", tool)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    nbj = json.load(open(os.path.join(HERE, nb), encoding="utf-8"))
    hits = 0
    for c in nbj["cells"]:  # edit code cells only: the markdown instructions also mention "LIMIT = 20"
        if c["cell_type"] != "code":
            continue
        for i, line in enumerate(c["source"]):
            if re.match(r"LIMIT = (\d+|None)", line):
                c["source"][i] = re.sub(r"LIMIT = (\d+|None)", f"LIMIT = {limit if limit else 'None'}", line, count=1)
                hits += 1
    assert hits == 1, f"expected exactly one LIMIT line in a code cell, found {hits}"
    if only:  # rerun just these page stems, one page per call, short timeout (isolates pages that hang MinerU)
        stems = sorted(only)
        for c in nbj["cells"]:
            if c["cell_type"] != "code":
                continue
            s = "".join(c["source"])
            if "rows = [r for r in csv.DictReader" in s:
                s = s.replace("rows = [r for r in csv.DictReader", f"ONLY = set({stems!r})\nrows = [r for r in csv.DictReader", 1)
                s = s.replace('if r["split"] in SPLITS]', 'if r["split"] in SPLITS and f"{r[\'doc\']}_{r[\'page\']}" in ONLY]', 1)
            if "CHUNK = 5 if LIMIT else 40" in s:
                s = s.replace("CHUNK = 5 if LIMIT else 40", "CHUNK = 1").replace("timeout=1500", "timeout=240")
            c["source"] = s.split("\n"); c["source"] = [l + "\n" for l in c["source"][:-1]] + [c["source"][-1]]
    json.dump(nbj, open(os.path.join(d, nb), "w", encoding="utf-8"), indent=1)
    json.dump({"id": f"{user}/{slug}", "title": slug, "code_file": nb, "language": "python", "kernel_type": "notebook",
               "is_private": True, "enable_gpu": True, "enable_internet": True,
               "dataset_sources": [f"{user}/{DATASET}"], "competition_sources": [], "kernel_sources": []},
              open(os.path.join(d, "kernel-metadata.json"), "w"), indent=1)
    run("kernels", "push", "-p", d, "--accelerator", accel)


def wait(user, tool, every=60):
    slug = TOOLS[tool][1]
    while True:
        _, out = run("kernels", "status", f"{user}/{slug}", check=False)
        low = out.lower()
        if "complete" in low or "error" in low or "cancel" in low:
            return
        time.sleep(every)


def fetch(user, tool):
    d = os.path.join(HERE, "results", tool)
    os.makedirs(d, exist_ok=True)
    run("kernels", "output", f"{user}/{TOOLS[tool][1]}", "-p", d, "-o")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="your Kaggle username (not secret)")
    ap.add_argument("--accelerator", default="NvidiaTeslaT4")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("quota"); sp.add_parser("upload")
    for c in ("push", "wait", "fetch"):
        x = sp.add_parser(c); x.add_argument("tool", choices=TOOLS)
        if c == "push":
            x.add_argument("--limit", type=int)
            x.add_argument("--only-file", help="text file with one page stem (<doc>_<page>) per line: rerun only these pages")
    a = ap.parse_args()
    if a.cmd == "quota": run("quota")
    elif a.cmd == "upload": upload(a.user)
    elif a.cmd == "push": push(a.user, a.tool, a.limit, a.accelerator, set(open(a.only_file).read().split()) if a.only_file else None)
    elif a.cmd == "wait": wait(a.user, a.tool)
    elif a.cmd == "fetch": fetch(a.user, a.tool)

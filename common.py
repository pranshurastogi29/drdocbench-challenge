"""Shared helpers: page discovery, windowing, prompt."""
import glob
import hashlib
import os
import re
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

PAGE_SEP = "<<<PAGE_BREAK>>>"

def load_prompt(name="v0"):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", f"{name}.txt")
    return open(p, encoding="utf-8").read().replace("{SEP}", PAGE_SEP)


def load_env():
    """Read KEY=VALUE lines from .env next to this file into os.environ (existing vars win)."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(p):
        return
    for line in open(p):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def fold(doc):
    """Deterministic 50/50 split of dev documents: tune on fold 'a', confirm on held-out fold 'b'."""
    return "a" if int(hashlib.md5(doc.encode()).hexdigest(), 16) % 2 == 0 else "b"


def page_no(path):
    return int(re.search(r"page_(\d+)\.jpg$", path).group(1))


def list_pages(split):
    """Return {(subject, doc_id): [(page, image_path), ...]} sorted by page number."""
    docs = defaultdict(list)
    for img in glob.glob(os.path.join(DATA, split, "*", "*", "images", "page_*.jpg")):
        parts = img.split(os.sep)
        subject, doc = parts[-4], parts[-3]
        docs[(subject, doc)].append((page_no(img), img))
    return {k: sorted(v) for k, v in sorted(docs.items())}


def windows(pages, n=2):
    """Non-overlapping windows of n consecutive pages (last may be shorter)."""
    for i in range(0, len(pages), n):
        yield pages[i : i + n]


def gt_markdown(split, subject, doc, page):
    p = os.path.join(DATA, split, subject, doc, "mds", f"{doc}_{page}.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

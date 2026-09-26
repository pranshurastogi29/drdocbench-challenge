"""Build the Kaggle upload package: every dev+test page image as pages/<doc>_<page>.jpg plus manifest.csv.
  python kaggle/build_package.py      -> kaggle/manifest.csv, kaggle/drdocbench_pages.zip   (needs data/dev and data/test)
"""
import csv, os, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from common import list_pages

rows = []
for split in ("dev", "test"):
    for (subject, doc), pages in list_pages(split).items():
        for pg, path in pages:
            rows.append((split, subject, doc, pg, path))
with open(os.path.join(HERE, "manifest.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["split", "subject", "doc", "page", "file"])
    for s, su, d, p, _ in rows: w.writerow([s, su, d, p, f"pages/{d}_{p}.jpg"])
with zipfile.ZipFile(os.path.join(HERE, "drdocbench_pages.zip"), "w", zipfile.ZIP_STORED) as z:   # jpgs are already compressed
    z.write(os.path.join(HERE, "manifest.csv"), "manifest.csv")
    for s, su, d, p, path in rows: z.write(path, f"pages/{d}_{p}.jpg")
print(len(rows), "page images (dev %d, test %d)" % (sum(r[0] == "dev" for r in rows), sum(r[0] == "test" for r in rows)))

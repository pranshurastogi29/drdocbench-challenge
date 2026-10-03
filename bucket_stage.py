"""Stage the page images for a bucket, exactly as predict.py sends them to the model (1600px longest side, JPEG q92).
OpenRouter's Batch API rejects base64/data: URIs and needs public HTTP(S) image URLs, so the pages must be hosted.

  python bucket_stage.py            -> bucket_stage/<token>/plain/<doc>_<page>.jpg and .../contrast/...  + bucket_stage/manifest.json
The <token> is random, so the object URLs are unguessable. Upload the folder with the commands printed at the end.
"""
import base64, json, os, secrets, sys

import predict
from common import list_pages

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "bucket_stage")


def main():
    os.makedirs(OUT, exist_ok=True)
    mf = os.path.join(OUT, "manifest.json")
    m = json.load(open(mf)) if os.path.exists(mf) else {"token": secrets.token_hex(12), "pages": {}}
    n = 0
    for variant, pre in (("plain", "none"), ("contrast", "contrast")):
        predict.PREPROC = pre
        for split in ("dev", "test"):
            for (subject, doc), pages in list_pages(split).items():
                for pg, path in pages:
                    rel = f"{m['token']}/{variant}/{doc}_{pg}.jpg"
                    dst = os.path.join(OUT, rel)
                    if not os.path.exists(dst):
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        open(dst, "wb").write(base64.b64decode(predict.encode(path, 1600))); n += 1
                    m["pages"].setdefault(f"{doc}_{pg}", {"split": split, "subject": subject})[variant] = rel
    json.dump(m, open(mf, "w"), indent=1)
    tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print(f"{n} new images; {len(m['pages'])} pages x 2 variants; {tot / 1e6:.0f} MB in bucket_stage/ (token {m['token']})")


if __name__ == "__main__":
    main()

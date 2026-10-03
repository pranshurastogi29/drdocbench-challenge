"""Upload bucket_stage/ to a PRIVATE Cloud Storage bucket and write 2-day signed URLs to runs/url_map.json (gitignored: bearer links).

  python gcs_upload.py --bucket YOUR_BUCKET [--key secrets/gcs_sa.json] [--days 2]

The service-account key file is only handed to google-cloud-storage (which reads it to sign and authenticate); it is never opened,
printed or logged here. Bucket: uniform access, public-access prevention ON, lifecycle delete-after-3-days (see README steps).
Resumable: objects already in the bucket with the same size are skipped. Ends by fetching one signed URL to prove it is readable without credentials.
"""
import argparse
import datetime
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from google.cloud import storage

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bucket", required=True)
    ap.add_argument("--key", default=os.path.join(ROOT, "secrets", "gcs_sa.json")); ap.add_argument("--days", type=int, default=2)
    a = ap.parse_args()
    if not os.path.exists(a.key):
        raise SystemExit(f"service-account key not found at {a.key}")
    cl = storage.Client.from_service_account_json(a.key); bk = cl.bucket(a.bucket)
    mf = json.load(open(os.path.join(ROOT, "bucket_stage", "manifest.json")))
    rels = sorted({rel for v in mf["pages"].values() for k, rel in v.items() if k in ("plain", "contrast")})
    have = {b.name: b.size for b in cl.list_blobs(a.bucket, prefix=mf["token"] + "/")}

    def up(rel):
        p = os.path.join(ROOT, "bucket_stage", rel)
        if have.get(rel) != os.path.getsize(p):
            bk.blob(rel).upload_from_filename(p, content_type="image/jpeg")
        return rel

    with ThreadPoolExecutor(16) as ex:
        for i, _ in enumerate(ex.map(up, rels), 1):
            if i % 300 == 0: print(f"uploaded/checked {i}/{len(rels)}", flush=True)
    exp = datetime.timedelta(days=a.days)
    urls = {rel: bk.blob(rel).generate_signed_url(version="v4", expiration=exp, method="GET") for rel in rels}
    json.dump(urls, open(os.path.join(ROOT, "runs", "url_map.json"), "w"))
    print(f"{len(urls)} signed URLs (valid {a.days} days) -> runs/url_map.json")
    with urllib.request.urlopen(next(iter(urls.values())), timeout=60) as r:   # no credentials: what an upstream provider will do
        print("fetch check without credentials: HTTP", r.status, r.headers.get("content-type"), len(r.read()), "bytes")


if __name__ == "__main__":
    main()

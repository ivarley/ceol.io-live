"""The data the listening service needs that is not in the repo: the session's
repertoire index, the whole corpus's index and the aligner's sequences, built
by the lab (`lab index`, `corpus.sequences`), about 76 MB. Kept in the
recordings bucket under LISTEN_DATA_PREFIX and fetched at start into
LAB_DATA_DIR when not already there. The tune-ness model is in the repo
(lab/configs/tuneness.json).

Upload from the lab's worktree, where the files are built and lab/.env holds
the AWS credentials (this writes to the bucket):

    venv/bin/python -m listen.data upload
"""

import os
import sys

FILES = [
    "index/repertoire-n6-folded-p2i2.pkl",
    "index/repertoire-n6-folded-p2i2.meta.json",
    "index/all-n6-folded-p2i2.pkl",
    "index/all-n6-folded-p2i2.meta.json",
    "index/sequences-all-p2-v1.pkl",
]
PREFIX = os.environ.get("LISTEN_DATA_PREFIX", "listen-data/v1/")


def data_dir():
    # set before anything imports lab.paths, which reads it once
    d = os.environ.setdefault("LAB_DATA_DIR", os.path.join(os.getcwd(), "listen-data"))
    os.makedirs(d, exist_ok=True)
    return d


def ensure_data():
    """Fetch whatever of FILES is missing. Loud on failure: a service without
    its indexes cannot name anything."""
    d = data_dir()
    missing = [f for f in FILES if not os.path.exists(os.path.join(d, f))]
    if not missing:
        return
    from recording import get_s3_bucket, get_s3_client

    s3, bucket = get_s3_client(), get_s3_bucket()
    for f in missing:
        dest = os.path.join(d, f)
        if os.path.exists(dest):          # another process fetched it meanwhile
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print(f"listen: fetching s3://{bucket}/{PREFIX}{f}", flush=True)
        # a temporary name per process: two uvicorn workers once fetched into
        # the same .part, and the second's rename found it gone and failed the
        # deploy (2026-10-06)
        part = f"{dest}.{os.getpid()}.part"
        s3.download_file(bucket, PREFIX + f, part)
        os.replace(part, dest)


def upload():
    import lab.env  # noqa: F401  (loads lab/.env: the AWS credentials)
    from lab import paths
    from recording import get_s3_bucket, get_s3_client

    s3, bucket = get_s3_client(), get_s3_bucket()
    for f in FILES:
        src = paths.data(f)
        print(f"{src} -> s3://{bucket}/{PREFIX}{f} ({os.path.getsize(src) / 1e6:.1f} MB)", flush=True)
        s3.upload_file(src, bucket, PREFIX + f)


if __name__ == "__main__":
    if sys.argv[1:] == ["upload"]:
        upload()
    else:
        print(__doc__)

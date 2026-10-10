"""The phone's decider file, kept current (spec 053, "Listening on the phone,
offline").

A phone listening for itself decides from a 16 MB file (lab/corpus/decider_file.py):
thesession.org's whole corpus as the matcher reads it, the popular tunes and
each tune's length once round. The corpus grows every week, so the file is
rebuilt from each Sunday dump and published here, and the app fetches a newer
one when it has a connection (GET /api/listen/decider-data). The session's own
tunes are not in it: the app fetches them for the night, as the listening
service does (GET /api/session-instances/<id>/known-tunes).

In the recordings bucket, per file format (the phone says which it reads):

    listen-data/decider/v<format>/<sha256>.bin   each file, by its content
    listen-data/decider/v<format>/manifest.json  the current one

The manifest is written last, so it never names a file not yet there:

    {"format", "sha256", "bytes", "built_at", "key", "inputs_sha256",
     "checked_at", "source": {...}}

`inputs_sha256` is the hash of what the file is built from (the dump, the
popular tunes, the excluded settings, the configuration, the builder), so an
unchanged week is noticed before building and only `checked_at` moves. Old
files are left where they are: a phone mid-download keeps a working link, and
they cost cents.

The rebuild rides along on the active-sessions cron (jobs/publish_decider_data.py)
like the merge sync: a few minutes and about 200 MB, and no database.
"""

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

PREFIX = os.environ.get("DECIDER_DATA_PREFIX", "listen-data/decider/")
DUMP_TUNES_URL = (
    "https://raw.githubusercontent.com/adactio/TheSession-data/main/csv/tunes.csv"
)
DUMP_POPULARITY_URL = "https://raw.githubusercontent.com/adactio/TheSession-data/main/csv/tune_popularity.csv"
MIN_TUNES = 10000  # fewer in a fresh dump means a bad download: publish nothing
URL_EXPIRY_S = 3600


def _s3():
    from recording import get_s3_bucket, get_s3_client

    return get_s3_client(), get_s3_bucket()


def manifest_key(fmt):
    return f"{PREFIX}v{int(fmt)}/manifest.json"


def current_manifest(fmt):
    """The published manifest for a format, or None if there is none. The app's
    credentials may read objects but not list the bucket, and without that S3
    answers a missing object with AccessDenied rather than NoSuchKey; either
    means none yet (a real lack of access shows when publishing writes)."""
    s3, bucket = _s3()
    try:
        body = s3.get_object(Bucket=bucket, Key=manifest_key(fmt))["Body"].read()
    except Exception as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "AccessDenied", "403"):
            return None
        raise
    return json.loads(body)


def _put_manifest(manifest):
    s3, bucket = _s3()
    s3.put_object(
        Bucket=bucket,
        Key=manifest_key(manifest["format"]),
        ContentType="application/json",
        Body=json.dumps(manifest, indent=1).encode(),
    )


def publish(path, meta):
    """Upload a built file and make it the current one. -> the manifest."""
    fmt, sha = meta["version"], meta["file"]["sha256"]
    key = f"{PREFIX}v{fmt}/{sha}.bin"
    s3, bucket = _s3()
    s3.upload_file(
        path, bucket, key, ExtraArgs={"ContentType": "application/octet-stream"}
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "format": fmt,
        "sha256": sha,
        "bytes": meta["file"]["bytes"],
        "built_at": meta["built_at"],
        "key": key,
        "inputs_sha256": meta["inputs_sha256"],
        "checked_at": now,
        "source": {
            **meta["source"],
            "n_tunes": meta["n_tunes"],
            "popular_n_tunes": meta["popular_n_tunes"],
        },
    }
    _put_manifest(manifest)
    _cache.clear()
    return manifest


# -- the weekly rebuild --------------------------------------------------------


def _week_start(now):
    """The most recent Monday 07:00 UTC at or before `now`: an hour after the
    merge sync's window, the Sunday dump well in."""
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=7, minute=0, second=0, microsecond=0
    )
    return monday if monday <= now else monday - timedelta(days=7)


def is_due(manifest, now=None):
    """Not yet checked since this week's Monday 07:00 UTC. A missed Monday is
    caught up at the next run rather than skipped."""
    now = now or datetime.now(timezone.utc)
    if manifest is None:
        return True
    checked = datetime.strptime(
        manifest.get("checked_at") or "1970-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    return checked < _week_start(now)


def _download(url, dest):
    import requests

    with requests.get(
        url,
        stream=True,
        timeout=120,
        headers={"User-Agent": "ceol.io decider rebuild (https://ceol.io)"},
    ) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)


def rebuild_and_publish(csv_path=None, popularity_path=None, force=False):
    """Fetch the dump and the popular tunes (unless given them), rebuild if
    anything the file is built from has changed, publish.
    -> ("published" | "unchanged", manifest)."""
    from lab.corpus import decider_file as D

    fmt = D.FORMAT_VERSION
    with tempfile.TemporaryDirectory() as tmp:
        if csv_path is None:
            csv_path = os.path.join(tmp, "tunes.csv")
            _download(DUMP_TUNES_URL, csv_path)
        if popularity_path is None:
            popularity_path = os.path.join(tmp, "tune_popularity.csv")
            _download(DUMP_POPULARITY_URL, popularity_path)
        digest = D.inputs_digest(
            D.file_sha256(csv_path), D.popular_tunes(popularity_path)
        )
        manifest = current_manifest(fmt)
        if manifest and manifest.get("inputs_sha256") == digest and not force:
            manifest["checked_at"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            _put_manifest(manifest)
            return "unchanged", manifest
        out = os.path.join(tmp, f"decider-v{fmt}.bin")
        t0 = time.time()
        meta = D.build(csv_path, popularity_path, out)
        if meta["n_tunes"] < MIN_TUNES:
            raise RuntimeError(
                f"the dump has {meta['n_tunes']} tunes (< {MIN_TUNES}); not publishing it"
            )
        manifest = publish(out, meta)
        logger.info(
            f"decider data published: {manifest['key']}, {manifest['bytes'] / 1e6:.1f} MB, "
            f"{meta['n_tunes']} tunes, popular {meta['popular_n_tunes']}, "
            f"built in {time.time() - t0:.0f}s"
        )
        return "published", manifest


# -- for the app ---------------------------------------------------------------

_cache = {}  # format -> (fetched at, manifest or None)
CACHE_S = 600


def offer(fmt):
    """What GET /api/listen/decider-data answers: the current file for a format
    and a short-lived link to it, or `available: false`."""
    hit = _cache.get(fmt)
    if hit is None or time.time() - hit[0] > CACHE_S:
        hit = (time.time(), current_manifest(fmt))
        _cache[fmt] = hit
    m = hit[1]
    if not m:
        return {"format": fmt, "available": False}
    s3, bucket = _s3()
    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": m["key"]}, ExpiresIn=URL_EXPIRY_S
    )
    return {
        "format": fmt,
        "available": True,
        "sha256": m["sha256"],
        "bytes": m["bytes"],
        "built_at": m["built_at"],
        "url": url,
        "expires_in": URL_EXPIRY_S,
    }

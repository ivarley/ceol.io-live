"""The phone's decider file, kept current (spec 053, "Listening on the phone,
offline").

A phone listening for itself decides from a 16 MB file (lab/corpus/decider_file.py):
thesession.org's whole corpus as the matcher reads it, and the session's
repertoire. The corpus grows every week, so the file is rebuilt from each Sunday
dump and published here, and the app fetches a newer one when it has a
connection (GET /api/listen/decider-data).

In the recordings bucket, per file format (the phone says which it reads):

    listen-data/decider/v<format>/<sha256>.bin   each file, by its content
    listen-data/decider/v<format>/manifest.json  the current one

The manifest is written last, so it never names a file not yet there:

    {"format", "sha256", "bytes", "built_at", "key", "inputs_sha256",
     "checked_at", "source": {...}}

`inputs_sha256` is the hash of what the file is built from (the dump, the
repertoire, the configuration, the builder), so an unchanged week is noticed
before building and only `checked_at` moves. Old files are left where they are:
a phone mid-download keeps a working link, and they cost cents.

The rebuild rides along on the active-sessions cron (jobs/publish_decider_data.py)
like the merge sync: it needs only the standard library, about 150 MB and a
minute or so.
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
MIN_TUNES = 10000  # fewer in a fresh dump means a bad download: publish nothing
URL_EXPIRY_S = 3600

# The default session's tunes: those of every session with a segmented
# recording, as the lab's repertoire index takes them (lab pull's manifests).
REPERTOIRE_SQL = """
    SELECT DISTINCT st.tune_id
    FROM session_tune st
    WHERE st.session_id IN (
        SELECT si.session_id
        FROM recording r
        JOIN session_instance si ON si.session_instance_id = r.session_instance_id
        WHERE r.status = 'ready'
          AND EXISTS (SELECT 1 FROM recording_tune_segment rts WHERE rts.recording_id = r.recording_id))
"""


def _s3():
    from recording import get_s3_bucket, get_s3_client

    return get_s3_client(), get_s3_bucket()


def manifest_key(fmt):
    return f"{PREFIX}v{int(fmt)}/manifest.json"


def current_manifest(fmt):
    """The published manifest for a format, or None if there is none."""
    s3, bucket = _s3()
    try:
        body = s3.get_object(Bucket=bucket, Key=manifest_key(fmt))["Body"].read()
    except s3.exceptions.NoSuchKey:
        return None
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
            "repertoire_n_tunes": meta["repertoire_n_tunes"],
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


def default_repertoire(conn):
    cur = conn.cursor()
    cur.execute(REPERTOIRE_SQL)
    return sorted(r[0] for r in cur.fetchall())


def _download_dump(dest):
    import requests

    with requests.get(
        DUMP_TUNES_URL,
        stream=True,
        timeout=120,
        headers={"User-Agent": "ceol.io decider rebuild (https://ceol.io)"},
    ) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)


def rebuild_and_publish(conn, csv_path=None, force=False):
    """Fetch the dump (unless given one), rebuild if anything it is built from
    has changed, publish. -> ("published" | "unchanged", manifest)."""
    from lab.corpus import decider_file as D

    fmt = D.FORMAT_VERSION
    with tempfile.TemporaryDirectory() as tmp:
        if csv_path is None:
            csv_path = os.path.join(tmp, "tunes.csv")
            _download_dump(csv_path)
        repertoire = default_repertoire(conn)
        digest = D.inputs_digest(D.file_sha256(csv_path), repertoire)
        manifest = current_manifest(fmt)
        if manifest and manifest.get("inputs_sha256") == digest and not force:
            manifest["checked_at"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            _put_manifest(manifest)
            return "unchanged", manifest
        out = os.path.join(tmp, f"decider-v{fmt}.bin")
        t0 = time.time()
        meta = D.build(csv_path, repertoire, out)
        if meta["n_tunes"] < MIN_TUNES:
            raise RuntimeError(
                f"the dump has {meta['n_tunes']} tunes (< {MIN_TUNES}); not publishing it"
            )
        manifest = publish(out, meta)
        logger.info(
            f"decider data published: {manifest['key']}, {manifest['bytes'] / 1e6:.1f} MB, "
            f"{meta['n_tunes']} tunes, repertoire {meta['repertoire_n_tunes']}, "
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

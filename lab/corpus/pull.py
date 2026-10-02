"""`lab pull` — copy the eval corpus out of production into lab/data.

Read-only against production by construction: the connection is opened with
`default_transaction_read_only=on`, so a bug here cannot write. The
`--database-url` guard is the one from scripts/import_recording.py — an empty
value (an unset shell variable) is an error, never a fallback to local.

Per recording that has at least one placed segment, writes
`recordings/<id>/manifest.json` (the resolved segments, the session's
repertoire, the night's logged order) and downloads the MASTER audio —
`storage_key`, never the 32kbps playback proxy, because a corpus cut from the
proxy's artefacts would be a quiet, expensive mistake (spec 050). Downloads are
resumable and idempotent: an existing file with the right size is skipped.

Also fetches the public thesession.org dump (tunes.csv) unless it is fresh.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import lab.env  # noqa: F401
from lab import paths
from lab.corpus.tunes_csv import dump_age_days

# The export query from recording_routes.export_recording_segments, plus the
# segment's own id and end_ms so we can tell implicit from explicit ends.
SEGMENTS_SQL = """
    SELECT v.recording_tune_segment_id, v.session_instance_tune_id, v.tune_id,
           v.display_name, v.tune_type, v.start_ms, v.resolved_end_ms,
           v.end_is_explicit, v.instance_start_ms, v.absolute_start
    FROM recording_tune_segment_resolved v
    WHERE v.recording_id = %s
    ORDER BY v.start_ms
"""

RECORDINGS_SQL = """
    SELECT r.recording_id, r.session_instance_id, r.label, r.storage_key, r.mime_type,
           r.duration_ms, r.file_size_bytes, r.sample_rate, r.channels, r.started_at,
           r.clock_offset_ms, r.segmenting_complete,
           si.session_id, si.date, s.name AS session_name
    FROM recording r
    JOIN session_instance si ON si.session_instance_id = r.session_instance_id
    JOIN session s ON s.session_id = si.session_id
    WHERE r.status = 'ready'
      AND EXISTS (SELECT 1 FROM recording_tune_segment rts WHERE rts.recording_id = r.recording_id)
    ORDER BY r.recording_id
"""

REPERTOIRE_SQL = """
    SELECT st.tune_id, st.setting_id, st.key, st.alias, t.name, t.tune_type
    FROM session_tune st
    JOIN tune t ON t.tune_id = st.tune_id
    WHERE st.session_id = %s
    ORDER BY st.tune_id
"""

# The night's logged order. GROUND TRUTH ONLY: stored so a later oracle
# experiment can simulate "a human confirmed the previous tune"; never read by
# an expert (spec 053, "logged order is not evidence").
LOGGED_ORDER_SQL = """
    SELECT session_instance_tune_id, tune_id, name, record_type, order_position
    FROM session_instance_tune
    WHERE session_instance_id = %s AND deleted = FALSE
    ORDER BY order_position COLLATE "C"
"""

# Give up on a mirror that is delivering less than this, and try the next one.
STALL_AFTER_S = 20
MIN_BYTES_PER_S = 20_000


def dump_mirrors():
    """Where to get the dump, best-known-authoritative first.

    GitHub's raw host is the canonical source and the one the app's merge scan
    already uses, so it is tried first. It is also rate-limited per client and
    was serving 433 B/s from here, which is why there is a second entry:
    jsDelivr mirrors the same repository file from a CDN. It is a third party,
    so which mirror served the corpus is recorded in tunes.meta.json, and the
    file is checked for a plausible tune count either way.
    """
    from services.tune_merge_scan_service import DUMP_TUNES_URL

    return [
        ("raw.githubusercontent", DUMP_TUNES_URL),
        ("jsdelivr", "https://cdn.jsdelivr.net/gh/adactio/TheSession-data@main/csv/tunes.csv"),
    ]


# Every tune-to-tune transition this session has ever logged, with the night
# it happened on so a model can leave that night out. Not ground truth about
# the night being scored, and not read from the current night at all: it is
# what a live system would already know from every previous evening.
TRANSITIONS_SQL = """
    SELECT si.session_instance_id, si.date::text AS date,
           sit.session_instance_tune_id, sit.tune_id, sit.record_type, sit.order_position
    FROM session_instance_tune sit
    JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
    WHERE si.session_id = %s AND sit.deleted = FALSE
    ORDER BY si.session_instance_id, sit.order_position COLLATE "C"
"""

_EXT_BY_MIME = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/ogg": "ogg",
}


def add_parser(sub):
    p = sub.add_parser("pull", help="copy manifests, master audio and tunes.csv from production (read-only)")
    p.add_argument("--database-url", default=None,
                   help="production DATABASE_URL (default: PROD_DB_URL from lab/.env); read-only transaction enforced")
    p.add_argument("--recordings", help="comma-separated recording ids (default: every recording with segments)")
    p.add_argument("--skip-audio", action="store_true", help="manifests and tunes.csv only")
    p.add_argument("--skip-corpus", action="store_true", help="do not fetch tunes.csv")
    p.add_argument("--refresh-corpus", action="store_true", help="fetch tunes.csv even if it is fresh")
    p.set_defaults(func=main)


def _parse_ids(text):
    if not text:
        return None
    return sorted({int(x) for x in text.replace(" ", "").split(",") if x})


def _connect_readonly(database_url):
    if not database_url.strip():
        raise SystemExit("--database-url is empty (an unset shell variable, or no PROD_DB_URL in lab/.env?). Refusing to fall back to the local database.")
    import psycopg2

    return psycopg2.connect(
        database_url,
        options="-c default_transaction_read_only=on -c timezone=utc",
    )


def _jsonable(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _rows(cur, sql, params=()):
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [{c: _jsonable(v) for c, v in zip(cols, row)} for row in cur.fetchall()]


def write_manifests(conn, wanted_ids):
    cur = conn.cursor()
    recordings = _rows(cur, RECORDINGS_SQL)
    if wanted_ids is not None:
        recordings = [r for r in recordings if r["recording_id"] in wanted_ids]
        missing = set(wanted_ids) - {r["recording_id"] for r in recordings}
        if missing:
            print(f"warning: recordings {sorted(missing)} have no segments (or are not ready); skipped", file=sys.stderr)
    cur.execute("SELECT current_database(), inet_server_addr()::text")
    dbname, host = cur.fetchone()
    repertoire_cache = {}
    history_cache = {}
    manifests = []
    for rec in recordings:
        rid = rec["recording_id"]
        segments = _rows(cur, SEGMENTS_SQL, (rid,))
        for s in segments:
            s["implicit_trailing"] = (not s["end_is_explicit"]) and int(s["resolved_end_ms"]) >= int(rec["duration_ms"])
        sid = rec["session_id"]
        if sid not in repertoire_cache:
            repertoire_cache[sid] = _rows(cur, REPERTOIRE_SQL, (sid,))
        logged = _rows(cur, LOGGED_ORDER_SQL, (rec["session_instance_id"],))
        if sid not in history_cache:
            history_cache[sid] = _rows(cur, TRANSITIONS_SQL, (sid,))
            _write_session_history(sid, history_cache[sid])
        manifest = {
            "manifest_version": 1,
            "pulled_at": datetime.now(timezone.utc).isoformat(),
            "source_db": {"database": dbname, "host": host},
            "recording": rec,
            "segments": segments,
            "repertoire": repertoire_cache[sid],
            "logged_order": logged,
        }
        paths.ensure_dir(paths.recording_dir(rid))
        with open(paths.manifest_path(rid), "w") as f:
            json.dump(manifest, f, indent=1, default=_jsonable)
        n_tunes = sum(1 for s in segments if s["tune_id"] is not None)
        print(f"recording {rid:>4}  {rec['label']:<40} {len(segments):>3} segments ({n_tunes} with tune_id), "
              f"{len(repertoire_cache[sid])} repertoire, {len(logged)} logged")
        manifests.append(manifest)
    return manifests


def _write_session_history(session_id, rows):
    """The session's whole logged order, one file per session."""
    path = paths.ensure_dir(paths.data("sessions", str(session_id)))
    out = os.path.join(path, "logged_order.json")
    with open(out, "w") as f:
        json.dump({"session_id": session_id, "rows": rows,
                   "pulled_at": datetime.now(timezone.utc).isoformat()}, f)
    instances = len({r["session_instance_id"] for r in rows})
    print(f"session   {session_id}  history: {len(rows)} logged records over {instances} nights -> {out}")


def master_path(manifest):
    rec = manifest["recording"]
    ext = _EXT_BY_MIME.get((rec.get("mime_type") or "").lower())
    if not ext:
        ext = os.path.splitext(rec["storage_key"])[1].lstrip(".").lower() or "bin"
    return os.path.join(paths.recording_dir(rec["recording_id"]), f"master.{ext}")


def download_masters(manifests):
    import recording as rec_mod  # app module: S3 client + bucket from env

    problem = rec_mod.check_configured()
    if problem:
        raise SystemExit(f"cannot download audio: {problem}")
    s3 = rec_mod.get_s3_client()
    bucket = rec_mod.get_s3_bucket()
    for manifest in manifests:
        rec = manifest["recording"]
        key = rec["storage_key"]
        dest = master_path(manifest)
        head = s3.head_object(Bucket=bucket, Key=key)
        size = int(head["ContentLength"])
        if os.path.exists(dest) and os.path.getsize(dest) == size:
            print(f"recording {rec['recording_id']:>4}  master present ({size / 1e6:.0f} MB), skipped")
            continue
        part = dest + ".part"
        print(f"recording {rec['recording_id']:>4}  downloading {key} ({size / 1e6:.0f} MB) ...", flush=True)
        with open(part, "wb") as f:
            s3.download_fileobj(bucket, key, f)
        if os.path.getsize(part) != size:
            raise RuntimeError(f"short download for recording {rec['recording_id']}: {os.path.getsize(part)} != {size}")
        os.replace(part, dest)
        print(f"recording {rec['recording_id']:>4}  -> {dest}")


def download_meter_logs(manifests):
    """The listening meter's log beside each recording, where the phone made one.

    The native recorder (spec 053) uploads what the meter showed while it recorded,
    and every tap, to recordings/<uuid>/listen-states.jsonl beside the audio
    (recording.listen_log_key). Most recordings have none: they were not made by
    the phone. Small, so fetched every time.
    """
    import recording as rec_mod

    if rec_mod.check_configured():
        return
    s3 = rec_mod.get_s3_client()
    bucket = rec_mod.get_s3_bucket()
    for manifest in manifests:
        rec = manifest["recording"]
        dest = os.path.join(paths.recording_dir(rec["recording_id"]), "listen-states.jsonl")
        try:
            obj = s3.get_object(Bucket=bucket, Key=rec_mod.listen_log_key(rec["storage_key"]))
        except Exception:  # none for this recording
            continue
        body = obj["Body"].read()
        with open(dest, "wb") as f:
            f.write(body)
        lines = body.count(b"\n")
        print(f"recording {rec['recording_id']:>4}  meter log, {lines} lines -> {dest}")


def fetch_tunes_csv(force=False, attempts=4):
    """Download the public dump, whole or not at all.

    The app's `_open_dump` retries establishing the response; it does not retry
    the body, and a 17MB stream off raw.githubusercontent breaks mid-read often
    enough to matter (it did on the first run here: IncompleteRead with 5MB
    outstanding). So the whole download is the unit that gets retried, the
    result is checked against Content-Length and against a floor on the number
    of tunes, and only then does it become `tunes.csv`. A truncated corpus that
    looks like a corpus would silently shrink every index built from it.
    """
    import time

    from services.tune_merge_scan_service import DUMP_TUNES_URL, MIN_DUMP_TUNES, _open_dump

    dest = paths.tunes_csv_path()
    age = dump_age_days(dest)
    if age is not None and age < 7 and not force:
        print(f"tunes.csv is {age:.1f} days old, kept (--refresh-corpus to refetch)")
        return dest
    paths.ensure_dir(paths.corpus_dir())

    class _NoThrottle:
        def wait(self):
            pass

    part = dest + ".part"
    last_error = None
    for attempt in range(1, attempts + 1):
        for mirror, url in dump_mirrors():
            print(f"fetching {url} (attempt {attempt}/{attempts}, {mirror}) ...", flush=True)
            try:
                resp = _open_dump(url, _NoThrottle())
                expected = resp.headers.get("Content-Length")
                expected = int(expected) if expected and expected.isdigit() else None
                n = 0
                started = time.time()
                with open(part, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
                        n += len(chunk)
                        # raw.githubusercontent throttled this to 433 B/s once,
                        # which is two hours for 17MB and no error to notice.
                        # Slow is a failure mode, so give up and try the mirror.
                        elapsed = time.time() - started
                        if elapsed > STALL_AFTER_S and n / elapsed < MIN_BYTES_PER_S:
                            raise RuntimeError(
                                f"too slow: {n / elapsed:.0f} B/s after {elapsed:.0f}s")
                if expected is not None and n != expected:
                    raise RuntimeError(f"short download: {n} of {expected} bytes")
                n_tunes = _count_dump_tunes(part)
                if n_tunes < MIN_DUMP_TUNES:
                    raise RuntimeError(f"dump looks truncated ({n_tunes} tunes < {MIN_DUMP_TUNES})")
            except Exception as e:  # network, throttling, truncation, or not a dump
                last_error = e
                print(f"  {mirror} failed: {e}", file=sys.stderr)
                continue
            os.replace(part, dest)
            with open(os.path.join(paths.corpus_dir(), "tunes.meta.json"), "w") as f:
                json.dump(
                    {"url": url, "mirror": mirror, "canonical_url": DUMP_TUNES_URL,
                     "fetched_at": datetime.now(timezone.utc).isoformat(),
                     "bytes": n, "tunes": n_tunes},
                    f, indent=1,
                )
            print(f"tunes.csv -> {dest} ({n / 1e6:.1f} MB, {n_tunes} tunes, from {mirror})")
            return dest
        if attempt < attempts:
            time.sleep(2 ** attempt)
    if os.path.exists(part):
        os.remove(part)
    raise SystemExit(f"could not fetch the tunes dump after {attempts} attempts: {last_error}")


def _count_dump_tunes(path):
    """Distinct tune ids in a downloaded dump, for the truncation check."""
    from lab.corpus.tunes_csv import iter_settings

    return len({s.tune_id for s in iter_settings(path)})


def main(args):
    wanted = _parse_ids(args.recordings)
    # Not lab.env.prod_database_url(): that falls back to DATABASE_URL, which the
    # repo's .env points at the LOCAL database.
    url = args.database_url
    if url is None:
        url = os.environ.get("PROD_DB_URL") or os.environ.get("PROD_DATABASE_URL") or ""
    conn = _connect_readonly(url)
    try:
        manifests = write_manifests(conn, wanted)
    finally:
        conn.close()
    if not args.skip_corpus:
        fetch_tunes_csv(force=args.refresh_corpus)
    if not args.skip_audio:
        download_masters(manifests)
    download_meter_logs(manifests)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))

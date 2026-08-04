#!/usr/bin/env python
"""Ingest one session audio file so it can be segmented (spec 050).

Probes the file, computes its waveform envelope, uploads it to S3, and writes
the `recording` row that /admin/recordings/<id>/segment then works against.

    venv/bin/python scripts/import_recording.py AUDIO_FILE --session-instance 347 \
        --label "B.D. Riley's 2026-01-15" --started-at 2026-01-15T19:30:00-06:00

Target database comes from the usual PG* environment variables (loaded from
.env, same as the app), or from --database-url. Either way it is stated
explicitly rather than defaulted, since this writes.

Re-running for a file already uploaded is safe: pass --recording-id to refresh
an existing row's peaks/duration in place instead of creating a second one.
"""

import argparse
import base64
import datetime
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_dotenv(path):
    """Minimal .env loader (the app relies on python-dotenv at runtime; this
    script runs standalone, and existing env vars always win)."""
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def human_ms(ms):
    seconds, ms = divmod(int(ms), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio_file", help="Path to the audio file (anything ffmpeg reads)")
    parser.add_argument("--session-instance", type=int, required=True, help="session_instance_id this recording covers")
    parser.add_argument("--label", help="Human label; defaults to the filename")
    parser.add_argument("--person", type=int, help="person_id of whoever made the recording (optional)")
    parser.add_argument(
        "--started-at",
        help="ISO-8601 wall-clock time of t=0 in the file, e.g. 2026-01-15T19:30:00-06:00. "
             "Optional -- only needed to line audio up against logged timestamps.",
    )
    parser.add_argument(
        "--offset-ms", type=int, default=0,
        help="Milliseconds between the instance's zero point (the anchor recording's t=0) and this file's t=0. "
             "Leave at 0 for the first/only recording.",
    )
    parser.add_argument(
        "--anchor", action="store_true",
        help="Mark this recording as the instance's clock anchor. Implied when the instance has no anchor yet.",
    )
    parser.add_argument("--recording-id", type=int, help="Update this existing recording instead of creating one")
    parser.add_argument(
        "--storage-key",
        help="Point the new row at an S3 object that is already uploaded, instead of minting a key. "
             "Pair with --skip-upload to register the same audio in another environment without re-uploading it.",
    )
    parser.add_argument("--skip-upload", action="store_true", help="Recompute peaks/metadata only; leave S3 alone")
    parser.add_argument(
        "--database-url",
        help="Target database as a postgres:// URL (Render's External Database URL). "
             "Overrides the PG* environment variables.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Probe and compute peaks, write nothing")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))

    import recording as rec
    from database import get_db_connection

    if not os.path.exists(args.audio_file):
        parser.error(f"No such file: {args.audio_file}")

    print(f"Probing {args.audio_file} ...")
    info = rec.probe_audio(args.audio_file)
    size = os.path.getsize(args.audio_file)
    print(f"  duration   {human_ms(info['duration_ms'])}")
    print(f"  audio      {info['sample_rate']} Hz, {info['channels']} ch, {size / 1e6:.1f} MB")

    print("Computing waveform envelope ...")
    peaks, peaks_hz = rec.compute_peaks(args.audio_file)
    print(f"  {len(peaks):,} buckets at {peaks_hz} Hz ({len(peaks) / 1024:.0f} KiB)")

    started_at = None
    if args.started_at:
        started_at = datetime.datetime.fromisoformat(args.started_at)
        if started_at.tzinfo is None:
            parser.error("--started-at needs a UTC offset (e.g. ...T19:30:00-06:00), otherwise the anchor is ambiguous")

    label = args.label or os.path.basename(args.audio_file)
    mime = {
        ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".aac": "audio/aac",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
        ".opus": "audio/ogg", ".flac": "audio/flac", ".webm": "audio/webm",
    }.get(os.path.splitext(args.audio_file)[1].lower(), "audio/mpeg")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    if args.database_url is not None:
        # `--database-url "$PROD_URL"` with PROD_URL unset arrives as an empty
        # string. Falling back to the local database there is the worst possible
        # behaviour -- it silently writes to dev while the operator believes they
        # are writing to production -- so an empty value is an error, not a
        # default. (This happened.)
        if not args.database_url.strip():
            parser.error("--database-url is empty (an unset shell variable?). Refusing to fall back to the local database.")
        import psycopg2

        conn = psycopg2.connect(args.database_url, options="-c timezone=utc")
    else:
        conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Say where this is going before it writes anything. The only clue last
        # time was the session's name looking subtly wrong.
        cur.execute("SELECT current_database(), inet_server_addr()::text")
        db_name, db_host = cur.fetchone()
        print(f"Target database: {db_name} on {db_host or 'local socket'}")

        cur.execute(
            "SELECT si.date, s.name FROM session_instance si "
            "JOIN session s ON s.session_id = si.session_id WHERE si.session_instance_id = %s",
            (args.session_instance,),
        )
        row = cur.fetchone()
        if not row:
            print(f"ERROR: no session_instance {args.session_instance}", file=sys.stderr)
            return 1
        print(f"\nSession instance {args.session_instance}: {row[1]} on {row[0]}")

        # First recording on an instance becomes the anchor whether or not it was
        # asked for -- an instance timeline with no zero point is meaningless, and
        # the partial unique index makes a second silent anchor impossible anyway.
        cur.execute(
            "SELECT recording_id FROM recording WHERE session_instance_id = %s AND is_clock_anchor",
            (args.session_instance,),
        )
        existing_anchor = cur.fetchone()
        is_anchor = args.anchor or existing_anchor is None
        if is_anchor and existing_anchor and existing_anchor[0] != args.recording_id:
            print(
                f"ERROR: recording {existing_anchor[0]} is already the clock anchor for this instance. "
                "Clear its is_clock_anchor first, or drop --anchor and pass --offset-ms.",
                file=sys.stderr,
            )
            return 1

        peaks_b64 = base64.b64encode(peaks).decode("ascii")

        if args.recording_id:
            cur.execute("SELECT storage_key FROM recording WHERE recording_id = %s", (args.recording_id,))
            found = cur.fetchone()
            if not found:
                print(f"ERROR: no recording {args.recording_id}", file=sys.stderr)
                return 1
            storage_key = found[0]
        elif args.storage_key:
            storage_key = args.storage_key
        else:
            # A uuid segment keeps two same-named files from colliding, and keeps
            # the key from leaking anything about who recorded what.
            storage_key = f"recordings/{uuid.uuid4().hex}/{os.path.basename(args.audio_file)}"

        if not args.skip_upload:
            print(f"Uploading to s3://{rec.get_s3_bucket()}/{storage_key} ...")
            rec.upload_recording(args.audio_file, storage_key, mime_type=mime)
            print("  done")

        if args.recording_id:
            from database import save_to_history

            save_to_history(cur, "recording", "UPDATE", args.recording_id)
            cur.execute(
                """
                UPDATE recording
                   SET label = %s, person_id = COALESCE(%s, person_id), mime_type = %s, duration_ms = %s, file_size_bytes = %s,
                       sample_rate = %s, channels = %s, is_clock_anchor = %s, clock_offset_ms = %s,
                       started_at = COALESCE(%s, started_at), peaks = %s, peaks_hz = %s
                 WHERE recording_id = %s
                """,
                (label, args.person, mime, info["duration_ms"], size, info["sample_rate"], info["channels"],
                 is_anchor, args.offset_ms, started_at, peaks_b64, peaks_hz, args.recording_id),
            )
            recording_id = args.recording_id
            verb = "Updated"
        else:
            cur.execute(
                """
                INSERT INTO recording
                    (session_instance_id, person_id, label, storage_key, mime_type, duration_ms, file_size_bytes,
                     sample_rate, channels, is_clock_anchor, clock_offset_ms, started_at, peaks, peaks_hz)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING recording_id
                """,
                (args.session_instance, args.person, label, storage_key, mime, info["duration_ms"], size,
                 info["sample_rate"], info["channels"], is_anchor, args.offset_ms, started_at,
                 peaks_b64, peaks_hz),
            )
            recording_id = cur.fetchone()[0]
            verb = "Created"

        conn.commit()
        print(f"\n{verb} recording {recording_id}"
              f"{' (clock anchor)' if is_anchor else f' (offset {human_ms(args.offset_ms)})'}")
        print(f"Segment it at: /admin/recordings/{recording_id}/segment")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

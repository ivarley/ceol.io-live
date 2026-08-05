#!/usr/bin/env python
"""Regenerate schema/seed_recording.sql -- the segmenter's local fixture (spec 050).

The seed pins ONE real night with ONE real recording so that after
`make reset-test-db` (or the reseed pytest runs on every exit) the segmenter
still has something honest to open: B.D. Riley's 2025-03-27, its 83-tune log,
and the waveform of the actual audio.

It is generated, not hand-written, because the log is real production data and
hand-copying 117 rows is how fixtures drift from the thing they claim to mirror.

    venv/bin/python scripts/generate_recording_seed.py \
        --peaks-json <peaks.json> --storage-key recordings/<uuid>/<file>

Refresh the peaks first if the audio changed:

    venv/bin/python scripts/generate_recording_seed.py \
        --emit-peaks-json /path/to/audio.mp3 --peaks-json <peaks.json>

Both inputs are files, so refreshing the fixture never needs production
credentials: --log-json is an export of the night's log (the query is in the
source below), and --peaks-json comes from the audio via --emit-peaks-json.
"""

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The night the fixture mirrors, and the ids it occupies locally. Chosen well
# clear of the seed's own id space (max session_instance_id is ~107).
PROD_INSTANCE_ID = 449
LOCAL_INSTANCE_ID = 449
LOCAL_RECORDING_ID = 1
SIT_ID_BASE = 44900
LOCAL_SESSION_ID = 1  # austin/mueller, seeded


def q(value):
    """SQL literal for a string/None."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def emit_peaks_json(audio_path, out_path):
    """Probe + compute peaks for `audio_path` and write the JSON the seed needs."""
    import recording as rec

    info = rec.probe_audio(audio_path)
    peaks, hz = rec.compute_peaks(audio_path)
    payload = {
        "duration_ms": info["duration_ms"],
        "sample_rate": info["sample_rate"],
        "channels": info["channels"],
        "file_size_bytes": os.path.getsize(audio_path),
        "peaks_hz": hz,
        "peaks_b64": base64.b64encode(peaks).decode("ascii"),
    }
    with open(out_path, "w") as fh:
        json.dump(payload, fh)
    print(f"wrote {out_path}: {len(peaks):,} buckets at {hz}Hz")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--peaks-json", required=True, help="Peaks/metadata JSON (see --emit-peaks-json)")
    parser.add_argument("--emit-peaks-json", metavar="AUDIO", help="Compute the peaks JSON from AUDIO and exit")
    parser.add_argument(
        "--log-json", default="schema/seed_recording_log.json",
        help="The night's log, exported from production and checked in beside the seed. Rows are "
             "[order_position, record_type, tune_id, name, tune_name, tune_type, session_alias].",
    )
    parser.add_argument("--storage-key", help="S3 key the seeded recording points at")
    parser.add_argument(
        "--stream-key",
        help="S3 key of the playback proxy (spec 051). Without it the fixture has a single "
             "encode and the segmenter's quality control has nothing to switch between.",
    )
    parser.add_argument("--stream-size-bytes", type=int, help="Size of the proxy, for the quality control's label")
    parser.add_argument("--label", default="B.D. Riley's 2025-03-27")
    parser.add_argument("--out", default="schema/seed_recording.sql")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.emit_peaks_json:
        emit_peaks_json(args.emit_peaks_json, args.peaks_json)
        return 0

    with open(args.peaks_json) as fh:
        audio = json.load(fh)

    # The log comes from a JSON export rather than a live production connection:
    # regenerating a dev fixture should never require production credentials.
    # Export it with:
    #   SELECT json_agg(json_build_array(sit.order_position, sit.record_type, sit.tune_id,
    #                                    sit.name, t.name, t.tune_type, st.alias)
    #                   ORDER BY sit.order_position)
    #   FROM session_instance_tune sit
    #   LEFT JOIN tune t ON t.tune_id = sit.tune_id
    #   LEFT JOIN session_tune st ON st.tune_id = sit.tune_id AND st.session_id = 1
    #   WHERE sit.session_instance_id = 449 AND sit.deleted = FALSE;
    log_path = args.log_json if os.path.isabs(args.log_json) else os.path.join(project_root, args.log_json)
    with open(log_path) as fh:
        log = json.load(fh)
    rows = log["rows"]
    instance_date = log["date"]
    if not rows:
        print(f"ERROR: log export for instance {PROD_INSTANCE_ID} is empty", file=sys.stderr)
        return 1

    tunes = {}       # tune_id -> (name, tune_type)
    aliases = {}     # tune_id -> session alias
    for _, _, tune_id, _, tune_name, tune_type, alias in rows:
        if tune_id:
            tunes[tune_id] = (tune_name, tune_type)
            if alias:
                aliases[tune_id] = alias

    out = []
    w = out.append
    w("-- =============================================================================")
    w("-- Segmenter fixture: one real night with one real recording (spec 050)")
    w("-- =============================================================================")
    w("-- GENERATED by scripts/generate_recording_seed.py -- do not hand-edit.")
    w("--")
    w(f"-- B.D. Riley's (austin/mueller) on {instance_date}: the production log for that")
    w(f"-- night ({sum(1 for r in rows if r[1] == 'tune')} tunes across")
    w(f"-- {sum(1 for r in rows if r[1] == 'break')} set breaks) plus the recording of it.")
    w("--")
    w("-- Applied by scripts/setup_local_db.sh after seed_data.sql, so the segmenter")
    w("-- survives the reseed that pytest runs on every exit. Without this the page")
    w("-- 302s to the index the moment anyone runs the test suite.")
    w("--")
    w("-- The waveform is inlined (base64, ~290KB) rather than recomputed at seed time:")
    w("-- seeding must not depend on having the audio file or ffmpeg on hand. The audio")
    w("-- itself lives in S3, so playback needs AWS credentials -- but the waveform, the")
    w("-- log, and every marking interaction work without them.")
    w("-- =============================================================================")
    w("")
    w("BEGIN;")
    w("")
    w("-- Idempotent: drop the fixture before rebuilding it.")
    w(f"DELETE FROM recording WHERE recording_id = {LOCAL_RECORDING_ID};")
    w(f"DELETE FROM session_instance_tune WHERE session_instance_id = {LOCAL_INSTANCE_ID};")
    w(f"DELETE FROM session_instance WHERE session_instance_id = {LOCAL_INSTANCE_ID};")
    w("")

    w("-- Tunes referenced by the log that the main seed doesn't already carry.")
    w("--")
    w("-- DO NOTHING, not DO UPDATE: about a dozen of these ids already exist in")
    w("-- seed_data.sql under an older naming convention ('Banshee, The' where")
    w("-- production says 'The Banshee'), and several of those names are asserted on")
    w("-- by existing tests. A cosmetic mismatch in a dev fixture is much cheaper than")
    w("-- rewriting shared seed rows out from under those tests.")
    w("INSERT INTO tune (tune_id, name, tune_type) VALUES")
    vals = [f"    ({tid}, {q(nm)}, {q(ty)})" for tid, (nm, ty) in sorted(tunes.items())]
    w(",\n".join(vals))
    w("ON CONFLICT (tune_id) DO NOTHING;")
    w("")

    w("-- The session already knows this tune by a different name.")
    for tid, alias in sorted(aliases.items()):
        w(f"INSERT INTO session_tune (session_id, tune_id, alias) VALUES ({LOCAL_SESSION_ID}, {tid}, {q(alias)})")
        w("ON CONFLICT (session_id, tune_id) DO UPDATE SET alias = EXCLUDED.alias;")
    w("")

    w("INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time)")
    w(f"VALUES ({LOCAL_INSTANCE_ID}, {LOCAL_SESSION_ID}, DATE '{instance_date}', TIME '19:00', TIME '22:30');")
    w("")

    w("-- The log, in order. Break rows are the set boundaries the segmenter groups on.")
    w("INSERT INTO session_instance_tune")
    w("    (session_instance_tune_id, session_instance_id, tune_id, name, order_position, record_type) VALUES")
    log_vals = []
    for i, (op, rt, tune_id, name, _, _, _) in enumerate(rows):
        log_vals.append(
            f"    ({SIT_ID_BASE + i}, {LOCAL_INSTANCE_ID}, "
            f"{tune_id if tune_id else 'NULL'}, {q(name)}, {q(op)}, {q(rt)})"
        )
    w(",\n".join(log_vals) + ";")
    w("")

    w("-- The recording. peaks is the RMS envelope of the real audio (see recording.py).")
    w("INSERT INTO recording (recording_id, session_instance_id, label, storage_key, mime_type,")
    w("                       duration_ms, file_size_bytes, sample_rate, channels,")
    w("                       is_clock_anchor, clock_offset_ms, peaks, peaks_hz,")
    w("                       stream_key, stream_mime_type, stream_size_bytes) VALUES")
    w(f"    ({LOCAL_RECORDING_ID}, {LOCAL_INSTANCE_ID}, {q(args.label)}, {q(args.storage_key)}, 'audio/mpeg',")
    w(f"     {audio['duration_ms']}, {audio['file_size_bytes']}, {audio['sample_rate']}, {audio['channels']},")
    w(f"     TRUE, 0, {q(audio['peaks_b64'])}, {audio['peaks_hz']},")
    stream_mime = q("audio/mp4") if args.stream_key else "NULL"
    stream_size = args.stream_size_bytes if args.stream_size_bytes else "NULL"
    w(f"     {q(args.stream_key)}, {stream_mime}, {stream_size});")
    w("")

    w("-- Explicit ids above leave the sequences behind; setup_local_db.sh resyncs them")
    w("-- globally after seeding, but this file is also runnable on its own.")
    w("SELECT setval('session_instance_session_instance_id_seq', (SELECT MAX(session_instance_id) FROM session_instance));")
    w("SELECT setval('session_instance_tune_session_instance_tune_id_seq', (SELECT MAX(session_instance_tune_id) FROM session_instance_tune));")
    w("SELECT setval('recording_recording_id_seq', (SELECT MAX(recording_id) FROM recording));")
    w("")
    w("COMMIT;")
    w("")

    out_path = os.path.join(project_root, args.out)
    with open(out_path, "w") as fh:
        fh.write("\n".join(out))

    print(f"wrote {out_path}")
    print(f"  {len(rows)} log rows, {len(tunes)} distinct tunes, {len(aliases)} session aliases")
    print(f"  {os.path.getsize(out_path) / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

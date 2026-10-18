"""Cut the /samples clips from their session recordings and store them in S3.

    python scripts/make_listen_samples.py

Run it where the recordings are: the Render shell of the `ceol` service. For each
entry in recording.LISTEN_SAMPLES it reads the segmenter mark (segment_id), cuts that
stretch out of the night's recording without re-encoding, and uploads it to
samples/<slug>.mp3, replacing any earlier clip. Run it again after changing the list.
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from database import get_db_connection  # noqa: E402
from recording import (  # noqa: E402
    LISTEN_SAMPLES,
    check_configured,
    generate_presigned_url,
    sample_storage_key,
    slice_segment,
    upload_recording,
)


def main():
    problem = check_configured()
    if problem:
        sys.exit(problem)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for sample in LISTEN_SAMPLES:
            cur.execute(
                """
                SELECT storage_key, start_ms, resolved_end_ms, display_name
                FROM recording_tune_segment_resolved
                WHERE recording_tune_segment_id = %s
                """,
                (sample["segment_id"],),
            )
            row = cur.fetchone()
            if not row:
                sys.exit(f"No segment {sample['segment_id']} for {sample['name']}.")
            storage_key, start_ms, end_ms, display_name = row
            if not storage_key.lower().endswith(".mp3"):
                sys.exit(
                    f"{sample['name']}: the recording isn't an MP3 ({storage_key})."
                )
            with tempfile.TemporaryDirectory() as tmp:
                clip = os.path.join(tmp, f"{sample['slug']}.mp3")
                slice_segment(
                    generate_presigned_url(storage_key), start_ms, end_ms, clip
                )
                upload_recording(clip, sample_storage_key(sample["slug"]), "audio/mpeg")
                print(
                    f"{sample['name']} (marked as {display_name}): "
                    f"{(end_ms - start_ms) / 1000:.0f}s, {os.path.getsize(clip) // 1024} KB "
                    f"-> {sample_storage_key(sample['slug'])}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

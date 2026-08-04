"""Session audio recordings: object storage and waveform extraction.

Two jobs, both in service of the segmenter (spec 050):

  * **Storage.** A recording is one whole audio file in S3, played back through
    a presigned URL. S3 honours range requests, so the browser can seek and
    scrub a three-hour file without downloading it — which is the only reason
    this works on a phone.

  * **Peaks.** The waveform the operator reads is precomputed here, not in the
    browser. Decoding three hours of AAC client-side to draw a waveform is a
    non-starter on mobile; a ~236KB envelope is not.

The envelope is **RMS**, not peak amplitude, on purpose. The whole task is
telling sustained music from the talk between tunes, and a room full of chatter
throws tall isolated spikes that a max-abs envelope renders as a solid block —
exactly the distinction being looked for, erased. RMS keeps the tune blocks
visibly darker than the gaps.
"""

import os
import subprocess

import boto3

# Envelope resolution. 20 buckets/sec = one sample per 50ms: fine enough to
# place a tune boundary by eye, coarse enough that a 3h file is ~236KB.
PEAKS_HZ = 20

# ffmpeg decodes to this rate before bucketing. The envelope only needs gross
# amplitude, so 4kHz mono is plenty and keeps the pipe ~24x smaller than 48k.
_DECODE_RATE = 4000

# The envelope is mapped to a dB window fitted to THIS recording's own quiet and
# loud ends, rather than a fixed range. A pub has a loud noise floor -- measured
# on a real 3-hour session, everything from the between-tune murmur to the band
# in full flight spans barely 22dB -- so any fixed window (0 to -60dBFS, say)
# crushes the whole night into the top fifth of the scale and the gaps that the
# operator is hunting for stop being visible. Clipping the outer few percent at
# both ends keeps one shout or one dropped mic from resetting the scale.
_FLOOR_PERCENTILE = 0.02
_CEIL_PERCENTILE = 0.995
# If a recording really is near-silent end to end, fall back to this window
# rather than dividing by a zero-width range.
_MIN_DB_RANGE = 6.0


def get_s3_client():
    """Create and return an S3 client using environment variables."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
    )


def get_s3_bucket():
    """Return the configured S3 bucket name."""
    return os.environ.get("AWS_S3_BUCKET")


def upload_recording(file_path, storage_key, mime_type="audio/mp4"):
    """Upload a complete audio file to S3 under `storage_key`."""
    s3 = get_s3_client()
    with open(file_path, "rb") as fh:
        s3.upload_fileobj(
            fh,
            get_s3_bucket(),
            storage_key,
            ExtraArgs={"ContentType": mime_type},
        )
    return storage_key


def generate_presigned_url(storage_key, expiry=21600):
    """Presigned GET URL for a stored recording.

    Six hours by default: long enough that a segmenting session outlasts it only
    rarely, short enough that a leaked URL expires. The page re-fetches on load.
    """
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": get_s3_bucket(), "Key": storage_key},
        ExpiresIn=expiry,
    )


def probe_audio(file_path):
    """Read duration/sample rate/channels from an audio file via ffprobe.

    Returns {"duration_ms": int, "sample_rate": int|None, "channels": int|None}.
    """
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "format=duration:stream=sample_rate,channels",
            "-of", "default=noprint_wrappers=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    fields = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip()] = v.strip()

    def as_int(key):
        try:
            return int(fields[key])
        except (KeyError, ValueError):
            return None

    duration = fields.get("duration")
    if duration in (None, "N/A"):
        raise ValueError(f"ffprobe could not determine the duration of {file_path}")

    return {
        "duration_ms": int(round(float(duration) * 1000)),
        "sample_rate": as_int("sample_rate"),
        "channels": as_int("channels"),
    }


def _rms_of_frame(frame):
    """RMS of a mono 16-bit PCM fragment.

    audioop does this in C and is ~50x faster over a 47-million-sample decode,
    but it was removed in Python 3.13 — hence the fallback, which is correct,
    just slow. Resolved once at import, not per call.
    """
    import math

    return math.sqrt(sum(float(s) * s for s in frame) / len(frame)) if len(frame) else 0.0


try:  # pragma: no cover - exercised by whichever interpreter is running
    import audioop as _audioop

    def _rms_of_bytes(buf):
        return _audioop.rms(buf, 2)
except ImportError:  # pragma: no cover - Python 3.13+
    _audioop = None

    def _rms_of_bytes(buf):
        import array

        block = array.array("h")
        block.frombytes(buf)
        return _rms_of_frame(block)


def compute_peaks(file_path, peaks_hz=PEAKS_HZ):
    """Compute the RMS amplitude envelope of an audio file.

    Streams mono 16-bit PCM out of ffmpeg and reduces it bucket by bucket, so
    memory stays flat no matter how long the recording is.

    Returns (peaks: bytes, peaks_hz: int) — one 0-255 byte per bucket.
    """
    samples_per_bucket = max(1, int(round(_DECODE_RATE / peaks_hz)))
    bytes_per_bucket = samples_per_bucket * 2

    proc = subprocess.Popen(
        [
            "ffmpeg", "-v", "error",
            "-i", file_path,
            "-ac", "1",
            "-ar", str(_DECODE_RATE),
            "-f", "s16le",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    sums = []      # RMS per bucket, still in raw int16 units
    carry = b""    # bytes left over from the previous read: a partial bucket

    try:
        while True:
            buf = proc.stdout.read(1 << 22)
            if not buf:
                break
            if carry:
                buf = carry + buf
            n_whole = len(buf) // bytes_per_bucket
            for b in range(n_whole):
                frame = buf[b * bytes_per_bucket:(b + 1) * bytes_per_bucket]
                sums.append(float(_rms_of_bytes(frame)))
            carry = buf[n_whole * bytes_per_bucket:]
        # Trailing partial bucket (and any odd half-sample byte, which audioop
        # would reject) -- drop the stray byte, keep the rest.
        if len(carry) >= 2:
            sums.append(float(_rms_of_bytes(carry[:len(carry) - len(carry) % 2])))
    finally:
        if proc.stdout:
            proc.stdout.close()
        stderr = proc.stderr.read() if proc.stderr else b""
        if proc.stderr:
            proc.stderr.close()
        rc = proc.wait()

    if rc != 0:
        raise RuntimeError(f"ffmpeg failed ({rc}): {stderr.decode('utf-8', 'replace')[:500]}")
    if not sums:
        raise ValueError(f"No audio samples decoded from {file_path}")

    import math

    ordered = sorted(sums)
    last = len(ordered) - 1

    def pct(q):
        return ordered[max(0, min(last, int(len(ordered) * q)))]

    floor = max(pct(_FLOOR_PERCENTILE), 1.0)
    ceiling = max(pct(_CEIL_PERCENTILE), floor)
    db_range = max(_MIN_DB_RANGE, 20 * math.log10(ceiling / floor))

    out = bytearray(len(sums))
    for idx, value in enumerate(sums):
        if value <= floor:
            out[idx] = 0
            continue
        scaled = 20 * math.log10(value / floor) / db_range * 255
        out[idx] = max(0, min(255, int(round(scaled))))

    return bytes(out), peaks_hz

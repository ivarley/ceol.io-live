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
import re
import shutil
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


# -----------------------------------------------------------------------------
# Finding ffmpeg
# -----------------------------------------------------------------------------
# The CLI importer only ever ran on a laptop, where ffmpeg is on PATH. In-app
# upload moves the identical pipeline onto the Render web dyno, which runs
# Render's native Python runtime: no Dockerfile, no apt step, and no ffmpeg.
#
# `imageio-ffmpeg` solves that without a build hook -- it is an ordinary wheel
# carrying a static ffmpeg binary, so it installs from requirements.txt like any
# other dependency. It ships ffmpeg ONLY, not ffprobe, which is why probe_audio
# below has to be able to work without one.
#
# PATH wins whenever it has one, so local development keeps using the system
# build (newer, and the one the CLI has always used).
_BINARIES = {}


def _ffmpeg_exe():
    """Absolute path to an ffmpeg binary. Raises if there is none."""
    if "ffmpeg" not in _BINARIES:
        found = shutil.which("ffmpeg")
        if not found:
            try:
                import imageio_ffmpeg

                found = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:  # not installed, or no binary for this platform
                found = None
        _BINARIES["ffmpeg"] = found

    exe = _BINARIES["ffmpeg"]
    if not exe:
        raise RuntimeError(
            "ffmpeg is not available on this server: it is not on PATH and the "
            "imageio-ffmpeg fallback could not be loaded. Audio ingest cannot run."
        )
    return exe


def _ffprobe_exe():
    """Absolute path to ffprobe, or None.

    None is the NORMAL case on the server (imageio-ffmpeg bundles no ffprobe);
    probe_audio falls back to reading ffmpeg's own stream report.
    """
    if "ffprobe" not in _BINARIES:
        _BINARIES["ffprobe"] = shutil.which("ffprobe")
    return _BINARIES["ffprobe"]


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


def check_configured():
    """Return a human-readable reason object storage is unusable, or None.

    Without this, an unset AWS_S3_BUCKET reaches boto3 as Bucket=None and comes
    back as "expected string or bytes-like object, got 'NoneType'" -- which the
    segmenter then shows to the operator as the reason their audio won't play.
    Naming the missing variable turns that into a two-minute fix.
    """
    missing = [
        name
        for name in ("AWS_S3_BUCKET", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        return f"object storage is not configured on this server ({', '.join(missing)} unset)"
    return None


def build_storage_key(filename, prefix="recordings"):
    """Mint an S3 key for a newly uploaded file.

    The uuid segment does two jobs: it keeps two files of the same name from
    colliding, and it keeps the key from leaking who recorded what to anyone who
    sees a presigned URL. The original filename rides along only so an object
    listing is readable by a human.
    """
    import re as _re
    import uuid

    safe = _re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(filename or "recording")).strip("-")
    return f"{prefix}/{uuid.uuid4().hex}/{safe or 'recording'}"


def generate_presigned_upload(storage_key, mime_type, expiry=3600):
    """Presigned PUT URL the browser uploads to directly.

    Direct-to-S3 rather than through Flask, because a three-hour master is
    ~350MB: routing that through the web dyno would hold a worker for the whole
    upload, spool the file to the dyno's disk, and buy nothing -- S3 is where it
    has to end up either way.

    `mime_type` is part of the signature, so the browser MUST send exactly this
    Content-Type or S3 rejects the PUT with SignatureDoesNotMatch.

    An hour is plenty: this signs the START of the upload, not its duration, so
    a slow three-hour transfer over a link that began inside the window still
    completes.
    """
    problem = check_configured()
    if problem:
        raise RuntimeError(problem)
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": get_s3_bucket(), "Key": storage_key, "ContentType": mime_type},
        ExpiresIn=expiry,
    )


def stored_object_size(storage_key):
    """Size in bytes of a stored object, or None if it isn't there.

    The upload confirmation calls this before writing a `recording` row, so a PUT
    that failed, was cancelled, or never happened cannot leave a row pointing at
    an object that does not exist -- which would show up much later as a
    segmenter page that loads and then plays nothing.
    """
    problem = check_configured()
    if problem:
        raise RuntimeError(problem)
    s3 = get_s3_client()
    try:
        head = s3.head_object(Bucket=get_s3_bucket(), Key=storage_key)
    except Exception:  # 404/403 both mean "not usable", and boto3 spells them differently
        return None
    return head.get("ContentLength")


def delete_stored_objects(*storage_keys):
    """Remove objects from the bucket. Returns a list of (key, reason) failures.

    Failures are RETURNED rather than raised because of where this is called
    from: the database row is already gone by then, and an object that outlives
    it costs storage and nothing else. Raising would report a delete that
    actually happened as a failure, which is the more confusing outcome.

    A key that isn't there is not a failure — S3's delete is idempotent, and
    that is exactly the state a retried delete should be able to reach.
    """
    problem = check_configured()
    if problem:
        return [(key, problem) for key in storage_keys if key]

    s3 = get_s3_client()
    bucket = get_s3_bucket()
    failures = []
    for key in storage_keys:
        if not key:
            continue
        try:
            s3.delete_object(Bucket=bucket, Key=key)
        except Exception as exc:
            failures.append((key, str(exc)))
    return failures


def download_recording(storage_key, dest_path):
    """Pull a stored object down to a local path.

    Ingest needs the whole file on disk: ffmpeg reads it twice (once for the
    envelope, once for the proxy), and making it fetch the object over HTTP each
    time would double the transfer for no gain. Streams to disk, so memory stays
    flat regardless of length.
    """
    problem = check_configured()
    if problem:
        raise RuntimeError(problem)
    s3 = get_s3_client()
    with open(dest_path, "wb") as fh:
        s3.download_fileobj(get_s3_bucket(), storage_key, fh)
    return dest_path


def generate_presigned_url(storage_key, expiry=21600):
    """Presigned GET URL for a stored recording.

    Six hours by default: long enough that a segmenting session outlasts it only
    rarely, short enough that a leaked URL expires. The page re-fetches on load.
    """
    problem = check_configured()
    if problem:
        raise RuntimeError(problem)
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": get_s3_bucket(), "Key": storage_key},
        ExpiresIn=expiry,
    )


# Playback proxy settings. Mono because the job is hearing tune boundaries, not
# stereo imaging; AAC because it is the one lossy codec every phone browser plays
# without argument (Opus would be smaller, but Safari's support for it is not
# something to bet a field tool on).
# 32kbps mono at 22.05kHz: roughly an eighth the size of a 256kbps stereo master
# (45MB for a three-hour session, against 348MB). 11kHz of bandwidth, which sits
# well above every fundamental in the room and holds enough harmonic detail to
# tell one tune from another by ear -- confirmed by listening to encodes of a
# real session, not assumed. Both are flags, because the right trade-off is a
# judgement about ears rather than something to hard-code.
STREAM_BITRATE = "32k"
STREAM_SAMPLE_RATE = 22050
STREAM_MIME = "audio/mp4"
STREAM_SUFFIX = ".stream.m4a"


def transcode_for_streaming(src_path, dest_path, bitrate=STREAM_BITRATE, sample_rate=STREAM_SAMPLE_RATE):
    """Write a small mono proxy of `src_path` for browser playback.

    NOT for analysis: the training corpus is cut from the master. This exists
    only so a three-hour recording starts playing on a phone in seconds rather
    than tens of seconds.

    Lowering the sample rate alongside the bitrate is what keeps a small file
    from sounding like a broken radio: the native AAC encoder spends its bits
    much better over 16kHz of bandwidth than it does trying to cover 22kHz.

    `-movflags +faststart` puts the MP4 index at the front, so the browser can
    start playing (and seeking) after the first range request instead of having
    to reach the end of the file first -- on a long recording that is the
    difference between a couple of seconds and most of the download.
    """
    result = subprocess.run(
        [
            _ffmpeg_exe(), "-v", "error", "-y",
            "-i", src_path,
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-c:a", "aac",
            "-b:a", bitrate,
            "-movflags", "+faststart",
            dest_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg transcode failed ({result.returncode}): {result.stderr[:500]}")
    return dest_path


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_AUDIO_STREAM_RE = re.compile(r"Stream #\d+:\d+.*: Audio: .*")
_SAMPLE_RATE_RE = re.compile(r"(\d+)\s*Hz")
_CHANNEL_COUNT_RE = re.compile(r"(\d+)\s*channels")

# ffmpeg names the common layouts rather than counting them.
_CHANNEL_LAYOUTS = {"mono": 1, "stereo": 2, "2.1": 3, "quad": 4, "5.0": 5, "5.1": 6, "7.1": 8}


def _probe_with_ffmpeg(file_path):
    """probe_audio's fallback for servers with ffmpeg but no ffprobe.

    `ffmpeg -i FILE` with no output file prints the container and stream report
    to stderr and then exits non-zero ("At least one output file must be
    specified") -- which is exactly the report ffprobe would have formatted for
    us, so the non-zero exit is expected and ignored.
    """
    proc = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-i", file_path],
        capture_output=True,
        text=True,
    )
    report = proc.stderr or ""

    match = _DURATION_RE.search(report)
    if not match:
        raise ValueError(
            f"ffmpeg could not determine the duration of {file_path}: "
            f"{report.strip().splitlines()[-1] if report.strip() else 'no output'}"
        )
    hours, minutes, seconds = int(match.group(1)), int(match.group(2)), float(match.group(3))
    duration_ms = int(round((hours * 3600 + minutes * 60 + seconds) * 1000))

    sample_rate = channels = None
    stream = _AUDIO_STREAM_RE.search(report)
    if stream:
        line = stream.group(0)
        rate = _SAMPLE_RATE_RE.search(line)
        if rate:
            sample_rate = int(rate.group(1))
        counted = _CHANNEL_COUNT_RE.search(line)
        if counted:
            channels = int(counted.group(1))
        else:
            for name, count in _CHANNEL_LAYOUTS.items():
                if re.search(rf"\b{re.escape(name)}\b", line):
                    channels = count
                    break

    return {"duration_ms": duration_ms, "sample_rate": sample_rate, "channels": channels}


def probe_audio(file_path):
    """Read duration/sample rate/channels from an audio file.

    Uses ffprobe when it is there and ffmpeg's own stream report when it is not
    (see _ffprobe_exe -- the server has no ffprobe).

    Returns {"duration_ms": int, "sample_rate": int|None, "channels": int|None}.
    """
    ffprobe = _ffprobe_exe()
    if not ffprobe:
        return _probe_with_ffmpeg(file_path)

    out = subprocess.run(
        [
            ffprobe, "-v", "error",
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
            _ffmpeg_exe(), "-v", "error",
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

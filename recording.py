"""
Session audio recording module.
Handles S3 upload/download and audio file chunking for session recordings.
"""

import os
import hashlib
import tempfile
import boto3
from botocore.exceptions import ClientError

CHUNK_DURATION_MS = 30000  # 30 seconds


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


def upload_chunk_to_s3(recording_id, sequence_number, audio_data):
    """Upload an audio chunk to S3.

    Args:
        recording_id: The recording ID
        sequence_number: 0-indexed chunk sequence number
        audio_data: Raw audio bytes

    Returns:
        str: The S3 key where the chunk was stored
    """
    s3_key = f"recordings/{recording_id}/chunk_{sequence_number:04d}.webm"
    s3 = get_s3_client()
    s3.put_object(
        Bucket=get_s3_bucket(),
        Key=s3_key,
        Body=audio_data,
        ContentType="audio/webm",
    )
    return s3_key


def generate_presigned_url(s3_key, expiry=3600):
    """Generate a presigned GET URL for an S3 object.

    Args:
        s3_key: The S3 object key
        expiry: URL expiry in seconds (default 1 hour)

    Returns:
        str: Presigned URL
    """
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": get_s3_bucket(), "Key": s3_key},
        ExpiresIn=expiry,
    )


def get_recording_timeline(cur, recording_id):
    """Get all chunks for a recording with presigned URLs.

    Args:
        cur: Database cursor
        recording_id: The recording ID

    Returns:
        list: Ordered chunks with presigned URLs
    """
    cur.execute(
        """
        SELECT recording_chunk_id, sequence_number, start_timestamp_ms, end_timestamp_ms,
               s3_key, file_size_bytes
        FROM recording_chunk
        WHERE recording_id = %s AND upload_status = 'uploaded'
        ORDER BY sequence_number
    """,
        (recording_id,),
    )

    chunks = []
    for row in cur.fetchall():
        chunks.append(
            {
                "recording_chunk_id": row[0],
                "sequence_number": row[1],
                "start_ms": row[2],
                "end_ms": row[3],
                "url": generate_presigned_url(row[4]),
                "file_size_bytes": row[5],
            }
        )
    return chunks


def compute_checksum(data):
    """Compute SHA-256 hex digest for audio data."""
    return hashlib.sha256(data).hexdigest()


def chunk_audio_file(file_path):
    """Split an audio file into 30-second chunks using pydub.

    Args:
        file_path: Path to the audio file

    Returns:
        list of dicts: [{"sequence_number": int, "start_ms": int, "end_ms": int, "data": bytes}]
    """
    from pydub import AudioSegment

    # Detect format from extension
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    format_map = {"mp3": "mp3", "wav": "wav", "m4a": "mp4", "ogg": "ogg", "webm": "webm", "flac": "flac"}
    fmt = format_map.get(ext, ext)

    audio = AudioSegment.from_file(file_path, format=fmt)

    # Convert to mono 48kHz for consistency
    audio = audio.set_channels(1).set_frame_rate(48000)

    total_ms = len(audio)
    chunks = []
    seq = 0
    pos = 0

    while pos < total_ms:
        end = min(pos + CHUNK_DURATION_MS, total_ms)
        segment = audio[pos:end]

        # Export as webm/opus
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            segment.export(tmp_path, format="webm", codec="libopus", bitrate="64k")
            with open(tmp_path, "rb") as f:
                data = f.read()
        finally:
            os.unlink(tmp_path)

        chunks.append(
            {
                "sequence_number": seq,
                "start_ms": pos,
                "end_ms": end,
                "data": data,
            }
        )
        seq += 1
        pos = end

    return chunks

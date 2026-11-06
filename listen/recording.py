"""Recording on the server (spec 061 stage 5): a night listened to from the
website, with "Record this night" on, becomes the night's recording.

The browser keeps no audio. The service already writes every stream's audio
to its folder (`audio.flac`, the Listener's LiveStore); this files that file
under the night, the same way the iPhone's upload goes (ios/Ceol/Ceol/
RecordingStore.swift), through the web app's own endpoints and as the person
listening (their token), so the web app's permission is the one that holds:

  GET  /api/session-instances/<id>/recordings   at the start: may they?
  POST /api/recordings/upload-url               sign a PUT to the bucket
  PUT  <the signed URL>                         the FLAC
  POST /api/recordings                          the row; the app's ingest follows
  PUT  /api/recordings/<id>/listen-log          what the meter showed, and the taps

A recording is filed when the browser says stop, when a stream nobody has sent
to is swept (a tab that closed without saying so), and when the service shuts
down (a deploy), for whatever each holds by then. Once filed, the stream's
folder is deleted.

Audio from before a recording's first real sample is not kept: a stream that
resumes on a service that no longer has it (after a deploy) starts with a skip
to where the browser is, and that silence is not the night.
"""

import datetime
import json
import os
import shutil
import time
import urllib.error
import urllib.request

SR = 22050
MIN_S = 10  # shorter than this is not a night's recording
RETRY_S = (30, 60, 120, 240, 480)


class Refused(Exception):
    """The web app said no (4xx): trying again won't change it."""


def _request(
    api_url,
    token,
    method,
    path,
    body=None,
    data=None,
    content_type="application/json",
    timeout=60,
):
    url = path if path.startswith("http") else f"{api_url}{path}"
    # Cloudflare, in front of ceol.app, refuses Python's own user agent (error 1010)
    headers = {"X-Ceol-Client": "listen", "User-Agent": "ceol-listen"}
    if token and not path.startswith("http"):
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
    if data is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        try:
            message = json.loads(e.read()).get("error") or str(e)
        except Exception:
            message = str(e)
        if 400 <= e.code < 500:
            raise Refused(message) from e
        raise
    return json.loads(raw) if raw else {}


def may_record(api_url, token, instance_id):
    """None if this person may file a recording under the night, else why not."""
    try:
        _request(
            api_url,
            token,
            "GET",
            f"/api/session-instances/{int(instance_id)}/recordings",
            timeout=15,
        )
        return None
    except Refused as e:
        return str(e)
    except Exception as e:
        return f"couldn't ask Ceol: {e!r}"


class NightRecording:
    """What a stream needs to become a night's recording: the night, who is
    listening (their token), when the browser started hearing, and the first
    sample of real audio this stream took."""

    def __init__(self, instance_id, token, started_at=None, title=None):
        self.instance_id = int(instance_id)
        self.token = token
        self.started_at = _parse_time(started_at) or datetime.datetime.now(
            datetime.timezone.utc
        )
        self.title = (title or "").strip() or None
        self.from_sample = None
        self.storage_key = None
        self.recording_id = None
        self.log_sent = False
        self.filed = False
        self.error = None

    def took_audio(self, at_sample):
        """The stream is about to take real audio at this sample."""
        if self.from_sample is None:
            self.from_sample = int(at_sample)

    # -- filing, in a worker thread ---------------------------------------

    def file(self, stream_dir, api_url, sleep=time.sleep, retry_s=RETRY_S):
        """File the stream's audio under the night, trying again on a failure
        the web app (or the bucket) may get over. -> the recording id, or None."""
        for attempt in range(len(retry_s) + 1):
            try:
                rid = self._file_once(stream_dir, api_url)
                self.filed = True
                shutil.rmtree(stream_dir, ignore_errors=True)
                return rid
            except Refused as e:
                self.error = f"refused: {e}"
                print(
                    f"listen: recording for night {self.instance_id} refused: {e}",
                    flush=True,
                )
                return None
            except Exception as e:
                self.error = repr(e)
                print(
                    f"listen: recording for night {self.instance_id} not filed yet: {e!r}",
                    flush=True,
                )
                if attempt < len(retry_s):
                    sleep(retry_s[attempt])
        return None

    def _file_once(self, stream_dir, api_url):
        import soundfile as sf

        audio = os.path.join(stream_dir, "audio.flac")
        start = self.from_sample or 0
        with sf.SoundFile(audio) as f:
            frames = f.frames
        if frames - start < MIN_S * SR:
            self.error = "too short"
            return None
        if self.recording_id is None:
            if self.storage_key is None:
                path = (
                    audio
                    if start == 0
                    else _trimmed(
                        audio, start, os.path.join(stream_dir, "recording.flac")
                    )
                )
                name = f"ceol-listen-{self.started_at.date().isoformat()}.flac"
                signed = _request(
                    api_url,
                    self.token,
                    "POST",
                    "/api/recordings/upload-url",
                    {"session_instance_id": self.instance_id, "filename": name},
                )
                with open(path, "rb") as fh:
                    size = os.fstat(fh.fileno()).st_size
                    req = urllib.request.Request(
                        signed["upload_url"],
                        data=fh,
                        method="PUT",
                        headers={
                            "Content-Type": signed["content_type"],
                            "Content-Length": str(size),
                        },
                    )
                    with urllib.request.urlopen(req, timeout=600):
                        pass
                self.storage_key = signed["storage_key"]
            began = self.started_at + datetime.timedelta(seconds=start / SR)
            body = {
                "session_instance_id": self.instance_id,
                "storage_key": self.storage_key,
                "started_at": began.isoformat(),
                "duration_ms": int(1000 * (frames - start) / SR),
            }
            if self.title:
                body["label"] = f"{self.title} (Ceol website)"
            self.recording_id = _request(
                api_url, self.token, "POST", "/api/recordings", body
            )["recording_id"]
            print(
                f"listen: night {self.instance_id} filed as recording {self.recording_id}",
                flush=True,
            )
        if not self.log_sent:
            log = meter_log(stream_dir, start)
            if log:
                try:
                    _request(
                        api_url,
                        self.token,
                        "PUT",
                        f"/api/recordings/{self.recording_id}/listen-log",
                        data=log,
                        content_type="application/x-ndjson",
                    )
                except Refused as e:
                    print(
                        f"listen: meter log for recording {self.recording_id} refused: {e}",
                        flush=True,
                    )
            self.log_sent = True
        return self.recording_id


def _trimmed(src, start, dst):
    """The audio from `start` on, block by block (a night is too long to hold)."""
    import soundfile as sf

    with sf.SoundFile(src) as f, sf.SoundFile(
        dst, "w", samplerate=SR, channels=1, subtype="PCM_16", format="FLAC"
    ) as out:
        f.seek(start)
        while True:
            block = f.read(1 << 20, dtype="int16")
            if not len(block):
                break
            out.write(block)
    return dst


def meter_log(stream_dir, start=0):
    """The Listener's states and taps as the iPhone's meter log has them
    (CeolKit ListenWire.logLine: {"at_ms", "dir", "msg"} a line, in time
    order): states "in", taps "out", on the recording's clock. -> bytes."""
    offset_ms = int(1000 * start / SR)
    lines = []
    for name, kind, direction in (
        ("states.jsonl", "state", "in"),
        ("taps.jsonl", "tap", "out"),
    ):
        try:
            with open(os.path.join(stream_dir, name)) as f:
                for raw in f:
                    try:
                        m = json.loads(raw)
                    except ValueError:
                        continue
                    at = int(m.get("t_ms") or 0) - offset_ms
                    if at >= 0:
                        lines.append((at, direction, {"type": kind, **m}))
        except FileNotFoundError:
            pass
    lines.sort(key=lambda x: x[0])
    return "".join(
        json.dumps({"at_ms": at, "dir": d, "msg": m}) + "\n" for at, d, m in lines
    ).encode()


def _parse_time(value):
    if not value:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else None

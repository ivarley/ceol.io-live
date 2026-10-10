"""The phone's decider file, kept current (services/decider_data_service.py):
when the weekly check is due, publishing (file first, manifest last), an
unchanged week, and what the app is offered. S3 is a dict here."""

import io
import json
from datetime import datetime, timezone

import pytest

from services import decider_data_service as dd


class FakeS3:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self):
        self.objects = {}
        self.order = []

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = Body
        self.order.append(Key)

    def upload_file(self, path, Bucket, Key, ExtraArgs=None):
        with open(path, "rb") as f:
            self.objects[Key] = f.read()
        self.order.append(Key)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://s3.example/{Params['Key']}?expires={ExpiresIn}"


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(dd, "_s3", lambda: (fake, "bucket"))
    dd._cache.clear()
    return fake


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_due_once_a_week_from_monday_seven():
    m = {"checked_at": "2026-10-05T07:20:00Z"}  # Monday 5 October, after 07:00
    assert not dd.is_due(m, utc(2026, 10, 5, 7, 35))
    assert not dd.is_due(m, utc(2026, 10, 11, 23, 0))  # the Sunday after
    assert not dd.is_due(m, utc(2026, 10, 12, 6, 59))  # next Monday, before seven
    assert dd.is_due(m, utc(2026, 10, 12, 7, 0))
    # a missed Monday is caught up later in the week, not skipped
    assert dd.is_due({"checked_at": "2026-09-28T07:14:00Z"}, utc(2026, 10, 8, 12, 0))
    assert dd.is_due(None, utc(2026, 10, 8, 12, 0))


def test_publish_writes_the_file_before_the_manifest(s3, tmp_path):
    path = tmp_path / "d.bin"
    path.write_bytes(b"CEOLDEC1 and the rest")
    meta = {
        "version": 1,
        "built_at": "2026-10-12T07:16:00Z",
        "inputs_sha256": "in",
        "n_tunes": 23400,
        "popular_n_tunes": 3300,
        "source": {"tunes_csv_sha256": "csv"},
        "file": {"sha256": "abc123", "bytes": 21},
    }
    m = dd.publish(str(path), meta)
    assert s3.order == [
        "listen-data/decider/v1/abc123.bin",
        "listen-data/decider/v1/manifest.json",
    ]
    assert m["key"] == "listen-data/decider/v1/abc123.bin" and m["sha256"] == "abc123"
    assert (
        json.loads(s3.objects["listen-data/decider/v1/manifest.json"])["built_at"]
        == "2026-10-12T07:16:00Z"
    )


def test_the_app_is_offered_the_current_file(s3, tmp_path):
    assert dd.offer(1) == {"format": 1, "available": False}
    dd._cache.clear()
    path = tmp_path / "d.bin"
    path.write_bytes(b"x" * 10)
    dd.publish(
        str(path),
        {
            "version": 1,
            "built_at": "2026-10-12T07:16:00Z",
            "inputs_sha256": "in",
            "n_tunes": 1,
            "popular_n_tunes": 0,
            "source": {},
            "file": {"sha256": "abc", "bytes": 10},
        },
    )
    o = dd.offer(1)
    assert o["available"] and o["sha256"] == "abc" and o["bytes"] == 10
    assert o["url"].startswith("https://s3.example/listen-data/decider/v1/abc.bin")
    assert dd.offer(2) == {"format": 2, "available": False}


def popularity(tmp_path, books):
    p = tmp_path / "tune_popularity.csv"
    p.write_text(
        "name,tune_id,tunebooks\n" + "".join(f'"T",{t},{n}\n' for t, n in books.items())
    )
    return str(p)


def test_an_unchanged_week_builds_nothing(s3, tmp_path, monkeypatch):
    csv = tmp_path / "tunes.csv"
    csv.write_text(
        "tune_id,setting_id,name,type,meter,mode,abc,date,username\n"
        "1,1,A Reel,reel,4/4,Dmajor,DEFG ABcd|edcB AGFE|DEFG ABcd|edcB A2 d2|,2020,x\n"
    )
    monkeypatch.setattr(dd, "MIN_TUNES", 1)
    pop = popularity(tmp_path, {1: 500})
    outcome, first = dd.rebuild_and_publish(csv_path=str(csv), popularity_path=pop)
    assert outcome == "published"
    s3.order.clear()
    outcome, again = dd.rebuild_and_publish(csv_path=str(csv), popularity_path=pop)
    assert outcome == "unchanged" and again["sha256"] == first["sha256"]
    # only the check recorded
    assert s3.order == ["listen-data/decider/v2/manifest.json"]
    pop = popularity(tmp_path, {1: 50})  # no longer popular: a different file
    outcome, _ = dd.rebuild_and_publish(csv_path=str(csv), popularity_path=pop)
    assert outcome == "published"


def test_a_truncated_dump_is_not_published(s3, tmp_path):
    csv = tmp_path / "tunes.csv"
    csv.write_text(
        "tune_id,setting_id,name,type,meter,mode,abc,date,username\n"
        "1,1,A Reel,reel,4/4,Dmajor,DEFG ABcd|edcB AGFE|,2020,x\n"
    )
    with pytest.raises(RuntimeError, match="not publishing"):
        dd.rebuild_and_publish(
            csv_path=str(csv), popularity_path=popularity(tmp_path, {1: 500})
        )
    assert s3.objects == {}

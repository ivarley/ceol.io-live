"""/samples: two tunes to play to Listen, cut from session recordings and served from S3."""

from unittest.mock import patch


def test_samples_page_lists_both_tunes(client):
    r = client.get("/samples")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "The Kesh" in html and "The Silver Spear" in html
    assert 'src="/samples/the-kesh.mp3"' in html


@patch("recording.generate_presigned_url", return_value="https://s3.example.com/k?sig=1")
def test_sample_audio_redirects_to_storage(presign, client):
    r = client.get("/samples/the-silver-spear.mp3")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://s3.example.com/k?sig=1"
    assert presign.call_args.args[0] == "samples/the-silver-spear.mp3"


def test_unknown_sample_is_not_found(client):
    assert client.get("/samples/whatever.mp3").status_code == 404

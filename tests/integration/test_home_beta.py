"""The home page's "Ceol for iPhone" card: a TestFlight link that, until
TESTFLIGHT_BETA_OPEN=1, opens a "coming soon" dialog instead."""

BETA = "https://testflight.apple.com/join/1hWVVEyc"


def test_beta_not_open_shows_coming_soon(client, monkeypatch):
    monkeypatch.delenv("TESTFLIGHT_BETA_OPEN", raising=False)
    html = client.get("/").get_data(as_text=True)
    assert BETA in html
    assert 'id="iosBetaSoon"' in html
    assert "The beta is coming soon" in html


def test_beta_open_links_straight_to_testflight(client, monkeypatch):
    monkeypatch.setenv("TESTFLIGHT_BETA_OPEN", "1")
    html = client.get("/").get_data(as_text=True)
    assert BETA in html
    assert 'id="iosBetaSoon"' not in html

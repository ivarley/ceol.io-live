"""The home page's "Ceol for iPhone" card links to the App Store; the TestFlight
beta link lives on the help page On Your Phone instead."""

APP_STORE = "https://apps.apple.com/app/id6817016920"
BETA = "https://testflight.apple.com/join/1hWVVEyc"


def test_home_links_to_the_app_store(client):
    html = client.get("/").get_data(as_text=True)
    assert APP_STORE in html
    assert BETA not in html


def test_help_has_the_beta(client):
    html = client.get("/help/phone").get_data(as_text=True)
    assert APP_STORE in html
    assert BETA in html

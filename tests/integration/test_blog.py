"""The blog (blog.py): /blog, /blog/<slug> and the feed at /blog/rss, in both languages."""

import re
import xml.etree.ElementTree as ET

import pytest

import blog


def _lang_of(html):
    return re.search(r'<html lang="(\w+)"', html).group(1)


def test_every_post_has_both_bodies(client):
    import os

    root = os.path.join(os.path.dirname(blog.__file__), "templates")
    for p in blog.POSTS:
        assert os.path.exists(os.path.join(root, "blog", p["slug"] + ".html"))
        assert os.path.exists(os.path.join(root, "ga", "blog", p["slug"] + ".html"))
        assert set(p["title"]) == set(p["summary"]) == {"en", "ga"}


def test_the_index_lists_the_posts_newest_first(client):
    resp = client.get("/blog")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    positions = [html.index(f'href="/blog/{p["slug"]}"') for p in blog.posts()]
    assert positions == sorted(positions)
    assert 'type="application/rss+xml"' in html
    assert "Welcome to the Ceol blog" in html


def test_a_post_page(client):
    resp = client.get("/blog/welcome")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<h1>Welcome to the Ceol blog</h1>" in html
    assert "Howdy! Fáilte!" in html
    assert "October 29, 2026" in html


def test_an_unknown_post_is_404(client):
    assert client.get("/blog/no-such-post").status_code == 404


@pytest.mark.parametrize("url", ["/blog", "/blog/welcome"])
def test_the_pages_come_in_both_languages(client, url):
    english = client.get(url)
    client.set_cookie("ceol_lang", "ga")
    irish = client.get(url)
    assert irish.status_code == 200
    assert _lang_of(irish.get_data(as_text=True)) == "ga"
    assert irish.data != english.data
    assert "Fáilte go blag Ceol" in irish.get_data(as_text=True)


def test_the_feed(client):
    resp = client.get("/blog/rss")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("application/rss+xml")
    root = ET.fromstring(resp.data)
    channel = root.find("channel")
    assert channel.findtext("language") == "en"
    items = channel.findall("item")
    assert len(items) == len(blog.POSTS)
    first = items[0]
    assert first.findtext("title") == "Welcome to the Ceol blog"
    assert first.findtext("link").endswith("/blog/welcome")
    assert first.findtext("guid") == first.findtext("link")
    assert "Oct 2026" in first.findtext("pubDate")
    body = first.findtext("description")
    assert "Howdy! Fáilte!" in body
    # Links are absolute for feed readers.
    assert 'href="/' not in body
    assert re.search(r'href="https?://[^/]+/register"', body)


def test_the_feed_takes_its_language_from_the_query(client):
    resp = client.get("/blog/rss?lang=ga")
    root = ET.fromstring(resp.data)
    channel = root.find("channel")
    assert channel.findtext("language") == "ga"
    item = channel.find("item")
    assert item.findtext("title") == "Fáilte go blag Ceol"
    assert "Seo an chéad iontráil" in item.findtext("description")
    # The self link names the language, so a reader keeps it.
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    assert channel.find("atom:link", ns).get("href").endswith("/blog/rss?lang=ga")


def test_the_blog_is_in_the_menu_and_on_about(client):
    assert 'href="/blog"' in client.get("/about").get_data(as_text=True)
    assert 'href="/blog"' in client.get("/help").get_data(as_text=True)


@pytest.mark.parametrize("url", ["/ian"])
def test_ians_page_comes_in_both_languages(client, url):
    english = client.get(url)
    assert english.status_code == 200
    html = english.get_data(as_text=True)
    assert "I'm the developer of the Ceol app." in html
    assert "images/ian.jpg" in html
    client.set_cookie("ceol_lang", "ga")
    irish = client.get(url)
    assert _lang_of(irish.get_data(as_text=True)) == "ga"
    assert "Is mé forbróir aip Ceol." in irish.get_data(as_text=True)


def test_the_post_signs_off_with_a_link_to_ian(client):
    assert 'href="/ian">Ian</a>' in client.get("/blog/welcome").get_data(as_text=True)

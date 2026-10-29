"""The blog at /blog: hand-written posts, newest first, in both languages.

A post is two templates, `templates/blog/<slug>.html` (English) and
`templates/ga/blog/<slug>.html` (Irish), each an HTML fragment (no `extends`): the
post's body. Its title and summary live here, in both languages, with its date and
author. To publish a post, write the two fragments and add it to POSTS.

The index (`/blog`), each post (`/blog/<slug>`) and the feed (`/blog/rss`) render
the fragment of the request's language (i18n.localized). The feed is the only
page where `?lang=ga` picks the language, because feed readers send no cookie.
"""

from datetime import date, datetime, timezone

POSTS = [
    {
        "slug": "welcome",
        "date": date(2026, 10, 29),
        "author": "Ian",
        "title": {"en": "Welcome to the Ceol blog", "ga": "Fáilte go blag Ceol"},
        "summary": {
            "en": "The first entry on the brand new ceol.app blog: what Ceol is for, "
            "its three main features, and what to expect here.",
            "ga": "An chéad iontráil ar bhlag úrnua ceol.app: cad chuige Ceol, "
            "a thrí phríomhghné, agus a bhfuil le súil leis anseo.",
        },
    },
]


def posts():
    """Every post, newest first."""
    return sorted(POSTS, key=lambda p: p["date"], reverse=True)


def post(slug):
    for p in POSTS:
        if p["slug"] == slug:
            return p
    return None


def body_template(p):
    """The post's body fragment, to be passed through i18n.localized."""
    return f"blog/{p['slug']}.html"


def published_at(p):
    """The post's date as a UTC datetime, for the feed's pubDate."""
    return datetime(
        p["date"].year, p["date"].month, p["date"].day, 12, tzinfo=timezone.utc
    )

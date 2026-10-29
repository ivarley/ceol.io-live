"""The blog at /blog: hand-written posts, newest first, in both languages.

A post is two templates, `templates/blog/<slug>.html` (English) and
`templates/ga/blog/<slug>.html` (Irish), each an HTML fragment (no `extends`): the
post's body. Its title and summary live here, in both languages, with its date and
author. To publish a post, write the two fragments and add it to POSTS.

The index (`/blog`), each post (`/blog/<slug>`) and the feed (`/blog/rss`) render
the fragment of the request's language (i18n.localized). The feed is the only
page where `?lang=ga` picks the language, because feed readers send no cookie.
"""

import html as html_lib
import re
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


def _html_to_text(fragment):
    """The post's body as plain text: paragraphs apart, list items as lines."""
    s = re.sub(r"<li\b[^>]*>", "- ", fragment)
    s = re.sub(r"</(p|li|h\d|ol|ul)>", "\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html_lib.unescape(s)
    s = "\n".join(line.strip() for line in s.splitlines())
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def email_body(p, lang, site):
    """The post as an email in `lang`: (html, text). The body fragment with its
    links made absolute, under the title, ending with a link to the post."""
    from flask import render_template
    from flask_babel import force_locale, gettext as _
    from i18n import localized

    fragment = render_template(localized(body_template(p), lang=lang))
    fragment = re.sub(r'(href|src)="/', rf'\1="{site}/', fragment)
    url = f"{site}/blog/{p['slug']}"
    title = p["title"][lang]
    with force_locale(lang):
        read_online = _("Read this post on the website")
    body_html = (
        f"<h1>{html_lib.escape(title)}</h1>\n{fragment}\n"
        f'<p><a href="{url}">{read_online}</a></p>'
    )
    body_text = f"{title}\n\n{_html_to_text(fragment)}\n\n{read_online}: {url}"
    return body_html, body_text

"""Spec 057: the server's and the templates' strings exist in Irish.

- Every string the code or a template marks for translation (`_()`, `gettext`,
  `ngettext`, `lazy_gettext`) has an Irish entry in translations/ga/LC_MESSAGES/
  messages.po: not missing, not empty, every plural form filled.
- The compiled .mo the server reads matches the .po (`make i18n-compile`).
- A template carrying the marker `{# i18n-converted #}` has no English left outside
  `_()`: no bare text and no literal aria-label, title, placeholder or alt.

A drafted string still flagged `review` counts as present; `scripts/i18n_po.py pending`
lists those. Adding a string: `make i18n-extract`, write its Irish, `make i18n-compile`.
"""

import os
import re

import pytest
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import read_mo
from babel.messages.pofile import read_po

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PO = os.path.join(ROOT, "translations", "ga", "LC_MESSAGES", "messages.po")
MO = os.path.join(ROOT, "translations", "ga", "LC_MESSAGES", "messages.mo")
IGNORE = {
    "venv",
    "node_modules",
    "lab",
    "spike",
    "tests",
    "frontend",
    "static",
    "ios",
    "streaming",
    "listen",
    "abc-renderer",
    "e2e",
    "scripts",
    ".git",
    ".claude",
    "translations",
}

# Templates whose every user-facing string goes through _(): those carrying the
# marker {# i18n-converted #}. A template gains it when converted, then stays converted.
MARKER = "i18n-converted"


def _converted_templates():
    names = []
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "templates")):
        for f in files:
            if f.endswith(".html"):
                path = os.path.join(dirpath, f)
                with open(path, encoding="utf-8") as fh:
                    if MARKER in fh.read():
                        names.append(os.path.relpath(path, os.path.join(ROOT, "templates")))
    return sorted(names)


CONVERTED_TEMPLATES = _converted_templates()


def _extracted():
    def keep(dirname):
        return os.path.basename(dirname) not in IGNORE

    method_map = [("**.py", "python"), ("templates/**.html", "jinja2")]
    ids = set()
    for _filename, _lineno, message, _comments, _context in extract_from_dir(
        ROOT,
        method_map,
        keywords={
            "_": None,
            "gettext": None,
            "ngettext": (1, 2),
            "lazy_gettext": None,
            "_l": None,
            "js_ngettext": (1, 2),
        },
        directory_filter=keep,
    ):
        ids.add(message if isinstance(message, str) else tuple(message))
    return ids


@pytest.fixture(scope="module")
def catalog():
    with open(PO, "rb") as f:
        return read_po(f, locale="ga")


def _key(message_id):
    return message_id if isinstance(message_id, str) else tuple(message_id)


def test_every_marked_string_has_irish(catalog):
    entries = {_key(m.id): m for m in catalog if m.id}
    missing, empty = [], []
    for msgid in sorted(_extracted(), key=str):
        m = entries.get(msgid)
        if m is None:
            missing.append(msgid)
        elif not m.string or (
            isinstance(m.string, (list, tuple)) and not all(m.string)
        ):
            empty.append(msgid)
    assert (
        not missing
    ), f"not in messages.po (run make i18n-extract, then add the Irish): {missing}"
    assert not empty, f"no Irish yet in messages.po: {empty}"


def test_the_compiled_catalog_is_current(catalog):
    with open(MO, "rb") as f:
        compiled = read_mo(f)
    # A plural's forms come back as a tuple from the .po and a list from the .mo.
    def forms(s):
        return tuple(s) if isinstance(s, (list, tuple)) else s

    want = {_key(m.id): forms(m.string) for m in catalog if m.id and m.string}
    got = {_key(m.id): forms(m.string) for m in compiled if m.id}
    assert got == want, "messages.mo is stale: run make i18n-compile"


def _bare_english(html):
    """Text a person would read that isn't inside a Jinja tag or expression."""
    s = re.sub(r"\{#.*?#\}", " ", html, flags=re.S)
    s = re.sub(
        r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->",
        " ",
        s,
        flags=re.S | re.I,
    )
    literal_attrs = re.findall(
        r'\b(?:aria-label|title|placeholder|alt)="([^"{]*[A-Za-z][^"{]*)"', s
    )
    s = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", s, flags=re.S)
    s = re.sub(r"<[^>]*>", " ", s, flags=re.S)
    words = [w for w in re.split(r"\s+", s) if re.search(r"[A-Za-z]", w)]
    return words + literal_attrs


def test_the_chrome_is_converted():
    assert {"header_nav.html", "hamburger_menu.html", "tab_bar.html"} <= set(CONVERTED_TEMPLATES)


@pytest.mark.parametrize("name", CONVERTED_TEMPLATES)
def test_converted_templates_have_no_bare_english(name):
    with open(os.path.join(ROOT, "templates", name), encoding="utf-8") as f:
        left = _bare_english(f.read())
    assert not left, f"{name}: English outside _(): {left}"

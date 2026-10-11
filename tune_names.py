"""The name a tune is shown under, and the other names shown beside it.

One rule for every place a tune is named to a viewer — the search cards, the
previews, the logger's quick matches and the listening meter: the name you gave it
in your own tunebook leads, else the session's own name (this session's when the
view is scoped to one, else the name used by the session of yours that wins the
precedence), else the catalogue's. The other names go beside it, "also known as",
so two people looking at the same session see why their titles differ.

Names that are the same tune name spelt differently ("Dairy Maid", "The Dairy
Maid", "Dairy Maid, The") are not offered as alternatives: `name_key` folds the
article, accents, quotes, case and punctuation, and `display_names` drops any
candidate whose key is already shown.
"""

import re
import unicodedata

# Smart quotes -> ASCII, as the matcher's normalize_quotes (database.py) and the
# clients' normName fold them.
_QUOTES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‛": "'",
        "ʼ": "'",
        "′": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "″": '"',
        "«": '"',
        "»": '"',
    }
)
_LEADING_ARTICLE = re.compile(r"^(the|an|a)\s+")
_TRAILING_ARTICLE = re.compile(r",\s*(the|an|a)$")
_APOSTROPHE = re.compile(r"'")
_NOT_WORD = re.compile(r"[^a-z0-9]+")


def name_key(name):
    """The key two spellings of one tune name share: lower-case, accents and quotes
    folded, the article dropped whether it leads ("The Dairy Maid") or trails in
    thesession.org's way ("Dairy Maid, The"), apostrophes gone, other punctuation a
    space, spaces collapsed."""
    s = unicodedata.normalize("NFKD", (name or "").translate(_QUOTES))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()
    s = _TRAILING_ARTICLE.sub("", s)
    s = _LEADING_ARTICLE.sub("", s)
    # An apostrophe joins its word ("Kelly's" is "kellys"); any other mark is a space.
    return _NOT_WORD.sub(" ", _APOSTROPHE.sub("", s)).strip()


def display_names(
    catalogue,
    *,
    personal=None,
    this_session=None,
    your_session=None,
    matched=None,
    limit=2,
):
    """(display_name, other_names) for one tune.

    `catalogue` is thesession.org's name; `personal` yours (person_tune.name_alias);
    `this_session` the scoped session's (session_tune.alias), `your_session` the
    name used by the session of yours that wins the precedence; `matched` the name
    the search found the tune by, when that was none of the others.

    The title is the first of personal, the session's (this one's, else yours'),
    the catalogue's. The others, at most `limit`, are the matched name, then the
    session's, then the catalogue's, skipping any that reads as the title or as an
    earlier one once the article and the spelling are folded."""
    session_name = _clean(this_session) or _clean(your_session)
    chain = [_clean(personal), session_name, _clean(catalogue)]
    title = next((n for n in chain if n), catalogue or "")
    seen = {name_key(title)}
    others = []
    for n in (_clean(matched), session_name, _clean(catalogue)):
        if not n:
            continue
        k = name_key(n)
        if not k or k in seen:
            continue
        seen.add(k)
        others.append(n)
        if len(others) >= limit:
            break
    return title, others


def _clean(name):
    return name.strip() if isinstance(name, str) and name.strip() else None

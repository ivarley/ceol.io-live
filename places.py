"""Places and session paths (spec 055).

A session's path is exactly `{place}/{second}`. The first segment is the slug of a
`place` row — a town or metro (kind 'place') or a festival prefix (kind 'festival',
spec 056) — and `session.place_id` is the session's TOWN, whichever slug its path
uses. This module holds everything about that rule that needs the database:

- the place matcher the add-session sheet and thesession.org imports go through
  (`match_place`), with the normalization it compares by;
- the place-dependent clauses of the path rule (`validate_path_for_place`) — the
  character and two-segment checks are session_path.py's, which the clients mirror;
- resolution of `/sessions/<anything>` (`resolve_session_path`) and the
  `path_redirect` writer (`record_redirect`).

Every function takes a cursor and leaves committing to the caller.
"""

import re

# A session's second path segment under a festival prefix is a year; under a town it
# must not look like one (spec 055 "The rule").
_YEAR = re.compile(r"^\d{4}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID = re.compile(r"^\d+$")

# How many path_redirect hops resolution follows (a redirect whose target was itself
# renamed later). record_redirect collapses chains as it writes, so more than one hop
# only happens for rows written before a chain was collapsed.
MAX_REDIRECT_HOPS = 3

# Parent chains are short (town -> metro); this only stops a corrupt cycle looping.
_MAX_PARENT_DEPTH = 10


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def slugify(text):
    """The URL slug of a name. Byte-for-byte the `clean` step of the client's
    generatePath (frontend/src/addsession/logic.js), so a town created from the city
    text has the slug the sheet put in front of the path."""
    s = str(text if text is not None else "").lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


# fmt: off
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
# fmt: on
_US_STATE_BY_NAME = {name.lower(): name for name in US_STATES.values()}
_US_ABBREV_BY_NAME = {name: abbr for abbr, name in US_STATES.items()}

UNITED_STATES = "United States"

# Lowercased, periods dropped -> the stored long form. Deliberately short (spec 055):
# anything else is stored as entered.
_COUNTRY_ALIASES = {
    "us": UNITED_STATES,
    "usa": UNITED_STATES,
    "united states": UNITED_STATES,
    "united states of america": UNITED_STATES,
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "ireland": "Ireland",
    "éire": "Ireland",
    "eire": "Ireland",
}


def _clean(value):
    return re.sub(r"\s+", " ", str(value)).strip() if value is not None else ""


def normalize_country(country):
    """The stored long form of a country: aliases folded, otherwise as entered
    (whitespace tidied). Blank is None."""
    text = _clean(country)
    if not text:
        return None
    return _COUNTRY_ALIASES.get(text.lower().replace(".", ""), text)


def normalize_area(area, country=None):
    """The stored long form of an area. In the United States a state abbreviation
    or any casing of the name becomes the name; elsewhere `area` is free text (a
    county, a region) with no vocabulary to check against. Blank is None."""
    text = _clean(area)
    if not text:
        return None
    if normalize_country(country) == UNITED_STATES:
        key = text.replace(".", "")
        if key.upper() in US_STATES:
            return US_STATES[key.upper()]
        if text.lower() in _US_STATE_BY_NAME:
            return _US_STATE_BY_NAME[text.lower()]
    return text


def _same(a, b):
    return (a or "").casefold() == (b or "").casefold()


def _area_slug(area, country):
    """The suffix a disambiguated slug takes from an area: a US state's
    abbreviation (athens-ga), otherwise the area's own slug."""
    if country == UNITED_STATES and area in _US_ABBREV_BY_NAME:
        return _US_ABBREV_BY_NAME[area].lower()
    return slugify(area)


# ---------------------------------------------------------------------------
# Reading places
# ---------------------------------------------------------------------------

_PLACE_COLUMNS = "place_id, slug, name, kind, parent_place_id, area, country"


def _place_row(row):
    if not row:
        return None
    return {
        "place_id": row[0],
        "slug": row[1],
        "name": row[2],
        "kind": row[3],
        "parent_place_id": row[4],
        "area": row[5],
        "country": row[6],
    }


def get_place(cur, place_id):
    cur.execute(f"SELECT {_PLACE_COLUMNS} FROM place WHERE place_id = %s", (place_id,))
    return _place_row(cur.fetchone())


def get_place_by_slug(cur, slug):
    cur.execute(f"SELECT {_PLACE_COLUMNS} FROM place WHERE slug = %s", (slug,))
    return _place_row(cur.fetchone())


def place_ancestors(cur, place_id):
    """The place and every place above it, nearest first."""
    chain = []
    seen = set()
    current = place_id
    while (
        current is not None and current not in seen and len(chain) < _MAX_PARENT_DEPTH
    ):
        seen.add(current)
        place = get_place(cur, current)
        if not place:
            break
        chain.append(place)
        current = place["parent_place_id"]
    return chain


def place_contains(cur, container_id, town_id):
    """True when `container_id` is the town itself or one of its ancestors."""
    return any(p["place_id"] == container_id for p in place_ancestors(cur, town_id))


def place_summary(cur, place):
    """The wire shape of a place (spec 055 "API: the place object")."""
    if place is None:
        return None
    parent = (
        get_place(cur, place["parent_place_id"]) if place["parent_place_id"] else None
    )
    return {
        "place_id": place["place_id"],
        "slug": place["slug"],
        "name": place["name"],
        "kind": place["kind"],
        "area": place["area"],
        "country": place["country"],
        "parent": {"slug": parent["slug"], "name": parent["name"]} if parent else None,
    }


def path_prefixes(cur, town_id):
    """The first segments a session in this town may use, town first: the town and
    each place above it (spec 055 "Primary path")."""
    return [p["slug"] for p in place_ancestors(cur, town_id) if p["kind"] == "place"]


# ---------------------------------------------------------------------------
# The place matcher
# ---------------------------------------------------------------------------


def _slug_taken(cur, slug):
    cur.execute("SELECT 1 FROM place WHERE slug = %s", (slug,))
    return cur.fetchone() is not None


def disambiguated_slug(cur, base, area=None, country=None):
    """A free slug for a second place whose name slugs to a taken `base`: from the
    area if there is one (athens-ga), else from the country (athens-greece), then
    numbered if even that is taken. The first place keeps the bare slug."""
    suffix = _area_slug(area, country) if area else slugify(country) if country else ""
    candidate = f"{base}-{suffix}" if suffix else base
    if candidate != base and not _slug_taken(cur, candidate):
        return candidate
    n = 2
    while _slug_taken(cur, f"{candidate}-{n}"):
        n += 1
    return f"{candidate}-{n}"


def match_place(cur, city, area=None, country=None):
    """Find the town a session's city text means (spec 055 "Adding a session").

    Returns a dict:
      status  'match'     — `place` is the town;
              'new'       — no such town: create one at `slug`;
              'ambiguous' — a town with this slug exists somewhere else: ask "did you
                            mean `place`?"; a new one would take `slug` (already
                            disambiguated);
              'invalid'   — the city has nothing to make a slug from (`error`).
      name, area, country — the normalized values a new town would store.
    """
    name = _clean(city)
    country_n = normalize_country(country)
    area_n = normalize_area(area, country_n)
    base = slugify(name)
    result = {"name": name, "area": area_n, "country": country_n, "place": None}
    if not base:
        return {
            **result,
            "status": "invalid",
            "slug": None,
            "error": "City must contain a letter or number",
        }

    def same_geography(p):
        return _same(p["area"], area_n) and _same(p["country"], country_n)

    # The bare slug, and the slugs disambiguation would have given this town — so the
    # second Athens is found again at athens-greece, not offered as a third.
    candidates = [base]
    if area_n:
        candidates.append(f"{base}-{_area_slug(area_n, country_n)}")
    if country_n:
        candidates.append(f"{base}-{slugify(country_n)}")
    cur.execute(
        f"SELECT {_PLACE_COLUMNS} FROM place WHERE slug = ANY(%s)", (candidates,)
    )
    by_slug = {p["slug"]: p for p in map(_place_row, cur.fetchall())}
    for slug in candidates:
        p = by_slug.get(slug)
        if p and p["kind"] == "place" and same_geography(p):
            return {**result, "status": "match", "place": p, "slug": p["slug"]}

    # A town whose slug is not its name's (`sf` for "San Francisco").
    cur.execute(
        f"""SELECT {_PLACE_COLUMNS} FROM place
            WHERE kind = 'place' AND LOWER(name) = LOWER(%s) ORDER BY place_id""",
        (name,),
    )
    for p in map(_place_row, cur.fetchall()):
        if same_geography(p):
            return {**result, "status": "match", "place": p, "slug": p["slug"]}

    existing = by_slug.get(base)
    if existing is None:
        return {**result, "status": "new", "slug": base}
    suggested = disambiguated_slug(cur, base, area_n, country_n)
    if existing["kind"] != "place":
        # A festival holds the slug: there is no town to have meant.
        return {**result, "status": "new", "slug": suggested}
    return {**result, "status": "ambiguous", "place": existing, "slug": suggested}


def create_place(
    cur,
    slug,
    name,
    kind="place",
    parent_place_id=None,
    area=None,
    country=None,
    user_id=None,
):
    cur.execute(
        """
        INSERT INTO place (slug, name, kind, parent_place_id, area, country,
                           created_by_user_id, last_modified_user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING place_id
        """,
        (slug, name, kind, parent_place_id, area, country, user_id, user_id),
    )
    return get_place(cur, cur.fetchone()[0])


class PlaceAmbiguous(Exception):
    """The city names a town that exists with a different area or country."""

    def __init__(self, match):
        super().__init__(f"Did you mean {match['place']['name']}?")
        self.match = match


class PlaceError(ValueError):
    """A place choice that cannot be used, with a sentence for the form."""


def resolve_town(
    cur, city, area, country, place_id=None, place_new=False, user_id=None
):
    """The town a write means, creating it if need be. Shared by both write paths.

    `place_id` is the adder's pick from a "did you mean" (or any explicit choice);
    `place_new` is their "a new place" answer, which creates the town at the
    disambiguated slug. Otherwise the matcher decides, and an ambiguous match raises
    PlaceAmbiguous for the caller to turn into a 409.
    """
    if place_id not in (None, ""):
        try:
            place = get_place(cur, int(place_id))
        except (TypeError, ValueError):
            place = None
        if not place or place["kind"] != "place":
            raise PlaceError("That place no longer exists")
        return place, False

    match = match_place(cur, city, area, country)
    if match["status"] == "invalid":
        raise PlaceError(match["error"])
    if match["status"] == "match":
        return match["place"], False
    if match["status"] == "ambiguous" and not place_new:
        raise PlaceAmbiguous(match)
    place = create_place(
        cur,
        match["slug"],
        match["name"],
        "place",
        None,
        match["area"],
        match["country"],
        user_id,
    )
    return place, True


# ---------------------------------------------------------------------------
# The rule's place clauses
# ---------------------------------------------------------------------------


def validate_path_for_place(cur, path, session_type, town_place_id):
    """The clauses of the path rule that need the database (spec 055 "The rule").
    `path` has already passed normalize_session_path. Returns an error sentence, or
    None when the path is allowed."""
    if path.count("/") != 1:
        return (
            "Path must have exactly two parts, a place and a name, like austin/mueller"
        )
    prefix, second = path.split("/", 1)
    place = get_place_by_slug(cur, prefix)
    if place is None:
        return (
            f'The first part of the path must be a place; there is no place "{prefix}"'
        )
    if place["kind"] == "festival":
        if session_type != "festival":
            return f'"{prefix}" is a festival; only its years can live under it'
        if not _YEAR.match(second):
            return f'Under the festival "{prefix}" the second part of the path is a year, like {prefix}/2026'
        return None
    if session_type == "festival":
        return "A festival's path is its own name and a year, like oflahertys/2026"
    if _YEAR.match(second):
        return (
            "The second part of the path can't be a year; that shape is for festivals"
        )
    if town_place_id is None:
        return "The session needs a city before its path can be checked"
    if not place_contains(cur, place["place_id"], town_place_id):
        town = get_place(cur, town_place_id)
        return (
            f"The path must start with the session's town or an area containing it "
            f'({", ".join(path_prefixes(cur, town_place_id))}), not "{prefix}"'
            if town
            else f'The path must start with the session\'s town, not "{prefix}"'
        )
    return None


def rewrite_generated_prefix(cur, path, city, town):
    """When the path's first segment is the slug of the typed city but the town the
    matcher chose has another slug (`sf` for "San Francisco", `athens-ga` after a
    disambiguation) and nothing called that exists above the town, put the town's
    slug in front. That is the path the sheet would have generated had it known the
    town; the response carries the path actually saved."""
    prefix, second = path.split("/", 1)
    if prefix == town["slug"] or prefix != slugify(city):
        return path
    if prefix in path_prefixes(cur, town["place_id"]):
        return path
    return f"{town['slug']}/{second}"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _session_by_path(cur, path):
    cur.execute("SELECT session_id, path FROM session WHERE path = %s", (path,))
    return cur.fetchone()


def _alias(cur, path):
    """Spec 055 resolution step 3: `{P}/{name}` where P is a town or metro and
    exactly one session with that second segment lives in P or under it."""
    parts = path.split("/")
    if len(parts) != 2:
        return None
    place = get_place_by_slug(cur, parts[0])
    if place is None or place["kind"] != "place":
        return None
    cur.execute(
        "SELECT session_id, path, place_id FROM session "
        "WHERE split_part(path, '/', 2) = %s AND place_id IS NOT NULL",
        (parts[1],),
    )
    hits = [
        (row[0], row[1])
        for row in cur.fetchall()
        if row[1].count("/") == 1 and place_contains(cur, place["place_id"], row[2])
    ]
    return hits[0] if len(hits) == 1 else None


def _redirect(cur, path):
    """Spec 055 resolution step 4: follow path_redirect up to MAX_REDIRECT_HOPS."""
    current = path
    for _ in range(MAX_REDIRECT_HOPS):
        cur.execute(
            "SELECT to_path FROM path_redirect WHERE from_path = %s", (current,)
        )
        row = cur.fetchone()
        if not row:
            return None
        current = row[0]
        session = _session_by_path(cur, current)
        if session:
            return session
    return None


def _resolve_session(cur, path):
    """Steps 1, 3 and 4 for a would-be session path: (session_id, path, moved)."""
    row = _session_by_path(cur, path)
    if row:
        return row[0], row[1], False
    row = _alias(cur, path) or _redirect(cur, path)
    if row:
        return row[0], row[1], True
    return None


def resolve_session_path(cur, path):
    """Resolve `/sessions/<path>` (spec 055 "Resolution"). Returns None (404) or:

      {"kind": "session",  "session_id", "path", "moved"}
      {"kind": "instance", "session_id", "path", "moved", "instance": <date or id>}
      {"kind": "place",    "place"}

    `path` is the session's real path; `moved` means the request used an alias or a
    redirected path and should be answered with a 301 to the real one.
    """
    path = (path or "").strip("/")
    if not path:
        return None
    parts = path.split("/")

    if len(parts) == 1:
        row = _session_by_path(cur, path)  # pre-migration one-segment paths
        if row:
            return {
                "kind": "session",
                "session_id": row[0],
                "path": row[1],
                "moved": False,
            }
        place = get_place_by_slug(cur, path)
        if place:
            return {"kind": "place", "place": place}
        row = _redirect(cur, path)
        if row:
            return {
                "kind": "session",
                "session_id": row[0],
                "path": row[1],
                "moved": True,
            }
        return None

    found = _resolve_session(cur, path)
    if found:
        return {
            "kind": "session",
            "session_id": found[0],
            "path": found[1],
            "moved": found[2],
        }

    last = parts[-1]
    if _DATE.match(last) or _ID.match(last):
        found = _resolve_session(cur, "/".join(parts[:-1]))
        if found:
            return {
                "kind": "instance",
                "session_id": found[0],
                "path": found[1],
                "moved": found[2],
                "instance": last,
            }
    return None


def record_redirect(cur, old_path, new_path):
    """A session moved from `old_path` to `new_path`: write `old -> new`, repoint
    rows that led to `old` so chains collapse to one hop, and drop any row whose
    `from_path` is now a live path again (renaming back to an old path)."""
    if not old_path or not new_path or old_path == new_path:
        return
    cur.execute("DELETE FROM path_redirect WHERE from_path = %s", (new_path,))
    cur.execute(
        "UPDATE path_redirect SET to_path = %s WHERE to_path = %s", (new_path, old_path)
    )
    cur.execute(
        """
        INSERT INTO path_redirect (from_path, to_path) VALUES (%s, %s)
        ON CONFLICT (from_path) DO UPDATE SET to_path = EXCLUDED.to_path,
            created_date = (NOW() AT TIME ZONE 'UTC')
        """,
        (old_path, new_path),
    )

"""Canonical instrument vocabulary and normalization.

Single source of truth for the instrument list used across profile editing,
session attendance, and per-instrument tune status. Previously six divergent
hardcoded lists existed (Python constant, an attendance.js array, and four
template pickers) with inconsistent casing; everything now derives from here.

Values are stored in the DB verbatim in canonical Title Case and compared
case-insensitively. Anything not recognised as a canonical instrument or a known
alias is kept verbatim as an "Other" free-text instrument.
"""

# Canonical, display-ordered instrument list.
CANONICAL_INSTRUMENTS = [
    "Fiddle",
    "Flute",
    "Whistle",
    "Low Whistle",
    "Uilleann Pipes",
    "Concertina",
    "Button Accordion",
    "Piano Accordion",
    "Banjo",
    "Mandolin",
    "Harp",
    "Guitar",
    "Bouzouki",
    "Piano",
    "Bodhrán",
]

# Legacy / alternate spellings mapped onto canonical names. Keys are lowercase.
# Plain "accordion" resolves to "Button Accordion" (the trad default); those rows
# are worth an eyeball after the one-time migration.
_INSTRUMENT_ALIASES = {
    "tin whistle": "Whistle",
    "penny whistle": "Whistle",
    "accordion": "Button Accordion",
    "melodeon": "Button Accordion",
    "box": "Button Accordion",
    "bodhran": "Bodhrán",
    "uillean pipes": "Uilleann Pipes",
    "uileann pipes": "Uilleann Pipes",
    "pipes": "Uilleann Pipes",
    "tenor banjo": "Banjo",
}

_CANONICAL_BY_LOWER = {name.lower(): name for name in CANONICAL_INSTRUMENTS}


def normalize_instrument(value):
    """Map a raw instrument string to its canonical form.

    Returns the canonical Title-Case name when the value matches a canonical
    instrument or a known alias (case-insensitively); otherwise returns the
    trimmed original (an "Other" free-text instrument). Returns None for
    empty/blank input.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    key = trimmed.lower()
    if key in _CANONICAL_BY_LOWER:
        return _CANONICAL_BY_LOWER[key]
    if key in _INSTRUMENT_ALIASES:
        return _INSTRUMENT_ALIASES[key]
    return trimmed


def normalize_instruments(values):
    """Normalize a list of instrument strings.

    Drops blanks and de-dupes case-insensitively while preserving order.
    """
    out = []
    seen = set()
    for value in values or []:
        norm = normalize_instrument(value)
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def is_canonical_instrument(value):
    """True if the value is one of the canonical instruments (case-insensitive)."""
    return value is not None and value.strip().lower() in _CANONICAL_BY_LOWER

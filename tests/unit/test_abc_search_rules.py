"""Unit tests for the notation-search rules in database.py.

These are the single definition of "is this query notation, and what does it match?",
mirrored in SQL by abc_search_key() (schema/055_abc_search_index.sql) and in the browser
by frontend/src/shared/abcquery.js. If any of the three drifts, notation search silently
stops matching — so the contract is pinned here.
"""

import pytest

from database import (
    ABC_MIN_QUERY_LEN,
    abc_query_key,
    abc_search_terms,
    is_abc_friendly,
)

pytestmark = pytest.mark.unit


class TestAbcQueryKey:
    def test_drops_whitespace(self):
        assert abc_query_key("fdd cAA | B") == "fddcaa|b"

    def test_lowercases_so_octave_case_is_ignored(self):
        # ABC's case distinction marks octave; players type notes without caring.
        assert abc_query_key("GED") == abc_query_key("ged") == "ged"

    def test_drops_grace_notes_and_chord_symbols(self):
        # The reason "AAABc" can find a setting stored as {g}A{d}A{e}A "Am"{g}ABc.
        assert abc_query_key('{g}A{d}A{e}A "Am"{g}ABc') == "aaaabc"

    def test_drops_legacy_bang_line_breaks(self):
        assert abc_query_key("GED!BED") == "gedbed"

    def test_empty_and_none(self):
        assert abc_query_key("") == ""
        assert abc_query_key(None) == ""
        assert abc_query_key('"Am"') == ""


class TestIsAbcFriendly:
    @pytest.mark.parametrize("q", ["fdd cAA | B", "GED", "|:E2BE dEBE:|", "^c3d", "(3EEE"])
    def test_accepts_notation(self, q):
        assert is_abc_friendly(q)

    @pytest.mark.parametrize("q", ["Drowsy Maggie", "The Kesh", "reel", "silver spear"])
    def test_rejects_names(self, q):
        assert not is_abc_friendly(q)

    def test_note_letter_words_are_accepted_and_that_is_fine(self):
        # "cabbage" is all note letters. Mixed mode BLENDS notation with name matches and
        # ranks it below them, so a false positive costs extra rows, never a wrong answer.
        assert is_abc_friendly("cabbage")


class TestAbcSearchTerms:
    def test_mixed_blends_a_note_query(self):
        use_abc, pattern = abc_search_terms("fdd cAA | B")
        assert use_abc and pattern == "%fddcaa|b%"

    def test_mixed_ignores_a_name_query(self):
        assert abc_search_terms("Drowsy Maggie") == (False, None)

    def test_mixed_needs_the_minimum_length(self):
        # Shorter than this matches nearly the whole catalog, and pg_trgm cannot use the
        # trigram index below 3 characters either.
        assert ABC_MIN_QUERY_LEN == 3
        assert abc_search_terms("ab") == (False, None)
        assert abc_search_terms("abc")[0] is True

    def test_explicit_abc_mode_honors_anything_typed(self):
        use_abc, pattern = abc_search_terms("ab", "abc")
        assert use_abc and pattern == "%ab%"

    def test_name_mode_never_searches_notation(self):
        assert abc_search_terms("fdd cAA", "name") == (False, None)

    def test_nothing_left_to_match_on(self):
        assert abc_search_terms('"Am"', "abc") == (False, None)

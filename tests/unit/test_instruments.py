"""
Unit tests for instruments.py - the canonical instrument vocabulary and
normalization used app-wide (profile editing, attendance, per-instrument tune
status).
"""

import pytest

from instruments import (
    CANONICAL_INSTRUMENTS,
    normalize_instrument,
    normalize_instruments,
    is_canonical_instrument,
)


@pytest.mark.unit
class TestNormalizeInstrument:
    def test_canonical_passthrough(self):
        assert normalize_instrument("Fiddle") == "Fiddle"
        assert normalize_instrument("Button Accordion") == "Button Accordion"

    def test_casing_is_canonicalized(self):
        assert normalize_instrument("fiddle") == "Fiddle"
        assert normalize_instrument("BANJO") == "Banjo"
        assert normalize_instrument("  tin whistle  ") == "Whistle"

    def test_known_aliases(self):
        assert normalize_instrument("tin whistle") == "Whistle"
        assert normalize_instrument("penny whistle") == "Whistle"
        assert normalize_instrument("accordion") == "Button Accordion"
        assert normalize_instrument("melodeon") == "Button Accordion"
        assert normalize_instrument("bodhran") == "Bodhrán"
        assert normalize_instrument("uillean pipes") == "Uilleann Pipes"

    def test_unknown_kept_verbatim_as_free_text(self):
        assert normalize_instrument("electric_guitar") == "electric_guitar"
        assert normalize_instrument("Kazoo") == "Kazoo"
        # "vocals" was dropped from the canonical list -> preserved as free text
        assert normalize_instrument("vocals") == "vocals"

    def test_blank_and_none(self):
        assert normalize_instrument(None) is None
        assert normalize_instrument("") is None
        assert normalize_instrument("   ") is None


@pytest.mark.unit
class TestNormalizeInstruments:
    def test_dedupes_case_insensitively_preserving_order(self):
        assert normalize_instruments(["fiddle", "Fiddle", "FIDDLE"]) == ["Fiddle"]
        assert normalize_instruments(["banjo", "tin whistle", "Banjo"]) == ["Banjo", "Whistle"]

    def test_merges_aliases_to_one(self):
        assert normalize_instruments(["accordion", "button accordion"]) == ["Button Accordion"]

    def test_drops_blanks(self):
        assert normalize_instruments(["", "  ", "fiddle", None]) == ["Fiddle"]

    def test_empty(self):
        assert normalize_instruments([]) == []
        assert normalize_instruments(None) == []


@pytest.mark.unit
class TestIsCanonicalInstrument:
    def test_true_for_canonical(self):
        assert is_canonical_instrument("Fiddle")
        assert is_canonical_instrument("fiddle")  # case-insensitive

    def test_false_for_free_text(self):
        assert not is_canonical_instrument("Kazoo")
        assert not is_canonical_instrument("tin whistle")  # alias, not canonical itself
        assert not is_canonical_instrument(None)


@pytest.mark.unit
def test_canonical_list_shape():
    # Guards against accidental dupes / casing drift in the source list.
    assert len(CANONICAL_INSTRUMENTS) == len(set(CANONICAL_INSTRUMENTS))
    assert "Whistle" in CANONICAL_INSTRUMENTS
    assert "Low Whistle" in CANONICAL_INSTRUMENTS
    assert "Vocals" not in CANONICAL_INSTRUMENTS
    assert "Tin Whistle" not in CANONICAL_INSTRUMENTS

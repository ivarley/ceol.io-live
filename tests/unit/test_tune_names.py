"""The one rule for a tune's displayed name and the names shown beside it
(tune_names.py)."""

from tune_names import display_names, name_key


class TestNameKey:
    def test_the_article_is_dropped_leading_and_trailing(self):
        assert (
            name_key("Dairy Maid")
            == name_key("The Dairy Maid")
            == name_key("Dairy Maid, The")
        )
        assert name_key("An Buachaill Caol Dubh") == name_key("Buachaill Caol Dubh")
        assert name_key("A Fig For A Kiss") == name_key("Fig For A Kiss, A")

    def test_accents_quotes_case_and_punctuation_fold(self):
        assert name_key("Kelly’s Castle") == name_key("kellys castle")
        assert name_key("Slán le hÉirinn") == name_key("slan le heirinn")
        assert name_key("  Cooley's   Reel ") == "cooleys reel"

    def test_different_names_stay_different(self):
        assert name_key("Cooley's") != name_key("Cooley's Reel")
        assert name_key("Frieze Breeches (Hyde Park)") != name_key(
            "Frieze Breeches, The"
        )
        assert name_key("") == ""


class TestDisplayNames:
    def test_your_own_name_leads_and_the_others_follow(self):
        assert display_names(
            "Skillet Pot", personal="May Day", your_session="First Of May"
        ) == ("May Day", ["First Of May", "Skillet Pot"])

    def test_the_sessions_name_leads_when_you_have_none(self):
        assert display_names("Skillet Pot", your_session="First Of May") == (
            "First Of May",
            ["Skillet Pot"],
        )
        assert display_names("Skillet Pot") == ("Skillet Pot", [])

    def test_this_session_beats_the_session_that_wins_the_precedence(self):
        assert display_names(
            "Frieze Breeches, The",
            this_session="Frieze Breeches (Hyde Park)",
            your_session="Frieze Breeches (Riverside)",
        ) == ("Frieze Breeches (Hyde Park)", ["Frieze Breeches, The"])

    def test_a_spelling_of_the_title_is_not_an_alternative(self):
        assert display_names("Dairy Maid, The", personal="Dairy Maid") == (
            "Dairy Maid",
            [],
        )
        assert display_names(
            "Connaughtman's Rambles, The",
            personal="Rambling Connaughtman",
            this_session="The Rambling Connaughtman",
        ) == ("Rambling Connaughtman", ["Connaughtman's Rambles, The"])

    def test_the_matched_name_comes_first_and_the_list_is_capped(self):
        assert display_names(
            "Skillet Pot",
            personal="May Day",
            your_session="First Of May",
            matched="Mayday",
        ) == ("May Day", ["Mayday", "First Of May"])
        assert display_names(
            "Skillet Pot", your_session="First Of May", matched="Skillet Pot"
        ) == (
            "First Of May",
            ["Skillet Pot"],
        )

    def test_blank_names_are_ignored(self):
        assert display_names(
            "Skillet Pot", personal="  ", this_session="", matched=None
        ) == ("Skillet Pot", [])

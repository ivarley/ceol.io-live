"""analysis.form: a setting's repeats written out, as played."""

from lab.analysis.form import expand, played_form, split_bars


def _played(abc):
    _, bars = split_bars(abc)
    order, starts = expand(bars)
    return [bars[i].text.strip() for i in order], starts


def test_a_repeated_part_then_one_written_once():
    assert _played("|:A|B|C|D:|E|F|G|H|") == (list("ABCDABCDEFGH"), [0, 4, 8])


def test_two_repeated_parts_and_the_double_colon():
    both = (list("ABCDABCDEFGHEFGH"), [0, 4, 8, 12])
    assert _played("|:A|B|C|D:|:E|F|G|H:|") == both
    assert _played("A|B|C|D::E|F|G|H:|") == both


def test_first_and_second_endings():
    played, starts = _played("|:A|B|C|1D:|2d||:E|F|G|1H:|2h|]")
    assert played == list("ABCDABCdEFGHEFGh") and starts == [0, 4, 8, 12]
    assert _played("|:A|B|C|[1D:|[2d|]")[0] == list("ABCDABCd")


def test_a_double_bar_without_repeats_is_a_new_section():
    assert _played("A|B|C|D||E|F|G|H|]") == (list("ABCDEFGH"), [0, 4])


def test_the_played_form_is_on_a_grid_of_eighths_with_its_bars():
    f = played_form("|:ABcd efga|bagf edcB|ABcd efga|bagf e2e2:|\n"
                    "|:a2ab agfe|dfaf gfed|a2ab agfe|1dfed e4:|2dfed e2ef||", key="D")
    assert f.length == 128
    assert f.bar_starts == list(range(0, 128, 8))
    assert f.section_starts == [0, 32, 64, 96]

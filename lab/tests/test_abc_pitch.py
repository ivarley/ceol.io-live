from fractions import Fraction

from lab.corpus.abc_pitch import (
    interval_sequence,
    key_signature,
    ngrams,
    parse_abc,
    pitch_sequence,
    to_abc_letters,
)


def pitches(abc, **kw):
    return pitch_sequence(parse_abc(abc, **kw))


def test_key_signatures():
    assert key_signature("D") == {"F": 1, "C": 1}
    assert key_signature("G") == {"F": 1}
    assert key_signature("Ador") == {"F": 1}          # A dorian = 1 sharp
    assert key_signature("Adorian") == {"F": 1}
    assert key_signature("Amix") == {"F": 1, "C": 1}  # A mixolydian = 2 sharps
    assert key_signature("Em") == {"F": 1}
    assert key_signature("Eminor") == {"F": 1}
    assert key_signature("Bm") == {"F": 1, "C": 1}
    assert key_signature("F") == {"B": -1}
    assert key_signature("Dmajor") == {"F": 1, "C": 1}
    assert key_signature("Gmixolydian") == {}
    assert key_signature("Edorian") == {"F": 1, "C": 1}
    assert key_signature("Bb") == {"B": -1, "E": -1}
    assert key_signature("none") == {}
    assert key_signature("HP") == {}


def test_plain_scale_in_c():
    assert pitches("CDEFGABc") == [60, 62, 64, 65, 67, 69, 71, 72]


def test_key_signature_applies():
    # D major: F and C are sharp
    assert pitches("DEFG", key="D") == [62, 64, 66, 67]
    assert pitches("K:D\nDEFG") == [62, 64, 66, 67]
    assert pitches("[K:D]DEFG") == [62, 64, 66, 67]
    # dorian
    assert pitches("EFGA", key="Edorian") == [64, 66, 67, 69]


def test_explicit_accidental_persists_to_bar_end_only():
    # =F cancels the key's sharp for the rest of the bar, same octave only
    out = pitches("F =F F f | F", key="D")
    assert out == [66, 65, 65, 78, 66]


def test_octave_marks():
    assert pitches("C, C c c'") == [48, 60, 72, 84]
    assert pitches("C,, c''") == [36, 96]


def test_durations_in_eighths():
    notes = parse_abc("A A2 A/ A/2 A3/2 A//", unit_length="1/8")
    assert [n.eighths for n in notes] == [
        Fraction(1), Fraction(2), Fraction(1, 2), Fraction(1, 2), Fraction(3, 2), Fraction(1, 4)]
    # Not the ABC standard's L:1/16 for a meter under 3/4: thesession.org
    # writes 2/4 in eighths and the dump carries no L: line.
    notes = parse_abc("A A2", meter="2/4")
    assert [n.eighths for n in notes] == [Fraction(1), Fraction(2)]
    notes = parse_abc("L:1/16\nA")
    assert notes[0].eighths == Fraction(1, 2)


def test_ornaments_and_decorations_are_stripped():
    assert pitches("~A !trill!B +fermata+c {d}e \"G\"f .g Hd Ta") == [69, 71, 72, 76, 77, 79, 74, 81]


def test_chords_take_first_note():
    assert pitches("[CEG]2 D") == [60, 62]


def test_rests_break_the_sequence():
    assert pitches("A z B x2 c") == [69, None, 71, None, 72]
    assert interval_sequence([69, None, 71, 72]) == [None, 1]


def test_repeats_bars_endings_tuplets_ties_slurs():
    abc = "|:A B|1 c d:|2 (3efg (a-a) e>f|]"
    assert pitches(abc) == [69, 71, 72, 74, 76, 77, 79, 81, 81, 76, 77]


def test_body_line_starting_with_note_and_colon_is_not_a_header():
    # 'A:|' at line start is notes + repeat, not a header field
    assert pitches("A:|") == [69]


def test_comments_and_continuations():
    assert pitches("A B % here be dragons\nc\\\nd") == [69, 71, 72, 74]


def test_header_lines_ignored_except_k_l_m():
    abc = "X:1\nT:Cooley's\nR:reel\nM:4/4\nL:1/8\nK:Edor\nEB{c}BA B2 EB|"
    assert pitches(abc)[:4] == [64, 71, 71, 69]


def test_interval_and_ngrams():
    iv = interval_sequence([60, 62, 64, 65, 67, 69])
    assert iv == [2, 2, 1, 2, 2]
    assert ngrams(iv, n=3) == [(2, 2, 1), (2, 1, 2), (1, 2, 2)]
    assert interval_sequence([60, 84]) == [12]  # clipped


def test_to_abc_letters_roundtrip_shape():
    assert to_abc_letters([60, 62, 66, 72, 84, None]) == "C D ^F c c' z"

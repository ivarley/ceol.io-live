"""The app menu survives theme.css's :visited rule (spec 052 §B8).

theme.css carries `a:visited { color: var(--link-color) }` so a visited link does not
fall back to the browser's purple. At (0,1,1) that beats any bare single-class
selector, so a component that colours a link with one class loses to it — but only
for destinations the viewer has actually been to.

That is what makes this worth a test rather than a careful reading. The menu looked
correct in every automation profile, in every screenshot taken by a fresh browser, and
in getComputedStyle (which reports the UNVISITED colour on purpose, for privacy). It
was wrong only in a browser with real history, where the items went accent green one
at a time as the app got used, and Log Out quietly stopped being red.

So: anything in the menu that sets a colour either states :visited too, or wins on
specificity without it.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CSS = ROOT / "static" / "css" / "hamburger_menu.css"
THEME = ROOT / "static" / "css" / "theme.css"

# One rule: "selector list { body }", non-greedy so nested braces do not swallow it.
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def _rules():
    # Comments go first. The explanatory comment in hamburger_menu.css quotes the very
    # rule it defends against, braces and all — left in, the regex below reads that
    # quote as a rule and the surrounding text as a selector, and the check silently
    # stops finding anything. It passed against deliberately broken CSS that way.
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.S)
    for selectors, body in _RULE.findall(css):
        yield [s.strip() for s in selectors.split(",") if s.strip()], body


def _b_specificity(selector):
    """The 'b' column: classes, attribute selectors and pseudo-CLASSES.

    Pseudo-classes count, which is the whole point — `.hamburger-item:hover` is
    (0,2,0) and already beats a:visited (0,1,1) without stating :visited itself.
    Pseudo-ELEMENTS (::before) belong to the 'c' column, so they are excluded.
    """
    without_elements = re.sub(r"::[\w-]+", "", selector)
    return (
        len(re.findall(r"\.[A-Za-z_-][\w-]*", without_elements))
        + len(re.findall(r"\[[^\]]*\]", without_elements))
        + len(re.findall(r"(?<!:):[A-Za-z-]+", without_elements))
    )


class TestTheVisitedRuleStillExistsToDefendAgainst:
    def test_theme_still_colours_visited_links(self):
        # If this ever goes away the guards below are dead weight, and the comments
        # explaining them become misleading. Better to be told.
        assert re.search(
            r"a:visited\s*\{[^}]*color", THEME.read_text()
        ), "theme.css no longer colours a:visited — the menu's :visited guards can go"


class TestEveryColouredMenuRuleBeatsIt:
    def test_no_single_class_menu_selector_sets_a_colour_without_visited(self):
        offenders = []
        for selectors, body in _rules():
            if not re.search(r"(^|[;\s])color\s*:", body):
                continue
            # Anchors only. .hamburger-who is a <p> — it cannot be :visited, and the
            # menu marks the current page with aria-current alone, no colour.
            menu = [s for s in selectors if ".hamburger-item" in s]
            if not menu:
                continue
            # A selector carrying :visited defends the whole list it appears in.
            if any(":visited" in s for s in selectors):
                continue
            # ...as does one that already out-specifies (0,1,1) on its own.
            if all(_b_specificity(s) >= 2 for s in menu):
                continue
            weak = [s for s in menu if _b_specificity(s) < 2]
            offenders.append(f"{', '.join(selectors)} -> color, weakest: {weak}")

        assert not offenders, (
            "These colour a menu link with a single class, which loses to theme.css's "
            "a:visited (0,1,1) — so the rule applies until the viewer visits that "
            "destination, and then silently stops. Add a `:visited` selector to the "
            "list:\n  " + "\n  ".join(offenders)
        )

    def test_the_two_that_were_actually_wrong_are_covered(self):
        # The resting colour and Log Out. Named explicitly so a refactor that drops
        # one of them fails here with the reason, not just on the general rule above.
        css = CSS.read_text()
        assert ".hamburger-item:visited" in css
        assert ".hamburger-item-out:visited" in css

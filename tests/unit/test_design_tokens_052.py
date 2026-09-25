"""Design tokens stay generated from one source (spec 052 §B6).

`design/tokens.json` is the palette, the scales and the z-order. `scripts/build_tokens.py`
renders it into the `:root` block of `static/css/theme.css` and into `design/Tokens.swift`.

The reason this is a test and not a convention: a colour that drifts between the two
clients breaks nothing. Nothing throws, no page 500s, no build fails — the app just
stops matching itself, on a device nobody is looking at while they edit the CSS. The
only way that gets noticed is if something fails when the generated files stop agreeing
with their source.

So the check is literally "regenerate and compare".
"""

import importlib.util
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TOKENS = ROOT / "design" / "tokens.json"
CSS = ROOT / "static" / "css" / "theme.css"
SWIFT = ROOT / "design" / "Tokens.swift"


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_tokens", ROOT / "scripts" / "build_tokens.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build():
    return _builder()


@pytest.fixture(scope="module")
def tokens():
    return json.loads(TOKENS.read_text())


class TestGeneratedFilesMatchTheirSource:
    def test_theme_css_is_what_the_generator_would_write(self, build):
        expected = build.splice_css(CSS.read_text(), build.render_css(build.load()))
        assert CSS.read_text() == expected, (
            "static/css/theme.css has drifted from design/tokens.json. "
            "Edit the JSON, then run: python scripts/build_tokens.py"
        )

    def test_the_swift_enum_is_what_the_generator_would_write(self, build):
        assert (
            SWIFT.exists()
        ), "design/Tokens.swift is missing; run scripts/build_tokens.py"
        assert SWIFT.read_text() == build.render_swift(build.load()), (
            "design/Tokens.swift has drifted from design/tokens.json. "
            "Edit the JSON, then run: python scripts/build_tokens.py"
        )

    def test_the_check_flag_agrees(self, build, monkeypatch):
        # The same comparison the script offers to CI, exercised through its own entry
        # point rather than re-implemented here.
        monkeypatch.setattr("sys.argv", ["build_tokens.py", "--check"])
        assert build.main() == 0


class TestTheGeneratedCssIsStillUsable:
    """A generator that produced valid-looking but wrong CSS would pass the tests above,
    because they only compare it against itself."""

    def test_every_token_in_the_json_reaches_the_stylesheet(self, tokens):
        css = CSS.read_text()
        start = css.index("BEGIN generated tokens")
        stop = css.index("END generated tokens")
        block = css[start:stop]
        declared = dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))
        for group in tokens["groups"]:
            for tok in group["tokens"]:
                if "raw" in tok:
                    assert tok["raw"] in block
                    continue
                assert (
                    tok["name"] in declared
                ), f"--{tok['name']} never reached theme.css"
                assert " ".join(declared[tok["name"]].split()) == " ".join(
                    tok["value"].split()
                )

    def test_the_block_sits_inside_the_root_rule(self):
        css = CSS.read_text()
        root = css.index(":root {")
        begin = css.index("BEGIN generated tokens")
        end = css.index("END generated tokens")
        close = css.index("\n  }", root)
        assert root < begin < end < close, "the generated block escaped the :root rule"

    def test_the_variables_the_app_leans_on_are_present(self):
        # A spot check with teeth: these are named in components that would look
        # broken, not merely unstyled, if the variable vanished.
        css = CSS.read_text()
        for name in (
            "--primary",
            "--bg-color",
            "--text-color",
            "--border-color",
            "--site-header-h",  # every sticky offset on the session page
            "--z-toast",
            "--z-sheet-content",
            "--sp-2",
            "--r-sm",
        ):
            assert f"{name}:" in css, f"{name} is missing from theme.css"


class TestTheSwiftSideIsHonest:
    def test_colors_carry_their_source_hex(self, tokens):
        # Read the expected hex from the source rather than naming one here: this
        # assertion pinned the old blue accent and had to be rewritten the day the
        # palette went green, which is exactly the rot it was meant to detect.
        swift = SWIFT.read_text()
        assert "static let primary = Color(" in swift
        primary = next(
            t["value"]
            for g in tokens["groups"]
            for t in g["tokens"]
            if t["name"] == "primary"
        )
        assert (
            f"// {primary}" in swift
        ), "the hex a designer would search for should survive into Swift"

    def test_web_only_values_are_listed_rather_than_silently_dropped(self):
        # Font stacks, multi-part shadows and rgba() scrims have no useful Swift form.
        # Dropping them quietly would leave somebody hunting for a token that the
        # generator had decided not to emit.
        swift = SWIFT.read_text()
        for name in ("font-family-sans-serif", "shadow-lg", "scrim"):
            assert name in swift, f"{name} should be named in the not-represented note"

    def test_css_breakpoints_do_not_become_swift_constants(self):
        # iOS has size classes; it does not branch on pixel widths. --breakpoint-xs is
        # also literally `0`, which would otherwise be read as a z-order.
        swift = SWIFT.read_text()
        assert "static let breakpoint" not in swift

    def test_z_order_stays_ordered(self, tokens):
        # The tiers only mean anything if the numbers keep their relative order; a
        # toast under a sheet is the kind of thing nobody notices until a demo.
        values = {
            t["name"]: int(t["value"])
            for g in tokens["groups"]
            for t in g["tokens"]
            if t["name"].startswith("z-") and t["value"].lstrip("-").isdigit()
        }
        assert (
            values["z-base"] < values["z-bootstrap-modal"] < values["z-modal-overlay"]
        )
        assert (
            values["z-modal-content"] < values["z-header"]
        ), "modals sit BELOW the header on purpose, so the menu stays reachable"
        assert (
            values["z-header"] < values["z-sheet-content"]
        ), "a full-screen sheet carries its own chrome and must cover the header"
        assert values["z-sheet-content"] < values["z-search-dropdown"]
        assert max(values.values()) == values["z-toast"], "toasts are the top layer"


# ---------------------------------------------------------------------------
# accent fill vs accent text (spec 052 §B10)
# ---------------------------------------------------------------------------

CSS_DIRS = ("static/css", "frontend/src", "templates")
CSS_SUFFIXES = (".css", ".svelte", ".html")

# An accent BACKGROUND comes from a fill token; accent TEXT stays on --primary.
# They are not interchangeable and the reason is measurable: white on --primary
# is 2.54:1, which is under AA and is what made the chips look washed out.
_ACCENT_BG = re.compile(
    r"(?:background|background-color|accent-color)\s*:\s*[^;{}]*"
    r"var\(--(?:primary|primary-dark|modal-primary-dark)[,)]"
)


def _stylesheets():
    for d in CSS_DIRS:
        for path in (ROOT / d).rglob("*"):
            if path.suffix in CSS_SUFFIXES and "node_modules" not in str(path):
                yield path


def _token(tokens, name):
    return next(
        t["value"]
        for g in tokens["groups"]
        for t in g["tokens"]
        if t.get("name") == name
    )


def _luminance(hex_colour):
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    parts = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class TestTheAccentFillIsTheLogoGreen:
    def test_the_fill_is_the_colour_the_logo_is_drawn_in(self, tokens):
        # logo3-1.png is one flat colour. The fill is that colour, so a selected
        # chip and the wordmark in the header are the same green.
        assert _token(tokens, "primary-fill") == _token(tokens, "logo-green")

    def test_white_on_the_fill_passes_AA(self, tokens):
        fill = _token(tokens, "primary-fill")
        ratio = _contrast(fill, "#ffffff")
        assert ratio >= 4.5, f"white on {fill} is {ratio:.2f}:1"

    def test_the_hover_is_darker_than_the_fill_and_still_visible(self, tokens):
        fill, hover = _token(tokens, "primary-fill"), _token(tokens, "primary-fill-hover")
        assert _luminance(hover) < _luminance(fill), (
            "--primary-fill-hover has to be darker than --primary-fill, or hovering "
            "a filled control brightens it. This is why --primary-dark is not used "
            "here: it is lighter than the fill."
        )
        bg = _token(tokens, "bg-color")
        assert _contrast(hover, bg) >= 3.0, "a hovered control must not sink into the page"

    def test_the_accent_text_colour_stays_light_enough_to_read(self, tokens):
        # The other half of the split. --primary is text, so it is measured against
        # the page rather than against white, and the fill would fail this badly
        # (3.71:1) — which is why one token cannot do both jobs.
        assert _contrast(_token(tokens, "primary"), _token(tokens, "bg-color")) >= 4.5


class TestNoAccentBackgroundUsesTheTextToken:
    """The rule that keeps the two apart, checked where it is actually broken:
    in the stylesheets, not in the token file."""

    def test_no_stylesheet_paints_a_background_with_the_text_accent(self):
        offenders = []
        for path in _stylesheets():
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if _ACCENT_BG.search(line):
                    rel = path.relative_to(ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        assert not offenders, (
            "These paint a surface with --primary (or its hover darks), which is the "
            "accent TEXT colour — white on it is 2.54:1, under AA. Use --primary-fill "
            "/ --primary-fill-hover for anything that sits behind white text:\n  "
            + "\n  ".join(offenders)
        )

#!/usr/bin/env python3
"""Generate the app's design tokens from design/tokens.json (spec 052 §B6).

Writes two things from one source:

  * the ``:root`` block in ``static/css/theme.css``, between the BEGIN/END markers
  * ``design/Tokens.swift``, the same values as a Swift enum

The point is that a native client and the web share a palette without anybody
hand-syncing two files. Colours drift silently — nothing fails, the two clients
just stop matching — so the check is a test rather than a convention:
``tests/unit/test_design_tokens_052.py`` regenerates and compares.

Why the CSS is written back INTO theme.css rather than emitted as its own file:
theme.css is loaded by every template plus the live logger's separate shell, and a
new stylesheet would have to be added to each of them in the right order. Rewriting
a marked region changes nothing about how the CSS loads.

Usage:
    python scripts/build_tokens.py           # write the files
    python scripts/build_tokens.py --check   # exit 1 if they are out of date
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design" / "tokens.json"
CSS = ROOT / "static" / "css" / "theme.css"
SWIFT = ROOT / "design" / "Tokens.swift"

BEGIN = "  /* BEGIN generated tokens — see design/tokens.json */"
END = "  /* END generated tokens */"

BANNER = "Generated from design/tokens.json by scripts/build_tokens.py. Do not edit."

# Values a Swift enum can carry usefully. A CSS font stack, a shadow triple or a
# media breakpoint is not a colour or a number, and pretending otherwise would put
# strings in the Swift file that no Swift code could use.
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
PX = re.compile(r"^(-?\d+(?:\.\d+)?)px$")
SECONDS = re.compile(r"^(\d+(?:\.\d+)?)s$")
PLAIN_NUMBER = re.compile(r"^-?\d+$")


def load():
    return json.loads(TOKENS.read_text())


def _wrap(text: str, indent: str, width: int = 88) -> list[str]:
    """Comment text as one or more CSS comment lines."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(indent) + len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) == 1:
        return [f"{indent}/* {lines[0]} */"]
    out = [f"{indent}/* {lines[0]}"]
    out += [f"{indent}   {ln}" for ln in lines[1:-1]]
    out.append(f"{indent}   {lines[-1]} */")
    return out


def render_css(data) -> str:
    ind = "    "
    out = [BEGIN, f"{ind}/* {BANNER} */"]
    for gi, group in enumerate(data["groups"]):
        if group.get("comment"):
            out.append("")
            out.append(f"{ind}/* ===== {group['comment']} ===== */")
        elif gi:
            out.append("")
        for tok in group["tokens"]:
            if tok.get("comment"):
                out += _wrap(tok["comment"], ind)
            if "raw" in tok:
                out.append(f"{ind}{tok['raw']};")
            else:
                out.append(f"{ind}--{tok['name']}: {tok['value']};")
    out.append(END)
    return "\n".join(out)


# CSS breakpoints describe the web's responsive layout. iOS has size classes and
# does not branch on pixel widths, so emitting them as Swift constants would invite
# somebody to write the wrong thing with them. (--breakpoint-xs is also literally
# `0`, which otherwise parses as a z-order.)
SKIP_PREFIXES = ("breakpoint-",)


def _swift_value(name: str, value: str):
    """(kind, literal) for the values Swift can hold, or None to skip."""
    if name.startswith(SKIP_PREFIXES):
        return None
    v = value.strip()
    if HEX.match(v):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        pairs = (h[0:2], h[2:4], h[4:6])
        r, g, b = (int(pair, 16) / 255 for pair in pairs)
        return "color", f"Color(red: {r:.4f}, green: {g:.4f}, blue: {b:.4f})  // {v}"
    m = PX.match(v)
    if m:
        return "length", f"CGFloat({m.group(1)})"
    m = SECONDS.match(v)
    if m:
        return "duration", f"Double({m.group(1)})"
    if PLAIN_NUMBER.match(v):
        return "layer", f"Double({v})"
    return None


def _camel(name: str) -> str:
    head, *rest = name.split("-")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def render_swift(data) -> str:
    buckets: dict[str, list[str]] = {
        "color": [],
        "length": [],
        "duration": [],
        "layer": [],
    }
    skipped: list[str] = []
    for group in data["groups"]:
        for tok in group["tokens"]:
            if "raw" in tok:
                continue
            got = _swift_value(tok["name"], tok["value"])
            if not got:
                skipped.append(tok["name"])
                continue
            kind, literal = got
            if tok.get("comment"):
                buckets[kind].append(f"    /// {tok['comment']}")
            buckets[kind].append(f"    static let {_camel(tok['name'])} = {literal}")

    lines = [
        "// " + BANNER,
        "//",
        "// The web reads these from CSS custom properties; this is the same source",
        "// rendered for Swift, so the two clients cannot drift apart by hand.",
        "",
        "import SwiftUI",
        "",
        "public enum CeolTokens {",
    ]
    for kind, title in (
        ("color", "Colors"),
        ("length", "Lengths — radii, spacing, fixed heights"),
        ("duration", "Motion"),
        ("layer", "Z-order"),
    ):
        if not buckets[kind]:
            continue
        lines += ["", f"    // MARK: - {title}", ""]
        lines += buckets[kind]
    lines.append("}")
    if skipped:
        lines += [
            "",
            "// Not represented here, because Swift has no useful equivalent: font stacks,",
            "// multi-part shadows, rgba() scrims and CSS breakpoints. They stay CSS-only.",
            "//",
        ]
        names = sorted(skipped)
        chunks = [names[i:][:6] for i in range(0, len(names), 6)]
        lines += ["// " + ", ".join(chunk) for chunk in chunks]
    return "\n".join(lines) + "\n"


def splice_css(css_text: str, block: str) -> str:
    if BEGIN in css_text:
        start = css_text.index(BEGIN)
        end = css_text.index(END) + len(END)
        return css_text[:start] + block + css_text[end:]
    # First run: replace the body of the existing :root { ... } rule.
    m = re.search(r"(:root \{\n)(.*?)(\n *\})", css_text, re.S)
    if not m:
        raise SystemExit("theme.css: could not find the :root block to replace")
    # Plain names in the slices: black wants `x[a() :]` where flake8 wants `x[a():]`,
    # and neither is worth a config change.
    body_start, body_end = m.start(2), m.end(2)
    return css_text[:body_start] + block + css_text[body_end:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify only; do not write")
    args = ap.parse_args()

    data = load()
    css_block = render_css(data)
    swift = render_swift(data)
    new_css = splice_css(CSS.read_text(), css_block)

    if args.check:
        stale = []
        if CSS.read_text() != new_css:
            stale.append(str(CSS.relative_to(ROOT)))
        if not SWIFT.exists() or SWIFT.read_text() != swift:
            stale.append(str(SWIFT.relative_to(ROOT)))
        if stale:
            print("Out of date with design/tokens.json:", ", ".join(stale))
            print("Run: python scripts/build_tokens.py")
            return 1
        print("Design tokens are up to date.")
        return 0

    CSS.write_text(new_css)
    SWIFT.write_text(swift)
    n = sum(len(g["tokens"]) for g in data["groups"])
    print(f"Wrote {n} tokens to {CSS.relative_to(ROOT)} and {SWIFT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Spec 057: the iOS app's String Catalog (ios/Ceol/Ceol/Localizable.xcstrings).

The compiler extracts every localizable literal (Text("…"), Button, Label, tr("…"))
into .stringsdata files at build time; `xcrun xcstringstool sync` merges them into the
catalog. The Irish is written in ios/Ceol/i18n-ga/*.json, one file per area of the app
(so areas can be translated side by side), and applied into the catalog marked
"needs_review" until the product owner approves it.

    scripts/ios_strings.py sync --derived ios/.derived     # catalog <- the build's strings
    scripts/ios_strings.py apply                            # catalog <- ios/Ceol/i18n-ga/*.json
    scripts/ios_strings.py missing --derived ios/.derived   # build strings with no Irish anywhere
    scripts/ios_strings.py check                            # catalog strings with no Irish

A fragment file maps the catalog key (as the compiler writes it: "%lld tunes",
"Welcome back, %@") to its Irish. Reordered arguments use positional specifiers
("%2$@ … %1$@"). A key whose only argument is a count may give the five Irish plural
forms instead: {"one": …, "two": …, "few": …, "many": …, "other": …}.
`make ios-strings` runs sync then apply; `make ios-test` fails while anything is missing.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "ios", "Ceol", "Ceol", "Localizable.xcstrings")
FRAGMENTS = os.path.join(ROOT, "ios", "Ceol", "i18n-ga")
FORMS = ("one", "two", "few", "many", "other")


def needs_irish(key):
    """Keys with words in them. Bare format specifiers and punctuation ("%@ · %@") don't."""
    return bool(re.search(r"[A-Za-z]", re.sub(r"%(\d+\$)?(lld|ld|d|@|f|\.\d+f|s)", "", key)))


def stringsdata_files(derived):
    pattern = os.path.join(derived, "Build", "Intermediates.noindex", "Ceol.build", "*",
                           "Ceol.build", "Objects-normal", "arm64", "*.stringsdata")
    return [f for f in glob.glob(pattern) if "Shortcuts" not in os.path.basename(f)]


def build_keys(derived, only=None):
    """Keys the build extracted; `only` limits them to these Swift files (basenames)."""
    keys = set()
    for f in stringsdata_files(derived):
        data = json.load(open(f, encoding="utf-8"))
        if only and os.path.basename(data.get("source", "")) not in only:
            continue
        for entry in data.get("tables", {}).get("Localizable", []):
            keys.add(entry["key"])
    return keys


def load_catalog():
    with open(CATALOG, encoding="utf-8") as f:
        return json.load(f)


def save_catalog(catalog):
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def fragments():
    merged = {}
    for path in sorted(glob.glob(os.path.join(FRAGMENTS, "*.json"))):
        for key, value in json.load(open(path, encoding="utf-8")).items():
            merged[key] = value
    return merged


def has_irish(entry):
    ga = (entry or {}).get("localizations", {}).get("ga", {})
    unit = ga.get("stringUnit", {})
    if unit.get("value"):
        return True
    plural = ga.get("variations", {}).get("plural", {})
    return bool(plural) and all(plural.get(f, {}).get("stringUnit", {}).get("value") for f in FORMS)


def cmd_sync(args):
    files = stringsdata_files(args.derived)
    if not files:
        print(f"no .stringsdata under {args.derived}: build first (make ios-build)")
        return 1
    subprocess.run(["xcrun", "xcstringstool", "sync", CATALOG, "--stringsdata", *files], check=True)
    # Keep the file stable: sorted keys, two-space indent.
    save_catalog(load_catalog())
    print(f"synced {len(files)} files")
    return 0


def cmd_apply(_args):
    catalog = load_catalog()
    strings = catalog.setdefault("strings", {})
    applied = 0
    for key, value in fragments().items():
        entry = strings.setdefault(key, {})
        locs = entry.setdefault("localizations", {})
        current = locs.get("ga", {})
        # A string the product owner approved ("translated") is left alone.
        if current.get("stringUnit", {}).get("state") == "translated":
            continue
        if isinstance(value, dict):
            locs["ga"] = {"variations": {"plural": {
                f: {"stringUnit": {"state": "needs_review", "value": value[f]}} for f in FORMS}}}
        else:
            locs["ga"] = {"stringUnit": {"state": "needs_review", "value": value}}
        applied += 1
    save_catalog(catalog)
    print(f"applied {applied} Irish strings")
    return 0


def cmd_missing(args):
    have = fragments()
    catalog = load_catalog().get("strings", {})
    only = set(args.files.split(",")) if args.files else None
    missing = sorted(k for k in build_keys(args.derived, only)
                     if needs_irish(k) and k not in have and not has_irish(catalog.get(k)))
    for k in missing:
        print(json.dumps(k, ensure_ascii=False))
    print(f"{len(missing)} strings without Irish", file=sys.stderr)
    return 1 if missing else 0


def catalog_missing():
    strings = load_catalog().get("strings", {})
    return sorted(k for k, entry in strings.items()
                  if needs_irish(k) and entry.get("extractionState") != "stale"
                  and entry.get("shouldTranslate", True) and not has_irish(entry))


def cmd_check(_args):
    missing = catalog_missing()
    for k in missing:
        print(json.dumps(k, ensure_ascii=False))
    print(f"{len(missing)} catalog strings without Irish", file=sys.stderr)
    return 1 if missing else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("sync", "missing"):
        p = sub.add_parser(name)
        p.add_argument("--derived", default=os.path.join(ROOT, "ios", ".derived"))
        if name == "missing":
            p.add_argument("--files", help="comma-separated Swift file names to limit the check to")
    sub.add_parser("apply")
    sub.add_parser("check")
    args = parser.parse_args()
    return {"sync": cmd_sync, "apply": cmd_apply, "missing": cmd_missing, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

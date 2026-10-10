#!/usr/bin/env python3
"""Spec 057: small edits to translations/ga/LC_MESSAGES/messages.po that pybabel has no
command for.

    ./venv/bin/python scripts/i18n_po.py set FILE.json     # {"English": "Gaeilge", ...}; marks each `review`
    ./venv/bin/python scripts/i18n_po.py approve "English" # clears `review` (or --all)
    ./venv/bin/python scripts/i18n_po.py pending           # what still needs review

A plural entry's value is a list of the five Irish forms (one, two, few, many, other).
Run `make i18n-compile` afterwards.
"""

import json
import sys

from babel.messages.pofile import read_po, write_po

PO = "translations/ga/LC_MESSAGES/messages.po"
REVIEW = "review"


def load():
    with open(PO, "rb") as f:
        return read_po(f, locale="ga")


def save(catalog):
    with open(PO, "wb") as f:
        write_po(f, catalog, width=0, sort_by_file=True)


def key_of(message):
    return message.id[0] if isinstance(message.id, (list, tuple)) else message.id


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "pending"
    catalog = load()
    if cmd == "set":
        updates = json.load(open(argv[2], encoding="utf-8"))
        for message in catalog:
            if not message.id:
                continue
            k = key_of(message)
            if k in updates:
                message.string = (
                    tuple(updates[k]) if isinstance(updates[k], list) else updates[k]
                )
                message.flags.add(REVIEW)
        save(catalog)
    elif cmd == "approve":
        for message in catalog:
            if message.id and (argv[2:] == ["--all"] or key_of(message) in argv[2:]):
                message.flags.discard(REVIEW)
        save(catalog)
    elif cmd == "pending":
        for message in catalog:
            if message.id and REVIEW in message.flags:
                print(f"{key_of(message)!r} -> {message.string!r}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

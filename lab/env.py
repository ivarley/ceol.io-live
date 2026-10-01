"""Bootstrap: make the app's modules importable and load the environment.

The lab reuses `recording.py` (S3, ffmpeg) and `services/` (the thesession dump
download) rather than duplicating them, which means the repo root has to be on
sys.path, exactly as jobs/ and scripts/ do it. Importing this module is the
whole setup; every lab entry point does it first.

Two env files, in this order:

1. the repo's `.env`, which points at the LOCAL database and is what the app
   uses;
2. `lab/.env`, which overrides it, and is where production credentials belong.

The lab reads production and writes nothing to it, and it wants different
values from the app for the same names, so the two files are kept apart rather
than the app's being edited. `lab/.env` is gitignored by the repo's unanchored
`.env` rule; it holds secrets and must never be committed.
"""

import os
import sys

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

LAB_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(REPO_ROOT, ".env"))
load_dotenv(os.path.join(LAB_DIR, ".env"), override=True)


def prod_database_url():
    """The production URL, from lab/.env. Read-only by the pull's construction."""
    for name in ("PROD_DB_URL", "PROD_DATABASE_URL", "DATABASE_URL"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None

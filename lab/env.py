"""Bootstrap: make the app's modules importable and load `.env`.

The lab reuses `recording.py` (S3, ffmpeg) and `services/` (the thesession dump
download) rather than duplicating them, which means the repo root has to be on
sys.path, exactly as jobs/ and scripts/ do it. Importing this module is the
whole setup; every lab entry point does it first.
"""

import os
import sys

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

load_dotenv(os.path.join(REPO_ROOT, ".env"))

"""Where things live under lab/data (gitignored)."""

import os

from lab.env import REPO_ROOT

DATA_DIR = os.environ.get("LAB_DATA_DIR") or os.path.join(REPO_ROOT, "lab", "data")


def data(*parts):
    return os.path.join(DATA_DIR, *parts)


def recording_dir(recording_id):
    return data("recordings", str(int(recording_id)))


def manifest_path(recording_id):
    return os.path.join(recording_dir(recording_id), "manifest.json")


def wav_path(recording_id):
    return os.path.join(recording_dir(recording_id), "mono22k.wav")


def wav_sha1_path(recording_id):
    return os.path.join(recording_dir(recording_id), "mono22k.sha1")


def features_path(recording_id):
    return os.path.join(recording_dir(recording_id), "features.npz")


def session_history_path(session_id):
    return data("sessions", str(int(session_id)), "logged_order.json")


def corpus_dir():
    return data("corpus")


def tunes_csv_path():
    return os.path.join(corpus_dir(), "tunes.csv")


def index_dir():
    return data("index")


def board_path():
    return data("board.sqlite")


def bench_dir(task=None):
    return data("bench", task) if task else data("bench")


def run_dir(run_id):
    return data("runs", run_id)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def prepared_recording_ids():
    """Labelled recordings that have been pulled (manifest with segments), ascending.

    A recording pulled before anyone segmented it (to draft its segments) has a
    manifest with none; it is not part of the corpus until it is labelled and
    pulled again, so every "all recordings" default leaves it out.
    """
    import json

    root = data("recordings")
    if not os.path.isdir(root):
        return []
    ids = []
    for name in os.listdir(root):
        path = manifest_path(name)
        if name.isdigit() and os.path.exists(path):
            with open(path) as f:
                if json.load(f).get("segments"):
                    ids.append(int(name))
    return sorted(ids)

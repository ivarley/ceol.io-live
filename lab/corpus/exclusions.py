"""thesession.org settings left out of matching (spec 053, "Settings that match
everything").

A few settings are pages of variations, many times their tune's usual length:
The Mason's Apron's 12549 and 12550 are about 1,600 notes against a usual 120.
Somewhere in 1,600 notes of a reel in A or G is a passage like almost any
reel, so the tune turns up wherever the listener is unsure: across thirteen
labelled nights The Mason's Apron was the commonest wrong name (8 times, right
once). The list (lab/configs/excluded_settings.json) gives each setting and
why; they are dropped from the n-gram index and the aligner's sequences when
those load, so the built files and the listening service's data stay as they
are.

    python -m lab exclusions          # list the candidates by the rule, against the list
"""

import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "excluded_settings.json")
MIN_NOTES, MIN_TIMES = 800, 6.0     # the rule the list was made by: this long, and this many times the median

_CACHE = None


def excluded_settings():
    """{setting_id} to leave out of matching."""
    global _CACHE
    if _CACHE is None:
        try:
            with open(PATH) as f:
                _CACHE = {int(s["setting_id"]) for s in json.load(f)["settings"]}
        except OSError:
            _CACHE = set()
    return _CACHE


def apply_to_index(idx):
    """Drop the excluded settings from a loaded `corpus.index.Index`: their
    postings, and the document frequency and gram counts that came from them."""
    drop = excluded_settings()
    if not drop:
        return idx
    touched_tunes = set()
    for g, posts in list(idx.postings.items()):
        if any(s in drop for _, s in posts):
            kept = tuple(p for p in posts if p[1] not in drop)
            touched_tunes.update(t for t, s in posts if s in drop)
            if kept:
                idx.postings[g] = kept
                idx.df[g] = len({t for t, _ in kept})
            else:
                del idx.postings[g]
                idx.df.pop(g, None)
    if touched_tunes:
        counts = dict.fromkeys(touched_tunes, 0)
        for posts in idx.postings.values():
            for t in {t for t, _ in posts if t in counts}:
                counts[t] += 1
        idx.tune_gram_count.update(counts)
    idx.meta["excluded_settings"] = sorted(drop)
    return idx


def apply_to_sequences(by_tune):
    """Drop the excluded settings from `TuneSequences.by_tune`
    ({tune: [(setting_id, eighths, notes)]})."""
    drop = excluded_settings()
    if not drop:
        return by_tune
    for t in list(by_tune):
        kept = [x for x in by_tune[t] if int(x[0]) not in drop]
        if kept:
            by_tune[t] = kept
        else:
            del by_tune[t]
    return by_tune


def candidates():
    """Settings by the rule: [(times the median, notes, setting_id, tune_id, name, type)]."""
    import csv
    import re
    import statistics

    from lab import paths

    by = {}
    for r in csv.DictReader(open(paths.tunes_csv_path(), newline="")):
        by.setdefault(r["tune_id"], []).append((len(re.findall(r"[A-Ga-g]", r["abc"])), r))
    out = []
    for t, ss in by.items():
        if len(ss) < 3:
            continue
        med = statistics.median(n for n, _ in ss)
        for n, r in ss:
            if n >= MIN_NOTES and n >= MIN_TIMES * med:
                out.append((round(n / med, 1), n, int(r["setting_id"]), int(t), r["name"], r["type"]))
    return sorted(out, reverse=True)


def add_parser(sub):
    p = sub.add_parser("exclusions", help="settings left out of matching: the rule's candidates against the list")
    p.set_defaults(func=main)


def main(args):
    listed = excluded_settings()
    for times, n, sid, tid, name, typ in candidates():
        print(f"{'listed ' if sid in listed else 'NOT listed'}  {sid:>6}  {name} ({typ}, tune {tid}): "
              f"{n} notes, {times}x its tune's median")
    return 0

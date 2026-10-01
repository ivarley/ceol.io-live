"""Every setting's notes as sequences, for aligning a transcription against.

The n-gram index keeps only which tunes contain which phrases; an aligner
needs each tune's whole line. Two readings per setting, both as pitch
classes (-1 for a rest):

- `eighths`: one entry per eighth note, a held note repeated, placed by the
  same `particalized_pitches` the particalized index uses;
- `notes`: one entry per change of pitch, so neither tempo nor articulation
  matters.

Built with the index's parser, so the two cannot read a setting differently,
and cached beside the indexes under the parser version.
"""

import os
import pickle

import numpy as np

from lab import paths
from lab.corpus import abc_pitch


def _collapse(pcs):
    out = []
    for p in pcs:
        if p is None:
            continue
        if not out or out[-1] != p:
            out.append(p)
    return out


def _array(pcs):
    return np.array([-1 if p is None else int(p) % 12 for p in pcs], dtype=np.int8)


class TuneSequences:
    VERSION = "1"

    def __init__(self, by_tune):
        self.by_tune = by_tune    # tune_id -> [(setting_id, eighths, notes)]

    @classmethod
    def path(cls, candidate_set):
        return os.path.join(paths.index_dir(), f"sequences-{candidate_set}-p{abc_pitch.PARSER_VERSION}"
                                               f"-v{cls.VERSION}.pkl")

    @classmethod
    def build(cls, candidate_set):
        from lab.corpus.index import candidate_tune_ids
        from lab.corpus.tunes_csv import iter_settings

        by_tune = {}
        for s in iter_settings(paths.tunes_csv_path(), tune_ids=candidate_tune_ids(candidate_set)):
            try:
                notes = abc_pitch.parse_abc(s.abc, key=s.mode, meter=s.meter)
                eighths = abc_pitch.particalized_pitches(notes)
                plain = _collapse(p % 12 if p is not None else None
                                  for p in abc_pitch.pitch_sequence(notes))
            except Exception:  # a bad setting must not lose the corpus
                continue
            if len(plain) < 8:
                continue
            by_tune.setdefault(s.tune_id, []).append(
                (s.setting_id, _array(eighths), _array(plain)))
        return cls(by_tune)

    @classmethod
    def load(cls, candidate_set="repertoire"):
        path = cls.path(candidate_set)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return cls(pickle.load(f))
        seqs = cls.build(candidate_set)
        paths.ensure_dir(os.path.dirname(path))
        with open(path, "wb") as f:
            pickle.dump(seqs.by_tune, f)
        return seqs

"""The candidate registry.

Adding an idea is adding a module here and a line below. Placeholders that are
not built yet are listed in UNBUILT so `lab bench candidates` shows what the
bench is meant to cover, not just what it covers today.
"""

from lab.bench.candidates.base import Candidate  # noqa: F401
from lab.bench.candidates.boundary_keychange import BoundaryKeyChange
from lab.bench.candidates.boundary_mel_lr import BoundaryMelLR
from lab.bench.candidates.boundary_novelty import BoundaryNovelty
from lab.bench.candidates.music_energy import MusicEnergy
from lab.bench.candidates.music_mel_lr import MusicMelLR

REGISTRY = {c.name: c for c in (MusicEnergy, MusicMelLR, BoundaryNovelty, BoundaryKeyChange, BoundaryMelLR)}

# Ideas the spec names but that are not built. Listed so the gap is visible.
UNBUILT = {
    "boundary_embedding": "probe on a pretrained audio embedding; the likeliest win, needs a model dependency",
    "boundary_transcription": "the matcher stopped matching what it was matching; needs the ensemble, not the bench",
    "music_embedding": "same probe, for music-vs-room",
}

TASK_HINT = {
    "music_activity": ("music_energy", "music_mel_lr"),
    "boundary": ("boundary_novelty", "boundary_keychange", "boundary_mel_lr"),
}


def get_candidate(name, **params):
    if name not in REGISTRY:
        hint = f"; unbuilt: {sorted(UNBUILT)}" if name in UNBUILT else ""
        raise SystemExit(f"unknown candidate '{name}'; have {sorted(REGISTRY)}{hint}")
    return REGISTRY[name](**params)

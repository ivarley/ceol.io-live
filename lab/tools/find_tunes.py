"""Find a night's tunes from its recording alone, start to finish: what the
listening service runs as a background job when an admin asks the segmenter to
find the tunes (spec 053, "053 files/find-tunes-on-the-server.md"), and the
same steps `lab drafts --blind --merged` takes.

1. Listen to the whole recording, as the live service does (`lab.tools.listen`),
   with the session's tiers: its own tunes (logged before the night) first,
   popular ones second, the rest outside.
2. Draft the log from what the listener showed (`drafts.infer_log`).
3. Follow each set for its tunes' starts (`drafts.follow_drafts`).
4. Join and tidy the sets, end each on its held note.
5. Each tune's features and the chance it is right (`analysis.confidence`).

The caller is told where it has got to (`progress(phase, done, total)`), may
hold it between steps (`pause()`: True while it should wait) and may stop it
(`cancelled()`). Nothing here talks to the app; the caller posts the drafts.
"""

import hashlib
import os
import shutil
import tempfile
import time

LISTENING, FOLLOWING, FINISHING = "listening", "following", "finishing"


class Cancelled(Exception):
    pass


def _sha1(path, block=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def with_key_allowance(models):
    """`models` with the key allowance on (a tune tried a fifth or two from its
    written keys), for listening after the fact: over nine nights it named
    three more tunes for about 20% more compute (spec 053), which live
    listening on the service cannot spare but a background job can. A shallow
    copy: the tune sequences, the indexes and the trackers are shared."""
    import copy

    if models.aligner.transpose == "fifths":
        return models
    m = copy.copy(models)
    m.aligner = copy.copy(models.aligner)
    m.aligner.transpose = "fifths"
    return m


def find_tunes(wav_path, models, session_tunes=None, keys=None, progress=None, pause=None, cancelled=None,
               log=print, nu_partly=0.5, key_allowance=True):
    """-> {"drafts": [...], "confidence_model": "listen-<v>" or None,
    "paused_s": seconds held, "summary": {tunes, sets, need_check}}.

    `wav_path`: the recording as 22,050 Hz mono. `models`: a loaded
    `listen.Models(merged=True)`. `session_tunes`: tune ids the session logged
    before the night (None: a session with no history). `keys`: {tune_id: the
    key the session plays it in}."""
    import soundfile as sf

    from lab.analysis.confidence import CHECK_UNDER, ConfidenceModel, features
    from lab.audio.chunks import AudioStore
    from lab.board.board import Board
    from lab.tools.drafts import (consolidate_unsure, drop_squeezed, follow_drafts, infer_log, join_sets,
                                  prefer_set_type, refine_ends, tidy)
    from lab.tools.listen import HOP_MS, Listener

    progress = progress or (lambda *a: None)
    pause = pause or (lambda: False)
    cancelled = cancelled or (lambda: False)
    paused = [0.0]

    def checkpoint():
        if cancelled():
            raise Cancelled()
        if pause():
            t = time.time()
            while pause():
                if cancelled():
                    raise Cancelled()
                time.sleep(1)
            paused[0] += time.time() - t

    if key_allowance:
        models = with_key_allowance(models)
    with sf.SoundFile(wav_path) as f:
        duration = int(round(1000 * f.frames / f.samplerate))
    work = tempfile.mkdtemp(prefix="find-tunes-")
    # the listener keeps a copy of what it hears: FLAC, half a WAV's disk
    li = Listener(work, models=models, keep_s=120, audio_name="audio.flac", session_tunes=session_tunes or None,
                  second_tier=models.popular, nu_partly=nu_partly)
    states = []
    try:
        for block in sf.blocks(wav_path, blocksize=22050 * 10, dtype="float32"):
            li.store.append(block)
            while li.store.duration_ms >= li.next_t:
                checkpoint()
                li.step(li.next_t)
                st = {k: v for k, v in li.state.items() if k != "history"}
                st["_at_ms"] = li.next_t
                states.append(st)
                li.next_t += HOP_MS
                progress(LISTENING, li.next_t, duration)
    finally:
        li.close()

    checkpoint()
    drafts = infer_log(states, duration, models.names)
    log(f"find tunes: {len(drafts)} tunes drafted from {len(states)} steps")
    store = AudioStore(wav_path)
    store.clock_ms = store.duration_ms
    audio = (store, _sha1(wav_path))
    manifest = {"recording": {"duration_ms": duration}}
    with Board(os.path.join(work, "board.sqlite")) as board:
        def sets_done(done, total):
            checkpoint()
            progress(FOLLOWING, done, total)

        drafts = follow_drafts(None, manifest, drafts, log=log, audio=audio, board=board, keys=keys or {},
                               progress=sets_done)
        progress(FINISHING, 0, 1)
        drafts = tidy(join_sets(tidy(drop_squeezed(tidy(drafts), log=log)), log=log))
        drafts = tidy(refine_ends(None, drafts, log=log, audio=audio, board=board))
    store.close()
    shutil.rmtree(work, ignore_errors=True)

    features(drafts, states, duration)
    model = None
    try:
        model = ConfidenceModel.load()
    except OSError:
        log("find tunes: no confidence model; the tunes go in without one")
    for d in drafts:
        d["p_right"] = model.percent(d["features"]) if model else None
    if model:
        # an unsure tune of the wrong type for its set takes the set's type; then
        # unsure names do not flip-flop: a run of them is one tune
        drafts = prefer_set_type(drafts, states, duration, model, log=log)
        drafts = tidy(consolidate_unsure(drafts, states, duration, model, log=log))
    progress(FINISHING, 1, 1)
    return {
        "drafts": drafts,
        "confidence_model": f"listen-{model.version}" if model else None,
        "paused_s": round(paused[0], 1),
        "summary": {"tunes": len(drafts), "sets": len({d["set"] for d in drafts}),
                    "need_check": sum(1 for d in drafts if d["p_right"] is not None and d["p_right"] < CHECK_UNDER)},
    }

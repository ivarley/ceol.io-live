"""Following a set through its tunes, to find where each one starts (spec 053).

Given a set's tunes in the order they were played, the heard notes on a grid
of eighth notes, and each tune's played form (analysis/form), find the path
that explains the audio best:

    not a tune  ->  tune 1, eighth by eighth, round and round
                ->  tune 2 from its first eighth  -> ...  ->  not a tune

This is score following. Inside a tune the position moves on one eighth per
slot of the grid, or now and then two (a slot the grid gained) or none (a
slot it lost), so a grid that drifts a little is absorbed rather than
compounded; past the form's end it goes round again, as the players do. A
tune is entered only at its first eighth. The change to the next tune is
cheap from the last bar of the form and dear anywhere else, so where one
tune ends and the next begins is decided together, by one alignment: the
outgoing tune's grid running forward and the incoming tune's opening running
back meet at one slot.

Every setting of a tune runs side by side and the best explains its stretch.

Scores add (a Viterbi path, not a probability): a slot whose heard pitch
class is the form's scores MATCH, another pitch MISMATCH, nothing heard 0,
the same scoring as the aligner. "Not a tune" scores NOISE a slot whatever
was heard, so the path takes a stretch as a tune only where it matches the
tune better than that.
"""

from dataclasses import dataclass

import numpy as np

MATCH, MISMATCH = 2.0, -1.0
NOISE = 0.3          # per slot, "not a tune"
SKIP, STAY = 1.5, 1.5  # the position moving two, or none
ENTER = 4.0          # entering the set's first tune from "not a tune"
CHANGE = 2.0         # one tune to the next, from the last bar of the form
OFF_END = 12.0       # ... more, from anywhere else in the form
LEAVE = 2.0          # the last tune to "not a tune"

NEG = -1e18


@dataclass
class Chain:
    """One setting of one tune, in one key: its played form as pitch classes."""
    tune: int            # index of the tune in the set
    setting_id: int
    form: np.ndarray     # int8 pitch classes, -1 for nothing
    last_bar: int        # eighths in the form's last bar
    shift: int = 0       # semitones the setting was moved (the session's own key)


_TONIC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def tonic_pc(key_text):
    """'Amixolydian', 'F#minor', 'Bb' -> the tonic's pitch class, or None."""
    t = (key_text or "").strip()
    if not t or t[0].upper() not in _TONIC:
        return None
    pc = _TONIC[t[0].upper()]
    if len(t) > 1 and t[1] in "#b":
        pc += 1 if t[1] == "#" else -1
    return pc % 12


def shifted(form, semitones):
    """A form's pitch classes moved by some semitones (nothing heard stays -1)."""
    return np.where(form < 0, form, (form.astype(np.int16) + semitones) % 12).astype(np.int8)


def chains_for(tune, settings, session_key=None):
    """The chains a tune is followed through. `settings`: [(setting_id, mode,
    analysis.form.Form)]. Each setting in its written key; or, when the session
    plays the tune in a key of its own (session_tune.key), moved there instead:
    Mac's Fancy on 143 is played in D mixolydian, every setting on
    thesession.org is in A mixolydian, and in A it started 14.6 s late, in D
    0.2 s early."""
    out = []
    want = tonic_pc(session_key)
    for setting_id, mode, f in settings:
        shift = 0
        if want is not None and tonic_pc(mode) is not None:
            shift = (want - tonic_pc(mode) + 6) % 12 - 6
        out.append(Chain(tune=tune, setting_id=setting_id, form=shifted(f.eighths, shift),
                         last_bar=f.length - f.bar_starts[-1], shift=shift))
    return out


def slot_grid(t0_ms, t1_ms, tmap=None, period_ms=None):
    """Slot times from t0 to t1, one per eighth, following a tempo map
    ({t_ms, period_ms}, times relative to t0) or a fixed period."""
    times = [float(t0_ms)]
    if tmap:
        tt = np.asarray(tmap["t_ms"], dtype=float) + t0_ms
        pp = np.asarray(tmap["period_ms"], dtype=float)
    while times[-1] < t1_ms:
        p = float(np.interp(times[-1], tt, pp)) if tmap else period_ms
        times.append(times[-1] + p)
    return np.array(times[:-1])


def heard_slots(notes, times):
    """The pitch class of each slot: a note that starts in the slot, else one
    still sounding at its centre, else -1."""
    out = np.full(len(times), -1, dtype=np.int8)
    if len(times) < 2:
        return out
    half = np.diff(times, append=times[-1] + (times[-1] - times[-2])) / 2.0
    ends = times + half
    for n in sorted(notes, key=lambda n: n["t0_ms"]):
        pc = int(n["midi"]) % 12
        a = np.searchsorted(ends, n["t0_ms"], side="right")
        b = np.searchsorted(times, n["t1_ms"], side="left")    # held while sounding at a slot's centre
        if a < len(out) and out[a] < 0:
            out[a] = pc
        for k in range(a + 1, min(b, len(out))):
            if out[k] < 0:
                out[k] = pc
    return out


def _emissions(heard, form):
    h = heard[:, None].astype(np.int16)
    f = form[None, :].astype(np.int16)
    e = np.where(h == f, MATCH, MISMATCH)
    return np.where((h < 0) | (f < 0), 0.0, e)


def follow(heard, chains, n_tunes):
    """The best path. -> per slot (state, position): state -1 before the set,
    n_tunes after it, else the tune index; position -1 outside a tune; plus
    the setting chosen for each tune."""
    T = len(heard)
    C = len(chains)
    L = max(len(c.form) for c in chains)
    lengths = np.array([len(c.form) for c in chains])
    valid = np.arange(L)[None, :] < lengths[:, None]
    emit = np.zeros((C, T, L))
    for i, c in enumerate(chains):
        emit[i, :, :len(c.form)] = _emissions(heard, c.form)
    tune_of = np.array([c.tune for c in chains])
    # cost of leaving each chain from each position
    exit_pen = np.full((C, L), CHANGE + OFF_END)
    for i, c in enumerate(chains):
        exit_pen[i, len(c.form) - c.last_bar:len(c.form)] = CHANGE
        exit_pen[i, len(c.form):] = np.inf

    V = np.full((C, L), NEG)
    pre, post = 0.0, NEG
    back = np.zeros((T, C, L), dtype=np.int8)       # 0 advance, 1 skip, 2 stay, 3 entered
    enter_from = np.full((T, n_tunes), -1, dtype=np.int64)   # chain*L+pos left (or -1: from "before")
    post_from = np.full(T, -2, dtype=np.int64)      # -1 stayed after, else chain*L+pos left
    for t in range(T):
        # leaving each tune: the best exit score per tune, and from where
        exits = np.where(valid, V - exit_pen, NEG)
        best_exit = np.full(n_tunes, NEG)
        best_exit_at = np.full(n_tunes, -1, dtype=np.int64)
        flat = exits.reshape(C, L)
        for i in range(C):
            j = int(np.argmax(flat[i]))
            if flat[i, j] > best_exit[tune_of[i]]:
                best_exit[tune_of[i]] = flat[i, j]
                best_exit_at[tune_of[i]] = i * L + j
        # moving on inside each chain (round the form's end)
        adv = np.full((C, L), NEG)
        skip = np.full((C, L), NEG)
        for i in range(C):
            n = lengths[i]
            adv[i, :n] = np.roll(V[i, :n], 1)
            skip[i, :n] = np.roll(V[i, :n], 2) - SKIP
        stay = V - STAY
        cand = np.stack([adv, skip, stay])
        choice = np.argmax(cand, axis=0)
        newV = np.take_along_axis(cand, choice[None], 0)[0]
        # entering a tune at its first eighth
        for i in range(C):
            k = tune_of[i]
            src = pre - ENTER if k == 0 else best_exit[k - 1]
            if src > newV[i, 0]:
                newV[i, 0] = src
                choice[i, 0] = 3
                enter_from[t, k] = -1 if k == 0 else best_exit_at[k - 1]
        newV = np.where(valid, newV + emit[:, t, :], NEG)
        back[t] = choice
        # after the set
        out = best_exit[n_tunes - 1] - LEAVE + CHANGE  # leaving pays LEAVE, not CHANGE
        if post >= out:
            post, post_from[t] = post + NOISE, -1
        else:
            post, post_from[t] = out + NOISE, best_exit_at[n_tunes - 1]
        pre = pre + NOISE
        V = newV
    # trace back
    path_state = np.full(T, -1, dtype=np.int64)
    path_pos = np.full(T, -1, dtype=np.int64)
    end_tune = V.max()
    if post >= end_tune:
        state, ci, p = "post", -1, -1
    else:
        state = "chain"
        ci, p = np.unravel_index(int(np.argmax(V)), V.shape)
    chosen = {}
    for t in range(T - 1, -1, -1):
        if state == "post":
            path_state[t] = n_tunes
            src = post_from[t]
            if src >= 0:
                state, ci, p = "chain", src // L, src % L
            continue
        if state == "pre":
            path_state[t] = -1
            continue
        path_state[t] = tune_of[ci]
        path_pos[t] = p
        chosen.setdefault(int(tune_of[ci]), chains[ci].setting_id)
        c = back[t, ci, p]
        n = lengths[ci]
        if c == 0:
            p = (p - 1) % n
        elif c == 1:
            p = (p - 2) % n
        elif c == 3:
            src = enter_from[t, tune_of[ci]]
            if src < 0:
                state = "pre"
            else:
                ci, p = src // L, src % L
    return path_state, path_pos, chosen


def boundaries(path_state, times, n_tunes):
    """-> (start time of each tune, end time of the set)."""
    starts = []
    for k in range(n_tunes):
        idx = np.nonzero(path_state == k)[0]
        starts.append(float(times[idx[0]]) if len(idx) else None)
    after = np.nonzero(path_state == n_tunes)[0]
    end = float(times[after[0]]) if len(after) else float(times[-1])
    return starts, end

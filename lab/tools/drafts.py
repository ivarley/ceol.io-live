"""Draft a recording's segments from what the listening meter showed (spec 053).

The phone's recorder keeps a meter log beside each recording (lab pull fetches
it as listen-states.jsonl): every state the listening service sent while the
night was recorded, every tap, every tune logged from the meter and every set
ended. That is most of a segmentation already. This turns it into a draft
start (and, for a set's last tune, an end) for each tune of the night's log,
for a person to correct in the segmenter rather than place from nothing.

    python -m lab drafts 143                       # the table, and drafts.json
    python -m lab drafts 143 --apply --email you@  # write them to the segmenter
    python -m lab drafts 140 --replay              # no meter log: the listener run over the audio
    python -m lab drafts 112 --blind               # the night was never logged: infer the log too
    python -m lab drafts 112 --blind --apply ...   # log the tunes and place them, in one pass

The rules, fixed before any of this night's corrections were seen:

- Each logged tune is anchored on its "this one" tap (the first for that tune
  not before the previous tune's anchor, in the log's order), and placed by
  the run of states showing it there. A tune added by hand has no tap: it is
  placed by a run showing it between its neighbours' anchors, or, if it was
  never shown, a guess halfway between them, marked so.
- The first tune of a set starts where the music does: walking back from when
  it was first shown, over states that heard a tune (tune-ness at least 0.5),
  at most SET_LEAD_MAX_MS (tuning and noodling between sets can sound like a
  tune), then one hop (4 s, the audio a state covers) more.
- A later tune of a set starts IN_SET_LEAD_MS before it was first shown: on
  night 137 the follower first showed a tune a median 15 s after its labelled
  start (053 files/blind-r137-comparison.md).
- A set's last tune ends where the music stops: the last state after it that
  heard a tune, before the set was ended. Other tunes get no end; the next
  tune's start ends them, as in the segmenter.

Then, unless --no-follow, score following (analysis/follow.py) replaces each
set's starts: the drafts give the sets, the tunes in order and each set's
rough span (from 90 s before its first tune was shown to 30 s after its
drafted end), and following finds where each tune starts in the audio, one
tune's end and the next one's start decided together. It needs the audio
(lab pull, then lab prepare) and takes minutes. Set ends stay the meter's.
On 143, against the player's corrections: first of a set within 1 s 22 of
31, later in a set 36 of 41, where the meter alone had 5 and 4.

--apply signs in as you (a password login that returns a token, as the app's
does), skips any tune that already has a segment unless --force, PUTs the
rest to /api/recordings/<id>/segments/<session_instance_tune_id>, and signs
out. It writes to production only with --apply.
"""

import json
import os
import sys
import time

import numpy as np

from lab import paths

HOP_MS = 4000
IN_SET_LEAD_MS = 15000
TUNE = 0.5                # tune-ness at or above this: the state heard a tune
MIN_GAP_MS = 10000        # a draft start stays this far after the tune before
ID_WINDOW = 8             # rows (breaks, hand-added tunes) made between two taps
MIN_RUN_MS = 16000        # a run showing a tune without a tap, to be taken as the tune
SET_LEAD_MAX_MS = 40000   # a set's start reaches back at most this far before it was shown


def load_log(path):
    states, taps, logged = [], [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            msg = row["msg"]
            kind = msg.get("type")
            if row["dir"] == "in" and kind == "state":
                states.append({**msg, "_at_ms": row["at_ms"]})
            elif row["dir"] == "out" and kind == "tap":
                taps.append({**msg, "at_ms": row["at_ms"]})
            elif row["dir"] == "app" and kind == "logged":
                logged.append({**msg, "at_ms": row["at_ms"]})
    return states, taps, logged


def audio_time_of(states, at_ms):
    """The audio time (t_ms) of the state on screen at wall-clock at_ms."""
    t = None
    for s in states:
        if s["_at_ms"] <= at_ms:
            t = s["t_ms"]
        else:
            break
    return t


def runs_of(states, tune_id, slack=2):
    """Runs of states showing tune_id: [first_t, last_t], allowing `slack`
    states of something else inside a run."""
    runs, cur, miss = [], None, 0
    for s in states:
        if s.get("shown") == tune_id:
            if cur is None:
                cur = [s["t_ms"], s["t_ms"]]
            cur[1] = s["t_ms"]
            miss = 0
        elif cur is not None:
            miss += 1
            if miss > slack:
                runs.append(cur)
                cur, miss = None, 0
    if cur is not None:
        runs.append(cur)
    return runs


def sets_of(logged_order):
    """The night's tunes in logged order, grouped into sets by its breaks."""
    sets, cur = [], []
    for row in logged_order:
        if row["record_type"] == "break":
            if cur:
                sets.append(cur)
            cur = []
        elif row.get("tune_id") is not None or row["record_type"] == "tune":
            cur.append(row)
    if cur:
        sets.append(cur)
    return sets


def draft(states, logged, logged_order, duration_ms, names=None):
    names = names or {}
    for st in states:
        for c in st.get("top", []):
            if c.get("name"):
                names.setdefault(c["tune_id"], c["name"])
    by_t = [s["t_ms"] for s in states]
    tuneful = {s["t_ms"]: (s.get("tuneness") or 0) >= TUNE for s in states}

    # 1. which row each "this one" made. A tap that logs a tune creates one row,
    #    and row ids rise in the order rows are created, so the k-th logged event
    #    made the next row of its tune after the previous event's row. A row no
    #    event made was added by hand; an event whose row is gone was deleted.
    sets = sets_of(logged_order)
    rows = []
    for k, tunes in enumerate(sets):
        for i, row in enumerate(tunes):
            tid = row.get("tune_id")
            rows.append({"session_instance_tune_id": row["session_instance_tune_id"], "tune_id": tid,
                         "name": row.get("name") or names.get(tid), "set": k + 1, "first_in_set": i == 0,
                         "how": None, "first_shown_ms": None, "start_ms": None, "end_ms": None,
                         "_anchor": None, "_run": None})
    by_id = {d["session_instance_tune_id"]: d for d in rows}
    last_id = min(by_id) - 1 if by_id else 0
    for ev in logged or []:
        mine = sorted(i for i, d in by_id.items() if d["tune_id"] == ev["tune_id"] and i > last_id
                      and d["_anchor"] is None and i <= last_id + ID_WINDOW)
        if not mine:
            continue                       # its row was deleted
        t = audio_time_of(states, ev["at_ms"])
        if t is not None:
            by_id[mine[0]]["_anchor"], by_id[mine[0]]["how"] = t, "tap"
        last_id = mine[0]
    # a tapped row moved by hand to where its tap cannot be: placed as by hand
    for i, d in enumerate(rows):
        if d["_anchor"] is None:
            continue
        lo = max((x["_anchor"] for x in rows[:i] if x["_anchor"] is not None), default=0)
        hi = min((x["_anchor"] for x in rows[i + 1:] if x["_anchor"] is not None), default=duration_ms)
        if not lo <= d["_anchor"] <= hi:
            d["_anchor"], d["how"] = None, None

    # 2. a tune with no tap: a run showing it between its neighbours' anchors
    for i, d in enumerate(rows):
        if d["_anchor"] is not None or d["tune_id"] is None:
            continue
        lo = next((x["_anchor"] for x in reversed(rows[:i]) if x["_anchor"] is not None), 0)
        hi = next((x["_anchor"] for x in rows[i + 1:] if x["_anchor"] is not None), duration_ms)
        runs = [r for r in runs_of(states, d["tune_id"]) if lo <= r[0] <= hi]
        # without a tap, a state or two showing the tune by mistake is not its run
        held = [r for r in runs if r[1] - r[0] >= MIN_RUN_MS]
        runs = held or runs
        if runs:
            d["_anchor"], d["how"] = runs[0][0], "shown"

    # 3. the run of states showing it around the anchor
    for d in rows:
        if d["_anchor"] is None:
            continue
        runs = runs_of(states, d["tune_id"])
        held = [r for r in runs if r[0] <= d["_anchor"] <= r[1] + HOP_MS]
        near = sorted((r for r in runs if abs(r[0] - d["_anchor"]) <= 60000), key=lambda r: abs(r[0] - d["_anchor"]))
        d["_run"] = held[0] if held else (near[0] if near else [d["_anchor"], d["_anchor"]])
        d["first_shown_ms"] = d["_run"][0]

    # 4. starts, set by set; a set's end where its music stops
    floor, set_ends = 0, {}
    for k in range(1, len(sets) + 1):
        set_rows = [d for d in rows if d["set"] == k]
        for d in set_rows:
            if d["_run"] is None:
                continue
            if d["first_in_set"]:
                j = by_t.index(d["_run"][0]) if d["_run"][0] in by_t else 0
                while (j > 0 and tuneful.get(by_t[j - 1]) and by_t[j - 1] > floor
                       and d["_run"][0] - by_t[j - 1] <= SET_LEAD_MAX_MS):
                    j -= 1
                d["start_ms"] = max(floor, by_t[j] - HOP_MS)
            else:
                d["start_ms"] = max(floor, d["_run"][0] - IN_SET_LEAD_MS)
            floor = d["start_ms"] + MIN_GAP_MS
        found = [d for d in set_rows if d["_run"] is not None]
        if found:
            j = by_t.index(found[-1]["_run"][1]) if found[-1]["_run"][1] in by_t else len(by_t) - 1
            while j + 1 < len(by_t) and tuneful.get(by_t[j + 1]):
                j += 1
            set_ends[k] = min(by_t[j], duration_ms)
            floor = max(floor, set_ends[k])

    # 5. guesses: within a set, halfway between its neighbours' starts; at a
    #    set's end, halfway from the last tune shown to the set's end
    for i, d in enumerate(rows):
        if d["start_ms"] is not None:
            continue
        before = next((x for x in reversed(rows[:i]) if x["start_ms"] is not None), None)
        after = next((x for x in rows[i + 1:] if x["start_ms"] is not None), None)
        if before and after and before["set"] == d["set"] == after["set"]:
            a, b = before["start_ms"], after["start_ms"]
        elif before and before["set"] == d["set"]:
            a = before["_run"][1] if before["_run"] else before["start_ms"]
            b = set_ends.get(d["set"], after["start_ms"] if after else duration_ms)
        else:
            a = set_ends.get(d["set"] - 1, before["start_ms"] if before else 0)
            b = after["start_ms"] if after else duration_ms
        d["start_ms"] = int((a + b) / 2) if b > a else a
        d["how"] = "added by hand, not shown: a guess"
    for k, end in set_ends.items():
        last = [d for d in rows if d["set"] == k][-1]
        last["end_ms"] = end

    for d in rows:
        d.pop("_anchor", None)
        d.pop("_run", None)
        if d["end_ms"] is not None and d["end_ms"] <= d["start_ms"]:
            d["end_ms"] = None
    return rows


BRIEF_MS = 20000          # blind: a tune shown for less than this is a wobble or a false start
MERGE_GAP_MS = 20000      # blind: one tune's runs closer than this (plus BRIEF_MS) are one tune
SET_GAP_MS = 10000        # blind: more than this with nothing shown between two tunes is a set break
WINDOW_MS = 6000          # the listener names a tune from its last 6 s of notes


def infer_log(states, duration_ms, names=None):
    """A night's log from the listener's states alone, for a recording whose
    night was never logged: the tunes it showed, in order, grouped into sets.
    The rules are the blind segmentation's (night 137, 053 files/blind-r137.md),
    fixed before any label was read there: runs of one tune on display; a run
    under BRIEF_MS dropped; consecutive runs of one tune merged across less
    than MERGE_GAP_MS (plus BRIEF_MS) of other things; a set break where
    nothing is shown for more than SET_GAP_MS. -> draft rows as `draft` makes
    them, `session_instance_tune_id` None (the row does not exist yet), with
    `conf` (the median belief while shown) and `outside` (found in the whole
    corpus, not the session's repertoire)."""
    names = dict(names or {})
    types = {}
    runs = []                                   # [tune, first_t, last_t, [p], outside]
    for st in states:
        tid = st.get("shown")
        cand = next((c for c in st.get("top", []) if c["tune_id"] == tid), None)
        if cand and cand.get("name"):
            names.setdefault(tid, cand["name"])
        if cand and cand.get("type"):
            types.setdefault(tid, cand["type"].lower())
        if tid is None:
            continue
        if runs and runs[-1][0] == tid and st["t_ms"] - runs[-1][2] <= 3 * HOP_MS:
            runs[-1][2] = st["t_ms"]
            runs[-1][3].append(cand["p"] if cand else 0.0)
            runs[-1][4] = runs[-1][4] or bool(cand and cand.get("outside"))
        else:
            runs.append([tid, st["t_ms"], st["t_ms"], [cand["p"] if cand else 0.0],
                         bool(cand and cand.get("outside"))])
    kept = []
    for r in runs:
        if r[2] + HOP_MS - r[1] < BRIEF_MS:
            continue
        if kept and kept[-1][0] == r[0] and r[1] - kept[-1][2] < MERGE_GAP_MS + BRIEF_MS:
            kept[-1][2] = r[2]
            kept[-1][3] += r[3]
            kept[-1][4] = kept[-1][4] or r[4]
            continue
        kept.append(list(r))
    tuneful = {st["t_ms"]: (st.get("tuneness") or 0) >= TUNE for st in states}
    by_t = [st["t_ms"] for st in states]
    rows, set_no = [], 0
    for i, (tid, first, last, ps, outside) in enumerate(kept):
        new_set = i == 0 or first - (kept[i - 1][2] + HOP_MS) > SET_GAP_MS
        if new_set:
            set_no += 1
        rows.append({"session_instance_tune_id": None, "tune_id": int(tid), "name": names.get(tid),
                     "set": set_no, "first_in_set": new_set, "how": "blind",
                     "first_shown_ms": first, "start_ms": max(0, first - WINDOW_MS), "end_ms": None,
                     "conf": round(float(np.median(ps)), 3), "outside": outside, "type": types.get(tid),
                     "last_shown_ms": last, "_last": last})
    # a set's last tune ends where the music stops after it
    for i, d in enumerate(rows):
        if i + 1 < len(rows) and not rows[i + 1]["first_in_set"]:
            continue
        j = by_t.index(d["_last"])
        while j + 1 < len(by_t) and tuneful.get(by_t[j + 1]):
            j += 1
        d["end_ms"] = min(by_t[j], duration_ms)
    for d in rows:
        d.pop("_last")
    return rows


HELD_MS = 400             # a set's end: the last note held at least this long ...
QUIET_MS = 400            # ... with no new note for this long after it ...
RING_OUT_MS = 726         # ... ends this much after the transcribed note does


def held_note_end(notes, lo_ms, hi_ms):
    """The end of the last held note between lo and hi with nothing after it
    for QUIET_MS, or None: a tune ends on a long held note, then a moment of
    no music (the player, 2026-10-04)."""
    best = None
    notes = sorted(notes, key=lambda n: n["t0_ms"])
    for i, n in enumerate(notes):
        if n["t1_ms"] - n["t0_ms"] < HELD_MS or not lo_ms <= n["t1_ms"] <= hi_ms:
            continue
        nxt = [x["t0_ms"] for x in notes[i + 1:] if x["t0_ms"] > n["t1_ms"] - 50]
        if not nxt or nxt[0] - n["t1_ms"] >= QUIET_MS:
            best = n["t1_ms"]
    return best


def refine_ends(rid, drafts, log=print):
    """Each set's end from its last held note. The meter's end (the last 4 s
    step that heard a tune) is where to look: from 6 s before it to 2 s after,
    the end of the last note held at least HELD_MS with no new note for
    QUIET_MS (Basic Pitch), plus RING_OUT_MS, the note ringing on past where the
    transcription lets it go. Without such a note the meter's end stands.

    Measured on 311 labelled set ends over nights 1-5, 138-140, 143 and 112:
    the meter's end within 1 s of the label 125 times, this 168 (within 0.5 s
    62 -> 100, median error 1.34 -> 0.91 s); better 73, worse 33, sign test
    p = 0.0001; every night better. RING_OUT_MS is the median over those ends
    (leave-one-night-out gives the same counts); HELD_MS and QUIET_MS were
    chosen among a few on the same ends."""
    from lab.audio.chunks import AudioStore
    from lab.bench.retrieval import transcribe_segment
    from lab.board.board import Board
    from lab.frontends import get_frontend

    fe = get_frontend("basic_pitch")
    with open(os.path.join(paths.recording_dir(rid), "mono22k.sha1")) as f:
        sha = f.read().strip()
    store = AudioStore(paths.wav_path(rid))
    store.clock_ms = store.duration_ms
    moved = 0
    with Board() as board:
        for d in drafts:
            if d["end_ms"] is None:
                continue
            e = d["end_ms"]
            notes, _, _ = transcribe_segment(fe, store, sha, int(e - 10000), int(e + 6000), board=board)
            held = held_note_end(notes, e - 6000, e + 2000)
            if held is not None and held + RING_OUT_MS > d["start_ms"]:
                d["meter_end_ms"] = e
                d["end_ms"] = int(held + RING_OUT_MS)
                moved += 1
    log(f"set ends from a held note: {moved} of {sum(d['end_ms'] is not None for d in drafts)}")
    return drafts


JOIN_MS = 5000            # blind: two sets this close, same tune type, are one set
REVIEW_MS = 15000         # ... closer than this but not joined: listed for a person to judge


def join_sets(drafts, log=print):
    """Blind sets split where one tune's grid runs into the next. The player's
    rule (2026-10-03): if the next tune starts within a few seconds of where the
    last one stopped, and they are the same type, it is a changeover, a pause
    while someone remembers how to start the next tune, and the split point is
    the next tune's start (the quiet before it belongs to the tune before);
    15 s or more is two sets. A few seconds is JOIN_MS: on the eight labelled
    nights, same-type breaks under 5 s were one labelled set 13 times out of
    15, and from 5 to 15 s mostly two. Same-type gaps from JOIN_MS to REVIEW_MS
    are left split and listed for review. Run after following, so the gap is
    from where the music stopped to the followed start."""
    review = []
    for i in range(1, len(drafts)):
        d, prev = drafts[i], drafts[i - 1]
        if not d["first_in_set"] or prev["end_ms"] is None:
            continue
        gap = d["start_ms"] - prev["end_ms"]
        same = d.get("type") and d.get("type") == prev.get("type")
        if same and gap < JOIN_MS:
            d["first_in_set"] = False
            prev["end_ms"] = None
            d["how"] += ", joined"
        elif same and gap < REVIEW_MS:
            review.append((d, gap))
    set_no = 0
    for d in drafts:
        if d["first_in_set"]:
            set_no += 1
        d["set"] = set_no
    for d, gap in review:
        log(f"set break kept, for review: {gap / 1000:.0f} s before {d['name']} at {_fmt(d['start_ms'])}")
    return drafts


def tidy(drafts):
    """The drafts in time order, a set's end no later than the next tune's
    start. A set break can come from the display going blank while the music
    plays on (recording 112, set 5's end walked on over all of set 6), and a
    segment that runs into the next is not a segment the segmenter can hold."""
    drafts.sort(key=lambda d: d["start_ms"])
    for i, d in enumerate(drafts[:-1]):
        nxt = drafts[i + 1]["start_ms"]
        if d["end_ms"] is not None and d["end_ms"] > nxt:
            d["end_ms"] = nxt if nxt > d["start_ms"] else None
    set_no = 0
    for d in drafts:
        if d["first_in_set"]:
            set_no += 1
        d["set"] = set_no
    return drafts


FOLLOW_LEAD_MS = 90000    # a set's span for following: from this long before its first tune was shown
FOLLOW_TAIL_MS = 30000    # ... to this long after its drafted end


def follow_drafts(rid, manifest, drafts, log=print):
    """Each set's starts from score following (analysis.follow), in place of
    the meter's: the drafts give the sets, the tunes in order and each set's
    rough span; following finds where each tune starts, the one ending and
    the next beginning decided together. Set ends stay the meter's (where the
    music stops), which following does worse. A set with a tune that has no
    readable setting keeps the meter's starts. The meter's start is kept on
    each draft as `meter_start_ms`."""
    from lab.analysis.follow import follow_span
    from lab.analysis.form import played_forms
    from lab.audio.chunks import AudioStore
    from lab.board.board import Board

    duration = int(manifest["recording"]["duration_ms"])
    forms = played_forms({d["tune_id"] for d in drafts if d["tune_id"]})
    keys = {r["tune_id"]: r.get("key") for r in manifest.get("repertoire", [])}
    with open(os.path.join(paths.recording_dir(rid), "mono22k.sha1")) as f:
        sha = f.read().strip()
    store = AudioStore(paths.wav_path(rid))
    store.clock_ms = store.duration_ms
    prev_end = 0
    with Board() as board:
        sets_seen = sorted({d["set"] for d in drafts})
        for k in sets_seen:
            rows = [d for d in drafts if d["set"] == k]
            for d in rows:
                d["meter_start_ms"] = d["start_ms"]
            seen = [d["first_shown_ms"] or d["start_ms"] for d in rows]
            end = rows[-1]["end_ms"] or max(d["start_ms"] for d in rows) + 120000
            t0 = max(prev_end, min(seen) - FOLLOW_LEAD_MS)
            t1 = min(duration, end + FOLLOW_TAIL_MS)
            prev_end = end
            missing = [d["name"] for d in rows if d["tune_id"] not in forms]
            if missing:
                log(f"set {k}: not followed, no readable setting for {', '.join(str(m) for m in missing)}")
                continue
            log(f"following set {k} of {len(sets_seen)} ({_fmt(t0)}-{_fmt(t1)}, {len(rows)} tunes)")
            got = follow_span(store, sha, t0, t1, [forms[d["tune_id"]] for d in rows],
                              [keys.get(d["tune_id"]) for d in rows], board=board)
            if got is None:
                log(f"set {k}: not followed, no beat found")
                continue
            starts, _, _ = got
            for d, st in zip(rows, starts):
                if st is None:
                    continue
                # The listener names a tune only after hearing it, so a start
                # more than a step after it was first shown cannot be right: the
                # path, which must place every tune, has pushed one it matches
                # badly into the quiet after the music (Glen Allen, night 2,
                # put at 0:13:10 after a tune shown from 0:10:56 and ending 0:12:38).
                if d.get("first_shown_ms") is not None and st > d["first_shown_ms"] + HOP_MS:
                    d["how"] = f"{d['how']}, follow rejected"
                    continue
                d["start_ms"] = int(round(st))
                d["how"] = f"{d['how']}, followed"
            # a set end before its last start (the meter's was early) is dropped
            if rows[-1]["end_ms"] is not None and rows[-1]["end_ms"] <= rows[-1]["start_ms"]:
                rows[-1]["end_ms"] = None
    return drafts


def _fmt(ms):
    if ms is None:
        return ""
    s = int(round(ms / 1000))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


def replay(rid, out_path, log=print, transpose=0):
    """The listener (lab listen, the service's) run over a recording's audio
    offline, for a night recorded without the phone's meter: its states written
    as a meter log (dir "in"; at_ms is the audio time, there being no screen),
    so the rest of drafting reads it the same way. Hours of audio take tens of
    minutes; the file is kept and reused."""
    import tempfile

    import soundfile as sf

    from lab.tools.listen import HOP_MS as STEP, Listener, Models

    li = Listener(tempfile.mkdtemp(prefix=f"replay-{rid}-"), models=Models(transpose=transpose), keep_s=120)
    part = out_path + ".part"
    started = time.time()
    with open(part, "w") as out:
        begin = {"type": "begin", "replay": True, "recording_id": rid}
        out.write(json.dumps({"at_ms": 0, "dir": "app", "msg": begin}) + "\n")
        for block in sf.blocks(paths.wav_path(rid), blocksize=22050 * 10, dtype="float32"):
            li.store.append(block)
            while li.store.duration_ms >= li.next_t:
                li.step(li.next_t)
                state = {k: v for k, v in li.state.items() if k != "history"}
                out.write(json.dumps({"at_ms": li.next_t, "dir": "in", "msg": {"type": "state", **state}}) + "\n")
                if li.next_t % 600000 == 0:
                    log(f"replay: {li.next_t / 60000:.0f} min of audio in {(time.time() - started) / 60:.0f} min")
                li.next_t += STEP
    li.close()
    os.replace(part, out_path)


def add_parser(sub):
    p = sub.add_parser("drafts", help="draft a recording's segments from the phone's meter log")
    p.add_argument("recording", type=int)
    p.add_argument("--apply", action="store_true", help="write the drafts to the segmenter (production)")
    p.add_argument("--email", help="your Ceol login, for --apply")
    p.add_argument("--base-url", default="https://ceol.io")
    p.add_argument("--force", action="store_true", help="with --apply, also replace tunes already placed")
    p.add_argument("--saved", action="store_true",
                   help="with --apply: apply the drafts.json already made for this recording, as it is, "
                        "instead of drafting again")
    p.add_argument("--blind", action="store_true",
                   help="the night was never logged: infer its log from the audio too (implies --replay "
                        "unless there is a meter log); --apply then logs the tunes as well as placing them")
    p.add_argument("--fifths", action="store_true",
                   help="replay with the key allowance (a tune a fifth or two from its settings' keys); "
                        "kept apart, as replay-states-fifths.jsonl")
    p.add_argument("--replay", action="store_true",
                   help="no meter log: run the listener over the audio instead (tens of minutes; kept)")
    p.add_argument("--no-follow", action="store_true",
                   help="the meter's starts only, without score following (minutes, not seconds)")
    p.set_defaults(func=main)


def main(args):
    rid = args.recording
    if args.saved:
        path = os.path.join(paths.recording_dir(rid), "drafts.json")
        if not args.apply:
            raise SystemExit("--saved is for --apply: it applies the drafts already made")
        if not os.path.exists(path):
            raise SystemExit(f"no saved drafts for recording {rid}: run python -m lab drafts {rid} first")
        with open(path) as f:
            saved = json.load(f)
        if bool(saved.get("blind")) != bool(args.blind):
            raise SystemExit(f"the saved drafts were made {'with' if saved.get('blind') else 'without'} "
                             f"--blind; apply them the same way")
        drafts = saved["drafts"]
        print(f"applying the saved drafts: {len(drafts)} tunes in {max(d['set'] for d in drafts)} sets")
        return apply_log(rid, drafts, args) if args.blind else apply(rid, drafts, args)
    if args.apply:
        # ask for the password now, not after minutes of replaying and following
        _signed_in(args)
        print("signed in; drafting (following prints a line per set)", flush=True)
    with open(paths.manifest_path(rid)) as f:
        manifest = json.load(f)
    log = os.path.join(paths.recording_dir(rid), "listen-states.jsonl")
    if args.blind and not os.path.exists(log):
        args.replay = True
    if args.replay or not os.path.exists(log):
        if not args.replay:
            raise SystemExit(f"no meter log for recording {rid} (lab pull fetches it, where the phone made one); "
                             f"--replay runs the listener over the audio instead")
        log = os.path.join(paths.recording_dir(rid),
                           "replay-states-fifths.jsonl" if args.fifths else "replay-states.jsonl")
        if not os.path.exists(log):
            replay(rid, log, transpose="fifths" if args.fifths else 0)
    states, _, logged = load_log(log)
    names = {r["tune_id"]: r["name"] for r in manifest.get("repertoire", [])}
    if args.blind:
        drafts = infer_log(states, int(manifest["recording"]["duration_ms"]), names)
    else:
        drafts = draft(states, logged, manifest["logged_order"], int(manifest["recording"]["duration_ms"]), names)
    if not args.no_follow:
        if not os.path.exists(paths.wav_path(rid)):
            raise SystemExit(f"following needs the audio: python -m lab pull --recordings {rid}, then "
                             f"python -m lab prepare --recordings {rid} (or --no-follow)")
        drafts = follow_drafts(rid, manifest, drafts)
    if args.blind:
        drafts = join_sets(tidy(drafts))
        drafts = tidy(drafts)
    if os.path.exists(paths.wav_path(rid)):
        drafts = tidy(refine_ends(rid, drafts)) if args.blind else refine_ends(rid, drafts)
    out = os.path.join(paths.recording_dir(rid), "drafts.json")
    with open(out, "w") as f:
        json.dump({"recording_id": rid, "followed": not args.no_follow, "blind": args.blind,
                   "rules": {"in_set_lead_ms": IN_SET_LEAD_MS, "tuneness": TUNE},
                   "drafts": drafts}, f, indent=1)

    set_no = 0
    for d in drafts:
        if d["first_in_set"]:
            set_no += 1
            print(f"-- set {set_no}")
        name = d["name"] or f"tune {d['tune_id']}"
        moved = d.get("meter_start_ms")
        moved = f"  (meter {_fmt(moved)})" if moved is not None and abs(moved - d["start_ms"]) >= 1000 else ""
        how = d["how"].split(",")[0].split(" ")[0] + (" +follow" if "followed" in d["how"] else "") \
            + (" !follow" if "rejected" in d["how"] else "")
        print(f"  {_fmt(d['start_ms']):>8}  {name[:34]:<34} {how:<13} shown {_fmt(d['first_shown_ms']):>8}"
              + (f"  ends {_fmt(d['end_ms'])}" if d["end_ms"] else "") + moved)
    guesses = sum(d["how"].startswith("added") for d in drafts)
    print(f"{len(drafts)} tunes in {set_no} sets; {guesses} guessed; -> {out}")
    if args.blind:
        low = [d for d in drafts if d["conf"] < 0.5]
        print(f"blind: {len(low)} tunes named with a median belief under 0.5 (check these first): "
              + ", ".join(f"{_fmt(d['start_ms'])} {d['name']}" for d in low[:12]))
    if args.apply:
        return apply_log(rid, drafts, args) if args.blind else apply(rid, drafts, args)
    return 0


def _signed_in(args):
    import getpass

    import requests

    if getattr(args, "_session", None) is not None:
        return args._session
    if not args.email:
        raise SystemExit("--apply needs --email")
    s = requests.Session()
    # A native client's login returns a Bearer token rather than a cookie.
    s.headers["X-Ceol-Client"] = "macos/lab-drafts"
    r = s.post(f"{args.base_url.rstrip('/')}/api/auth/login-password",
               json={"email": args.email, "password": getpass.getpass(f"Ceol password for {args.email}: ")})
    if r.status_code != 200 or "token" not in r.json():
        raise SystemExit(f"sign-in failed ({r.status_code}): {r.text[:200]}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    args._session = s
    return s


def apply_log(rid, drafts, args):
    """Log a blind night's tunes and place them, in one pass: each tune posted
    in time order to POST /api/recordings/<id>/segments with its start (and,
    for a set's last tune, its end). The server puts each new tune after the
    placed tune before it, and an explicit end closes a set, so the log's sets
    come out as drafted. A tune from outside the repertoire is named by its
    thesession.org id, which imports it. Refuses a night that already has
    tunes logged, unless --force."""
    base = args.base_url.rstrip("/")
    s = _signed_in(args)
    try:
        r = s.get(f"{base}/api/recordings/{rid}/segmenter")
        r.raise_for_status()
        logged = [t for t in r.json().get("tunes", []) if t.get("record_type", "tune") == "tune"]
        if logged and not args.force:
            raise SystemExit(f"recording {rid}'s night already has {len(logged)} tunes logged; "
                             f"use lab drafts {rid} (without --blind), or --force")
        done = failed = 0
        for d in sorted(drafts, key=lambda d: d["start_ms"]):
            body = {"start_ms": int(d["start_ms"]), "end_ms": d["end_ms"]}
            body["thesession_id" if d.get("outside") else "tune_id"] = d["tune_id"]
            r = s.post(f"{base}/api/recordings/{rid}/segments", json=body)
            if r.ok:
                done += 1
            else:
                failed += 1
                print(f"  {d['name']}: {r.status_code} {r.text[:120]}", file=sys.stderr)
        print(f"logged and placed {done}, failed {failed}")
    finally:
        s.post(f"{base}/api/auth/logout")
    return 0 if failed == 0 else 1


def apply(rid, drafts, args):
    base = args.base_url.rstrip("/")
    s = _signed_in(args)
    try:
        r = s.get(f"{base}/api/recordings/{rid}/segmenter")
        r.raise_for_status()
        placed = {t["session_instance_tune_id"] for t in r.json().get("tunes", []) if t.get("segment")}
        done = skipped = failed = 0
        for d in drafts:
            if d["session_instance_tune_id"] in placed and not args.force:
                skipped += 1
                continue
            r = s.put(f"{base}/api/recordings/{rid}/segments/{d['session_instance_tune_id']}",
                      json={"start_ms": int(d["start_ms"]), "end_ms": d["end_ms"]})
            if r.ok:                       # 201 for a new segment, 200 for a moved one
                done += 1
            else:
                failed += 1
                print(f"  {d['name']}: {r.status_code} {r.text[:120]}", file=sys.stderr)
        print(f"placed {done}, skipped {skipped} already placed, failed {failed}")
    finally:
        s.post(f"{base}/api/auth/logout")
    return 0 if failed == 0 else 1

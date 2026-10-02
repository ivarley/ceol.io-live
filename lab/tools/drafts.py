"""Draft a recording's segments from what the listening meter showed (spec 053).

The phone's recorder keeps a meter log beside each recording (lab pull fetches
it as listen-states.jsonl): every state the listening service sent while the
night was recorded, every tap, every tune logged from the meter and every set
ended. That is most of a segmentation already. This turns it into a draft
start (and, for a set's last tune, an end) for each tune of the night's log,
for a person to correct in the segmenter rather than place from nothing.

    python -m lab drafts 143                       # the table, and drafts.json
    python -m lab drafts 143 --apply --email you@  # write them to the segmenter

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

--apply signs in as you (a password login that returns a token, as the app's
does), skips any tune that already has a segment unless --force, PUTs the
rest to /api/recordings/<id>/segments/<session_instance_tune_id>, and signs
out. It writes to production only with --apply.
"""

import json
import os
import sys

from lab import paths

HOP_MS = 4000
IN_SET_LEAD_MS = 15000
TUNE = 0.5                # tune-ness at or above this: the state heard a tune
MIN_GAP_MS = 10000        # a draft start stays this far after the tune before
ID_WINDOW = 8             # rows (breaks, hand-added tunes) made between two taps
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


def _fmt(ms):
    if ms is None:
        return ""
    s = int(round(ms / 1000))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


def add_parser(sub):
    p = sub.add_parser("drafts", help="draft a recording's segments from the phone's meter log")
    p.add_argument("recording", type=int)
    p.add_argument("--apply", action="store_true", help="write the drafts to the segmenter (production)")
    p.add_argument("--email", help="your Ceol login, for --apply")
    p.add_argument("--base-url", default="https://ceol.io")
    p.add_argument("--force", action="store_true", help="with --apply, also replace tunes already placed")
    p.set_defaults(func=main)


def main(args):
    rid = args.recording
    with open(paths.manifest_path(rid)) as f:
        manifest = json.load(f)
    log = os.path.join(paths.recording_dir(rid), "listen-states.jsonl")
    if not os.path.exists(log):
        raise SystemExit(f"no meter log for recording {rid} (lab pull fetches it, where the phone made one)")
    states, _, logged = load_log(log)
    names = {r["tune_id"]: r["name"] for r in manifest.get("repertoire", [])}
    drafts = draft(states, logged, manifest["logged_order"], int(manifest["recording"]["duration_ms"]), names)
    out = os.path.join(paths.recording_dir(rid), "drafts.json")
    with open(out, "w") as f:
        json.dump({"recording_id": rid, "rules": {"in_set_lead_ms": IN_SET_LEAD_MS, "tuneness": TUNE},
                   "drafts": drafts}, f, indent=1)

    set_no = 0
    for d in drafts:
        if d["first_in_set"]:
            set_no += 1
            print(f"-- set {set_no}")
        name = d["name"] or f"tune {d['tune_id']}"
        print(f"  {_fmt(d['start_ms']):>8}  {name[:34]:<34} {d['how'][:6]:<6} shown {_fmt(d['first_shown_ms']):>8}"
              + (f"  ends {_fmt(d['end_ms'])}" if d["end_ms"] else ""))
    guesses = sum(d["how"].startswith("added") for d in drafts)
    print(f"{len(drafts)} tunes in {set_no} sets; {guesses} guessed; -> {out}")
    if args.apply:
        return apply(rid, drafts, args)
    return 0


def apply(rid, drafts, args):
    import getpass

    import requests

    if not args.email:
        raise SystemExit("--apply needs --email")
    base = args.base_url.rstrip("/")
    s = requests.Session()
    # A native client's login returns a Bearer token rather than a cookie.
    s.headers["X-Ceol-Client"] = "macos/lab-drafts"
    r = s.post(f"{base}/api/auth/login-password",
               json={"email": args.email, "password": getpass.getpass(f"Ceol password for {args.email}: ")})
    if r.status_code != 200 or "token" not in r.json():
        raise SystemExit(f"sign-in failed ({r.status_code}): {r.text[:200]}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
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

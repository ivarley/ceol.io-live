# 050 Recording Segmenter

Put start/end timestamps on the tunes already logged against a night's audio,
fast enough to do a three-hour session in one sitting.

This is **data prep, not a feature**. The output is a training corpus for a
future model that recognises tunes from audio: a model can only learn "this is
Banish Misfortune" from a pile of audio clips that are known to be Banish
Misfortune, and nothing in Ceol produced those clips until now. The session logs
already say *what* was played and in what order; the recordings say *how it
sounded*. The missing join is *when* — and that is what a human with a waveform
and one key produces in an evening.

Spec 022's chunked live-capture recorder is **not** reused: it was never
finished, held zero rows in every environment, and its shape (30-second S3
chunks from a phone) is wrong for a tool that scrubs a whole night. Its seven
tables are dropped by `schema/049`.

## Design decisions

- **One recording = one whole audio file**, played back through a presigned S3
  URL. S3 honours range requests, so a browser can seek anywhere in a 3-hour
  file without downloading it — the only reason this works on a phone.
- **The master is not what gets played by default.** A separate small mono proxy
  (`stream_key`, schema/051) is streamed to the browser; `storage_key` stays the
  master and the training corpus is always cut from it. BOTH are presigned and
  sent to the page, and an `audio` control switches between them — which one you
  want depends on the connection you happen to be on, which import time cannot
  know. The choice is remembered per browser. Switching preserves the playhead
  and the play state, because changing an `<audio>` element's `src` otherwise
  resets it to zero and throws away the spot being worked on. Feeding a model the
  artefacts of a 32kbps encode instead of the real audio would be a quiet,
  expensive mistake, so the two keys are kept apart by construction rather than
  by remembering.
- **Ends are implied, not typed.** Marking the next tune's start marks the
  previous tune's end. An explicit end is only needed at the end of a set, where
  minutes of chatter follow. `end_ms` is therefore nullable, and NULL means
  "runs until the next segment starts" — never "unknown".
- **Waveform peaks are precomputed server-side.** Decoding three hours of AAC in
  the browser to draw a waveform is a non-starter on mobile; a ~230KB envelope
  is not.
- **The envelope is RMS on a fitted dB scale**, not peak amplitude on a linear
  one. See "Why RMS in dB" below — this is the difference between a tool that
  works and one that shows a solid block.
- **System-admin only.** This is a corpus-building tool, not a member feature.

## Data model (`schema/049_recording_tune_segments.sql`)

### `recording`

One audio file covering some or all of one session instance.

| Column | Notes |
|---|---|
| `recording_id` | PK |
| `session_instance_id` | FK, NOT NULL |
| `person_id` | FK, nullable — who made it. Person merge repoints this. |
| `storage_key` | S3 object key |
| `mime_type`, `duration_ms`, `file_size_bytes`, `sample_rate`, `channels` | from ffprobe |
| `is_clock_anchor` | exactly one per instance (partial unique index) |
| `clock_offset_ms` | ms after the anchor's t=0 that this file's t=0 falls |
| `started_at` | absolute wall-clock time of t=0, nullable |
| `peaks` | base64 of a Uint8Array, one 0-255 byte per bucket |
| `peaks_hz` | buckets per second (20) |

**Many recordings per instance** — several phones on the table, or one phone
that stopped and restarted — so they share an instance timeline: the anchor's
t=0 *is* the instance's zero point, and everything else states its offset from
it. Instance-relative time is `clock_offset_ms + <ms into the file>`; absolute
time is `started_at + <ms into the file>`.

Only the single-recording case matters today. `clock_offset_ms` exists so the
multi-recording case never needs a migration.

### `recording_tune_segment`

The junction: "this logged tune occupies this time range in this audio file".

| Column | Notes |
|---|---|
| `recording_tune_segment_id` | PK |
| `recording_id` | FK |
| `session_instance_tune_id` | FK — the tune reaches its `tune_id` through here |
| `start_ms` | NOT NULL |
| `end_ms` | **nullable — NULL means "until the next segment starts"** |

Unique on `(recording_id, session_instance_tune_id)`: a tune is placed at most
once per recording. The same tune played twice in a night is two
`session_instance_tune` rows, so this is not a constraint in practice.

Pointing at `session_instance_tune` rather than `tune` is what makes tune merges
free: `merge_tune_ids` remaps `session_instance_tune.tune_id`, and the segments
follow. (Spec 030's function used to `UPDATE recording_tune_segment SET tune_id`
directly; `schema/049` re-declares it without that step — see below.)

### `recording_tune_segment_resolved` (view)

**The artifact this whole spec exists to produce.** One row per placed tune with
its end resolved: implicit ends become the next segment's start, a trailing
implicit end becomes the end of the file. Carries `tune_id`, the display name,
the tune type, and both instance-relative and absolute start times. Slice the
audio on these and you have a labelled corpus.

## Why RMS in dB, fitted per recording

Measured on the real 3h17m B.D. Riley's recording: the envelope spans about
**22dB** end to end — from the between-tune murmur of a pub to the band in full
flight. Two consequences:

- **Peak amplitude hides the gaps.** A room full of chatter throws tall isolated
  spikes; a max-abs envelope renders talk and music as the same solid block,
  erasing exactly the distinction the operator is hunting for. RMS keeps the
  tune blocks visibly darker than the gaps.
- **A fixed dB window crushes everything.** Mapping 0 to -60dBFS puts the whole
  night in the top fifth of the scale. The window is therefore fitted to each
  recording's own 2nd and 99.5th percentiles, clipping the outer few percent so
  one shout or one dropped mic can't reset the scale.

## Ingestion

```bash
venv/bin/python scripts/import_recording.py AUDIO_FILE --session-instance 347 \
    --label "B.D. Riley's 2026-01-15" --started-at 2026-01-15T19:30:00-06:00
```

Probes with ffprobe, streams mono 16-bit PCM out of ffmpeg and reduces it bucket
by bucket (flat memory regardless of length), transcodes a playback proxy,
uploads both to S3, writes the row.

The proxy defaults to **32kbps mono at 22.05kHz** — roughly an eighth the size
of a 256kbps stereo master (45MB for a three-hour session, against 348MB), with
11kHz of bandwidth. That sits well above every fundamental in the room and holds
enough harmonic detail to tell one tune from another by ear, which was confirmed
by listening to encodes of a real session at four settings rather than assumed. `--stream-bitrate`
and `--stream-rate` change it; `--no-stream` skips it. It carries
`-movflags +faststart`, which puts the MP4 index at the front so the browser can
begin playing after the first range request rather than having to reach the end
of the file. Backfill an existing recording with
`--recording-id N --skip-upload`: the proxy uploads even under `--skip-upload`,
since that flag means "the master is already there". Target DB comes
from the usual `PG*` environment variables, so pointing it at production is
deliberately explicit.

## The tool

`/admin/recordings` lists what's imported and how far each is segmented.
`/admin/recordings/<id>/segment` is the tool: a Svelte page under the spec-035
thin-shell pattern (`serializers.build_recording_segmenter_payload` feeds both
the embed and `GET /api/recordings/<id>/segmenter`).

**The interaction is one key.** A cursor sits on the next tune in the log; find
where it starts in the audio, press <kbd>M</kbd>, the cursor advances. Ends come
free.

Except at the end of a set, where an explicit end IS wanted — and there
<kbd>M</kbd> means exactly that, rather than asking the operator to remember a
second key at the one moment they are least likely to. Having just marked a
set's last tune, the next press ends that set; the press after it starts the
next tune. <kbd>E</kbd> still works and is still needed for ending a set you
have already moved past. The banner and the mark button both switch colour and
wording while <kbd>M</kbd> means "end", so the mode is visible rather than
remembered — the original bug here was not the keystroke but the silence about
which one applied.

Two canvases over the same envelope:

- an **overview** of the whole night, every placed tune drawn as a coloured
  band — the progress bar — click anywhere to jump;
- a **detail tape** that runs under a fixed centre line, so the mark point is
  always in the same place on screen. Dragging scrubs, which keeps the finger
  off the mark point on a phone.

**Onset snap** (on by default, <kbd>S</kbd> toggles) nudges a mark to the
nearest sharp rise, and leaves it alone when the window holds no real onset.
The window is ±500ms and that number matters: it started at ±1.5s, which was
wide enough to walk a carefully-placed mark forward onto the next loud phrase
of a tune that had *already begun* — snapping confidently past the thing being
marked. Snap should only ever apply a correction. It also announces itself
(`snapped +0.35s — S to turn off`) rather than moving silently, which was the
worse half of that bug: no feedback, and no hint that the behaviour was
optional.

Writes are optimistic: the mark lands under the crosshair immediately, and a
failed save rolls it back and says so.

**The play button carries a spinner** until the browser can actually play, and
again if playback runs dry. This matters more than it sounds: the waveform
paints instantly from the precomputed peaks, so the page looks completely ready
while a 350MB file is still loading over cellular — reported from a phone as
"I thought it wasn't working". The button is never *disabled* while loading,
because `preload="metadata"` means the browser fetches nothing until asked:
disabling it would deadlock (no play → no load → no canplay → no play).

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/recordings/<id>/segmenter` | the full payload (= the page embed) |
| `GET /api/recordings/<id>/peaks` | the envelope as raw bytes, cached |
| `PUT /api/recordings/<id>/segments/<sit_id>` | place or move a tune (upsert) |
| `DELETE /api/recordings/<id>/segments/<sit_id>` | unplace a tune |
| `GET /api/recordings/<id>/export` | the resolved slice list |
| `GET /api/session-instances/<id>/recordings` | recordings + progress |

PUT is an upsert keyed on `(recording, tune)` rather than a create-then-update
pair, so re-marking is the same call as first-marking and the client never has
to track whether a segment exists.

Peaks are served as binary rather than inside the JSON payload: ~230KB for a long
night, which base64 would inflate by a third and which has no business blocking
first paint.

## Consequences elsewhere

- `merge_tune_ids` is re-declared in `schema/049` with its
  `UPDATE recording_tune_segment SET tune_id` step replaced by a count taken
  before the `session_instance_tune` remap. The returned JSON keeps its
  `recording_tune_segment.updated` key.
- `services/person_merge_service` still repoints `recording.person_id`, which is
  why that column survived the reshape.
- The spec-022 API handlers and their `INLINE_AUTH` allowlist entries are gone.

## Status

Working end to end. Verified against the real B.D. Riley's recording: import,
waveform, marking, implicit/explicit ends, undo, and export all confirmed in the
browser and in the DB.

Not done, deliberately: no in-app upload (the CLI is the ingestion path), no
multi-recording UI (the schema supports it; nothing needs it yet), and no
audio-slicing export — `GET .../export` hands you the cut list, and ffmpeg does
the cutting.

# 053 Ceol Listen — the lab

Work out which tune is playing from a recording of a session, and get better at
it every time compute or a new idea is thrown at the problem.

This spec describes a **milieu**, not a recogniser. The recogniser will be an
ensemble of small experts, none of which exists yet, and the thing worth
designing first is the environment in which experts are proposed, scored,
combined, and replaced. Spec 050 produced the labelled corpus this depends on:
455 human-placed tune segments across eight nights at B.D. Riley's, 274 distinct
tunes, fifteen and a half hours. That corpus is an **evaluation set**, not a
training set. It is small enough that any claim of improvement needs error bars,
and precious enough that nothing should get to see it twice by accident.

The design conversation that produced this is kept verbatim in
[053 files/design-conversation.md](053%20files/design-conversation.md); the
build order is in [053 files/steel-thread-plan.md](053%20files/steel-thread-plan.md).

## Two loops

Everything in the lab belongs to one of two loops, and confusing them is the
first way this goes wrong.

The **ensemble loop** answers "is the whole system better". A *run* replays a
recording through the board with a named configuration of experts, and the
harness scores the hypotheses it produced against the segments. It is slow —
a pitch tracker over three hours of audio is tens of minutes — and it is the
only thing that measures what a player at the table would feel.

The **bench loop** answers "does this idea have any promise" for one narrowly
defined task, in seconds. "Is a tune playing right now." "Is there a tune
boundary within three seconds of here." "Which of these two confusable tunes is
this." A candidate is any function from cached features to a prediction, rule
or model, and the bench scores it leave-one-night-out. Candidates that score
graduate into experts. **Nothing joins the ensemble because it seemed
reasonable**; its bench result is the reason it is there.

## Design decisions

- **The corpus is for evaluation.** The eight nights share a room, a table and
  most of the same players, so a split by tune would flatter every method that
  learns the room. Every score in the lab is computed leave-one-night-out, and
  the bench enforces that split rather than trusting each candidate to. Learned
  candidates are allowed — some of these tasks will need them — but they are
  small, and they are evaluated on nights they never saw.
- **Replay is the harness.** A recording is a stream of arrival chunks with a
  virtual clock; the live pipeline will consume the same interface with a real
  one. Every experiment is "replay these ranges with this config", and a run can
  be restricted to two segments of one night because a three-hour pass is not
  how ideas get tried.
- **A blackboard over observation types.** Experts read typed observations off
  a shared board and write typed observations back. The dependency graph is over
  *types*, not experts: the matcher consumes `interval_sequence` and does not care
  which of three transcribers produced it. Several experts producing the same type
  is the normal case, not a conflict, and disagreement between them is visible
  on the board. The driver is reactive — an expert reruns when new input of a
  type it consumes lands — and feedback (a strong hypothesis informing a
  transcriber) is permitted; the once-per-chunk rule keeps it from looping.
- **Provenance on every row.** Every observation records the expert that wrote
  it, that expert's version and parameters, the observation ids it read, the
  window of audio it actually looked at, and what it cost. Every observation and
  hypothesis is keyed by a *run*, and a run's configuration is stored whole, so
  any past run can be re-executed when a better transcriber turns up.
- **Arrival chunks and analysis windows are different things.** Chunks are how
  audio lands and what advances the clock; live, they are the upload granularity
  and a hard floor on latency. Windows are what an expert reads: each declares
  its own length and hop on a fixed grid, reads any range of audio up to the
  clock, and stamps the window it used. A pitch tracker wants ten seconds; a
  boundary detector wants thirty on either side; a matcher wants the last forty
  notes whatever their duration. Both are configuration, and both get swept.
- **Non-audio evidence is an expert like any other.** The session's repertoire,
  what has been confirmed tonight, the expected length of a reel — these are
  producers of observations, composed with audio evidence by the same
  assembler. This is the advantage over an app that listens for ten seconds in
  isolation. The night's *logged* order is never evidence: it is the ground
  truth's sibling, stored in the manifest for later oracle experiments and
  never read by an expert.
- **Boundaries are first-class.** Two problems the segments distinguish: music
  versus not (the gaps between sets), and tune changes inside a set, which have
  no silence at all. The assembler must expect the tune it is confidently
  nailing to stop being the tune that is playing. It closes and reopens spans on
  `boundary` observations and carries a duration hazard, and the first boundary
  producers come off the bench rather than being assumed from energy — a noisy
  pub has big waveforms outside the tune.
- **Hypotheses have a lifecycle and are a distribution.** Proposed, updated,
  superseded, withdrawn, confirmed, each over a time span, each carrying ranked
  candidates with confidences rather than one answer. "One of these two" is an
  honest state and the contract can say so. Confidence should sharpen as a tune
  is heard for the second and third time.
- **Value of information, not run everything.** Experts declare cost. A
  scheduler hook decides whether an expensive expert runs on this window, skips
  are logged as observations, and the harness reports cost per minute of audio
  alongside accuracy. The first rule is a hand rule; the hook is what matters.
- **Calibration is measured.** Stopping early on a confident wrong answer is
  the failure that would make this feel broken, so the harness reports whether
  ninety percent confidence is right ninety percent of the time.
- **Lab and runtime are separate.** The lab is a package in this repo with its
  own dependencies, excluded from deploy, from the app's test collection and
  from its coverage denominator, but not from lint. Nothing reaches a runtime
  worker that has not been scored here. Nothing runs on the phone: a phone-side
  computation cannot be replayed or re-run with provenance.

## Data

Everything lives under `lab/data/`, which is gitignored. The corpus is pulled
from production read-only; the board is SQLite.

### Corpus

Per recording, `recordings/<id>/`:

| File | Contents |
|---|---|
| `manifest.json` | the `recording` row; session id, date, name; every segment from `recording_tune_segment_resolved` with `end_is_explicit` and `implicit_trailing`; the session's repertoire (`session_tune ⋈ tune`); the night's logged order (ground truth only); `pulled_at`, `source_db` |
| `master.<ext>` | the master audio, always `storage_key`, never the playback proxy |
| `mono22k.wav` + `.sha1` | one derived mono 22.05 kHz decode; sample-exact seeks and the hash every cache key hangs off |
| `features.npz` | bench features on a 100 ms grid: 64-band mel in dB, 12-bin chroma, RMS dB, onset strength |

`corpus/tunes.csv` is the public thesession.org dump (one row per setting,
~50k tunes), the same file `services/tune_merge_scan_service.py` already
reads weekly. Ceol's `tune_id` *is* thesession's id, so ground truth and corpus
compare directly. `index/<set>-n5-v<parser>.pkl` is an interval n-gram index
over a named candidate set — `all`, the session's `repertoire`, or the
deliberately optimistic `eval_tunes`.

Two things about the segments that every label-cutting routine must know:

- **`end_ms IS NULL` means "until the next segment starts."** Inside a set that
  is an accurate tune boundary. At the end of a set it silently absorbs the
  chatter that follows. So implicit ends are boundaries for the identification
  and boundary tasks, and the region after one is *excluded* from the
  music-activity task. Only explicit ends say music stopped.
- A trailing implicit end runs to the end of the file (one is 5,475 s). The
  harness caps those at ten minutes and flags them.

### Board (`board.sqlite`)

| Table | What a row is |
|---|---|
| `run` | one configuration applied to one recording over a stated range: `run_id`, `name`, `recording_id`, `config_json` (complete, including the range), `git_sha`, `status`, `audio_ms`, `wall_ms`, `parent_run_id` when re-executed from a stored config |
| `observation` | append-only: `type`, `t_start_ms`/`t_end_ms` (the window read), `clock_ms` (when it was produced), `expert`, `expert_version`, `params_json`, `inputs_json` (observation ids), `payload_json`, `cost_ms`, `cached` |
| `hypothesis` | a span the assembler believes is one tune: `t_start_ms`, `t_end_ms` (NULL while open), `status`, `opened_by` (`boundary`, `first_match`, `rival`), `superseded_by` |
| `hypothesis_event` | each lifecycle event with the ranked candidates at that moment (`ranked_json`, `top1_tune_id`, `top1_conf`) and the `obs_id` of the `hypothesis_update` observation that carries its provenance |
| `eval_segment`, `eval_boundary` | the harness's per-segment and per-boundary results for a run |
| `bench_result` | one scored candidate: task, candidate, version, params, features version, per-night and pooled metrics, git sha |
| `expert_cache` | expert output keyed on `(expert, version, params, audio sha1, window)` so downstream experiments never re-run a transcriber |

Audio never goes in SQLite. An `audio_chunk` observation carries a hash and a
sample count; the board serves samples for any `(t0, t1)` up to the clock from
the wav.

### Observation types

| Type | Payload | Produced by (steel thread) |
|---|---|---|
| `audio_chunk` | `sha1, sr, n_samples` | the chunk source |
| `music_activity` | `score, is_music` | `music_energy` (graduated bench baseline) |
| `boundary` | `t_ms, strength, kind` | `boundary_novelty` (graduated bench baseline) |
| `pitch_track` | `source, hop, times_ms[], f0_hz[], voiced_prob[]` | `pitch_pyin`, `pitch_yin` |
| `note_events` | `source, notes[{t0_ms, t1_ms, midi, conf}]` | `notes` |
| `interval_sequence` | `source, intervals[], note_t0_ms[], n_notes` | `intervals` |
| `tune_match` | `source, candidates[{tune_id, setting_id, score, hits, n_grams_queried}]` | `matcher` |
| `tune_prior` | `weights{tune_id: w}, default_w, basis` | `prior` |
| `hypothesis_update` | the ranked snapshot, mirrored into `hypothesis_event` | `assembler` |
| `scheduler_skip` | `expert, reason, top1_conf` | the scheduler |

A new type is a row in this table and a producer; nothing else changes.

## Experts and the driver

```python
class Expert(Protocol):
    name: str; version: str
    consumes: tuple[str, ...]; produces: tuple[str, ...]
    cost: float                  # relative, per second of audio
    params: dict                 # from the run config; stamped on every observation
    window: WindowSpec | None    # length, hop, lookahead — or None for event-driven
    def process(self, view: BoardView, window: Window) -> list[Observation]: ...
```

The version is bumped whenever the output's meaning changes, which invalidates
the cache. The `BoardView` an expert receives is read-only: audio for any range
up to the clock, observations of a type since it last ran, the manifest, the run
config, the open hypothesis, the confirmed tune ids.

The driver orders experts by a topological sort over types (cycles tolerated,
ties by config order). On each arrival chunk it appends the `audio_chunk`,
advances the clock, then loops: windowed experts run once for every grid window
that has become complete (a detector with fifteen seconds of lookahead is late
by fifteen seconds, and the harness measures that), event-driven experts run
when something they consume is new, each expert at most once per chunk, and the
scheduler may skip any of them with a logged reason. The loop ends when nothing
new lands.

The steel thread's experts, in dependency order: `music_energy`,
`boundary_novelty`, two pitch trackers, note segmentation, interval sequences, a
5-gram matcher over the corpus index, the repertoire prior, and the assembler.
Each carries a written "known weakness" in its docstring, because the point of
the steel thread is to look at each part and ask whether it is doing what we
expect — not to be right.

The assembler accumulates matcher evidence per tune since its span opened,
turns it into a posterior with the prior and a reserved "something else" mass,
sharpens the temperature as evidence accumulates, and applies a change hazard
that grows with elapsed time against the expected length of the top candidate's
tune type (a reel three times through is about 110 seconds, which is also the
corpus median). A `boundary` closes the span and opens a new one; a change of
top candidate supersedes; four seconds of non-music closes.

## The bench

A **task** is a name, a rule that cuts labels from manifests onto the feature
grid, and a scorer. A **candidate** declares which features it needs and a
`predict(features, t_ms)` returning scores on the grid; learned ones also `fit`.
The bench fits on seven nights, predicts the eighth, rotates, and records
per-night and pooled metrics with the parameters and feature version, so a
leaderboard for a task shows spread across nights and not just a mean.

| Task | Label | Score |
|---|---|---|
| `music_activity` | 1 inside a segment; 0 from an explicit end to the next start; excluded after an implicit end | frame accuracy, precision, recall |
| `boundary` | 1 within ±3 s of a segment start or explicit end | recall and precision at tolerance, false boundaries per hour, precision–recall over the peak threshold |
| `tune_pair` (later) | which of two tunes sharing many n-grams | accuracy |

The first candidates are deliberately mixed — an energy rule, a logistic
regression on mel frames, chroma self-similarity novelty, a key-change
detector, a logistic regression on mel deltas — so the bench's first output is
a ranking with rules and models on the same axis. Placeholders exist for an
audio-embedding probe and for "the matcher stopped matching".

**Graduation** is a wrapper: `CandidateExpert` runs a bench candidate over its
declared window on live features and emits `music_activity` or `boundary`. Its
params record the bench result it came from.

## The harness

`lab eval RUN` scores a run two ways and writes both as JSON and markdown.

**Identification**, per segment with a `tune_id`, at least ten seconds long,
inside the replayed range: time to first correct (the offset at which the right
tune first became top-1), time to stable correct (after which it stayed
top-1 to the end), top-1 and top-5 at the segment's end, the number of
provisional flips, the final confidence, and the cost of every observation in
the window. Aggregates report proportions with Wilson intervals, "found within
30 s / 60 s" rather than medians over never-found segments, a calibration table
with expected calibration error, and cost per audio minute by expert.

**Segmentation**, ignoring identity: recall and precision of predicted
boundaries at ±1, ±3 and ±5 seconds, false boundaries per hour, the median
error of matched ones, and detection latency (the clock at emission minus the
true time — which is how lookahead shows up). The assembler's own span opens
and closes are scored the same way, separately. Music-activity accuracy is
scored only over regions where the labels are trustworthy.

`lab diff A B` puts two runs side by side with deltas and both intervals, lists
segments each run fixed or broke, and refuses to compare runs that replayed
different segments unless told to intersect.

## Inspection

The tools exist so a human can look at one part and judge it:

- `lab timeline RUN` — per segment: the truth, the boundary marks with their
  errors, then every hypothesis event with a star where top-1 was right. Read
  first.
- `lab board RUN --type T --range` — the observations themselves, with expert,
  version, window, cost, inputs, and a per-type summary; `--json` for payloads.
- `lab transcribe --recording N --segment K --source S [--match]` — the pitch
  and note experts alone over one segment, printed as ABC-ish text a player can
  compare with the tune, and the matcher's top ten for that window.
- `lab bench leaderboard --task T` — candidates ranked with per-night spread.

## Runs and re-execution

`lab run --config C --recording N --segments 5-6` writes the complete
configuration, including the selection, into the run row. `lab run --from RUN`
re-executes exactly that, recording the parent. A sweep is several configs and
`lab diff`. Reproducibility for anything with a GPU in it means "within
tolerance", and the harness should say so rather than pretend.

## Lab versus the app

`lab/` is a package with one CLI (`venv/bin/python -m lab`), its own
`requirements.txt` (numpy, scipy, librosa, soundfile, scikit-learn) installed
into the same venv, and its own pytest configuration. Render installs only the
root requirements, so none of it deploys. The root `pytest.ini` does not recurse
into it and `.coveragerc` omits it, because coverage counts never-imported files
at zero and a package this size would sink the app's threshold. `make lint`
covers it; it is repo code.

It reuses what the app already has rather than duplicating it: S3 access and
ffmpeg from `recording.py`, the dump download from the merge-scan service, the
`--database-url` guard from the import script. Production is read only
(`default_transaction_read_only=on` on the connection) and the pull is
idempotent.

## What this is not

Not a runtime. Not a live recorder (that is the phone-as-durable-buffer work,
and it belongs with spec 024's op vocabulary, where the recogniser will be one
more participant proposing and retracting). Not a claim that any of the first
experts are good — the transcribers are monophonic trackers pointed at a room
full of heterophony and the matcher is five-gram voting with no rhythm. The
claim is narrower: every concept above is exercised end to end, every part can
be inspected on its own, and the next idea has somewhere to be scored.

## Status

Built and running against synthetic audio; **not yet run against the corpus**.

Working end to end: the corpus pull and the ABC parser (99.99% of the 55,384
settings in the public dump parse), the interval n-gram index, the feature
grid, the bench's tasks and five candidates, the board, the reactive driver
with windows and the scheduler hook, all nine experts, the identification and
segmentation harness, and the four inspection tools. Forty-two lab tests pass,
eleven of them driving the whole thread on a synthetic night rendered from
indexed ABC. That fixture removes every hard thing about the problem — no
room, no heterophony, no chatter — so it proves the machinery and nothing
about accuracy.

**Blocked on two things, both outside the code.** A production database URL,
for `lab pull` to write manifests; and AWS credentials in `.env`, for it to
fetch the master audio. Until then no real night has been pulled, the bench
has never been scored on real labels, and the two learned candidates have
never been fitted.

**Seven corpus fixes are wanted before the first real scoring run.** Six
segments have no explicit end where the log says a set ended, so their tails
have swallowed chatter — recording 4's last tune runs 91 minutes to the end of
the file, and five others by one to three minutes. One segment in recording 1
ends 583ms after the next one starts. With those fixed, `end_is_explicit` is
authoritative and the set-break cross-check stays a warning that should never
fire.

What the synthetic run already shows, and expect to see again at scale: the
assembler holds on to a tune after it has stopped. With no boundary detected
it kept claiming the first tune through the whole of the second, because
accumulated evidence for an open span outweighs a newcomer. The change hazard
exists for this and is plainly not yet strong enough. Separately,
`boundary_novelty` reads a two-minute window with sixteen seconds of
lookahead, so it says nothing at all about the first two minutes of a night —
a fast, low-precision partner is the obvious next producer of that type.

Costs measured on the synthetic run, per minute of audio: pyin about twelve
seconds, yin about a third of a second, everything else under a tenth. A full
pass of the 15.6-hour corpus is therefore a few hours, dominated entirely by
pyin, which is what the window cache and `--segments` exist for.

Not done, deliberately: no learned candidate has graduated (the lab does not
persist fitted models yet, and `CandidateExpert` refuses rather than guessing);
no `tune_pair` task; no audio-embedding probe; and nothing runs live.

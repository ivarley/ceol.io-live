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

Both loops run against the corpus, the recogniser works, and the largest
single improvement came from a sentence of domain knowledge rather than from
anything the harness could have discovered on its own.

### Where it stands

On the retrieval bench, all 503 segments, two minutes of audio each:

| Configuration | top-1 | top-5 |
|---|---|---|
| yin, absolute pitch, 130Hz band | 0.485 | 0.706 |
| pitch folded to classes | 0.616 | 0.793 |
| and the band raised to 160Hz | 0.702 | 0.825 |
| and fused repeats split back apart | 0.775 | 0.880 |
| and read again as runs of eighths, fused | 0.833 | 0.912 |
| and each set decoded as a whole | 0.861 | 0.922 |
| and the tracker kept off a third of the pitch | **0.878** | **0.930** |
| the session's transitions alone, no audio | 0.245 | 0.368 |

A whole night through the board scores top-1 60.3%, top-5 75.9%, median time
to first correct 52 seconds, at 56x realtime.

Against the full 23,307-tune corpus rather than the session's 1,279-tune
repertoire, set decoding scores the same to within a point. The transition
prior concentrates probability where it belongs, so the repertoire
restriction is unnecessary and these numbers are not an artefact of a small
candidate set.

### What moved it, in order

**Octave carries no information.** No two Irish tunes, and no two parts of
one, differ by octave alone. The matcher already worked this way without
anyone deciding it, because folding an interval to its nearest direction is
the same operation as taking the difference of pitch classes. The note
segmenter did not, and it mattered: a tracker that jumps an octave inside a
held note made the run-length step cut that note in two and insert an
interval the tune does not contain. Folding first is worth thirteen points.
The viewer and the labels now work in one octave for the same reason.

**Splitting fused repeats**, which the grid made possible and which is worth
seven points. Two eighth notes of the same pitch in a row look exactly like
one quarter note to a run-length step over a pitch track, because the pitch
never changes. The corpus notates them as two notes, so the zero between them
is a real symbol the transcription was dropping: the notation has a repeated
note in 8.1% of its intervals and the plain segmenter recovered 4.1%. One
repeat in two was lost.

A grid alone cannot fix it, because a held note and two struck notes of the
same pitch occupy the same span, so the split is gated on an onset at the
interior grid line. The gate has to be tight. At a third of a grid spacing it
LOSES thirteen points, because a session has an onset near almost every line
and everything long gets cut; at an eighth of a spacing it gains seven. The
crude control, split every long note, triples the repeated-note rate and is
much worse than not splitting at all.

**Keeping the tracker off a third of the pitch**, worth a point and a half,
found by labelling eight bars of a solo tin whistle that the recogniser had
never once identified.

Every wrong note on it was wrong by the same interval: F# heard as B, B as E,
D as G, each a fifth below the note played. With no accompaniment that could
only be the tracker, and the frequencies said how. It reported 248Hz for an
F# at 740Hz, which is exactly a third of it, and 88% of the frames under the
labels were below 587Hz, the lowest note a D whistle can play. yin had
settled on three periods of the waveform instead of one.

A multiple of two or four would not have mattered, since pitch is folded to
one octave. Three does matter: a third of a frequency is a twelfth below it,
a different note name, and no folding undoes that. Two changes, each
measured on the hand labels and then on all 502 segments:

- yin's `trough_threshold`, which decides how readily the shortest period
  with a dip is accepted, raised from librosa's 0.1 to 0.5. The whistle went
  from 25% of labelled time right to 42%, the other labelled segments rose
  slightly, and at 0.8 they fell away. Across the corpus with set decoding,
  0.861 to 0.873 top-1.
- A correction for the error that remains: where the energy at 3*f0 is three
  times what sits at f0 and 2*f0, the note is taken to be 3*f0. An octave
  error still has energy at 2*f0 and is left alone. At a ratio of 1.5 it also
  fired on correct notes and cost a point of notes-only top-1; at 3.0 nothing
  is lost and the corpus reads 0.878 top-1, 0.930 top-5.

Together they take the whistle to 43% of labelled time right. That is still
poor, and the rest is not explained yet: with both in place, nearly half the
frames under the labels still sit below anything the instrument can play.

**A slip jig's bar is not in the onset envelope**, which is a negative worth
keeping. The estimator only asks whether a beat divides in two or three, and
then assumes every triple-time tune has two beats to a bar; a slip jig has
three. Autocorrelation at three beats beats two beats on only 11% of the 18
slip jigs, against 5% of the 180 jigs, so it separates nothing. It costs
identification nothing either -- slip jigs are at 0.944 top-1, since the
eighth-note reading never needed the bar -- but it does mean the viewer's
estimated bar lines are wrong on every slip jig and slide, and something
other than onset energy will have to say where their bars are.

**Writing both sides as runs of eighth notes**, worth six points, and the
idea came from a player looking at the stave rather than from the bench.

A transcriber hears pitch and not articulation. Two tongued Gs and one held G
of the same length are the same pitch track, and nothing in a monophonic
tracker will separate them, so the matcher was being asked to distinguish
something it had no evidence about. Writing every note longer than an eighth
as a repeat of itself, on the transcription AND on the corpus, removes the
question: the notation's `GG` and its `G2` both become two eighths, and so
does whatever the tracker heard.

It is not free, because it leans on the grid being right where the plain
reading does not. Alone it takes top-1 from 0.776 to 0.816, but unevenly:
reels go 0.734 to 0.797 and jigs 0.844 to 0.906, while hornpipes fall 0.857
to 0.643 and polkas 0.731 to 0.615. The two readings are wrong about
different tunes, which is the condition under which fusing two opinions is
worth anything, and fusing them by score beats both on every tune type:
0.834 overall, with hornpipes at 0.929 and slides at 0.667 above either view
on its own. Segments never found at all fall from 7.0% to 4.0%.

**Two things that help the reader and not the matcher.** Both came from a
player, both are right about the music, and both are measured as changing
nothing or slightly worse for identification, so they live in the viewer
and not in the index.

The grid used to hold one tempo for a whole segment, taken from its first
minute. Measured in twenty-second windows the tempo moves by 1.4 to 2.6%, and
on Father Kelly the whole-segment estimate was also biased -- 139.3ms where
the windows and a hand-drawn beat both say about 142.7 -- so a fixed grid
ended the segment 1.48 seconds adrift, ten and a half eighth notes, and the
bar lines slid visibly off the notes. Against the hand-marked bar lines on
that reel, a fixed grid anchored on the first mark was 0.72 eighths out after
five seconds and 3.26 after nineteen; a grid that follows a tempo map built
from those windows stayed under 0.3 through twelve seconds and was 0.94 out
at nineteen. The viewer's grid, its stave and its extension of hand-drawn
beats beyond where they were drawn now all follow the map. The matcher does
not care: top-1 is 0.840 either way, because it compares six-interval
phrases about a second long, and a 2% tempo error does not change how many
eighths a note lasts locally, only where the grid is a minute later.

Rests are rare in this music, so a gap in a transcription is much more often
a note the tracker lost than a silence. The stave now holds the note before a
gap of up to a bar, which took Father Kelly from 45 rests to none. The
matcher leaves gaps open: holding them for up to 2, 4 or 8 eighths gave
0.832 top-1 against 0.840, because an open gap tells the index "unknown" and
costs nothing, while a held one guesses the pitch and a lost note was
usually not the pitch before it.

**The melody band.** Sweeping the tracker's lower bound: 0.616 at 130Hz,
0.702 at 160, 0.666 at 190. Below about 150 it is offered energy that is not
the melody at all, and takes it. Independent of the fold, which was the
surprise.

**Interval folding** took top-1 from 0.137 to 0.338, with the control that
the same n-gram length unfolded scores 0.137.

**How long it listens**, the latency-against-certainty curve: 0.123 at ten
seconds, 0.338 at thirty, 0.485 at ninety, still climbing at two minutes.

**Decoding a whole set.** Handed the true previous tune the prior was worth
twelve points; chaining its own answer forward, one, because that answer is
often wrong and a transition conditioned on a wrong tune is noise. Scoring
whole sequences recovers most of the difference.

**A voicing threshold** that discarded 96% of pyin's output, because its
voicing model is built for one instrument and this is six.

### The grid, and what one hand-drawn segment overturned

Nothing in the matcher uses rhythm yet: the index compares pitch shapes and
throws every duration away. Putting the transcription on the same grid the
corpus is notated on requires knowing where that grid is, and the first
attempt assumed the fastest steady periodicity in a recording is the eighth
note.

Hand-drawing the beats on one jig killed that assumption outright. Against
Coleman's Cross, whose eighth is 159ms, the onset envelope correlates 0.011
at 159ms, 0.060 at two eighths, 0.455 at the 478ms beat and 0.464 at the
955ms bar. The eighth is not the weakest of the three levels, it is absent:
players slur and roll across it, so most eighths are never struck. The
estimator, told to search between 110ms and 300ms, could not see the beat at
all and returned whatever noise sat in its band.

So the beat is found first and the grid divided out of it. Surveying 288
segments, the tallest autocorrelation peak is the beat every time, and the
meter is legible in where the subdivision peaks sit relative to it:

| | subdivision peaks, as a fraction of the beat |
|---|---|
| reels, polkas | 0.50, 1.00, 1.50, 2.00 |
| jigs, slip jigs | 0.36, 0.64, 1.00, 1.36 |

Halves against thirds, which is the definition of the reel-versus-jig
question rather than a proxy for it. Scored against the tune types the corpus
records, that reads the meter right on 0.95 of 288 segments where searching
for the eighth directly managed 0.80 of the 244 it answered at all.

The triple peaks sit at 0.36 and 0.64 rather than 0.33 and 0.67 because a
jig's first eighth is longer than its second, which is most of what makes it
sound like a jig. The period is still reported as an even third, because the
corpus notates it evenly and the grid exists to line the two up.

One more correction came out of the same survey. Reels were landing with a
median beat of 322ms and a 95th percentile of 603ms, which is one
distribution with a copy of itself at twice the period: a half-bar inherits
every peak the beat has, so it scores at least as well and wins about a fifth
of the time. Stepping down an octave whenever half the period is still a
plausible beat collapses that to 255-376ms and leaves the meter accuracy
untouched. It is safe only because the band stops it, since a reel's eighth
IS articulated and nothing in the curve distinguishes it from a beat; what
distinguishes it is that 161ms is not a tempo anyone's foot keeps.

On both segments with drawn beats the period is now exactly right, 147ms
against 147 on a reel and 159 against 159 on a jig, and so is the meter.

The reel is the one that tested the design, because it is played with a
swing. Its eighth note is 147ms and the onset envelope correlates 0.014
there: with the eighths uneven, no two consecutive onsets are the same
distance apart, so the eighth has no periodicity at all. The swung PAIR does,
reaching 0.685 at 294ms. Finding the beat and dividing is what survives that;
searching for the eighth could not have found it.

It also exposed a hole in the annotation format. The drawn beats came out
twice too slow, because the format recorded a meter where what it needed was
how many eighth notes are inside one drawn beat. A reel counted in two has
four and counted in four has two, and it is the same reel. The notation
settles which: at a 147ms eighth the segment is 3.07 times through the tune,
which is what a session plays, and at 295ms it would be 1.53 times, which is
nothing. The field now records eighths per beat, and offers 2, 3, 4 and 6.

Phase is still not settled. The estimate sits 54ms from a line fitted through
the drawn beats on the reel and 57ms on the jig, and those beats scatter 61ms
and 32ms rms about their own lines, so the error is the same size as the
ground truth's noise. The transcribed note onsets cannot adjudicate it
either, since even the best-fitting grid sits 31.7ms from them against 39.9ms
for a random phase.

**The downbeat is not the problem. The beat phase is.** Three hand-marked
segments took two goes to read, because the first reading was an artefact of
how they were scored.

| | Castle Kelly | Father Kelly | Coleman's Cross |
|---|---|---|---|
| | reel | reel | jig |
| period | right | right | right |
| beat phase, as a fraction of a beat | -0.43 | +0.47 | +0.12 |
| bar phase, as a fraction of a bar | +0.15 | +0.15 | +0.06 |

Half a beat is as wrong as a beat phase can be, so both reels are close to
maximally wrong and the jig is close to right. The bar error then follows
from it: the estimated bar line is built as the beat phase plus a whole
number of beats, and on all three the bar error equals the beat error to
within the noise of the marks. Choosing WHICH beat starts the bar is already
right. Placing the beats is not.

Two scoring bugs had to be fixed before that was visible, and both had made
the estimator look better than it is:

- Phase error was wrapped at the eighth note, so it could never report more
  than half an eighth however wrong the grid was. A grid sitting on the
  offbeat came back as "54ms", which sounded like precision. Wrapped at the
  beat it reads 0.43.
- The true phase was fitted against each beat's position in the list rather
  than against elapsed beats. Marks are drawn in patches, so a nine-second
  gap counted as one beat, and on Castle Kelly the fit put the first beat at
  -4668ms, before the segment began. Every phase number taken from it was
  meaningless, including the "+1.19 and +1.20 eighths, identical on two
  reels" that looked like a systematic offset worth correcting.

The reason is visible in the onset envelope, folded onto one beat starting
where the beat truly starts:

| | energy across one beat | peak-to-trough |
|---|---|---|
| Coleman's Cross | `+##+...+..+#+.+.` | 0.61 |
| Castle Kelly | `+.+++..+#+++++++` | 0.52 |
| Father Kelly | `++++++++++++++++` | 0.06 |

The jig's energy peaks where the beat starts. Father Kelly's is flat: there
is nothing in it to lock onto, and the phase fitter returns what amounts to a
coin toss. Castle Kelly has structure and still chooses wrong, because its
strongest moment is in the MIDDLE of the beat rather than at its start.

So onset energy locates the period reliably and the phase not at all, at
least on reels, and no constant correction can fix that: one of these two
reels has no signal to correct and the other has a signal pointing the wrong
way. Phase has to come from somewhere else. The candidates worth trying are
the transcribed note starts rather than the spectral flux, the fact that a
bar tends to begin a melodic phrase, and the tune's own eight-bar repetition,
which is a much longer lever than anything inside one beat.

### What did not work, and is on the board anyway

Harmonic separation plus a melody band took yin from 0.109 to 0.024. A tune
type classifier reaches 0.799 accuracy against a 0.480 baseline and is worth
three points alone, but nothing once sets are decoded, because sets do not
mix types and the transitions already knew. Weighting the prior by each
segment's own evidence strength does not help, because scoring in log space
already self-normalises: a weak segment's candidates sit close together, so
the sequence dominates without being told to. Predominant melody extraction,
the method with the best story for this music, is still behind yin. A third
tracker in the fusion adds nothing.

Breaking the phrase at a folded tritone does nothing either, which is worth
knowing because the tritone looked like the most damaged symbol in the
transcription: it appears in 1.4% of the transcription's intervals against
0.1% of the notation's, a 23-fold excess in a music that is almost entirely
diatonic. Refusing to let an n-gram span one changes top-1 and top-5 by
nothing at all across 125 segments and 987 tritones. They were already
harmless, because scoring counts the phrases that match rather than the
fraction of the query that matched, so a phrase built on a symbol the corpus
does not contain never votes and costs nothing by existing. That reasoning
stops holding the moment scoring is normalised by query length, which is why
it is written down.

### The tools that found all of it

`lab timeline` reads a run segment by segment. `lab trace-set` shows one set
at every stage: heard, shaped, matched, expected, decided. `lab view` plays
the audio with the notes drawn over it, sounds them as sine tones, sings the
labels over the music, and is where hand-drawn pitch labels come from.
`lab bench pitch` scores a front end against those labels directly rather
than through what it happens to retrieve. The same viewer draws in the beats,
and `lab bench pulse` scores the grid estimator against them. `lab suspects`
lists labelled segments whose audio does not sound like a tune.

That last one exists because of a miss the lab could not see. A segment
labelled as a reel was two and a half minutes of between-sets noise with the
tune stapled to the end, and it had been counting as a failure in every run
since the corpus was pulled. It was spotted by ear in seconds. The measure
that separates it is the height of the onset envelope's autocorrelation at
the beat: music repeats and a room between sets does not. That segment read
0.047, and once the label was corrected the same audio read 0.334 and the
tune came back at rank 1 from rank 84.

The measure also predicts accuracy in general, which is the more useful half:

| pulse strength | segments | top-1 | never found |
|---|---|---|---|
| under 0.10 | 6 | 0.333 | 0.500 |
| 0.10-0.28 | 51 | 0.529 | 0.275 |
| over 0.28 | 445 | 0.809 | 0.043 |

It is not a label checker. Plenty of weak-pulse segments are labelled
correctly and simply have no dance rhythm, which is what a slow air is, so
the report shows the tune type and leaves the judging to a person. Nor are
these segments candidates for removal from the eval set: a recogniser that
only works where the pulse is strong is not one worth having.

Reading the trace across two nights gave the clearest statement of the
bottleneck: everything turns on how much of the tune's notation the
transcription recovers. Above twenty shared six-note phrases the system is
right six times in seven; below ten it is never right.

### Two places the loops had drifted apart

Both found by building the grid, and both the same shape as the bug that
motivated sharing the segmentation code in the first place.

The board's pitch expert was reading from 130Hz while the bench had been
measured at 160 and the board's own config claimed 160 in its comment. Fixing
it is worth five points of top-1 on a whole night, and the reason it went
unnoticed is that nothing compared the two configurations, only the two
implementations.

The note splitter then grew a second copy of its own mode-to-behaviour
decision, one in the front end and one in the expert, and they disagreed
within the hour: the front end honoured the crude mode and the expert
silently ignored it. There is now one entry point that both call, and the
agreement test exercises the splitting step rather than only the segmenting
one. Extending that test immediately turned up a real defect -- a note
beginning a fraction of a millisecond before a grid line was split into a
sliver and the rest, and the sliver rounded to zero length with the same
pitch as its neighbour, so the splitter was inventing the very repeated notes
it exists to recover.

### The board against the bench

They answer different questions and the gap between them is mostly that. The
bench is handed each segment and decodes a whole set once it has heard it;
the board must answer while the tune is playing, without being told where
tunes start. An oracle that reads true segment starts closes three and a half
points of it and halves the time to first correct, from 58 seconds to 31, so
boundaries matter for how fast it knows far more than for whether it knows.

Two things that follow from that, both measured and both off:

- Clearing the interval window at a detected boundary is right in principle
  and harmful in practice, because the detector's precision is 0.26 and three
  resets in four throw away good context.
- Retroactive revision, letting a later tune change what was said about an
  earlier one, is worth eight points on the bench and costs fifteen on the
  board. The bench decodes segments; the board decodes spans, and with
  boundaries this noisy those spans are not tunes. Decoding a sequence of the
  wrong units cannot help however good the transition model is.

Both become worth turning on when boundary detection is, which makes it the
next thing to build rather than a side quest.

### Still open

Boundary detection is the weak part, f1 0.09 on the board against the bench's
0.46 for the best detector, because the graduated one is the novelty curve
and the lab cannot yet persist a fitted model. Front-end fusion is a bench
finding not yet on the board. Set boundaries in the decoder still come from
the log. Per-night variation is wide and unexplained. And nothing runs live.

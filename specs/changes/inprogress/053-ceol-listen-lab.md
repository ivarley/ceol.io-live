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

Three benches were added later and are where most of the work happens:

- **`lab bench retrieval`** asks whether the tune comes back from the index
  for each segment. It uses a front end, an index lookup and an optional
  transition prior or whole-set decoding, and scores top-1, top-5 and mrr.
  It is the main instrument; the "Where it stands" table is its output.
- **`lab bench pitch`** scores a front end frame by frame against pitch
  labels drawn in the viewer.
- **`lab bench pulse`** scores the grid estimator's period, meter, beat
  phase and bar phase against beats and bar lines drawn in the viewer.

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
- `lab compare A B --nights 1,2,3,4` — board configs pooled over nights (runs
  named `<config>-r<recording>`), each paired against the first with a sign
  test; `--record` adds the final record after revisions.
- `lab view` — the audio, piano roll, stave and beat grid for one segment,
  and where hand labels are made (see `lab/README.md`).

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

## How the lab is worked

The design above says where an idea gets scored. This is how the work has
actually gone, and the rules that fell out of it, most of them learned by
getting a number wrong first.

**The cycle.**

1. A hypothesis. The best ones have come from a player looking at the
   output and saying what is wrong with it musically: octaves carry no
   information, a transcriber hears pitch and not articulation, rests are
   rare, Cooley's is always followed by The Wise Maid. The harness finds
   whether an idea works; it has rarely suggested the idea.
2. The cheapest test that can refute it. One segment in the viewer, then the
   component against hand labels (`lab bench pitch`, `lab bench pulse`), then
   the retrieval bench over the whole corpus. Only an idea that survives the
   bench goes to the board.
3. A paired comparison against what it replaces, on the same segments.
4. The same change on the board, over several nights, judged on speed and
   stability as well as the final answer.
5. The result written down, whichever way it went: in this spec, in the
   docstring or comment next to the parameter it chose, and in a long-form
   commit message with the numbers.

**Rules.**

- **Every number has its scope.** "0.894 top-1" means 502 segments, eight
  nights, first 120 seconds, set decoding. A board number says which nights.
  Numbers on different scopes are never compared.
- **Paired, not pooled.** For each comparison, count the segments that became
  right and those that became wrong, and run a two-sided sign test on the
  two counts (`lab compare` does this for board runs; `sign_test` there is
  the one to reuse). On 500 segments a pooled difference under about a point
  is noise, and a pair like +2/-0 says so plainly.
- **A bug in the measurement voids the numbers taken through it.** Fix it,
  re-run the OLD configuration and check it reproduces its previous number
  exactly, then measure the new one on purpose. This caught a result that had
  been measured by accident (the prior's default weight) and two scoring bugs
  that made the grid estimator look better than it was.
- **The two loops share code, and are tested for agreeing.** Note splitting
  (`frontends.grid.regrid_notes`), fusing two readings
  (`bench.retrieval.fuse`), the transition model (`corpus.sequence`) and how
  a prior's default is read (`bench.retrieval.prior_weight`) each have one
  implementation both loops call. `test_engine.py` checks the board against
  the bench. Compare the two loops' CONFIGURATIONS too, not only their code:
  the board once read pitch from 130Hz while the bench was measured at 160.
- **Hand labels are ground truth for components.** Pitch, drawn beats and
  marked bar lines, made in `lab view`, saved to `lab/annotations/`, checked
  in. A component is scored against them directly, not only through whether
  the tune came back. One labelled segment has more than once overturned an
  assumption the whole corpus had been measured under (the eighth note is
  absent from the onset envelope; the tracker lands a twelfth low on a
  whistle).
- **Work from the worst case.** "The next wrong-est identification problem"
  is the unit of work: the segment ranked worst, opened in the viewer and
  listened to. Two of those turned out to be labelling problems, not
  recognition problems.
- **The eval set is judged by the audio, not by the recogniser.** A wrong
  label is fixed in the production segmenter and re-pulled. A segment is
  excluded (`lab/exclusions.json`) only for what the audio is -- one player
  starting and stopping -- never because it is hard.
- **What helps the reader is kept apart from what helps the matcher.** A
  tempo map and held gaps make the stave right and measured nothing or worse
  for identification, so they live in the viewer only.
- **Oracles size a lever before it is built.** The true previous tune, the
  true tune type, the true tune starts: each was fed in first to find what the
  real thing could be worth at most.
- **On the board, top-1 is not the only number.** The answer shown also has
  to settle. The first eighth-note version gained six points and tripled the
  flips, which a live display cannot have, and was not shipped.
- **Negatives are results.** Each is written down with its number, so the
  idea is not re-tried blind and the reasoning that made it harmless is
  visible if a later change breaks it (the tritone paragraph below is the
  example).
- **Anything fitted is scored on nights it never saw.** The corpus is an
  evaluation set; see the design decisions.
- **Drawn tunes say why, the bench says whether.** Three drawn tunes favoured
  Basic Pitch over yin on every label measure while the bench put it nine
  points behind, and lower thresholds improved all three and collapsed the
  bench. Score a component on labels to understand it; decide on the bench.
- **Label scoring must count repeated notes.** Drawn eighths cannot say held
  from struck, so the first scoring compared pitch changes only, merging
  repeats, and a tracker that re-struck held notes (a third of its intervals
  repeats, against 8% in the notation) looked better, not worse. Compare the
  heard repeat rate against the notation's before trusting a label score.

**Where results live.** Bench results in `bench_result` on the board
database (unless `--no-save`). Board runs are named `<config>-r<recording>`
so `lab compare` can pool them. Experiment configs that are not the baseline
and throwaway analysis scripts go in a scratch directory outside the repo;
`lab/data/` is not scratch, because `make lint` walks it. The corpus and
board are in `lab/data/` (gitignored); the annotations, exclusions and
configs are checked in.

## Status

Both loops run against the corpus, the recogniser works, and the largest
single improvement came from a sentence of domain knowledge rather than from
anything the harness could have discovered on its own.

### Where it stands

As of 2026-09-29, on branch `053-ceol-listen-lab`.

On the retrieval bench, 502 segments over eight nights (recordings 1, 2, 3,
4, 5, 138, 139, 140), the first two minutes of each:

| Configuration | top-1 | top-5 |
|---|---|---|
| yin, absolute pitch, 130Hz band | 0.485 | 0.706 |
| pitch folded to classes | 0.616 | 0.793 |
| and the band raised to 160Hz | 0.702 | 0.825 |
| and fused repeats split back apart | 0.775 | 0.880 |
| and read again as runs of eighths, fused | 0.833 | 0.912 |
| and each set decoded as a whole | 0.861 | 0.922 |
| and the tracker kept off a third of the pitch | 0.878 | 0.930 |
| and the previous tune pulling by how predictable its follower is | 0.894 | 0.930 |
| and 2/4 read in eighths, tuplets applied, one placement for both sides | 0.890 | 0.932 |
| and heard notes outside the key and its modal neighbour dropped | 0.896 | 0.932 |
| and yin fused with Basic Pitch and PESTO | 0.918 | 0.944 |
| the three, aligned against each shortlisted tune, audio alone (no prior) | **0.982** | **0.982** |
| the session's transitions alone, no audio | 0.245 | 0.368 |

**Read every bench number with its scope.** The bench is handed each tune cut
to its labelled boundaries: it never hears the chat between sets, the end of
the previous tune or a tune starting partway through its window, and it
chooses among the session's 1,279-tune repertoire. The live board, which
hears the raw night and finds its own boundaries, is at 0.819 (below). Every
setting in the lab was chosen on these eight nights, so a night none of them
has seen is the honest test, and it has not been run yet.

The aligner row is from 2026-09-29 (+35/-3 against the row above; at thirty
seconds 0.950 / 0.968, against 0.763 / 0.859 without it, +95/-1); see "The
aligner" below. Set decoding over the aligner's scores is broken for now and
is not in that row.

The last row is from 2026-09-28 (+16/-5 against the row above, p 0.03; at
thirty seconds, audio alone, 0.687 to 0.763, +51/-13), below. The two before
it are from 2026-09-26. The parser correction is +3/-5
against the row above it (p 0.73) and stands because the older row was reading
every polka at half length. The key filter is +5/-2 at two minutes (p 0.45);
it is on because it is worth three to four points at thirty seconds, which is
where the live board answers.
The command that produces it is in `lab/README.md`.

On the live board, all eight nights, the same 502 segments, answering while
the tune plays and finding its own boundaries:

| | top-1 at end | top-5 | right within 30s | right within 60s | never right | flips a tune |
|---|---|---|---|---|---|---|
| before the eighth-note reading | 0.697 | 0.811 | 12.5% | 40.4% | 26.9% | 3.7 |
| with it | 0.753 | 0.869 | 13.3% | 47.6% | 18.9% | 4.2 |
| with parser version 2 and the key filter (2026-09-26, `v2key`) | 0.769 | 0.876 | 12.0% | 49.8% | 17.7% | 4.14 |
| and Basic Pitch and PESTO beside yin (2026-09-28, `lab/configs/fuse3.json`) | **0.819** | **0.914** | **14.7%** | **48.6%** | **14.9%** | **3.15** |

The last row is the current board: +39/-14 top-1 against the row above, see
"Three trackers on the board". The aligner is not on the board yet, so the
board is at 0.819 where the bench is at 0.95 to 0.98 on labelled boundaries;
closing that gap is the plan's third item. `lab/configs/baseline.json` is
still yin alone (the second row plus chaining); `fuse3.json` is what the next
board work builds on.

Paired, the eighth-note reading made 41 segments newly right and 13 newly
wrong (sign test p < 0.001). `lab/configs/baseline.json` is that second row
plus chaining from finished spans, which measured within noise of it on four
nights (below). Told the true start of every tune, on four nights (1, 2, 4,
5), the board goes from 0.737 to 0.763 top-1 and from 12.8% to 49.7% right
within thirty seconds.

The gap between the two loops is mostly that they answer different
questions; see "The board against the bench" below.

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

**The previous tune pulls in proportion to how predictable its follower
is**, which came from a player who knows the session: you basically cannot
play Cooley's without The Wise Maid after it, and plenty of other tunes are
followed by anything. The session's own history agrees. Cooley's is followed
by The Wise Maid 83% of seventy times and The Silver Spear by The Earl's
Chair 68% of ninety-six, and across the 606 tunes followed three or more
times, half have a commonest follower under 35% of the time while a fifth
have one over 70%.

The prior had treated every predecessor alike and, where a transition was
weak, fallen back on how often each tune is played at all, which is a bias
towards the session's favourites. Now each predecessor's distribution over
what follows is raised to the power of its strength -- the commonest
follower's share, shrunk for tunes heard only a few times -- and the
popularity fallback is gone, for set openers too. Over 502 segments,
chaining the top answer forward / decoding the whole set:

| | top-1 | pairwise against the old prior |
|---|---|---|
| old: popularity fallback | 0.859 / 0.878 | |
| strength, strict | 0.875 / 0.886 | +17/-9 (p .17), +11/-7 (p .48) |
| strength, with the followed-before edge | **0.876 / 0.894** | +14/-5 (p .06), +10/-2 (p .04) |
| the app's rule, all or nothing | 0.863 / 0.876 | |

The strict version says a predecessor whose follower is a coin toss tells you
nothing. The one that measured better says it still tells you which tunes
have ever followed it, and those keep a modest edge over tunes that never
have; only the pull towards the favourite follower scales with
predictability. A sliding scale beat the app's threshold (more than half the
time, at least three times), and doubling the prior's weight over-trusted
the transitions under every variant.

This was nearly reported wrongly. The better version was first measured by
accident: every reader of the prior used `weights.get(tune, 1e-4)`, which
bypasses a defaultdict's own default, so the strict design's considered
share for an unseen tune was silently replaced by 1e-4 on the bench, and the
board's prior both converted the weights to a plain dict and sent a
hard-coded default. All three readers now take the model's own default --
`bench.retrieval.prior_weight` -- and the old prior reproduces its numbers
exactly through them. Both variants were then measured deliberately.

**The board had never used the transitions at all.** Its prior chained
from the last CONFIRMED tune, and nothing is ever confirmed: the assembler
holds back mass for "another tune" and for "due to change", so its confidence
tops out near 0.75 against a 0.9 bar, and across every run measured there
was not one confirmation. The spec said the board chained its own answer
forward; it did not, and the scheduler's "skip once confident" rule is dead
for the same reason. The prior now chains from the last finished span that
was at least 0.3 sure, and never penalises the previous span's own tune,
because a detected boundary is right about a quarter of the time and the
"previous" span is often the tune still playing. It now has a previous tune
for 99% of mid-set tunes, the right one 64% of the time, the current tune
split by a false boundary 17%.

It moves the live answer very little: 0.766 to 0.772 top-1 over four nights
(recordings 1-4, 290 segments), two segments newly right and none newly
wrong, within noise, with every variant tried landing in the same place. The likely
reason, not yet tested, is that the assembler sharpens towards the audio as a
span goes on, so a fixed-size prior counts early in a tune and hardly at all
by its end. That is the lever if the bench's gain is to reach the board.

A first version of the new lookup made board runs quadratic -- every finished
span of the night, a query each, on every update -- and nothing indexed
hypothesis events by hypothesis, so each query scanned every run ever stored.
It now fetches only the latest finished span, the two indexes exist, and the
old confirmation lookup is faster for them too.

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

**The in-key fraction cannot see the error that mattered most.** It was
adopted above as a confidence signal, and it is one, but the tin whistle
showed its blind spot. A note heard a fifth low is almost always still in the
key: in D, F# heard as B, B as E and D as G are all D-major notes. So that
whistle transcription read 94% in key while being right 25% of the time, and
across its later windows the fraction climbed to 97% with no improvement at
all in the phrases it shared with the notation. It catches noise and wrong
accidentals; it is no evidence against a transcription that is consistently
a fifth out.

Where it stands after the tracker change, the whole pipeline on the bench:
0.878 top-1, 0.930 top-5, 3.0% never found, up from 0.861, 0.922 and 3.4%.
Eighteen segments became right and nine became wrong. The gain is uneven by
type -- jigs 0.922 to 0.961, polkas 0.731 to 0.808, slides 0.762 to 0.810,
reels flat at 0.832 -- and the nights run from 0.826 to 0.960.

The board, answering live on recording 2 with the same tracker, reads 63.8%
top-1 and 75.9% top-5 against 86% for the bench on that same night. It has
neither the eighth-note reading nor whole-set decoding, and it must answer
while the tune is playing without being told where tunes start.

**The eighth-note reading on the board.** The interval expert now also reads
its window as runs of eighths, and the matcher looks that up and fuses it
with the plain reading using the bench's own `fuse`, so the two loops cannot
combine them differently. Over all eight nights, 502 segments, live:

| | top-1 | top-5 | right within 60s | never right | flips a tune |
|---|---|---|---|---|---|
| without it | 0.697 | 0.811 | 40.4% | 26.9% | 3.7 |
| first version | 0.745 | 0.857 | 52.2% | 17.1% | 10.5 |
| as shipped | **0.753** | **0.869** | **47.6%** | **18.9%** | **4.2** |

The first version carried the gain across and made the answer shown flip
three times as often, which a live display cannot have. Replaying the board's
own notes found why: the eighth-note reading is roughly twice as jumpy as the
plain one on its own, and two things in how it was fed made it worse. It took
the newest tempo estimate, and a single estimate half again too slow
rewrote the reading for ten seconds; and it numbered its slots from the first
note in the sliding window, so every note's slot rounded differently each
time the window moved. The median of the last minute's tempo and a fixed
origin bring flips back to where the board started and keep the gain. The
answer is found a little more slowly than with the jumpy version, which was
sometimes landing on the right tune by flipping onto it.

A moving average of evidence in the assembler was also built and is off. It
buys about one flip a tune of extra stability for a point of top-1 and five
points of "right within a minute".

**Whole-set decoding does not come across yet, and that is measured.** The
board was believed to chain the session's transitions from the last tune it
confirmed, which is the bench's "chain your own answer forward". (It did not:
nothing is ever confirmed. See "The board had never used the transitions at
all" above, which corrects this paragraph.) Chaining the
whole previous distribution instead is worth nothing more on the bench (0.859
both ways). The rest of the bench's gain from whole-set decoding, to 0.878,
comes from the tunes AFTER the one being decided and from knowing where the
set begins and ends; the live board has neither, and its earlier attempt to
let later tunes revise earlier ones was harmful because the spans it decodes
are not tunes. That part waits on boundary detection.

**What true boundaries are worth, measured on four nights (304 segments).**
Feeding the board the true start of every tune, with everything else as
shipped:

| | top-1 at end | top-5 | right within 30s | right within 60s | never right |
|---|---|---|---|---|---|
| detected boundaries | 0.737 | 0.859 | 12.8% | 45.4% | 21.4% |
| true starts | 0.763 | 0.872 | 49.7% | 78.0% | 13.8% |

So boundary detection is worth a little at the end of a tune and a great deal
in how SOON the tune is named: four times as many right within thirty seconds.
That is the case for building it, and it is mostly a case about speed.

Revision, letting later tunes change what was said about earlier ones, does
nothing even with true starts, and the reason sharpens what the detector has
to deliver. A first attempt at this measurement showed revision changing
nothing at all; that was a mistake in the experiment, since `revise_last`
below 2 never revises. At 3 it revises, and the live metrics cannot see it,
because they score what was shown during the tune and a revision only lands
after the next tune settles. So the record was scored instead -- the
evaluator's own answer at the end of each tune, followed forward to that
hypothesis's last word -- and with no revision at all that record is already
worse than what was shown, 0.628 against 0.763, with 82 answers changing
after their tune ended. The reason is that true STARTS are not true ends: a
span runs on through the chat or silence after its tune until the next start
arrives, and its last word is about whatever came next. Revision decodes
those contaminated rankings and makes the record slightly worse again, 0.622.
A detector therefore has to find where a tune stops as well as where the
next one starts; with only starts, the part of set decoding that needs
hindsight stays out of reach.

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

### Drafting labels from the notation, and why it was taken out

Hand labels are slow, so the notation was tried as a source of draft labels
for the player to confirm: the transcription's four-interval phrases that a
setting also contains were chained where their spacing in time agreed with
their spacing in the notation, and the notation was laid over the audio along
those chains. Never as an oracle, because the session does not play exactly
what thesession.org has written, and those departures are where a tracker is
being judged.

On Castle Kelly the player found barely a note of about two hundred right, and
drawing from scratch faster than correcting. The check made before showing it
said every draft under an existing label had the right pitch, 7 of 7, which
was worthless: the labels sat in the one well-anchored stretch, and the three
parameters it tuned (anchor length, gap bridging, extrapolation tempo) were
tuned on those same labels. The likely cause, untested, is that three or four
short phrases are a weak anchor in a tune that repeats itself bar to bar: a
chain can lock onto the wrong bar and still pass the timing check. The code
was removed rather than kept switched off.

The lesson for any aid to labelling: check it on stretches its own tuning
never saw, and let the player judge a few seconds of it before building more.

### Forty bars drawn by hand, and a parser that read polkas at half length

The player drew Tom Sullivan's (recording 4, segment 272), a polka the
recogniser gets right, as 159 eighths on hand-drawn beats: 32.6 seconds
unbroken, more than all the pitch labels before it together. Drawn eighths
cannot say held from struck, so notes are compared as pitch changes, and the
tracker's notes are aligned to them by edit distance allowing a match only
between notes that overlap in time.

| | right | wrong pitch | missed | extra | intervals recovered |
|---|---|---|---|---|---|
| yin | 113 | 7 | 3 | 33 | 84 of 122 |
| salience_viterbi | 105 | 4 | 14 | 5 | 86 of 122 |

yin hears nearly every note and adds a third as many again; salience_viterbi
adds almost none and drops more. They fail in opposite directions, which is
why the second scores better per frame on labels and worse on retrieval: a
missing note and an extra one cost different amounts once they are intervals.
At about 70% of intervals right, only around one six-note phrase in six
survives whole, which is the bottleneck this spec has named from the start.

Inside notes, the frames that are wrong in a note's first 60ms are mostly the
previous note carried over (200 frames for yin), not the attack harmonic the
player heard (17). Carryover moves where a note starts, not which notes there
are, so it costs the matcher little. Part of it is the labels: drawn eighths
start on grid lines, and attacks scatter about 30ms around them.

**The short extras are not the lever they looked like.** Twelve of yin's 33
are 69-70ms, just over the 60ms minimum note. On the labels a minimum of 70
or 80ms (identical, since frames are 11.6ms) takes extras from 33 to 19 and
intervals from 84 to 90. On the bench, audio alone, it is +14/-14 (0.861 both
ways); with set decoding +13/-6 (0.890 to 0.904, p 0.17), which is the same
churn happening to net positive. At 100ms reels fall 0.845 to 0.769 (-35/+10):
real reel notes live in that range. Merging interlopers moved the labels by
one interval. Not adopted; one labelled polka is not the corpus.

**The parser read every 2/4 tune at half length.** Asked whether the notation
held sixteenths, the corpus answered: 88% of polka notes were shorter than an
eighth, against 2% for reels. thesession.org writes everything with an eighth
as the unit, the dump carries no `L:` line, and the parser followed the ABC
standard's default of a sixteenth for meters under 3/4. The plain reading
only uses pitch and never noticed; the eighth-note reading made every polka
quarter note one eighth while the audio made it two, which is why that
reading alone had taken polkas DOWN, 0.731 to 0.615. The parser also skipped
tuplet marks, so each note of `(3efe` counted a whole eighth (5.8 triplets per
hornpipe setting, 1.5 per reel).

Parser version 2 reads an eighth as the unit, applies tuplets, and places the
notation's eighths with the same `particalize` that reads the audio. Where
several written notes start inside one eighth -- a pair of sixteenths, a
triplet -- the eighth keeps the first (`max_lag=0`, with the placement's phase
set so it rounds to the eighth a note starts in). Measured over 502 segments,
each paired against the old parser on today's corpus (which reproduces 0.894
exactly):

| | top-1 | top-5 | paired | p |
|---|---|---|---|---|
| audio alone | 0.849 to 0.861 | 0.904 to 0.912 | +10/-4 | 0.18 |
| with set decoding | 0.894 to 0.890 | 0.930 to 0.932 | +3/-5 | 0.73 |

Audio alone, the gain is where the bug was: polkas 0.769 to 0.846, hornpipes
0.786 to 0.857. Set decoding was already covering for it. Kept, because it
corrects a misreading rather than tuning a number.

**Two filters from the player, both within noise.** A minimum note as a
fraction of an eighth at the tune's tempo, rather than in milliseconds, so a
polka's extras go without a reel's real short notes; and dropping heard notes
outside the key, since flat seconds and fifths are nearly absent from this
music. The notation has 1.3% of its notes outside the key signature and a yin
transcription 8.9%, each kind seven to twelve times as common, so most heard
out-of-key notes are the tracker's. "In key" is the player's: a key and its
modal neighbour (D major with mixolydian, so C and C# both; A dorian with
minor), which is two neighbouring signatures, chosen as the pair holding the
most note time (`analysis.key.modal_pair`). Against parser version 2 with no
filter, 502 segments, first 120 seconds:

| | audio alone | paired | set decoding | paired |
|---|---|---|---|---|
| min note 0.4 of an eighth | 0.861 to 0.867 | +5/-2 | 0.890 to 0.894 | +4/-2 |
| drop two or more steps out of the signature | 0.861 to 0.857 | +8/-10 | 0.890 to 0.894 | +5/-3 |
| drop anything outside the signature | 0.861 to 0.871 | +14/-9 | 0.890 to 0.896 | +9/-6 |
| drop anything outside the modal pair | 0.861 to 0.867 | +13/-10 | 0.890 to 0.896 | +5/-2 |

Every p is above 0.4. The tempo-relative minimum behaves as intended where
the millisecond one did not -- seven segments change instead of twenty-eight,
reels are untouched -- but is small. The key filters are small for the same
reason breaking at a tritone did nothing: a phrase containing a wrong note
matches nothing and never votes, so dropping the note helps only when both
its neighbours were right. The stricter signature filter scoring highest while
wrongly removing C natural from D tunes is the size of the noise, not a
finding. All four are settings on the front end (`min_note_eighths`,
`out_of_key_drop`), off by default. At 0.89 the 120-second bench cannot
resolve half a point, so they were measured again with less audio.

**With less to listen to, the key filter is real.** Audio alone, same 502
segments:

| | 30 seconds | paired | 60 seconds | paired |
|---|---|---|---|---|
| no filter | 0.657 | | 0.799 | |
| drop two or more steps out | **0.697** | +25/-5, p < 0.001 | | |
| drop anything outside the signature | **0.697** | +31/-11, p 0.003 | | |
| drop anything outside the modal pair | **0.687** | +22/-7, p 0.008 | **0.821** | +18/-7, p 0.04 |
| min note 0.4 of an eighth | 0.647 | +4/-9, p 0.27 | | |
| modal pair and min note together | 0.673 | +25/-17, p 0.28 | | |

About four points at thirty seconds, two at sixty, within noise at two
minutes: with little audio every phrase counts, and a wrong note breaks the
phrases it sits in. Gains are in reels (0.618 to 0.655), jigs and hornpipes.
Which version does not measurably matter: the modal pair against the single
signature is +13/-18 (p 0.47). The player's definition is musically right and
the data cannot yet see the difference. The tempo-relative minimum note is
slightly worse at thirty seconds and drags the key filter down with it.

**A drawn reel says the same, louder.** The player drew The Bird in the Bush
(recording 2, segment 131) once through: 221 eighths, 36.6 seconds. The reel
is much harder for the tracker than the polka:

| | right | wrong pitch | missed | extra | intervals recovered |
|---|---|---|---|---|---|
| yin, polka | 113 of 123 | 7 | 3 | 33 | 84 of 122 (69%) |
| yin, reel | 132 of 173 | 26 | 15 | 60 | 84 of 172 (49%) |
| yin, reel, modal-pair key filter | 132 | 15 | 26 | 46 | 86 of 172 |
| yin, reel, 80ms minimum | 128 | 21 | 24 | 48 | 78 of 172 |
| salience_viterbi, reel | 114 | 10 | 49 | 24 | 73 of 172 |

The key filter keeps every right note and removes eleven wrong ones and
fourteen extras; nine of yin's wrong notes were a semitone sharp. Intervals
move only by two, because a removed wrong note leaves a gap and the intervals
across it need both neighbours right. The 80ms minimum costs the reel real
notes, the same thing the bench showed for reels. Half the intervals of an
ordinary reel are still wrong: the tracker, not the matcher, is where the
room is.

**Basic Pitch, the first neural front end: better on both drawn tunes, much
worse on the bench.** Spotify's note transcriber (`frontends/basicpitch.py`,
CoreML on macOS) hears every instrument and reports notes with onsets; the
melody is taken as the loudest note in the 160-1400Hz band at each 10ms, with
a silent frame between repeated notes so they stay two. On the player's two
drawn tunes it beat yin on every measure, including the one that mirrors the
matcher -- how many of the drawn tune's six-note phrases appear anywhere in
what was heard: 108 against 93 of 118 on the polka, 58 against 40 of 168 on the
reel. On 502 segments, audio alone, key filter on for both:

| | yin | basic_pitch | paired |
|---|---|---|---|
| 120 seconds | 0.867 | 0.775 | +18/-64 |
| 30 seconds | 0.687 | 0.596 | +37/-83 |
| fused with yin, 120 seconds | 0.867 | 0.867 | +15/-15 (top-5 +12/-5, p 0.14) |

It does not go quiet -- both trackers produce about five notes a second where
it wins and where it loses -- but it follows something other than the tune:
on the segments it loses it recovers a median 21 of the tune's phrases
against yin's 46, and even where both are right, 56 against 68. The two drawn
tunes were two where it does well. A tracker is judged on the bench, and a
drawn segment says why, not whether. What it follows instead is not known
yet; the loudest-note melody is the first suspect, since accompaniment and
harmonics are loud. Kept as a front end, not used.

Two corrections, 2026-09-27. The player listened to one it lost (The Scholar)
and heard it reporting too few notes, mostly at the right pitch. Lowering its
thresholds (onset 0.2, frame 0.15) improved every label measure on all three
drawn tunes and collapsed the bench to 0.285, because it then re-strikes held
notes: over a third of its intervals repeated a pitch, against 8% in the
notation. The label scoring compared pitch changes only, merging repeats, and
could not see it; it must count repeated notes from now on. The first
version's own choice to keep the model's same-pitch notes apart was the same
fault in smaller measure (25% repeats). Merged:

| audio alone, 120 seconds | top-1 | top-5 | against yin |
|---|---|---|---|
| yin | 0.867 | 0.914 | |
| Basic Pitch, repeats kept apart | 0.775 | 0.861 | +18/-64 |
| Basic Pitch, repeats merged | 0.831 | 0.900 | +19/-37, p 0.02 |
| the same, lower thresholds | 0.833 | 0.912 | +18/-35, p 0.03 |

Merging is +37/-9 against keeping them apart and is now the front end's
behaviour (version 2), which merges inside the melody line rather than after
the notes are cut; measured as built it reads 0.835 top-1, 0.896 top-5
(+6/-4 against the merge above, +20/-36 against yin, p 0.04). It is still behind yin, and right on 19 segments yin
gets wrong: choosing per segment the better of the two would give 0.904.

The same first-note rule on the audio side is worse, +8/-13 (p 0.38), and is
not used. Written notes sit exactly on the grid; heard ones wander around it,
and a note rounding into the eighth before is usually a real note played a
little early, which the audio side's one-eighth push (`max_lag=1`) keeps.

**The loudest note is not what Basic Pitch gets wrong (2026-09-27).** The
suspect above was the melody rule: a guitar chord tone or a drum's pitched
thump that is louder for a moment takes the skyline and costs two wrong
intervals. Two alternatives, taken from the same cached model output
(`melody` in `frontends/basicpitch.py`; the model's notes are now cached on
disk apart from the melody, so a melody variant costs no model run). Audio
alone, 120 seconds, 502 segments, paired against the loudest note (0.835 top-1,
0.896 top-5, reproducing the version-2 number exactly):

| melody | top-1 | top-5 | top-1 paired |
|---|---|---|---|
| loudest note (as built) | 0.835 | 0.896 | |
| highest note sounding | 0.811 | 0.890 | +16/-28, p 0.10 |
| continuity: switch 0.1, leap 0.01 a semitone | 0.807 | 0.892 | +3/-17, p 0.003 |
| continuity: switch 0.3, leap 0.02 | 0.815 | 0.882 | +8/-18, p 0.08 |
| continuity: switch 0.5, no leap cost | 0.793 | 0.880 | +5/-26 |
| continuity: switch 1.0, leap 0.05 | 0.709 | 0.823 | +5/-68 |
| continuity with no costs (control) | 0.835 | 0.896 | +0/-0 |

Continuity is a Viterbi path over pitches that pays to change note and more
for a bigger leap, against amplitude summed over 10ms frames. With no costs it
is the loudest note exactly, so the decoder is sound, and every cost tried
loses, monotonically in the cost; taking away its rest state changes nothing
(0.813 and 0.803 at the first two settings). The top note loses too. What a
moment of louder note costs the loudest-note line is less than what holding
the line through it costs, so whatever Basic Pitch follows when it is wrong,
it is not a brief loud interloper. The next suspects are the model's own
notes (what it hears at all, against yin, on the segments it loses) rather
than the choice among them.

**Three trackers that each lose to yin, fused, beat it by eight points at
thirty seconds (2026-09-28).** Two more pretrained trackers, both monophonic
like yin, both on the Mac's GPU. PESTO (`frontends/pestotrack.py`, a small
self-supervised model, weights trained on singing) and CREPE through
torchcrepe (`frontends/crepetrack.py`, supervised; the tiny model, since the
full one takes 94s per two minutes of audio against 11s and scored 52.5%
against 50.6% on the labels). On the hand labels, share of labelled time
right with the voicing gate open: yin 56.8%, CREPE full 52.5%, CREPE tiny
50.6%, PESTO 47.1%. Neither model's confidence is a usable gate: PESTO falls
from 0.827 top-1 open to 0.805 at 0.05, 0.502 at 0.1 and 0.169 at 0.2.

Audio alone, 502 segments, paired against yin:

| front ends | 30 s top-1 | 30 s top-5 | 30 s paired | 120 s top-1 | 120 s paired |
|---|---|---|---|---|---|
| yin | 0.687 | 0.779 | | 0.867 | |
| PESTO | 0.641 | 0.747 | +39/-62 | 0.827 | +19/-39 |
| Basic Pitch | 0.641 | 0.763 | +45/-68 | 0.835 | +20/-36 |
| CREPE tiny | 0.478 | 0.610 | +28/-133 | | |
| yin + CREPE tiny | 0.683 | 0.821 | +23/-25 | | |
| yin + PESTO | 0.727 | 0.829 | +38/-18, p 0.01 | 0.882 | +17/-9 |
| yin + Basic Pitch | 0.743 | 0.851 | +41/-13, p < 0.001 | | |
| yin + Basic Pitch + PESTO | **0.763** | **0.859** | **+51/-13, p < 0.001** | 0.890 | +20/-8, p 0.04 |
| the same + CREPE tiny | 0.759 | 0.859 | +5/-7 against the three | | |

With set decoding at 120 s, against the headline 0.896 / 0.932: yin + PESTO
0.914 / 0.940 (+13/-4, p 0.049), yin + Basic Pitch 0.916 / 0.944 (+14/-4, p
0.03), all three **0.918 / 0.944** (+16/-5, p 0.03). PESTO on top of yin and
Basic Pitch is +23/-13 at 30 s (p 0.13) and +4/-3 at 120 s: it is kept in the
fusion, but its share of the gain is not yet separable from noise.

Each tracker alone is behind yin, and each is right where yin is not: choosing
per segment the better of yin and PESTO would give 0.904 at 120 s, of yin and
Basic Pitch 0.906, of all three 0.922, and the sum fusion recovers most of
that without choosing. The earlier fused number (0.867 against 0.867) was
Basic Pitch version 1, audio alone, at 120 s, where fusion has least room;
the gain lives at thirty seconds, which is where the live board answers.
CREPE tiny is too weak to add anything and is not used.

**RMVPE, the tracker built for a melody over accompaniment, is the worst of
them (2026-09-28).** Through `rmvpe-onnx` 0.2.3 on CoreML
(`frontends/rmvpetrack.py`; the authors' singing weights, checked by SHA-256),
6s per two minutes of audio. Labels: 41.2% of labelled time right with the
gate open (0.05: 33.4%). Bench, audio alone, 30 s: 0.267 top-1 against yin's
0.687 (+12/-223); yin + RMVPE 0.625 (+13/-44 against yin); added to yin, Basic
Pitch and PESTO, 0.751 against 0.763 (+4/-10). Night by night it ranges from
0.612 (night 3) to 0.101 (night 139). Checked as a possible bug before it was
believed: its notes are as many and as long as yin's and PESTO's, peak
normalising the input changes nothing (frame agreement with yin 0.38-0.49
either way), and CoreML and the CPU agree (0.1% of frames more than half a
semitone apart). On segments of night 139 it loses, it agrees with yin on
38-49% of frames where PESTO agrees on 56-67%: it follows something else in
the room, which for a model trained to find a voice over a band is not a
surprise. Not used.

### Where a note starts, and why sung labels sounded late

Drawing eighths on Tom Sullivan's, the player heard every sung label behind
the beat and asked whether the tracker's notes start late. They do not. Against
peaks of a fine onset-strength curve (64-sample hop), the tracker's note starts
sit at a median of -1ms (middle half -29 to +27ms), the drawn beats at -5ms
(-27 to +18), and the two agree with each other to +1ms. On synthetic tones
with known onsets the tracker is +4ms. The lateness was the viewer's: it
started each tone when a screen refresh noticed the label had begun, up to a
frame late plus the browser's output delay. Scheduling the tones ahead on the
audio clock was not enough; the player still heard them late. The clip is not
shifted (the browser's decode of it lines up with the recording to the
millisecond), so what remains is the `<audio>` element's own path to the
speakers, which its reported position does not account for. At 1x the music
is now played from the decoded clip through the same audio context as the
tones, each tone started at its exact sample; slower speeds still use the
element, which keeps the pitch. An offset slider remains for adjusting by ear.

The same session turned up something to measure once there are enough labels:
the fiddle's and accordion's attack carries a harmonic that the tracker
reports as the note's first pitch, so a note can begin with a short wrong
note. The drawn eighths are the ground truth that can say how often.

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

### The key on the board, and what a player would see (2026-09-27)

**Judging the key from the recent notes makes the board faster and jumpier,
and the two cannot be pulled apart by the key filter alone.** The key filter
did nothing on the board (0.771 / 0.769 top-1 without and with it, +15/-16).
The explanation written down for it was that the board judged the key over a
two-minute window that early in a tune is mostly the previous one. The
interval expert now takes `key_window_ms` (judge from the last this-many ms,
apply to the whole window), `key_block_ms` (judge per fixed block on the
absolute clock, from the block and the one before) and `key_hysteresis` (keep
the modal pair in use until a new one holds this much more of the recent note
time). All off by default. All eight nights, 502 segments, against the key
judged over the whole window (`v2key`, which reproduced its night-2 run
exactly):

| key judged from | top-1 | <30s | <60s | never | flips |
|---|---|---|---|---|---|
| the whole window (today) | 0.769 | 12.0% | 49.8% | 17.7% | 4.14 |
| the last 20 s | 0.777 | 14.3% | 53.2% | 16.3% | 5.60 |
| the last 40 s | 0.777 | 12.7% | 51.0% | 17.3% | 4.94 |
| fixed 20 s blocks | 0.773 | 12.5% | 47.0% | 17.5% | 4.34 |
| the last 20 s, pair held to a 5-point margin | 0.769 | 12.4% | 50.6% | 17.9% | 4.33 |
| the last 20 s, pair held to a 10-point margin | 0.757 | 12.7% | 48.0% | 19.1% | 4.23 |

The last 20 seconds, paired: within 30s +19/-7 (p 0.03), within 60s +27/-10
(p 0.008), ever right +12/-5, top-1 +9/-5; and more flips on 253 segments,
fewer on 72. So the explanation was right. Where the gain comes from is shown
by the blocks: a recent key applied to the whole window drops the previous
tune's notes when the new tune is in another key, cleaning the window, and
blocks that leave a passed block's notes alone lose the speed entirely
(within 60s +9/-23 against today, p 0.02) while bringing flips back (4.34).
Holding the pair until a new one wins clearly does the same. Every variant
that removed the flips removed the gain with them.

**The display can take the flips instead.** `lab display` replays the stored
hypothesis events of finished runs through a display rule and scores what
would have been on screen, in seconds per rule. A new top guess replaces the
one shown at once if its confidence reaches `show_conf`, otherwise once it has
been top for `hold_ms`; with both zero it is the control, and it reproduces
`lab compare` (flips 4.13 against 4.14, because a withdrawal is not a change
of answer). The first version cleared the screen at every withdrawal, and the
boundary detector closes a span and the assembler reopens one on the same tune
every few seconds, so a hold restarted each time and a 10 s hold showed
almost nothing; a withdrawal now clears the screen only when nothing replaces
it at the same instant.

| on screen, 8 nights | top-1 at end | <30s | <60s | flips |
|---|---|---|---|---|
| today's key, every change shown | 0.769 | 12.0% | 49.8% | 4.13 |
| today's key, 2 s hold | 0.765 | 10.0% | 44.6% | 2.50 |
| 20 s key, 2 s hold | 0.777 | 11.0% | 47.4% | 2.98 |
| today's key, 4 s hold | 0.763 | 6.6% | 40.6% | 1.86 |
| 20 s key, 4 s hold | 0.769 | 7.6% | 43.8% | 2.11 |

With the same hold on both, the 20 s key is faster: within 60s +22/-8 (p
0.016) at 2 s and +23/-7 (p 0.005) at 4 s. Against today's screen, the 20 s
key with a 2 s hold has fewer flips on 222 segments and more on 91, top-1
+10/-6, and gives back speed within noise (within 30s +8/-13, within 60s
+18/-30, p 0.11). Showing a confident guess at once changed nothing at any
threshold from 0.4 up, because a new top guess almost never arrives confident.
Not in `baseline.json` yet: the display rule is not part of the board, and
the speed it gives back should be won back upstream first.

**A short list is worth more than any of it.** The player's idea: while no
answer is sure, offer the candidates with reasonable confidence to pick from.
With the 20 s key and 2 s hold, offering every candidate at confidence 0.05 or
above (at most five) has the right tune on screen within 60 s for 70.9% of
tunes against 47.4% for the single answer, and within 30 s for 25.7% against
11.0%, with a list 2.1 tunes long on average. Floors of 0.1, 0.15 and 0.2
give 63.5%, 59.6% and 55.8% within 60 s with lists of 1.4, 1.2 and 1.1.

**Confidence is ordered but never high.** An earlier reading from one night,
that confidence is underconfident (0.5 right nine times in ten), was the end
of each tune only. Over every moment of every tune on all eight nights, each
segment weighted equally: 0.1-0.2 is right 12% of the time, 0.3-0.4 31%,
0.5-0.6 52%, 0.6-0.7 65%, 0.7-0.8 76% (six segments' worth). Nothing reaches
80%, so no category fitted on seven nights keeps an 80% promise on the
eighth (`lab display --calibrate`). What confidence mostly tracks is time: the
top guess is right 6% of the time in a tune's first 30 s, 30% at 30-60 s, 63%
at 60-90 s and 79% at 90-120 s. The player wants a calibrated confidence shown
as categories (maybe / probably / certainly, each a promise checked on
held-out nights) rather than a number; a calibrator using the margin between
the top two, how many recent updates agree and elapsed time is the way, and is
deferred until accuracy is higher.

### Three trackers on the board (2026-09-28)

**The fused front end is better and steadier live.** The board now has a
pitch expert for each bench front end's own tracker (`pitch_basic_pitch`,
`pitch_pesto`, `pitch_rmvpe`: `FrontEnd.track` and `clean_track`, not a
copy), the note expert cuts each source's notes with that front end's own
settings (Basic Pitch's track is not split into repeats; PESTO has no
voicing gate), unless the config sets one explicitly, and the matcher fuses
the latest readings of every source with the bench's `fuse` (`fuse_sources`;
a source more than 6 s stale is left out). Agreement tests for both in
`test_engine.py`. The neural experts read 4 s windows on the 2 s hop rather
than yin's 10 s: they need no long context, and 10 s windows five times over
under nine parallel runs took PESTO from 3 s per two minutes of audio to 43 s
and a night to about seven hours. `v2key`'s night 2 re-ran identically after
these changes.

All eight nights, 502 segments, against `v2key` (yin alone):

| board | top-1 | top-5 | <30s | <60s | never | flips |
|---|---|---|---|---|---|---|
| yin | 0.769 | 0.876 | 12.0% | 49.8% | 17.7% | 4.14 |
| yin + Basic Pitch + PESTO | **0.819** | **0.914** | **14.7%** | 48.6% | **14.9%** | **3.15** |

Paired: top-1 +39/-14 (p 0.001), within 30s +28/-14 (p 0.04), ever right
+27/-13 (p 0.04), within 60s +33/-39 (p 0.56), fewer flips on 206 segments
and more on 103. The first change in a while that is both better and
steadier. Setup mistake caught before any number: a leftover explicit
`min_voiced: 0.2` in the config would have gated PESTO, which on the bench
scores 0.169 at that gate.

### The aligner: matching that pays for one wrong note, not six (2026-09-28/29)

**The largest gain the lab has measured.** The n-gram index counts shared
six-note phrases, so one added ornament note (yin) or one lost note (the
neural trackers) breaks every phrase spanning it. Tunepal and FolkFriend both
match by alignment instead. `bench.retrieval.Aligner` re-ranks the index's
shortlist that way:

- **Both sides as the same sequences.** The heard notes as a run of eighth
  notes on the estimated grid (unknown slots blank) and as changes of pitch
  only (tempo-free); every setting of every candidate the same two ways, with
  the index's own parser and eighth placement (`corpus/sequences.py`, cached).
  Pitch classes, not intervals, so a wrong note costs one symbol, not two.
- **Chunks, each placed anywhere.** The heard sequence is cut into chunks of
  32 eighths or 24 pitch changes; each finds its best local alignment
  (Smith-Waterman, `analysis/align.py`, numba: match +2, mismatch -1, gap -1,
  a blank scores nothing) anywhere in the tune written twice over, since
  repeats are not written out and a chunk may run across the end of a part.
  A chunk of chat, a wrong part or the next tune scores near nothing and
  costs nothing.
- **Score and order.** Summed chunk scores as a share of the most the heard
  notes could score; a candidate's best setting; averaged over readings and
  trackers. "replace" orders the shortlist by this alone; "fuse" sums it with
  the n-gram ranking.

yin, audio alone, first 30 s, 502 segments, against 0.687 / 0.779:

| aligner | top-1 | top-5 | top-1 paired |
|---|---|---|---|
| eighths, fused with the n-grams | 0.751 | 0.825 | +32/-0 |
| pitch changes, fused | 0.729 | 0.811 | +21/-0 |
| both, fused | 0.739 | 0.817 | +26/-0 |
| eighths, replace | 0.835 | 0.845 | +77/-3 |
| pitch changes, replace | 0.829 | 0.843 | +74/-3 |
| both, replace, shortlist 25 | 0.843 | 0.847 | +78/-0 |
| both, replace, shortlist 100 | 0.886 | 0.898 | +100/-0 |
| both, replace, shortlist 300 | **0.902** | **0.922** | +108/-0 |

With a 25-tune shortlist the right tune is on it for 87.1% of segments and the
aligner puts it first for 84.3%, so the shortlist is the ceiling and a longer
one lifts it. **Control:** each segment's shortlist aligned against the
previous segment's heard notes gives 0.008 top-1 (shortlist 100), which is
chance: the aligner is listening, and no leak or bias towards tunes with many
settings is producing the gain. It costs 15 to 60 s a night on the bench.

With the three trackers fused (both readings, replace, shortlist 300):

| | top-1 | top-5 | paired |
|---|---|---|---|
| 30 s, without the aligner | 0.763 | 0.859 | |
| 30 s, with it | **0.950** | **0.968** | +95/-1 |
| 120 s, yin alone with it | 0.970 | 0.976 | +53/-1 against yin alone at 120 s |
| 120 s, the three with it | **0.982** | **0.982** | +35/-3 against the 0.918 headline; +6/-0 against yin with it |

At 120 s top-1 equals top-5: whenever the right tune is on the shortlist it is
first, and the 9 remaining misses are the index not shortlisting it. At 30 s
the misses were redone in `053 files/raising-accuracy.md`: 25 of 502, 17 of
them reels, the right tune at rank 2-8 for 10, below 10 for 7, not shortlisted
for 8; The Mason's Apron, the wrong answer in 19 of 41 misses under the
n-grams, is the wrong answer in 2.

**Set decoding over the aligner's scores is broken.** At 120 s the three
trackers with the aligner and set decoding read 0.753 top-1 against 0.986
top-5 (+17/-100 top-1 against the headline, +23/-2 top-5), yin alone 0.733 /
0.980. The ranking is right and the decoder chooses wrongly among it: the
prior's weight (`beta` 0.15) was set against the n-gram scores, and the
aligner's are on another scale and far more decisive. Retune the weight, or
convert the aligner's score to the scale the decoder expects, before set
decoding and the aligner are used together.

**Against the full corpus the gain holds (2026-09-29).** The same runs
choosing among all 23,307 tunes (indexes and the sequence store rebuilt with
parser 2; 55,387 settings), 30 s, audio alone, shortlist 300:

| | repertoire | full corpus | aligner, paired, full corpus |
|---|---|---|---|
| yin | 0.687 | 0.669 | |
| yin + aligner | 0.902 | **0.876** | +104/-0 |
| the three fused | 0.763 | 0.763 | |
| the three + aligner | 0.950 | **0.932** / 0.946 top-5 | +87/-2 |

The long tail costs the aligner about two points (+0/-9 for the three against
the repertoire run, +2/-15 for yin), and of those 9, 7 are the index not
shortlisting the right tune among 23,000 (its rank falls to 331, 373, 939 or
off the list) and 2 are real near misses at rank 2 (The Scholar under The
South Shore, Larry Redican's Mother under The Whinny Hills of Leitrim). The
shortlist's recall is the ceiling again.

**Not yet measured:** a start that is not the labelled one; the board; tunes
played in another key than all their settings (the aligner compares note
names; `transpose=12` tries every key and is untested, and the player's
better proposal is below).

**An outside comparison, three clips.** irishtune.id (Alan Ng, launched
2026-09) was given 30 s of three of these segments through the player's
account: Paddy's Trip to Scotland (every tracker right), The Wise Maid (only
the fusion right) and The Honeymoon (nothing right). It named none of them,
each answer marked "HMM, MAYBE?"; it fingerprints in the browser and matches
in 33-147 ms against 8,238 tunes, and its tips ask for one player close to
the microphone. Three clips are an anecdote; it is built for a different
recording than a session.

### Still open

**The plan, as of 2026-09-29**, merged with `053 files/raising-accuracy.md`
(which holds the field survey, the miss analysis and the ten angles in
detail), in order:

1. **Finish measuring the aligner.** (The full corpus is done: 0.932 at 30 s,
   above.) Shortlist recall, which is now the ceiling on both candidate
   sets. A sloppy start: windows beginning up to 20 s before the labelled start, so
   the query opens on the previous tune or the chat, to size how much of the
   gain survives not being handed the boundary. Retune set decoding for the
   aligner's scores. The player's key allowance: a tune may be played in
   another key than its settings, tried outward round the circle of fifths
   (the written key, then one fifth either way, then two, and never further;
   a G tune is played in D or A, not A-flat), each step costing a little, so
   the written key stays the strong default and a wrong tune does not get
   twelve chances at a lucky match. Its runs also say how often this session
   plays a tune in another key than every setting.
2. **A night none of this was tuned on.** The player is labelling a recent
   night. Replay it raw on the board (the board never reads the labels; they
   only score it afterwards), with today's baseline, the three-tracker fusion
   and the aligner on the board, and give the player the timeline to read
   against what was played; the bench on its labelled segments beside it.
3. **The aligner on the board, with sequential evidence.** The bench is at
   0.95-0.98 and the board at 0.819: the board is the gap. Evidence
   accumulated over the span, the prior as a fixed offset, a commit when the
   top two are far enough apart; then the display's hold and short list
   re-measured on top.
4. **The aligner's cost model** (angles 2, 4 and 6 of the note, now one
   project): metrical weight from the notated slot, a profile per tune from
   its settings, fitted substitution and insertion costs. The near misses at
   ranks 2-8 are what it is for.
5. **Alternatives inside the alignment** (angles 3 and 5): a second-choice
   pitch where trackers disagree, and the tune's own repeats as a consensus.
6. **Research bets, lower now:** matching without transcribing, fine-tuning a
   tracker on session audio, CoverHunterMPS as another expert.
7. **Deferred by the player:** the calibrator (maybe / probably / certainly),
   and the "this session plays it differently" report.

The items below are older and are kept for their detail; where one is
covered by the plan above, the plan is what is current. In rough order of
what they were worth as of 2026-09-25 (items added later are marked):

- **(2026-09-26) Extra notes against missed ones.** On forty hand-drawn bars
  yin adds 33 notes to 123 and salience_viterbi drops 14; a length threshold
  removes yin's extras only by also removing real reel notes. Something that
  tells an ornament from a melody note other than its length is the open
  question, and more drawn bars -- a reel next, since reels are where a
  threshold hurts -- are what can score it.
- **(2026-09-27) Trusting a tracker according to the passage.** The
  player's idea: a quiet solo passage might be read better by one pitch
  expert and a full session by another, so the fusion could weight experts
  by a description of the passage that another expert posts. The board
  supports it without change (experts post side by side; `fuse` is the one
  place to weight them). The oracle sizes it: choosing per segment whichever
  of yin and Basic Pitch is right gives 0.902 top-1 at 120 seconds (0.904
  with repeats merged) and 0.761 at 30, against 0.867 and 0.687 for yin alone and 0.867 for
  today's sum fusion. The choice has to be predicted from the audio (pulse
  strength, in-key fraction, loudness, how many notes Basic Pitch hears at
  once) and scored on nights it was not fitted on.
- **(2026-09-27) The key on the board: faster or steadier, not yet both.**
  See the section above. The 20 s key is the faster board; the display's
  hold and short list are how a player would use it; a calibrated confidence
  is deferred until accuracy is higher.
- **(2026-09-27) Pitch trackers, in the order planned with the player.**
  1. Pretrained models. Basic Pitch is built and behind yin (above); what it
  follows when it is wrong is not settled, and the loudest-note melody is the
  first suspect, and it is ruled out: continuity and highest-note melodies
  both lose to it (above).
  PESTO, CREPE and RMVPE are now built: PESTO fused with yin and Basic Pitch
  is the new headline; CREPE tiny adds nothing and RMVPE takes away (above).
  Every published pretrained tracker tried was trained on singing or on
  synthesised monophonic audio; none has heard a session.
  2. Whole-segment notation alignment: the player segments many more
  sessions, each segment one tune, so the whole performance can be aligned
  to the notation with its repeats written out -- much stronger than the
  short-phrase anchoring that failed -- and checked against the drawn tunes
  before it is trusted. 3. Only if both work, fine-tuning a pretrained model
  on those alignments with the player's light corrections, scored on nights
  and players it never trained on.
- **(2026-09-27) A label scorer that counts repeated notes.** Saved bench
  results now keep each segment's rank and `lab bench pair` pairs two of them;
  the label scorer is still the scratch `align.py` in
  `~/Local/code/ceol-lab-scratch/`, and belongs in the lab as a `lab bench
  notes` that counts repeated notes.
- **(2026-09-27) Drawn tunes so far:** Tom Sullivan's (polka, r4 s272),
  The Bird in the Bush (reel, r2 s131), The Scholar (reel, r5 s336), each on
  drawn beats. Jigs, hornpipes and slides have none; a jig is next.

- **Where tunes stop, as well as where they start.** Told the true starts,
  the board is right within thirty seconds four times as often, but starts
  alone leave each span running on through the chat after its tune, so the
  record is contaminated and set decoding with hindsight stays out of reach.
  The graduated detector is the novelty curve at f1 0.09 on the board against
  0.46 for the best bench detector, because the lab cannot yet persist a
  fitted model. The player has said this comes next.
- **How the prior enters the assembler.** The transitions are worth 1.7
  points on the bench and nothing measurable live. Untested explanation: the
  assembler sharpens its temperature towards the audio as a span goes on, so
  a fixed-size prior only counts early.
- **The 0.9 confirmation bar is unreachable.** Confidence tops out near 0.75,
  so nothing is ever confirmed and the scheduler's "skip once confident" rule
  never fires. Either calibrate confidence so 0.9 means something or change
  the bar; the calibration table in `lab eval` is the place to start.
- **Beat phase on reels,** and so where bar lines fall. Onset energy gives
  the period and not the phase. Candidates: transcribed note starts, phrase
  starts, the tune's eight-bar repetition. A slip jig's or slide's bar is not
  in the onset envelope at all.
- **The tin whistle.** After the tracker fix nearly half the labelled frames
  still sit below anything a D whistle can play.
- **Duration in the matcher.** The eighth-note reading carries duration only
  as repeated symbols; nothing scores rhythm directly.
- Front-end fusion is on the board since 2026-09-28 (0.769 to 0.819, above);
  per-night variation (0.841 to 0.960 top-1 at the headline configuration) is wide and unexplained;
  nothing runs live.

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

Where a segment starts, agreed with the player on 2026-10-02 while scoring
boundaries on recording 143:

- **A tune starts at its first note as played, however quiet.** Not where it
  becomes clearly audible: that depends on the microphone, where it sat and
  how loud the room was, so it moves from night to night for reasons that
  are not the music, and a label that followed what a detector can hear would
  hide the detector's limits. (The Cordal on 143: a guitarist started it very
  quietly at 1:48:41, and it is clearly audible only on the second time through
  the A part, at 1:48:59; it starts at 1:48:41.)
- **A false start belongs to no tune.** The tune starts at the attempt that
  carried on. (Music For A Found Harmonium on 143: 2:57:43, after a couple of
  false starts.)

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

**As of 2026-10-01, when the lab was merged into the app branch.** The
recogniser works live. `lab listen` runs on a laptop's microphone behind a
certainty meter (top five tunes, ten-segment bars, "this is it" and "none of
these"), and the player's first try with it, segments of other session
recordings played from a phone, went perfectly by their account. Under it:
the aligner (match by alignment, not shared phrases; "The aligner"), the
change detector ("Is this still the same tune?", a causal decoder over every
tune plus "not a tune"), on the board as the follower (0.908 right at the end
and 84.5% within 30 s over eight nights against the old board's 0.815 and
14.3%; 0.902 on night 140's held-out segments), a full-corpus fallback for
tunes new to the session, tune-ness and a charge on hub tunes against
noodling and chat. A night never tuned on, segmented blind (night 137): 0.855
right at the end, 64 of 69 tunes named. What comes next is the app: the
detector on a server, fed by the native app's recorder (`053 files/
listen-on-the-server.md`); the lab's open items are under "Still open".

The rest of this section is the retrieval bench's history, as of 2026-09-29.

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
aligner" below. Set decoding is not in that row: retuned for the aligner it is
harmless and adds nothing measurable (2026-09-29, below).

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
| and Basic Pitch and PESTO beside yin (2026-09-28, `lab/configs/fuse3.json`) | 0.819 | 0.914 | 14.7% | 48.6% | 14.9% | 3.15 |
| the follower in place of the matcher and assembler (2026-09-30, `lab/configs/follower.json`; 588 segments, fuse3 on the same 0.815) | **0.908** | **0.934** | **84.5%** | **95.6%** | **3.4%** | **1.97** |

The last row is the current board (+70/-15 top-1, +414/-1 within 30 s against
fuse3 on the same 588 segments; night 140's held-out segments 0.902 against
0.721); see "The follower". The row before it was +39/-14 against its
predecessor, see "Three trackers on the board". The aligner is not on the board yet, so the
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

At 120 s top-1 equals top-5, and of the 9 remaining misses 4 are the index
not shortlisting the right tune and 5 are shortlisted but aligned to ranks 9 to
191 (corrected 2026-09-29; this first said all 9 were the index). At 30 s the
misses were redone in `053 files/raising-accuracy.md`: 25 of 502, 17 of them
reels, the right tune at rank 2-8 for 10, ranks 11-300 for 2, and outside the
300-tune shortlist for 13 (corrected 2026-09-29: the note counted 8, because a
tune the index returns below 300 keeps its place in the unaligned tail, at
329-592, and was read as "present"); The Mason's Apron, the wrong answer in 19
of 41 misses under the n-grams, is the wrong answer in 2. See "Shortlist
recall" below.

**Set decoding over the aligner's scores is broken.** At 120 s the three
trackers with the aligner and set decoding read 0.753 top-1 against 0.986
top-5 (+17/-100 top-1 against the headline, +23/-2 top-5), yin alone 0.733 /
0.980. The ranking is right and the decoder chooses wrongly among it: the
prior's weight (`beta` 0.15) was set against the n-gram scores, and the
aligner's are on another scale and far more decisive. Retune the weight, or
convert the aligner's score to the scale the decoder expects, before set
decoding and the aligner are used together.

**Retuned, set decoding adds nothing to the aligner (2026-09-29).** Each
set's aligned candidate lists were captured once (three trackers, both
readings, replace, 300-tune shortlist, original 502 segments) and the
decoder swept offline with the bench's own `decode_set`, over the prior's
weight `beta`, with the emission as today's log of the aligner's score or as
the score itself. The capture reproduces the 120 s run above except for 3
segments in one set on night 4 (0.747 against 0.753), which fits the
session's logged history having been re-pulled in between; the old history
file was overwritten, so that is not confirmed.

| | 120 s top-1 | paired against no prior | 30 s top-1 | paired against no prior |
|---|---|---|---|---|
| no prior, the aligner alone | 0.982 | | 0.950 | |
| log, beta 0.15 (as before) | 0.747 | +2/-120 | 0.697 | +2/-129 |
| log, beta 0.05 | 0.976 | +2/-5 | 0.948 | +5/-6 |
| log, beta 0.01 | 0.982 | +1/-1 | **0.956** | +3/-0 (p 0.25) |
| score itself, beta 0.01 | 0.982 | +1/-1 | 0.954 | +4/-2 |
| weight chosen on seven nights, scored on the eighth | 0.980 | +0/-1 | 0.952 | +2/-1 |

Nothing was broken except the weight: 0.15 is ten to fifteen times too much
for the aligner's scores, and at 0.05 or below the decoder stops overruling
the audio. But no weight helps. At 120 s top-1 already equals top-5, so there
is nothing among the top few for the prior to reorder; at 30 s there are 9
segments with the right tune at ranks 2-5 and the best weight recovers 3 of
them, in-sample, which leave-one-night-out shrinks to +2/-1. Where the
aligner is wrong it is usually confidently wrong or the tune is off the
shortlist, and a prior of 0.245 top-1 on its own cannot outvote either.

Not adopted on the bench. If set decoding is used with the aligner, `beta`
0.01 with the log emission is the setting (harmless in both lengths). Where
the prior could still earn its place is live: in the first seconds after a
change, before the aligner has much to go on, which of the tunes usually
follow is the only evidence. That belongs to plan item 3 and is measured
there, not here.

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

**Shortlist recall (2026-09-29).** How often the right tune is among the
tunes the aligner is handed. Each component ranking (three trackers, plain and
eighth readings) cut at T and then fused, exactly as the bench builds the
shortlist; the script reproduces the aligner runs' unshortlisted segments
exactly on all four scopes. Audio alone, the headline front end, bench scope
(labelled boundaries, eight nights every setting was tuned on):

| recall at T | 25 | 50 | 100 | 200 | 300 | 500 | 1000 | 2000 |
|---|---|---|---|---|---|---|---|---|
| repertoire, 30 s | 0.918 | 0.938 | 0.950 | 0.968 | **0.974** | 0.982 | 0.986 | 0.986 |
| repertoire, 120 s | 0.968 | 0.982 | 0.988 | 0.992 | **0.992** | 0.992 | 0.994 | 0.996 |
| full corpus, 30 s | 0.896 | 0.908 | 0.928 | 0.942 | **0.950** | 0.960 | 0.968 | 0.978 |
| full corpus, 120 s | 0.966 | 0.974 | 0.984 | 0.986 | **0.990** | 0.990 | 0.990 | 0.992 |

At 30 s on the repertoire the aligner puts the right tune first for 477 of
the 489 segments that are shortlisted (97.5%); the shortlist costs 13
segments and the ranking 12. Fusing is the right way to build it: the fused
list beats every single component at every T (yin plain, the best, has 0.942
at 300), and the union of each component's own top m is no better than the
fused list at the same size (union of top 100s, median 328 tunes, 0.968,
against 0.974 for the fused 300).

A longer shortlist, repertoire, 30 s, paired against the 300-tune headline
(0.950 / 0.968):

| aligned | top-1 | top-5 | top-1 paired |
|---|---|---|---|
| fused list cut at 1000 | 0.956 | 0.972 | +3/-0 (p 0.25) |
| cut at 3000 (everything the index returns) | 0.956 | 0.972 | identical to 1000 |
| every repertoire tune, the index bypassed | **0.960** | **0.978** | +5/-0 (p 0.06) |

The index returns only tunes that share at least one six-note phrase with
what was heard, so no cut-off reaches the 7 segments whose tune shares none
(The Sailor on the Rock, The Honeymoon, The Bank of Ireland on night 1, The
Maids of Mitchellstown, Sonny Murray's, The Donegal Reel, Take Your Churn).
None of the 7 is in another key: each scores best at no transposition. Aligned
against the whole repertoire, 2 of them come first (The Sailor on the Rock,
The Donegal Reel), one second, and the rest 7th to 87th. Aligning everything
roughly doubles the bench's time (about 30 minutes for the eight nights
against 60, under contention, so only a rough ratio) and on the repertoire
reaches recall 1.000, leaving 20 misses that are all the aligner's ranking.
Not adopted: +5/-0 is not significant, and against 23,307 tunes aligning
everything is not an option. What it says is that the shortlist is no longer
the main ceiling on the repertoire; the aligner's ranking is (item 4 of the
plan, the cost model), and on the full corpus the shortlist still is (25
unshortlisted at 30 s).

**A sloppy start (2026-09-29).** The bench with each window opening X
seconds before the labelled start, repertoire, audio alone, three trackers,
aligner (both readings, replace, 300). 60% of tunes begin within a second of
the previous one ending, so what the window opens on is mostly the end of the
previous tune in the set, otherwise chat. Paired on the original 502 segments
(the corpus was re-pulled while these ran; see "Still open"):

| window | top-1 | top-5 | paired against 30 s from the labelled start (0.950) | wrong answer is the previous tune |
|---|---|---|---|---|
| 5 s early, 30 s long | 0.922 | 0.944 | +4/-18 (p 0.004) | 3 of 39 |
| 10 s early, 30 s long | 0.853 | 0.908 | +1/-50 | 25 of 74 |
| 20 s early, 30 s long | 0.265 | 0.568 | +1/-345 | 215 of 369 |
| 5 s in front of the full 30 s | 0.932 | 0.952 | +4/-13 (p 0.05) | 3 of 34 |
| 10 s in front of the full 30 s | 0.928 | 0.952 | +3/-14 (p 0.01) | 8 of 36 |
| 20 s in front of the full 30 s | 0.849 | 0.932 | +1/-52 | 38 of 76 |
| the first 25 s only | 0.930 | 0.944 | +2/-12 (p 0.01) | |
| the first 20 s only | 0.918 | 0.934 | +3/-19 | |
| the first 10 s only | 0.791 | 0.833 | +3/-83 | |

Two things are mixed in a window that opens early: less of the tune, and
someone else's audio. Paired against the same amount of the tune heard
cleanly, 5 s of the previous tune costs nothing measurable (0.930 to 0.922,
+6/-10, p 0.45), 10 s costs 6.5 points (0.918 to 0.853, +6/-39) and 20 s
against 10 s of the tune is a collapse (0.791 to 0.265), because the
previous tune then fills two thirds of the window and wins on its own
chunks. With the whole 30 s of the tune kept, 5 or 10 s in front cost about
two points and 20 s ten, half of those misses naming the previous tune. The
aligner's advantage survives: at 5, 10 and 20 s early it is +106/-2,
+137/-5 and +73/-35 against the n-grams on the same windows (0.715, 0.590
and 0.189 without it).

What the board needs from this: a start found within about five seconds
keeps nearly all of the bench's accuracy; a start ten or more seconds early
does not, and the loss is mostly the previous tune winning. So on the board
the aligner should score the span since the current tune's estimated start,
and a candidate that was the previous span's answer needs its early chunks
discounted, or the chunks weighted towards the latest audio. That is part of
item 3 of the plan.

**The key allowance (2026-09-29).** The player's proposal: a tune may be
played in another key than any of its settings, so try it outward round the
circle of fifths from each setting's own key (a fifth either way, +7 or +5
semitones, then a tone either way), at most two steps, each costing a little,
so the written key stays the strong default and a wrong tune does not get
twelve chances at a lucky match. A key some setting is written in costs
nothing, and because the aligner compares note names a key and its relative
major or minor are the same to it: The Cock and the Hen, played in F-sharp
minor on night 140, is already covered by its A major setting.
`Aligner(transpose="fifths", max_fifths=2, step_cost=...)`. Every
shortlisted tune's score at each of the five shifts was captured, and the
cost swept offline; the capture's written-key ranks reproduce the 30 s
headline exactly. Repertoire, audio alone, three trackers, both readings,
replace, 300, bench scope, 502 segments:

| | top-1 | top-5 | paired against the written key (0.950) |
|---|---|---|---|
| up to 2 steps, no cost | 0.952 | 0.968 | +2/-1 |
| up to 2 steps, cost 0.005 to 0.02 per step | **0.954** | **0.972** | +2/-0 (p 0.5) |
| up to 2 steps, cost 0.03 | 0.952 | 0.972 | +1/-0 |
| up to 2 steps, cost 0.05 or more | 0.950 | 0.968 to 0.970 | +0/-0 |
| up to 1 step, cost 0 to 0.02 | 0.954 | 0.968 to 0.972 | +2/-0 |

The two newly right are Galway Belle (night 1, a fifth down from every
setting, rank 126 to 1) and Mac's Fancy (night 4, the same, 158 to 1); both
are also misses at 120 s. With no cost, The Porthole of the Kelp loses to a
transposed wrong tune (1 to 3), which is the case the cost is there for.

How often this session plays a tune away from all its settings' keys: of the
489 segments whose tune is shortlisted, the right tune scores clearly better
(by 0.03 or more) at a shift for 6, 1.2%: the two above, The New Leaf and
Kenny's set on night 139 (Sergeant Early's Dream and Paddy Fahey's, +2, a
tone up, which from their D dorian settings is B minor's key signature, as
the player heard it; Julia Delaney's in the same set is +2 by 0.027), and
Biddy Martin's (+7). The four in the written key's first place were already
right; the allowance widens their margin.

It is the musically right rule and it cannot be told from noise on the bench
(+2/-0). Trying the other keys for every shortlisted tune costs five
alignments per tune; trying them only for the first `key_top` tunes in the
index's order (which matches intervals, so it does not depend on key) gives
the same top-1 on all 502 segments from 20 up (Galway Belle is 17th, Mac's
Fancy 4th), so the default is 50, at a third of the cost.

At 120 s, all eight nights, cost 0.02, paired on the 502 against the
aligner in the written key (0.982): 0.982 / 0.986, +2/-1. Galway Belle
(74 to 1) and Mac's Fancy (191 to 1) come right, and Take Your Churn loses to
The Mason's Apron transposed (1 to 2): with 35 settings each tried in five
keys, the hub gets the lucky match the cost was meant to prevent, so at two
minutes 0.02 is not quite enough for it. Not in the headline; the aligner's
cost model (plan item 4) is where a per-tune cost for many settings belongs.

**The aligner made parallel (2026-09-29).** `analysis.align.batch_chunk_scores`
aligns every chunk against every candidate setting in one numba pass across
all cores, summing each tune's chunks in the same order as `chunk_score`, so
the values are identical, not close: tests check equality, and night 2 at
30 s reproduces every saved rank (written key, 184 s before, 59 s after, on a
loaded machine), as do nights 1 and 2 with the key allowance against the
capture. Settings are cached as aligned. Runs that use it should go one at a
time, since each already uses every core; twenty in parallel on this
laptop's four performance cores took the load average to 120.

**Not yet measured:** the board; tunes
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

### Night 140's new segments: the first measure on labels nothing was tuned on (2026-09-29)

Recording 140 (2026-09-17, instance 499) had 25 scored segments, which every
setting was tuned with; the player then labelled the rest of the night, 61
more. No setting was chosen on whether those came out right, so they are the
closest thing to held-out data yet, with the caveat that they share a night,
players and room with 25 that were tuned on, and the board had replayed the
raw audio (without these labels) before. A night recorded after 2026-09-17
and never in the corpus remains the clean test.

**The bench on the 61 new segments** (labelled boundaries, audio alone,
three trackers unless named; the 25 tuned-on segments beside them):

| | new 61, top-1 / top-5 | tuned-on 25 |
|---|---|---|
| yin, n-grams, 30 s | 0.590 / 0.721 | 0.720 / 0.800 |
| three trackers, n-grams, 30 s | 0.738 / 0.836 | 0.760 / 0.880 |
| and the aligner, 30 s | **0.967** / 0.967 | 0.960 / 1.000 |
| and the key allowance, 30 s | 0.967 / 0.967 | 0.960 / 1.000 |
| three trackers, n-grams, 120 s | 0.770 / 0.902 | 0.840 / 0.960 |
| and the aligner, 120 s | 0.934 / 0.967 | 1.000 / 1.000 |
| and the key allowance, 120 s | 0.951 / 0.967 | 1.000 / 1.000 |
| full corpus, the aligner, 30 s | 0.934 / 0.934 | 0.960 / 1.000 |
| full corpus, the aligner, 120 s | 0.951 / 0.967 | 1.000 / 1.000 |

Paired on the 61: fusing the three trackers +9/-0 (p 0.004), the aligner
+14/-0 at 30 s and +10/-0 at 120 s, the key allowance +0/-0 and +1/-0. The
held-out segments score as well as the tuned-on ones did: the gains were not
fitted to the eight nights. At 30 s on the repertoire the only two misses are
The Piper on Horseback and Rocking the Boat, which first entered the
session's repertoire with this night's log, so the repertoire index (built
before) cannot contain them: a tune new to the session. The full corpus finds
both at 120 s. Its misses there are Stoney Brennan (rank 2, under The Mason's
Apron), St Patrick's Day as a set dance (17) and The Cock and the Hen (406;
first on the repertoire). The 25 newly labelled segments on night 138 score
1.000 at 120 s with the aligner and key allowance.

**The board on the 61**, the runs made on 2026-09-26 and 09-28 re-scored
against the new labels (the board never reads labels; `lab eval` re-scores):

| board | top-1 | top-5 | <30s | <60s | never | flips |
|---|---|---|---|---|---|---|
| yin (`v2key`) | 0.738 | 0.852 | 16.4% | 49.2% | 26.2% | 3.57 |
| three trackers (`fuse3`) | 0.721 | 0.836 | 9.8% | 52.5% | 23.0% | 2.62 |

Paired on the 61: top-1 +2/-3, within 30 s +1/-5, ever right +4/-2. Over the
eight tuned nights the fusion was 0.769 to 0.819 (+39/-14); here it is not
measurably better, only steadier. The board, at 0.72-0.74 on segments nothing
was tuned on, against the bench's 0.97, is the gap; the aligner is not on the
board yet (plan item 3). Re-scoring replaced both runs' stored per-segment
rows for night 140 (25 before, 86 now), so an eight-night `lab compare`
including night 140 now counts 86 segments there; the old rows are kept in
the lab scratch directory.

**The player's three hard cases**, read from the `fuse3` timeline:

- **The Copperplate and The Old Copperplate** (set 29, after The Bag of
  Spuds; The Copperplate is The New Copperplate on thesession.org). The bench
  gets both right at 30 s with or without the aligner. The board found the
  boundary into The Copperplate 1.3 s early and then showed The Bag of Spuds,
  the tune before, for 50 s, then Rakish Paddy, and ended on Rakish Paddy 0.30
  over The New Copperplate 0.28: wrong. The Old Copperplate opened on Rakish
  Paddy and The New Copperplate and was right from 30 s. The two are close
  enough that the board kept both near the top throughout.
- **The set that goes from a jig to a reel** (set 35, Da Full Rigged Ship
  into Da New Rigged Ship). The bench gets both right with the aligner. The
  board found the boundary 2.9 s early and then showed Da Full Rigged Ship,
  the jig, for 43 s into the reel, was briefly right at 87 s, and ended on The
  Star of Munster: wrong. Nothing on the board uses the change of meter.
- **False starts.** The board never says "no tune": in every gap of 15 s or
  more between labelled tunes it showed a tune the whole time, mostly the
  tune that had just ended (The Old Copperplate for 80 s after it stopped) or
  The Mason's Apron over chat. So a false start will be called a tune, and so
  will the chat around it. Where the player's false starts are is still to be
  marked so they can be scored individually.

All three are the problem plan item 3 is now framed around: the board holds
the previous tune after a change, and has no state for "not a tune".

### Is this still the same tune? The change-detection bench (2026-09-29)

Plan item 3, first step. `lab/bench/stream.py` replays a whole night the way
the live logger hears it and asks of every chunk whether it agrees with the
tune already believed, a new one has begun, or none is playing. Every 4 s the
last 8 s of each tracker's notes (tempo-free pitch changes) are aligned, with
the retrieval bench's own `Aligner`, against a pool: the index's shortlist
over the trailing 24 s plus the last six chunks' pools. A causal decoder (a
forward filter over every tune seen plus "not a tune": stay, or jump to a
pooled tune or to "not a tune"; emission `lam` times the chunk's aligner
score, "not a tune" scoring `lam * tau`) displays its most believed state.
No labels are read; they only score it, with the board's measures plus two
new ones: carry-over (how long the previous tune stays displayed after a
change inside a set) and the share of the unlabelled time between tunes
displayed as a tune.

Settings chosen on the seven tuning nights (1-5, 138, 139) over a grid of
240 (`lam` 10-160, `tau` 0.35-0.6, `p_switch` 0.005-0.1, `p_none` 0.1 or
0.3; objective top-1 at the end plus within 30 s minus a tenth of the gap
shown as a tune): `lam` 80, `tau` 0.5, `p_switch` 0.05, `p_none` 0.1, inside
the grid, and the choice on six nights of seven when each is left out.
Paired against the board's `fuse3` runs on the same segments:

| | right at end | within 30 s | within 60 s | never | flips | board: right at end, within 30 s, never, flips | paired right at end | paired within 30 s |
|---|---|---|---|---|---|---|---|---|
| seven tuning nights, setting chosen leaving each night out (502) | 0.922 | 90.2% | 96.4% | 2.2% | 2.34 | 0.831, 14.5%, 13.9%, 3.09 | +60/-14 (p < 0.001) | +380/-0 |
| night 140, the 61 new segments, setting from the seven | **0.885** | **88.5%** | 93.4% | 6.6% | 2.30 | 0.721, 9.8%, 23.0%, 2.62 | +11/-1 (p 0.006) | +48/-0 |
| night 140, the 25 tuned on | 0.880 | 88.0% | 96.0% | 0% | 2.28 | 0.720, 20.0%, 20.0%, 3.08 | +5/-1 | +17/-0 |

On night 140's new segments the previous tune stays displayed a median 6.8 s
after a change (none over 20 s), 15% of the time between tunes is displayed
as a tune and none of it as the tune just played. Untuned (`lam` 10,
`tau` 0.35) the seven nights were 0.936 right at the end but 65.7% within
30 s, a median 22.8 s of carry-over and 44% of the gaps shown as a tune: the
tuning trades a little top-1 and more flips (1.49 to 2.34) for answering
three times as fast and letting go of the previous tune.

**What this is and is not.** It is the aligner answering live, from no
labels, on a raw night, and on the held-out segments it is right within 30 s
nine times as often as the board. It is not yet the board: the notes are
tracked in 60 s blocks and the key filter estimates each block's key over
the whole block, so a note at time t can be filtered with up to a minute of
later audio. Tracking is local and the effect should be small, but it is not
measured, and the board version must be strictly causal. Nor does it find
boundaries to hand to anything else: the display is the product here.
Computing a night's features takes 8 to 13 minutes for 3.5 hours of audio,
about 20 times faster than real time.

**Made causal (2026-09-30).** Notes for each chunk are now rebuilt from the
frame tracks and audio up to the chunk's end only: segmented, split and
key-filtered over the trailing 24 s, a note still sounding cut off where it
is, as it would be live (`causal_notes`; the default). The only look-ahead
left is inside the neural trackers' own input windows, under about a second,
which a live logger running a second behind also has. The block mode first
reproduced its saved features for night 2 exactly (2,459 of 2,459 chunks)
through the rewritten code. Night 140, the decoder as tuned above:

| | right at end | within 30 s | never | flips | carry-over median | time between tunes shown as a tune |
|---|---|---|---|---|---|---|
| block notes, new 61 | 0.885 | 88.5% | 6.6% | 2.30 | 6.8 s | 14.7% (all night) |
| causal notes, new 61 | 0.885 | 88.5% | 6.6% | 2.28 | 6.7 s | 6.8% (all night) |

+0/-0 on both measures, on the new 61 and on the tuned 25. The look-ahead was
worth nothing to identification; being causal halved the chat and silence
displayed as a tune on this night (694 four-second chunks of gap), which is
one night and not yet explained. The decoder was tuned on block notes; it
has not been re-tuned on causal ones, which can only help it. A night's
causal features take about 7 minutes for 3.5 hours of audio.

**The player's hints measure nothing (2026-09-30).** `HintDecoder` makes it
easier to leave the tune on display at a likely moment, never calling a
change on its own: once it has been shown for a share of its usual length at
this session (median labelled length on the tuning nights other than the one
scored, never night 140; its type's median otherwise); while its latest
notes sit near the end of the tune as written (the aligner now also returns
where a chunk's notes end, `analysis.align.where_in_tune`); after a number
of passes, counted as that position wrapping; and a tune whose meter
disagrees with the meter heard over the last 12 s, when the pulse is sure of
it, scoring less. With every hint off it equals `Decoder` (tested). The
features were recomputed causally for all eight nights with these fields;
night 140 reproduced its earlier numbers exactly.

Each hint chosen leave-one-night-out on the seven tuning nights from a small
grid that includes "no hint", paired night by night against the same base
decoder with no hint:

| hint | seven nights, top-1 at end | within 30 s | night 140 new 61, top-1 / within 30 s |
|---|---|---|---|
| usual length | +0/-0 (every fold chose no hint) | +0/-0 | +0/-0 / +0/-0 |
| end of a pass | +0/-0 | +0/-0 | +0/-0 / +0/-0 |
| passes played | +0/-1 | +0/-0 | +0/-0 / +0/-0 |
| change of meter | +0/-0 | +0/-0 | +0/-0 / +0/-0 |
| all four (in-sample) | +0/-3 | +1/-0 | +0/-0 / +0/-0 |

A first pairing showed every hint at +10 to +12/-0 on the seven nights. That
was a measurement error, caught before it was reported: the plain decoder's
rows used a base setting chosen leaving each night out (four different
choices across the folds), and the hint rows all sat on the base chosen on
all seven, so the pairing credited the difference between two base settings
to the hints. Paired against the same base, the gain is gone.

Why nothing: the audio already decides. A tuned `lam` of 40 puts about 12
nats on a chunk where the new tune scores 0.3 above the old, and the hints
move the switch prior by ln 2 to ln 10, 0.7 to 2.3 nats; they could only
matter where two tunes score alike, which is a handful of segments. The
carry-over that is left (median 10 s) is set by the 8 s alignment window,
whose first chunks after a change still hold the previous tune, not by
reluctance to switch. Shortening or weighting the window is the lever for
that, not the hints. The hints stay in the code, off by default, and the
meter hint in particular is worth re-testing on the false starts and on the
board, where evidence is thinner.

The plain decoder re-tuned on causal features: `lam` 40, `tau` 0.45,
`p_switch` 0.02, `p_none` 0.3 (the leave-one-night-out folds chose among
four settings). Seven nights, leaving each out: 0.926 right at the end,
89.6% within 30 s, 2.05 flips, carry-over 9.0 s. Night 140's new 61: 0.902
right at the end, 83.6% within 30 s, 1.59 flips, 11.7% of the gaps shown as
a tune; against the block-tuned setting's 0.885 and 88.5% on the same
features, a trade of speed for steadiness rather than a gain.

**The alignment window against carry-over (2026-09-30).** Each chunk's
tunes were also scored on only its last 4 s and last 6 s
(`night_features(extra_windows=...)`), and the decoder read a mix
(`mix_windows`: 8 s as before, 6 s, 4 s, 8 s + 4 s, 8 s + 2 x 4 s, 6 s + 4 s),
each with its own decoder setting. Chosen leaving each tuning night out on
right-at-the-end plus within-30-s, the 8 s window won every fold, so on that
objective nothing changes (+0/-0). Carry-over is not in that objective, and
the trade is plain when each window at its own best setting is paired
against 8 s:

| window | seven nights (in-sample): right at end | within 30 s | carry-over shorter / longer | night 140 new 61: carry median, 90th percentile | right at end | within 30 s |
|---|---|---|---|---|---|---|
| 8 s | 0.950 | 89.2% | | 11.0 s, 15.0 s | 0.902 | 83.6% |
| 6 s | +2/-6 (p 0.29) | +6/-7 | 141 / 5 (p < 0.001) | 8.7 s, 11.7 s (21 / 0) | +1/-2 | +2/-0 |
| 4 s | +0/-19 (p < 0.001) | +7/-16 | 212 / 6 | 6.9 s, 10.8 s (28 / 0) | +0/-4 | +2/-0 |
| 8 s + 4 s | +2/-14 (p 0.004) | +12/-3 (p 0.04) | 242 / 0 | 6.3 s, 10.3 s (32 / 0) | +0/-3 | +3/-0 |

Six seconds takes about 2.5 s off the time the previous tune stays on
display, on both the tuning nights and the held-out segments, at no
measurable cost to the answer at the end or to speed; four seconds, or
mixing it in, takes off about 4 s and costs the answer at the end
significantly. The player chose 6 s (2026-09-30); it is the stream bench's
default, with the decoder's defaults its tuned setting (`lam` 40, `tau`
0.45, `p_switch` 0.05, `p_none` 0.3), and what the board will use.

**Not tempo (2026-09-30).** The player asked whether the shorter window
helps faster tunes. Over all eight nights, segments that follow another tune
directly: the carry-over saved by 6 s (or 4 s) against 8 s correlates -0.01
(-0.00) with the tempo, the eighth-note period over the segment (n 351).
This session plays in a narrow band, 146 to 174 ms an eighth by tercile
medians, about 9% either way. What differs is the kind of tune: at 6 s jigs,
slides and slip jigs let go a median 4 s sooner, reels and polkas a median 0
(and the right-at-end losses are reels, +3/-5); reels are not faster here in
eighths a second, so that is not tempo either, and is not explained. A window
that follows tempo (each chunk the stored 4, 6 or 8 s window nearest a fixed
number of eighths) is no better than 6 s: 32 eighths lets go sooner and
loses the answer at the end (+1/-12, p 0.003), 40 to 56 eighths hold on
longer. Carry-over is measured in steps of the 4 s hop, which also floors how
fast the display can react; the board steps every 2 s.

Next: the false starts once the player marks them; then the same decoder
on the board.

### The follower: the change detector on the board (2026-09-30)

`lab/experts/follower.py` replaces the matcher and the assembler
(`lab/configs/follower.json`: fuse3's three trackers, pulse and notes, then
the follower; scheduler "always"). Every 4 s it takes the notes the `notes`
expert has posted over the trailing 24 s, drops those outside the key and
its modal neighbour, and calls the bench's own `ChunkScorer` and `Decoder`
(6 s window, the tuned defaults), writing what it displays as the assembler
does so every tool reads it. The two loops share the scoring and decoding
code: night 140's saved bench features reproduce exactly through
`ChunkScorer` (3,104 of 3,104 chunks), the stepping decoder equals the old
one, and `test_engine` checks that replaying the notes the follower was
given reproduces its display.

**A board bug found on the way.** The first run flipped 6.1 times a tune.
Night 140 replayed offline with only the notes the board had posted by each
moment gave 0.902 and 2.52 flips, so neither the notes nor their lateness
(median 2.2 s after a note ends; deciding 1 to 4 s behind the clock changed
little) was the cause. `BoardView.new` returned only the current chunk's
observations whenever it had any, so an expert that does not run on every
chunk lost the chunks in between; the follower, a 4 s hop on 2 s chunks, was
given half the notes. Fixed, with a regression test that fails on the old
code. Every expert before it ran on every chunk, and fuse3 re-run on night
140 after the fix reproduces its stored hypothesis events exactly (8,259 of
8,259), so no earlier board number is affected.

**All eight nights, 588 segments** (the new labels on nights 138 and 140
included), against the current board:

| board | top-1 at end | top-5 | <30s | <60s | never | flips |
|---|---|---|---|---|---|---|
| three trackers, n-grams, assembler (`fuse3`) | 0.815 | 0.910 | 14.3% | 49.5% | 15.1% | 3.04 |
| three trackers, the follower | **0.908** | **0.934** | **84.5%** | **95.6%** | **3.4%** | **1.97** |

Paired: top-1 at end +70/-15, within 30 s +414/-1, within 60 s +271/-0, ever
right +70/-1 (all p < 0.001); fewer flips on 265 segments and more on 144.
**Night 140's 61 held-out segments** (no setting chosen on them): 0.902
against 0.721 (+12/-1, p 0.003), within 30 s 82.0% against 9.8% (+45/-1),
never 6.6% against 23.0%, flips 2.15 against 2.62. A night takes about 3
minutes with the pitch tracks cached.

Scope: the decoder's settings were chosen on the bench over nights 1-5, 138
and 139, which are seven of these eight; fuse3's were chosen on all eight.
Night 140's new segments are the fair comparison, and they agree with the
pooled one. The board still reads only this session's repertoire, so a tune
new to the session (two on night 140) cannot be named.

The board is no longer the gap: live, it is right within 30 s five times as
often as it was, and within two points of the bench's answer at the end.

**Tunes new to the session: the full-corpus fallback (2026-09-30).** About
2% of what is played on a night is a tune the session has not logged on any
other of its 197 nights (14 of 607 labelled segments). Measured honestly by
making each night's own new tunes unknown: the pool is the repertoire index
restricted to tunes logged on OTHER nights, and the whole corpus's index
adds its own top 20 (`ChunkScorer(known=..., fallback_index=...)`), marked
"outside" so the decoder can discount them (`Decoder(nu=...)`: an outside
tune scores `lam * nu` less). "No fallback" is the same features with the
outside tunes removed, so both sides see identical evidence. Decoder as
tuned; aligner sequences for the whole corpus.

| | new tunes: right at end | within 30 s | known tunes: right at end | known tunes ending on a wrong outside tune (eight nights) |
|---|---|---|---|---|
| no fallback | 0 of 11 | 0 of 11 | 0.935 (510) | |
| fallback, `nu` 0 | **0.727** (+8/-0, p 0.008) | 0.545 | 0.935 (+1/-1) | 2 |
| fallback, `nu` 0.05 | 0.545 (+6/-0) | 0.545 | 0.937 (+1/-0) | 0 |
| fallback, `nu` 0.1 to 0.3 | 0.455 to 0 | | 0.937 | 0 |

The seven tuning nights; leaving each out, every fold chose `nu` 0. Night
140 with it, held out: The Piper on Horseback right after 29 s and Rocking
the Boat after 7 s, neither nameable before; Stoney Brennan (also new to the
session in this simulation) still missed, as the full-corpus retrieval bench
ranked it second under The Mason's Apron. The aligner is decisive enough that
an unfamiliar tune rarely out-scores the right known one, so the fallback
costs the known tunes nothing measurable; `nu` 0.05 is the cautious setting
if a wrong unfamiliar name is worse than none (it removes both such endings
and keeps 6 of the 11).

On the board (`follower(fallback_top=20, nu=0, known="other_nights")`
against the same without the fallback, both with each night's new tunes
unknown), all eight nights, 607 segments: right at the end 0.895 to 0.909
(+10/-1, p 0.01), within 30 s 83.5% to 84.5% (+6/-0), never right 4.9% to
3.3% (+10/-0). Tunes new to their night: 0 of 14 to 9 of 14 (+9/-0, p
0.004); known tunes 543 of 593 either way (+1/-1). Still missed: O'Connell's
Trip to Parliament, Pete Bradley's, Take Your Churn, Colonel McBain and
Stoney Brennan. The fallback is on in `lab/configs/follower.json`, where
"known" is the session's repertoire, as it would be live, with `nu` 0.05:
the player's choice (2026-10-01), "unknown is better than wrong". On the
bench that names 6 of the 11 tuning-night new tunes instead of 8 and ends no
known-tune segment on a wrong unfamiliar one instead of 2; the board numbers
above are at `nu` 0.

### A night segmented blind: night 137 (2026-10-01)

The first test on a night nothing was tuned on, treated as unlabelled.
Recording 137 (instance 404, 2026-04-30, 69 labelled tunes) was replayed raw
on the board with the follower (corpus fallback, `nu` 0.05) and the night's
own tunes made unknown; the segmentation (sets, tunes, estimated starts and
ends, confidence) was written from the board's display alone, with a
cleaning rule fixed in advance (drop detections shown under 20 s, merge one
tune's detections across under 20 s), and committed with its hash before any
label was read (`053 files/blind-r137.md`, `.json`; 7a62ad1). The comparison
is `053 files/blind-r137-comparison.md`.

| | night 137, blind |
|---|---|
| right when the tune ends (`lab eval`) | 59 of 69 (0.855), top-5 0.899 |
| first right, median | 15 s |
| changes of answer a tune | 2.6 |
| labelled tunes named right in their span / wrong / never | 64 / 4 / 1 |
| start error when right | median +9 s (middle half +5.5 to +17 s); 55% within 10 s |
| labelled sets starting within 30 s of a detected one | 25 of 29 (35 detected) |
| segments over no labelled tune | 7, every one a hub (Frieze Breeches 4, Mason's Apron 2, Tarbolton 1) |
| tunes new to the session | 1 of 3 named |

Against night 140's held-out segments (0.902) it is three to five points
lower, on a night that shares nothing with the tuning but the session.
Raw, the display made 280 detections, 189 of them under 20 s: the live
display needs its hold (`lab display`) on top of the follower. The two
levers the night shows: starts that are late by about 9 s, and the hubs
standing in for "not a tune" over chat and false starts.

### Is this a tune at all? Tune-ness, and a charge on hubs (2026-10-01)

The player's notes on night 137's seven false segments: tuning and random
noodling, a few phrases of a jig, a piper improvising a slow air with no
pulse; notes random and broken by silence, too short to be a tune, and
"musical coherence WAY lower than any tune". Every one was shown as a hub
(The Frieze Breeches, The Mason's Apron, Tarbolton).

**A charge per setting** (`Decoder(kappa=..., n_settings=...)`: a tune scores
`lam * kappa * ln(settings)` less; the median repertoire tune has 9 settings,
The Mason's Apron 35). Chosen leaving each tuning night out, 0.01 every
fold. The time between tunes shown as a hub: seven nights 6.3% to 2.5%,
night 140 5.2% to 1.3%, night 137 12.8% to 6.3%; right at the end +3/-2,
+0/-1, +0/-1. At 0.04 and above it wrecks naming (+1/-52), because the right
tune is often one with many settings: a blunt tool, and clustering each
tune's settings is the precise one, still to do.

**Tune-ness** (`lab/analysis/tuneness.py`, model `lab/configs/tuneness.json`).
Per 4 s chunk: the pulse over the last 12 s (strength, how sure the meter
is), loudness, and per tracker over the last 6 s how much is pitched, how
spread the pitch classes are and how settled the pitch; with the aligner's
note count, best score and margin. Labels: a chunk inside a labelled tune
(5 s from its edges) is a tune, one inside a gap of 15 s or more is not.
Logistic, class-balanced. Each night scored by a model fitted on the other
seven: AUC 0.988 to 0.997; audio features alone 0.993 on average; night 137,
never seen, 0.990. The strongest signs of a tune: loudness, notes, pulse,
Basic Pitch's voicing, the best tune's score. Much of the gap time is talk
and silence, which is easy; noodling is the hard minority, so read the AUC
with the player's stretches below. Into the decoder: "not a tune" scores
`lam * (tau - gamma * logodds / 10)`.

Both, each chosen leaving each night out (every fold: `gamma` 0.5, `kappa`
0.01), against neither:

| | time between tunes shown as a tune | right at the end | within 30 s |
|---|---|---|---|
| eight nights | 13.0% to **3.1%** | +5/-2 | +6/-5 |
| night 137, held out | 21.4% to **4.5%** | +1/-1 | +1/-0 |

The player's stretches on night 137, share of chunks shown as a tune, before
and with both: the piper's air after the Dr O'Neill's snippets 97% to 0%;
tuning at 4:34 64% to 27%; noodling with phrases of the Cuil Aodha jig 100%
to 50%; the piper's noodling at 35:58 91% to 55% and at 1:11:22 80% to 70%.
Noodling that carries real melodic fragments is what is left; the player's
"too short to be a tune" (a minimum duration before a segment counts) is the
next lever for it. `lab listen` runs both; the follower expert on the board
does not yet compute tune-ness (it reads notes, not pitch tracks).

### Where each tune starts: following a set through its tunes (2026-10-02)

The job here is after the fact, not live: segmenting hundreds of hours of
back recordings, and giving the session page segments that start where the
tune does. The tunes, their order and their sets are known (the night's log,
or the meter's), so what is left is where each one begins.

**The meter's drafts** (`lab drafts`, from the phone's meter log, first used
on recording 143): a set's first tune from where the music starts back from
when it was first shown, a later tune 15 s before it was first shown. Against
the player's corrections on 143: first of a set within 1 s 5 of 31 (median
3.4 s); later in a set 5 of 40 (median 6.0 s). The meter showed a later tune
a median 10.5 s after it began, not 15. Set ends, at the last state that heard
a tune: median 1.1 s off.

**A setting's played form** (`analysis/form.py`): the parser reads a setting
once through as written; a session plays A A B B. Expanding repeats, first and
second endings and `::` gives each setting on a grid of eighths with its bar
lines. It reads all 12,641 repertoire settings; 1,107 of 5,560 reels come out
16 bars, written without repeat signs because players repeat each part
anyway, so the written form cannot say how long a tune runs as played.

**Finding the opening** (feasibility, 143): each tune's first 24 eighths,
searched on a beat grid within 30 s either side of the corrected start. The
best match lands a median 9.6 s late, on the A part's repeat, which matches
more cleanly than the first time through; the earliest match scoring half of a
perfect one lands within 1 s for 33 of 64.

**Score following** (`analysis/follow.py`): a Viterbi path through "not a
tune", each tune's played form eighth by eighth and round again, and "not a
tune", over the heard notes (Basic Pitch) on a grid from the tempo map. The
position moves one eighth a slot, or two, or none; a tune is entered only at
its first eighth; the change to the next tune is cheap from the last bar of
the form and dear elsewhere, so the outgoing tune's grid running forward and
the incoming tune's opening running back meet at one slot. Every setting runs
side by side. Constants set before the first run, none tuned since.

| | first of a set, within 1 s | 2 s | 5 s | median | later in a set, within 1 s | 2 s | 5 s | median |
|---|---|---|---|---|---|---|---|---|
| 143, drafts | 5 / 31 | 11 | 22 | 3.40 s | 5 / 40 | 9 | 16 | 5.95 s |
| 143, following (spans from the meter) | 22 / 31 | 24 | 26 | 0.44 s | 35 / 41 | 39 | 39 | 0.16 s |
| nights 1-5, 138-140, following (spans from the labels) | 159 / 251 | 196 | 223 | 0.58 s | 315 / 357 | 334 | 351 | 0.25 s |

On 143, paired against the drafts: better 61, worse 9 (sign test p = 1.3e-10).
143 is the night it was built on; the eight older nights were never looked at
while building it, and every night is alike (changeovers within 1 s 83-98%,
set starts 44-77%). On the older nights a set's span is the labels' with 60 s
before and 30 s after, which hands the set start a bound the meter would not;
the changeovers do not depend on it.

Negative: where the path leaves the set's last tune is a worse set end than
tune-ness (median 2.3 s on the eight nights, 3.4 s on 143, against 1.1 s);
set ends stay with tune-ness for now.

Misses over 2 s on the eight nights: 78 of 608, 54 late and 24 early. Late is
the path waiting for a cleaner time round to enter the tune; on Tuttle's (143,
+26 s) the grid at the set's start was also wrong, the first tempo window
being mostly the chat before the set (179 ms an eighth against 145-151 in the
tune).

Negative: a tempo map from only the windows that heard a beat (pulse
strength at least half the span's median; the grid holds the nearest strong
window's tempo across the weak ones), threshold fixed before the run. Over the
nine nights: first of a set within 1 s 181 -> 182, better 40 worse 39 (p = 1);
later in a set 350 -> 349, better 53 worse 44 (p = 0.42). Tuttle's moved under
0.1 s: the wrong grid was not what held it back, the weakly transcribed first
time through was. Taken out; `tempo_map` keeps each window's `strength`.

Negative: walking a set's first tune back. The path enters a tune only at its
first eighth, and what it matched there could as well be the A part's repeat
or a later time round, so the start was allowed to step back by any distance
that puts the entry on an A start (from the played form), keeping the furthest
step from which the form, played from its first eighth, beats "not a tune"
over the stretch and over its first part alone. Over the nine nights it moved
8 set starts: better 3 (Take Your Churn +18.3 -> +5.6 s, The White Petticoat
+8.1 -> +0.8, The Dunmore Lasses +6.8 -> -4.4), worse 5 (four right ones
pulled back about one A part, 7-9 s; p = 0.73), and none of the long late
misses (Tuttle's +26 s, the four of about 33 s) moved. So those are not entries
a time round late, and "beats not a tune" is too weak a test of whether the
tune was playing: the chat or lead-in before a set sometimes passes it. Taken
out.

**The player listened to the worst six on 143** (2026-10-02). Rolling Waves
(the second) was mislabelled: following was right, 0:43:25. Martin Wynne's
moved to 1:09:06, where the player's rhythm settles and he plays the A part
twice; before that is a best guess. Tuttle's: a guitar plays the A part from
3:00:26 under the player talking, barely audible; the label stays there by
the rule above (first note as played), and following's 3:00:52 is what can
be heard. The Cordal: no music is audible where following put it (20 s
before the guitar's quiet start), so the path matched chat or room noise to
the tune's opening. Music For A Found Harmonium: a banjo plays the A part
once from 2:57:43; following took the stronger start at 2:58:00. Mac's Fancy:
played in D mixolydian, and every setting on thesession.org is in A
mixolydian. The player's verdict: reasonable mistakes on a recording whose
ground truth is hard to hear.

**The session's key** (`session_tune.key`, set on 2 of the 1,284 tunes in
session 1's repertoire): a setting is moved from its written key's tonic to
the session's. Mac's Fancy +14.6 s -> -0.2 s; over the nine nights better 1,
worse 1. Kept: it is a fact about how the session plays the tune.

Negative: the aligner's key allowance in following, each setting also a fifth
either way at a cost of 3: better 5, worse 4 over the nine nights (p = 1),
for three times the work. Taken out.

Negative: entering a set's first tune at a later section of its form (the B
part, or the A part's repeat) at a cost of 6, the start then counted back
along the grid to the form's first eighth, for an A part too quiet to hear
(the player's suggestion for The Cordal). Over the nine nights first of a
set better 8, worse 18; all tunes better 8, worse 20 (p = 0.036). The Cordal
did not move (-19.6 s), since the path was not entering at a later section
but matching chat 20 s before any music; Music For A Found Harmonium went
from +16.7 to -41 s. Taken out. What The Cordal wants is "not a tune" winning
more clearly where nothing tuneful plays: tune-ness as evidence in the path.

Where it stands, 143 on the corrected labels: first of a set within 1 s 22
of 31, later in a set 36 of 41.

**In `lab drafts`** (2026-10-02): the meter's drafts first (sets, tunes in
order, each set's rough span), then following for each set's starts; set ends
stay the meter's. On 143: first of a set within 1 s 22 of 31, later in a set
37 of 41 (all 41 within 2 s; the session's key now places Mac's Fancy).

**Back recordings, with no meter log** (`lab drafts N --replay`): the
listener run over the audio offline (about 12 times faster than real time on
the laptop) stands in for the meter, with no taps, so every tune is placed by
the first run of at least 16 s showing it after the tune before; then
following. Night 140, from its audio and its logged order only, the labels
used only to score:

| | within 1 s | 2 s | 5 s | median |
|---|---|---|---|---|
| later in a set, followed | 45 / 50 | 46 | 48 | 0.23 s |
| later in a set, replay alone | 3 / 50 | 8 | 30 | 4.35 s |
| first of a set, followed | 21 / 36 | 25 | 29 | 0.72 s |
| first of a set, replay alone | 6 / 36 | 9 | 19 | 3.35 s |
| set ends (where the music stops) | within 2 s 25 / 36 | | | 1.45 s |

About what following gave on 140 with spans from the labels (22 and 44
within 1 s), so the replay's spans are good enough. The worst: Soggy's +33 s,
Banish Misfortune -17 s, Out On The Ocean +16.5 s (the night's first tune,
at 0:00:00), The Salamanca -12 s, The Milliner's Daughter -11 s.

**Never-logged nights** (`lab drafts N --blind`, 2026-10-03): the log itself
inferred from the replay, by the blind-segmentation rules fixed on night 137
(runs of one tune on display; under 20 s dropped; one tune's runs merged
across under 40 s; a set break after more than 10 s with nothing shown; a
set's last tune ends where the music stops), then following for the starts.
`--apply` logs and places each tune in one pass. Each labelled night treated
as never logged, labels only to score:

| night | labelled tunes named right | wrong | nothing over it | blind tunes over no labelled tune | starts within 1 s, of those right | sets, blind / labelled |
|---|---|---|---|---|---|---|
| 1 | 71 / 83 | 11 | 1 | 7 | 53 / 71 | 43 / 34 |
| 2 | 52 / 59 | 7 | 0 | 4 | 37 / 52 | 29 / 23 |
| 3 | 64 / 68 | 3 | 1 | 2 | 56 / 64 | 36 / 31 |
| 4 | 75 / 83 | 7 | 1 | 6 | 51 / 75 | 43 / 34 |
| 5 | 68 / 81 | 12 | 1 | 5 | 45 / 68 | 48 / 36 |
| 138 | 80 / 81 | 1 | 0 | 1 | 63 / 80 | 33 / 32 |
| 139 | 60 / 69 | 9 | 0 | 9 | 53 / 60 | 39 / 26 |
| 140 | 79 / 86 | 6 | 1 | 3 | 60 / 79 | 39 / 36 |
| all | 549 / 610 (0.90) | 56 | 5 | 37 | 418 / 549 (0.76) | 310 / 252 |

Scope: the listener's decoder was tuned on nights 1-5 (and its window,
tune-ness and fallback chosen on nights 1-5 and 138-140), so these are its
own nights; only the inference rules and following were never fitted to them.
The first real test is a back recording the player checks. On night 140 the
mistakes were a tune held on the display into the next one (whose own run
then lands after the set), two tunes merged into one, and single confusions;
the median belief while shown did not separate wrong tunes (all 0.68-1.0).
Sets come out split: 310 blind against 252 labelled, a set break wherever
the display shows nothing for 10 s inside a set.

Then three changes: the player's join rule (same tune type and under 5 s
between them is one set, the 5 s read off these nights' labels: same-type
breaks under 5 s were one labelled set 13 times of 15); a followed start more
than one step after the tune was first shown rejected (the path had pushed
tunes it matched badly into the quiet after the music, which also read as 30 s
gaps between sets); and a set's end capped at the next tune's start. Same
eight nights, same scoring:

| | before | after |
|---|---|---|
| labelled tunes named right | 549 / 610 | 583 / 610 (0.96) |
| named wrong | 56 | 22 |
| nothing over a labelled tune | 5 | 5 |
| blind tunes over no labelled tune | 37 | 7 |
| starts within 1 s, of those right | 418 / 549 | 422 / 583 |
| sets, blind (labelled 252) | 310 | 266 |
| labelled set starts with a blind one within 5 s | | 212 / 252 |

Most of the "wrong" names before were the right tune put in the wrong place:
scored by overlap, a tune pushed past its music overlapped its neighbour. The
join threshold was read off these nights, so the set counts are fitted. The
19 same-type breaks that remain where the labels have one set are in
`053 files/set-breaks-to-review.md`, for the player; some are long (100-288 s),
which looks like music the blind log does not cover rather than a pause.

Recording 112 (2025-07-03, session 1, never logged, 202 min), blind: 80 tunes
in 34 sets, 74 starts from following, 4 rejected, 3 sets joined, 2 same-type
breaks of 8 and 14 s kept for review.

**Negative: searching the blind log's holes for missed tunes** (2026-10-03).
The listener can call a tune "not a tune" for its whole length when people
talk loudly over it: The Sailor On The Rock, night 1, 20:47-21:46 (labelled),
tune-ness 0.1-0.3 throughout and never shown, so the blind log jumped from
Speed The Plough to The Lady On The Island and the set-break review list
showed a 48 s gap. Every stretch of at least 20 s between where one blind tune
was last shown and the next one's start was transcribed with the listener's
three trackers and searched whole, as the bench searches a segment (the
repertoire's n-gram shortlist of 300, then the aligner), with no tune-ness and
no decoder. On the eight labelled nights: 244 such gaps; 17 hold a labelled
tune the blind log missed, 34 the tail of a tune it has, 193 no labelled tune.
For the 17, the labelled tune was first once (The Floating Crowbar) and in the
top three 3 times. Scores do not separate them: top score median 0.437 for a
missed tune against 0.391 for no tune, ranges overlapping; the top's lead over
the second a median 0.007 either way; the same hub tunes (The Tarbolton, The
Scholar, The Mason's Apron) lead everywhere. A whole minute of talk over music,
searched at once, loses what protects the listener from hubs. Nor does a
simple rule flag the holes for a person: the best, median tune-ness at least
0.3 in the gap, flags 22 gaps and catches 6 of the 17. Taken out. What might
work: the listener's own per-window scoring over the gap with "not a tune"
switched off, so the decoder's hub charge still applies.

**Recording 112, applied blind and corrected by the player** (2026-10-04): the
first night the listener was never tuned on, logged and segmented from its
audio alone. Of the player's 79 tunes, 76 named right; 2 wrong (The Duke Of
Leinster read as Cregg's Pipes then Christmas Eve; Mac's Fancy as The Blarney
Pilgrim, the session playing it in D mixolydian against settings all in A); 1
missed (The Bunch Of Green Rushes, played once through, near a false start,
not to be chased). One hallucinated tune: The Bucks Of Oranmore, a reel in
the middle of a jig set (following had rejected its start). Sets: 34 and 34;
28 of the player's set starts have a blind one within 5 s. The player left 63
of 75 starts as drafted (a draft anchors its corrector, so "left" means good
enough, not exact); of the 12 moved, 6 by 3 s or less, the largest 69 and
50 s. Set ends moved for 24 of 33, median 1.1 s, earlier 15 times and later 9:
the end comes from 4 s tune-ness steps. The player's verdict: very good,
almost all tunes right. Their description of an end, for a rule to find it:
a long held final note, then a moment of silence or at least no music,
sometimes applause.

**Set ends from the held final note** (2026-10-04). Against the 311 explicit
set ends labelled on nights 1-5, 138-140, 143 and 112, searched around the
meter's end (the last 4 s step that heard a tune, R0):

| rule | placed | median error | within 0.5 s | 1 s | 2 s |
|---|---|---|---|---|---|
| R0, the meter's end | 311 | 1.34 s | 62 | 125 | 215 |
| the end of the last note held >= 300 ms with no new note for 1 s | 113 | 0.92 s (early 0.55 s) | 27 | 65 | 86 |
| where the level falls 8 dB below the 10 s before and stays down 0.5 s | 189 | 1.69 s (late 1.65 s) | 42 | 66 | 101 |
| held >= 400 ms, quiet 400 ms, within 6 s before to 2 s after R0, plus 726 ms; else R0 | 311 | 0.91 s | 100 | 168 | 237 |

The held note's transcribed end comes early, the note ringing on past where
Basic Pitch lets it go; 726 ms is the median over those ends, and leave-one-
night-out gives the same counts. Chat and applause straight after the tune are
transcribed as notes too, so a whole second of nothing is rare; 400 ms is
enough. Paired against R0: better 73, worse 33 (sign test p = 0.0001); every
night better (within 1 s, e.g. night 3 8 -> 16, 138 9 -> 17, 112 18 -> 24).
The held note is found for 114 of 311 ends; the rest keep R0. The thresholds
were chosen among a few on these same ends. In `lab drafts` for every mode.

**The key allowance in the listener** (2026-10-04). The bench's allowance (a
tune a fifth or two from every setting's key, 0.02 a step) was never in the
listener, so blind mode could not name Mac's Fancy, played in D against
settings all in A. Nine nights (112, 1-5, 138-140) run blind with and without
it: named right 659 -> 662 of 689. Tune by tune: gained Mac's Fancy (112 and
night 4) and Jim Keefe's (night 1), all played away from their settings'
keys; at two changeovers a wrong extra tune went and the start came out
23-26 s late (Martin Wynne's #1, night 2; The Blockers, 138); at two others a
zero-length wrong tune appeared (The Mason's Apron, Frieze Britches). Compute:
252 -> 304 ms a 4 s step on the laptop (+20%). On by default for replays,
where time is cheap; off in the live service, which on Render already takes
2.0-3.2 s a step.

**Squeezed blind tunes.** Following has to place every tune it is given, and a
brief misreading at a changeover ends up squeezed in front of the tune really
there. Over the nine nights, both runs, all 23 blind tunes following left
under 5 s before the next were wrong, none right; they are dropped (5 s read
off these runs).

**One corpus for every session: shortlists merged** (2026-10-04). The bench's
headline setup (yin, Basic Pitch and PESTO fused, 30 s, both readings, aligner
replacing, a 300-tune shortlist) over 607 segments of nights 1-5 and 138-140,
each run keeping every segment's 300 candidates with their aligner scores, so
shortlists can be merged offline (the aligner scores a tune the same whichever
shortlist brought it):

| shortlist | named right / 607 | right tune on the shortlist |
|---|---|---|
| whole thesession.org corpus, 300 | 561 | 567 |
| the repertoire as today (includes each night's own tunes) | 572 | 584 |
| the repertoire as known before the night, as a filter | 559 | 570 |
| popular tunes (>= 100 tunebooks, 2,320), 300 | 545 (0.898) | |
| a new session: whole corpus + popular | 568 | 578 |
| this session: whole corpus + repertoire before the night | 572 | 584 |
| this session: + popular as well | 572 | 584 |

Against the whole corpus alone: a new session's union better 10, worse 3 (p
0.092); this session's better 14, worse 3 (p 0.013). Priors on the ranking
(tunebook tiers or a log-tunebook bonus, the session's history as a bonus, all
chosen leave-one-night-out) moved the whole-corpus run by 1 at most (560-562):
the gap is the shortlist, not the ranking, since the aligner already names the
right tune 561 times of the 567 it reaches. The repertoire as a filter, scored
fairly, is below the whole corpus: 18 of the 607 are tunes the session played
for the first time that night. So production's shortlist is a union: the whole
corpus, the session's own tunes, and, with no history, popular ones. The cost is
the aligner's, the bulk of the live step: up to 600-900 candidates against
300; the sizes are to trade against the profiling.

**Merged shortlists in the listener** (2026-10-05). The listener's pool from
one whole-corpus index: the corpus's top 100 a step and the session's own
tunes' top 100 (a restricted lookup; the tunes logged before the night, as a
live system would know them), tunes outside the session's discounted as the
fallback's were. Nine nights blind (112, 1-5, 138-140), key allowance on,
against the repertoire shortlist on the same code: named right 662 and 662 of
689, extra wrong tunes 5 and 5; tune by tune better 6, worse 2 (p 0.29). Gained
The Gold Ring (112, where The Bucks Of Oranmore had been), Martin Wynne's #1,
The Maid Behind The Bar, The Peeler's Jacket, Music For A Found Harmonium, The
Piper On Horseback (first played that night); lost Jim Keefe's (first played
that night, a polka named as The Mason's Apron, a reel; the repertoire
shortlist had it only because today's repertoire includes the night's own
tunes) and The Porthole Of The Kelp. Compute +3% a step. So the production
design costs nothing here and needs no index per session; The Duke Of Leinster
(112, first played that night) is still not reached.

**Confidence that means what it says** (2026-10-07). The listener will log
tunes itself, so each logged tune needs the chance it is right, shown where a
person checks it. The decoder's belief is not that chance: of the tunes it
held at 0.99 or more, 0.8% were wrong, and the 108 wrong or extra tunes of ten
nights' blind drafts (nine nights and 136, with the session's history and as a
new session; 1,581 tunes) mostly sat at 0.7-1.0. `analysis.confidence` fits a
logistic model on each drafted tune's belief (median and 10th percentile while
shown), how steadily it was shown, its length, its tunebook count, whether it
is outside the session and the stretch's tune-ness, against the labels
(thesession.org duplicates counted as one, `lab/configs/same_tunes.json`).
Scored leaving each night out, it is honest where it matters: said under 50%,
14% right (99 tunes); 50-70%, 57% (21); 70-90%, 70% against 82% said (37, the
one band a little overconfident); 90-97%, 100% (43); 97-99%, 97% (102); 99% and
over, 100% (1,279). Brier 0.018 against belief's 0.051. Under 70 it flags 120
tunes holding 94 of the 108 wrong ones (belief under 0.7 flagged 17). Length
and belief carry most of it; popular tunes come out slightly less sure (their
look-alikes are popular too) and tunes outside the session slightly more
(what reaches the log from outside has beaten the session's own). Model 1 is
`lab/configs/confidence.json`; drafts carry each tune's features and `p_right`
(0-99), and `--apply` sends them as the log row's `confidence` with
`confidence_model` "listen-1" (schema 060, spec 050 "A machine's guesses"), so
the segmenter asks for a check on every one under 100. Refitting with more
labelled nights is a new version; a stored confidence keeps the version that
made it.

**Letting go when belief drops** (2026-10-08). Of the 36 labelled tunes still
not named right over thirteen nights, 13 had been shown at some point but were
drafted as another; the next biggest groups: 8 a candidate never shown, 6 not
heard as a tune (quiet, talk), 6 never a candidate (first time, or Mac's
Fancy off its key), 3 under 45 s. The player's idea: a tune that was 100%
and drops has changed; stop hearing it. Measured as a signal on the saved
states: a tune held at 0.99 or more for 40 s whose belief falls under 0.9 is
a changeover 59% of the time, a set's end 38%, mid-tune 3% (26 of 817), and
such a drop comes at 89% of changeovers (held only 12 s: 8% mid-tune).
`Listener(drop_release_s=)`: on such a drop the tune is ruled out for that
long, as a "none of these" tap does. Replayed on all thirteen nights at 60 s,
against the same with the long settings left out, through the same final
steps: named right 882 -> 884 of 918 (fixed 5, all of the shown-but-drafted-
as-another kind: The Sailor's Bonnet, The Porthole Of The Kelp, The New Custom
House, The Bunch Of Green Rushes twice; broken 3 on the hard nights,
Mulqueen's and Da New Rigged Ship on 139, Mickey Chewing Bubblegum on 115;
p 0.73); wrong or extra 42 -> 47; to check 65 -> 69; starts unchanged (687 ->
684 within 1 s). Not adopted at 60 s. At 20 s, same nights and steps:
named right 882 -> 884 (fixed 3: The Porthole Of The Kelp, The Bunch Of Green
Rushes twice; broken 1: Da New Rigged Ship on 139; p 0.62); wrong or extra
42 -> 44; to check 65 -> 69; starts 687 -> 684 within 1 s. Two more named
against two more extras and four more to check, and neither length is
distinguishable from chance: not adopted; `drop_release_s` stays, off by
default. The shown-but-drafted-as-another misses are not mostly a held tune
refusing to let go.

**A judge by following** (2026-10-09). After Fable's suggestion (in
another session) of online score following as the live state: the live
decoder carries which tune, not where in it, and judges each 6 s window
afresh. First the misses, then following tried offline as a judge between
candidates, before any live tracker.

*The misses.* Of the 36 labelled tunes not named right over thirteen nights
(the drafts with the long settings left out, through the set's type and the
unsure runs merged), 17 had been shown by the meter. Most alike: the right
tune shown 16-32 s at 99-100%, the draft named for one shown longer at low
belief, often the same few (The Mason's Apron, Jenny's Welcome To Charlie,
The Spike Island Lasses, The Bucks Of Oranmore, The Burren); 5 of the 17 were
unsure runs merged under the wrong name; 2 never drafted; 3 drafted wrong
with confidence (Tuttle's for The Bunch Of Green Rushes at 98%, Tom Billy's
for Langstrom's Pony at 94%, The Boy In The Gap for The Piper On Horseback at
72%). The rest: a candidate never shown 11, never a candidate 8.

*The judge* (`drafts.judge_drafts`, `follow.span_fit`): each draft's stretch
is followed through every tune the listener showed or believed at 30%+ over
it (up to 5, the draft's own among them), all their settings, in the
session's key, entered and left anywhere; the draft takes the tune whose fit
beats its own by 20 (about 12 eighths matched). After the unsure runs are
merged, in the lab's drafting and in the find-tunes job. Thirteen nights:
13 drafts renamed; named right 882 -> 890 of 918 (fixed 9: Jim Keefe's, The
Sailor's Bonnet, The Porthole Of The Kelp, The New Custom House, The
Floating Crowbar, The Limerick Lasses, The Boys Of Malin, Sord Cholmcille,
The Piper On Horseback; broken 1: Mac's Fancy on 4, played away from its
settings' key, judged The Blarney Pilgrim; p 0.02); wrong or extra 42 -> 33.
Flat across its settings: any margin 0-40, judging all drafts or only those
under 85% or 50%, every variant names 890 (fixed 8-10, broken 0-2). About
90 s a night here (84 drafts on 140). Next: the key allowance in the judge
(Mac's Fancy), and the merged runs that cover two tunes (The Wild Irishman
and The Sailor's Bonnet on 140, one draft): following can split as well as
name. A live tracker (position, tempo, rounds as state) waits on these.

**"The tune may have changed" on the meter** (2026-10-08). The player wants
the meter, live, to go quickly from "I'm hearing X" to "the tune may have
changed, I'm listening for what it is". Measured on the saved states of the
thirteen labelled nights, at the changeovers inside sets where the old tune
was at 99% or more just before (477 to 505 of them by rule): today the meter
claims the old tune until 9 s after the new one's marked start (median; 90%
by 15 s) and names the new one at 11 s (22 s), and there is no state between
the two. The listener's belief in the old tune falls under 90% at 7 s, about
the step the meter lets go: most of the wait is the 6 s window and a step
every 4 s, not the meter holding on.

- *A state between.* The listener's state gains `changing`
  (`ChangeWatch`). First rule ("held"): shown at 99% for 40 s, then under
  95%. The meter stops claiming the old tune at 7 s (90% by 11 s); the new one
  is named when it was; "may have changed" inside tunes 3.4 times an hour.
- *The player's AND* (adopted, rule "rounds"): the tune has been at 99%, has
  gone round 1.8 times or more since it was shown (time over the beat the
  listener hears, times the tune's eighths per round, `form.RoundLengths`,
  the median over its settings), and its belief falls under 80%. 8 s (75% by
  10 s, 90% by 13 s), new tune named unchanged, 0.8 an hour inside tunes,
  against 3.4. Under 95% instead of 80%: 7 s (11 s), 2.3 an hour. How many
  times a tune went round (counted from its marked start): 3 times 354 of
  477, twice 35, 4 times 36, others 52; a rule wanting nearly 3 rounds (2.8)
  never fires on about 1 change in 9.
- *Following the held tune* (forward scores only, its settings plus a way
  out, the beat from the whole stretch, so a little flattered): the way out
  wins at a median 2.8 s (75% by 5.4 s, 90% by 13.5 s), never within 30 s on
  42 of 477, false alarms 6.1 an hour in the 45 s before a change. Fast when
  it locks on, but it misses about 1 in 10; with 1.8 rounds it is 3.0 s
  median, 90% by 15.5 s, 34 never, 2.1 an hour. Not adopted: it would need
  the follower live, and the rounds rule has a fifth of its false alarms.
- *A step every 2 s* (`Listener(hop_ms=2000)`, the decoder's lam and p_switch
  halved so a second counts the same; six nights): the old tune let go at 10
  s against 9, the new one named at 11 s against 12; with the rounds rule 9 s
  against 8, 1.5 an hour against 0.9. No gain for twice the compute; the
  step stays 4 s.

The meter shows it on the lab page and on the phone ("The tune may have
changed (was X). Listening for what it is…"), once the service runs this.

**Settings that match everything** (2026-10-08). The Mason's Apron was the
commonest wrong name over thirteen labelled nights (8 times, right once), and
two of its 35 settings on thesession.org are pages of variations, about 1,600
notes against a usual 120 (12549, 12550). The player asked for them to be
left out. Across the corpus, 13 settings are at least 800 notes and 6 times
their tune's median: The Mason's Apron (three), The Tarbolton and Bonnie Kate
(both wrong names over noodling on 136), Miss McLeod's, The Harvest Home,
Connie The Soldier and others. `corpus.exclusions` drops them from the n-gram
index and the aligner's sequences as those load (the built files and the
service's data stay as they are; `lab/configs/excluded_settings.json`, each
with its reason; `python -m lab exclusions` lists the rule's candidates).
Replayed on all thirteen nights (2.4 hours of audio among them had one of the
13 tunes as a candidate, so a targeted replay would have saved little), each
side through the same final steps: labelled tunes named right 882 and 882 of
918, none fixed or broken; wrong or extra tunes 39 -> 42; to check 64 -> 65.
The Mason's Apron as a wrong name straight from the listener 8 -> 3 (the
once it was played still right), but the stretches it took went to other
wrong names, and the set-type rule had already put most of it right
downstream: the long settings were where an unsure listener landed, not why
it was unsure. Kept, as the player asked and at no cost in names; not a
measured gain.

**An unsure tune takes its set's type** (2026-10-08). The player: use the
tune type, "in particular to heavily penalize the wrong type if confidence is
low". `drafts.prefer_set_type`, before the run-merging: a set's type is what
its confident tunes (85% and up) agree on; an unsure tune of another type is
renamed to the tune of the set's type the listener believed most over its
stretch (from the candidates it weighed); nothing to go by, or no candidate of
that type, and it stands. From the saved states, thirteen labelled nights: 6
renamed, every one wrong before; 3 right after (The Mason's Apron in a set of
reels as The Rolling Waves on 139 and as The Cock And The Hen on 140; Monaghan's
as Rip The Calico on 115), none right before made wrong. With the run-merging:
labelled tunes named right 883 -> 882 of 918 (merging alone 881), wrong or
extra tunes 55 -> 39, to check 84 -> 64. Adopted with it (blind drafting and
the server's job).

**Unsure runs as one tune** (2026-10-08). The player: "the 'makes a new
tune at each change' is super annoying to deal with after the fact. High
confidence should name as quick as it can, but anything 80% or below should
resist flip-flopping and should make its best guess over the entire span
rather than splitting it up." `drafts.consolidate_unsure`, after each tune's
confidence: in one set, a run of back-to-back unsure tunes (p_right under 85,
shown at 80% or under; under 2 s apart) has its short pieces (under 45 s)
absorbed into the long piece before them (or after, leading the run), and
takes the longest piece's name; two long unsure tunes side by side stay two (a
real changeover); a confident tune is never touched. From the saved states,
thirteen labelled nights: wrong or extra tunes 55 -> 40, tunes to check 84 ->
64, labelled tunes named right 883 -> 881 of 918 (fixed 0, lost 2, p 0.5: both
real tunes played once through, under 45 s, Jackson's on 112 and The Bunch Of
Green Rushes on 5). Merging every unsure run whole, named by the most belief
over it, lost 4 (two real tunes side by side merged, Michael Creamer's and The
Sailor's Bonnet, Liz Kelly's and Scarce O' Tatties); pieces under 30 s lost 1
but left 45 wrong. Adopted (blind drafting and the server's job): no names
gained, a quarter less to clean up, which is what the player asked for. The
pieces are often The Mason's Apron (three times on 139, once on 140, twice on
115), a tune the listener falls back on when unsure: to look at.

**Negative: a second opinion over whole stretches** (2026-10-08). After
drafting, look tunes up again over their stretch as the bench does (three
trackers, the whole corpus, the aligner on a 300-tune shortlist; at most the
middle 90 s, since whole sets at once took hours). A: each tune under 85%
renamed to the second opinion's choice, its neighbours' type preferred when
they agree. B: a run of back-to-back tunes in one set holding one under 85%
merged into one tune when the whole matched at least as well as its best
part. On the nights it was meant for and an easy one (112, 115, 132),
labelled tunes named right, against the drafts: A fixed 2 (Sord Cholmcille
on 132, one on 115) and broke 3 (two on 112, one on 115); B fixed none and
broke 8 (six on 112, two on 115), swallowing real tunes into their
neighbours and not repairing 115's Tuttle's, whose whole stretch did not
match Tuttle's better than its pieces matched their wrong names. Stopped
there: on the stretches the listener is unsure of, the bench's lookup is no
better a judge than the listener. Also neutral: confidence model version 2,
refitted with 132, 134 and 115 (1,735 tunes, 119 wrong), the same flags and
catches as version 1 on those nights (Brier 0.0507 against 0.0506 on 115);
version 1 kept.

**Night 115, the first found on the server, and a harder night** (2026-10-08).
The first "find the tunes" job in production (recording 115, 3 h 25 min,
2025-07-24): 84 min listening on Render (2.4x real time), 8 min following 40
sets, no pauses; 87 tunes logged, 18 flagged. Checked by the player: 78 of the
87 right; the 9 wrong all among the 18 flagged, but so were 9 right ones (The
Humours Of Whiskey at 6%, Wissahickon Drive at 4%), and one wrong was given
83% (The Sailor's Bonnet as The Mason's Apron, 90 s). Re-run locally the job
gives the same 87 and 18 exactly; the settings before the tiers give the same
78 and 9, so the tiers are not the cause, nor history (98% of the night's
tunes logged before it). The recording is harder to hear: inside labelled
tunes the listener's top tune was under 0.9 in 11.7% of steps, against 4.3%
on 112 (three weeks earlier) and 3.6% on 136; 3 dB quieter than 112, nothing
clipped. Six of the nine mistakes are one tune cut into pieces, each named
something else (Tuttle's as three tunes; Rip The Calico's last 30 s; 24 s
inside Wissahickon Drive; 5 s before Franc A'Phoill); three are whole tunes
misnamed (Mac's Fancy, played off its written key, as The Star Of Munster;
The Donegal Lancers as Jack Rowe; The Sailor's Bonnet). To do: refit the
confidence model (version 2) with 115, 134 and 132, the first harder night
among them; and the second opinion over a whole stretch of continuous music
(see "Still open"), which is what the cut-up tunes need.

**Following, profiled and made faster** (2026-10-07). Following set starts
(`follow_drafts`) is the slow part of drafting a night, and the part a server
would run with no caches. Profiled on night 134 with an empty transcription
cache and the models on the CPU: 9.5 s a set, of which Basic Pitch
re-transcribing the set 71% (its note-making alone 40%: the library's
"melodia trick" scanned the whole frames-by-pitches matrix for the loudest
energy left before every note it followed, 570,741 scans on six sets), the
Viterbi 17% and the tempo map 9%. Two exact changes: the melodia trick sorts
the candidates once (energy is only ever zeroed, so the loudest left is the
first not yet zeroed; the library's notes on random activations, tied ones
and five minutes of 112, 2.17 s -> 0.06 s), and the Viterbi's slot-by-slot
step is compiled with numba (the same path as the loop on 25 random sets).
Old against new on 134 and 132, each with an empty cache: every start the
same; 36 -> 19 s and 16 -> 9 s with warm models. What is left on 134: the tempo
map 12.5 s, the Viterbi 3.7 s, transcription (cached here; about 2.3 s a set
uncached). Not adopted: the tempo map reading one onset envelope for the whole
span instead of one per window (`pulse.SHARED_ONSET`, off), about 8 s a night
faster but starts within 1 s 600 -> 596 of 744 on ten nights (better 9, worse
13, p 0.52); no harm measured, no reason to take it. The larger lever, not
yet tried: reusing the listener's own transcription instead of transcribing
each set again.

**A second opinion over the whole tune** (2026-10-07, one case). Night 132,
checked by the player: 22 of 23 named right; the one wrong, drafted as
Cregg's Pipes (a reel) between two polkas at 3%, was Sord Cholmcille (8549,
23 tunebooks, never played at the session), played cleanly. The listener led
with it only for its last 16 s (0.98-1.00), after a minute of The Pigeon On
The Gate, Paudeen O'Rafferty and Cregg's Pipes, and drafting took the longest
run. Looked up over its whole stretch as the bench does (three trackers, the
whole corpus, the aligner on a 300-tune shortlist) it comes first, narrowly:
0.540 against a march's 0.532 over the labelled span, 0.545 against a polka's
0.525 over the drafted one; over its first 30 s it is 25th. To measure: a
second-opinion pass over each drafted tune's whole stretch, with the
neighbours' tune type as a preference (the player: "contiguous music between
two polkas, so it's very unlikely to be a reel"), wrong names fixed against
right ones broken on every labelled night.

**Night 134, logged by the listener and checked** (2026-10-07). A 1.9-hour
night never logged, never tuned on: the listener over its audio (merged
shortlists, the session's history before the night), drafted blind, applied
to the log with model 1's confidence, then checked by the player in the
segmenter. 43 of 44 named right; the one wrong, The Boy In The Gap for The
Piper On Horseback, was the only tune under 95% (72%). Starts within 3 s for
40 of the 44; four 13-22 s off (Music For A Found Harmonium +21.5 s; Cronin's
and Coleman's Cross +13 s, two of the three sets following could not read;
Moll Roe -12.8 s). The player's call from it: confidence shown in bands of 10,
a 99 as 100, and only the truly uncertain (shown at 80% or under) highlighted
and counted (spec 050, "A machine's guesses").

**A brand-new session, nine nights** (2026-10-07). The same nine nights
blind, as a session that has never logged a tune would get them (`lab drafts
--blind --new-session`): merged shortlists with popular tunes (>= 100
tunebooks, 2,320) in place of the session's own, and no session keys for
following. Against the same runs with the session's history before each
night, both drafted on today's code: named right 662 -> 654 of 689; wrong
or extra tunes 39 -> 58; tune by tune better 2, worse 19 (p 0.0002). The
losses split between the 31 labelled tunes under 100 tunebooks (better 0,
worse 9, p 0.004: Din Tarrant's, The New Leaf, The Star Of Ireland, Jim
Keefe's, Barbara Needham's, Pop Polka #2, The Ballinamore, The Bridge Of
Athlone, The Piper On Horseback) and popular tunes (better 2, worse 10, p
0.04). The popular ones are mostly confident confusions between look-alikes
that the session's history had settled: Larry Redican's Mother as The Whinny
Hills Of Leitrim (0.99, on two nights), Cooley's Delight as The Morning
Lark, O'Connell's Trip To Parliament and The Floating Crowbar as The Spike
Island Lasses, The New Custom House as The Broken Pledge. With 2,320 tunes
preferred, a tune's look-alike is preferred as much as it is. So a new
session works (95% of the labelled tunes are popular, and 654 of 689 named
right is usable), but the history is worth about 1% of names and a third of
the wrong ones. How fast a session earns it: of each night's tunes, the
session had logged 16% in its last night, 48% in its last 4, 62% in its last
8, 87% in its last 32 and 97% in all 200.

**A young session, and the production rule** (2026-10-07). The same nine
nights as a session that has logged only its last 8 nights (about 300 tunes),
three ways, against the full history (662 named right, 39 wrong or extra) and
a brand-new session (654, 58):

| the session knows | named right / 689 | wrong or extra |
|---|---|---|
| its full history | 662 | 39 |
| its last 8 nights, popular tunes a second tier (half the outside discount) | 659 | 48 |
| its last 8 nights + popular tunes as one tier | 654 | 58 |
| popular tunes only (brand new) | 654 | 58 |
| its last 8 nights only | 644 | 69 |

The tiered young session against a brand-new one: better 13, worse 6 (p 0.17),
against the full history better 7, worse 17 (p 0.06). One tier changes
nothing (a young session's tunes are nearly all popular already, and the
union is 2,341 tunes against 2,320); the history alone is worse than knowing
nothing, because it lacks the tunes it has not yet heard. So production's
rule is the tiers: the session's own tunes first, popular ones second (half
the discount of an outside tune), everything else last; a session with no
history has popular tunes as its own. What a player can be told, from this
one session: with no history about 95 in 100 tunes are named right; after
about eight nights logged a sixth fewer wrong names; with a long history a
third fewer. (`lab drafts --merged --history-nights K --popular tier`;
`--nu-partly` is untuned at 0.5.)

**Negative: tempo evidence step by step** (2026-10-05). Each 4 s step, each
candidate's aligner score less its type's cost for the beat over the last
12 s (analysis.tempo: up to 0.06, none under pulse strength 0.25; fitted
without the night's own labels; settings fixed before the run). Nine nights
blind, merged shortlists and key allowance, against the same without it: named
right 662 -> 663 of 689; gained Jim Keefe's (the polka read as The Mason's
Apron) and Da New Rigged Ship; no name lost, but four tunes still named came
out 30-60 s late (The Gold Ring 112, The Cook In The Kitchen 2, My Love Is In
America 4, Church Street 140; better 2, worse 4 by the start-and-name check,
p 0.69), and a wrong The Home Ruler appeared in The Gold Ring. The 12 s beat
window still holds the previous tune's beat at a changeover, so the new tune's
type is charged until it clears. Not adopted. The same evidence over a whole
blind tune, after the fact, has no changeover in it: next.

**Correction (2026-10-05): the tempo model had a bug, and the run above is
being repeated.** `fold` squeezed every eighth into 110-230 ms, so a polka at
250 ms was halved to 125 ms, a fast reel's speed: polkas measure 215-260 ms.
The "p10 124 ms" put down to the estimator doubling was this. Church Street,
one of the four late starts above, is a polka at about 251 ms. Repeated on the
fixed model: still 662 -> 663 named right, better 2, worse 3 (p 1). Church
Street is no longer late (that was the bug); The Gold Ring, The Cook In The
Kitchen and My Love Is In America still are, at changeovers. The negative
stands. Fixed: each type is fitted and
compared at the octave nearest its own speed, starting from the estimator's
raw periods (`near`); refitted on ten nights, reel 153 ms, jig 166, polka 222,
slide 148, slip jig 173, hornpipe 181.

**Negative: a whole-tune type check** (2026-10-05, the fixed model). Each blind
tune's beat over 30 s from 10 s in; a tune whose type is more than 6 log-
likelihood units below the best for that beat swapped for the listener's
strongest candidate over its stretch whose type is within 2 (thresholds fixed
before the run; each night's model fitted without its own labels). Offline, on
the merged nine-night runs: named right 662 -> 652 of 689; better 1 (Jim
Keefe's), worse 11 (p 0.006). The estimator misreads single tunes more often
than the listener names a wrong type: polkas measured at reel speed (Farewell
To Whiskey, The Dark Girl Dressed In Blue, about 150 ms), slides in twos
(Bedford Cross, The Road To Lisdoonvarna), jigs in twos at 255 ms (The Black
Rogue twice). Wrong-type names are 1 or 2 a night; misread beats are more, so
a veto by the beat fires on good names more than bad. Not adopted.

**Tempo and beat grouping by tune type** (2026-10-05). Night 1 with merged
shortlists named Jim Keefe's, a polka, as The Mason's Apron, a reel; the
player's suggestion: track a tune's usual tempo at the session and use it.
Each labelled segment over ten nights (1-5, 138-140, 143, 112), 30 s from 10 s
in, the beat estimator's eighth note folded into 110-230 ms:

| type | n | eighth, median (p10-p90) | in twos / threes |
|---|---|---|---|
| reel | 387 | 153 ms (144-168) | 382 / 5 |
| jig | 252 | 166 ms (157-179) | 16 / 236 |
| polka | 33 | 215 ms (p10 124, p90 223: wrong, see the correction below; refitted, 222 ms) | 33 / 0 |
| slide | 29 | 152 ms (133-207) | 8 / 21 |
| slip jig | 28 | 172 ms (158-192) | 3 / 25 |
| hornpipe | 21 | 176 ms (122-201) | 13 / 8 |

Twos against threes separates reels from jigs almost perfectly (the beat check
The Bucks Of Oranmore, a reel inside The Gold Ring, needed); speed separates
polkas from reels (Jim Keefe's measured 221 and 206 ms, The Mason's Apron 150
and 167). A tune holds its speed at this session: over the 87 tunes played
three or more times, the median spread across nights is 11%. Hornpipes split
on grouping (their swing) and slides vary, so this is a likelihood, not a
rule. To build: each candidate's likelihood of the measured speed and grouping
given its type, and given its own usual speed where the session has played it,
as evidence in the decoder beside the aligner; for a session with no history
the type-typical speeds stand in (this session's, until there are others).

### Still open

**As of 2026-10-01.** Items 1 to 3 below are done (item 2 became night 137,
segmented blind; item 3 the follower). Open, in rough order:
- **(2026-10-04) In progress:** the key allowance in the listener (Mac's
  Fancy, played in D against settings all in A); the repertoire index rebuilt
  when the repertoire grows (7 of 1,287 tunes were missing from it, among them
  The Duke Of Leinster, which recording 112 could therefore never name; the
  live service's data too), and `lab drafts` warning when the index lacks
  tunes of the recording's repertoire; a beat check against a short run of one
  tune type wedged between tunes of another (The Bucks Of Oranmore, a reel,
  for the first minute of The Gold Ring on 112).
- **(2026-10-04) Production: one corpus for every session.** Detection will
  run in production for many sessions, most of which have never logged a
  tune. The lab's repertoire index is a hard filter (and goes stale: 7 tunes
  missing, The Duke Of Leinster among them); production wants the reverse, one
  whole-corpus index shared by every session, with the session's history
  (repertoire, play counts, sets, keys) as a preference that raises a tune's
  odds, and thesession.org tunebook counts doing that job when there is no
  history. Rebuilding a per-session index is dropped as a stopgap. The test is
  the one below: our nights with the repertoire hidden, against weighted; the
  target is a brand-new session nearly as good, and ours no worse.
- **(2026-10-04) Live latency and more than one night at once.** The service
  takes 2.0-3.2 s of compute a 4 s step on Render Pro, about three quarters
  of a core for one stream (spike, 2026-10-01), so a second night streaming at
  the same time would push both behind real time, the lag growing through the
  night (nothing is lost: the phone keeps the recording and the service skips
  after a long gap). Profile where the step goes first. Candidates: the three
  trackers (Basic Pitch and PESTO are networks on the CPU), re-transcribing the
  overlapping window each step instead of only the new audio, fewer trackers
  live, batching across streams, the aligner and the key allowance (+20%);
  then the shape: transcription on the phone (Basic Pitch runs under Core ML)
  sending notes rather than audio, or one stream per instance, scaled with the
  sessions.
- **(2026-10-06) Profiling the live step, first results.** On 4 minutes of
  recording 112, Basic Pitch's on-disk cache bypassed (replays hit it; live
  audio never does), a step takes 283 ms on the laptop as a Mac runs it (PESTO
  on the GPU, Basic Pitch on Core ML) and 404 ms as the server runs it
  (LAB_DEVICE=cpu: both on the CPU, Basic Pitch on ONNX). On the CPU: PESTO 192
  ms (48%), Basic Pitch 59, the notes rebuilt from the last 24 s 53, the
  shortlist lookups 39, yin 26, the aligner 24, the beat and music-detector
  features 9, the decoder nothing. The beat estimate and attack times over the
  24 s span were worked out once per regridding tracker on the same audio; now
  once a step (76 -> 49 ms, 30 steps checked identical). The trackers without
  PESTO, on the bench (607 segments, repertoire, 30 s): yin + Basic Pitch 0.937
  against all three's 0.942, better 3, worse 6 (p 0.51; jigs 0.975 -> 0.961);
  Basic Pitch + PESTO 0.934, yin + PESTO 0.928, Basic Pitch alone 0.916. So
  PESTO is half a CPU step for half a point. Render took 2.0-3.2 s a step, 5-8
  times the laptop's CPU figure; the service set no thread limits, and in a
  container the libraries see the host's cores, so it now holds them to the
  container's budget (lab/tools/threads.py), logs it, and each step reports its
  time by part. What Render does is known only once that is deployed.
- **(2026-10-06) The live step on Render, measured.** Render's container sees
  8 host cores (and CPU affinity of 8) but has a 2-CPU quota, and it ran the
  service as two uvicorn workers (WEB_CONCURRENCY). The libraries are now held
  to 2 threads and the service runs one worker (WEB_CONCURRENCY=1; two workers
  doubled the models in memory, shared the 2 CPUs, and once raced each other
  fetching the data, failing a deploy). A 4-minute real-time stream of 112,
  one worker: a step a median 1,480 ms (was 2.0-3.2 s), states a median 2.0 s
  after their audio, peak memory 1.8 GB. By part: PESTO 520 ms (35%), the
  shortlist and aligner 223, the attack scan over the last 24 s 178, Basic
  Pitch 122, PESTO's notes 116, the beat estimate over 24 s 91, the beat and
  music-detector features 86, yin and its notes about 85. Render runs this code
  4-6 times slower than the laptop. Levers: without PESTO live, about -640 ms
  (bench 0.942 -> 0.937, better 3 worse 6, p 0.51); the attack scan and beat
  estimate worked out on the new 4 s only, not the last 24 s again, about -250
  ms and no change in results. Together about 0.6 s a step, some 15% of a CPU a
  night, so 4-5 nights at once on this plan.
- **(2026-10-06) Listening on the phone: the plan, and the first checks.** The
  player's direction for scaling: push to the phone what can go there, rather
  than drop a tracker live. The split: the phone runs the three trackers, turns
  pitch into notes, and works out the beat and the music-detector features,
  sending a few kilobytes of notes and features each 4 s instead of 88 KB/s of
  audio (the phone records the full audio for upload anyway; the stream was
  only for the meter). The server keeps the shortlist over the whole corpus,
  the aligner and the decoder, about 250 ms a step on Render with no audio work,
  and the corpus (over a gigabyte) never goes to the phone. Checks so far:
  - **PESTO converts to Core ML** (`python -m lab coreml`): its constant-Q
    spectrum rebuilt on magnitudes (Core ML has no complex numbers), the
    network as is, the roll and reduction to pitch outside the model. On 6 s of
    112, every one of 599 frames within 0.000 semitones of PyTorch; 32 ms per
    6 s on a Mac's Neural Engine/GPU, 66 ms Core ML on its CPU, 177 ms PyTorch
    on its CPU (Render runs 520 ms a step).
  - **Basic Pitch's own Core ML model** gives the same activations as the ONNX
    model the server runs, to the last digit (30 s of 112, all 151 notes the
    same), so the lab's Mac numbers and the server's agree too; 145 ms per 30
    s Core ML, 198 ms ONNX, on the Mac.
  - **To port to Swift**: yin, pitch to notes, the beat and attack estimates,
    the key filter, grid snapping, the music-detector features, about 1,000
    lines of Python, leaning on five librosa functions (yin, RMS, STFT, onset
    strength, onset detection) that Accelerate covers. Floating point will not
    match Python bit for bit, so agreement is to be checked against fixtures
    the lab writes (audio in, notes out), with a tolerance.
  - Still to measure: the phone's own speed, battery and heat over three hours,
    from the app. Next: the notes-in wire for the service, and the fixtures.
- **(2026-10-04) Loudness, relative to the night.** Absolute loudness was taken
  out of tune-ness after a test of laptop speakers recorded through a phone,
  which says nothing about a phone on a pub table (the player's correction).
  Level relative to the night's running median and its quietest moments is
  still to test, for tune-ness and set ends; it won't rescue quiet music under
  loud talk (The Sailor On The Rock).
- **(2026-10-04) Sessions without years of logs.** This session's repertoire
  is the player's years of logging; another session's is thin, and the whole
  corpus is the candidate set. Not every tune is equally likely there:
  thesession.org's tunebook count is a rough, decent proxy for popularity, with
  a long tail of obscure or made-up tunes to penalise or search in a second
  tier (the session's own repertoire stays a tier of its own, so a tail tune it
  plays, Luke Skywalker Walks On Sunshine, is still found). Testable here by
  hiding the repertoire: names right with the repertoire, with the whole corpus
  and no prior, and with tunebook tiers, the threshold and penalty swept on
  the labels. It will flatter a session that plays many obscure tunes.
- **A second opinion over the whole tune** (tried 2026-10-08: negative, see
  "Negative: a second opinion over whole stretches"; what was planned:) After drafting, look each drafted tune up again over
  its whole stretch (three trackers, the whole corpus, the aligner on a
  300-tune shortlist, as the bench does), with the neighbouring tunes' type as
  a preference ("contiguous music between two polkas is very unlikely to be a
  reel"), and change the name only where the second opinion disagrees
  clearly. One case so far (night 132, Sord Cholmcille: first by 0.540 to
  0.532 over its labelled span, 25th over its first 30 s). Measure on every
  labelled night (nine, 136, 134, 132): names fixed against names broken. The
  second opinion agreeing or not is also a candidate feature for the
  confidence model (version 2, refitted with 132 and 134).
- **Too short to be a tune:** a minimum duration before a detection counts,
  the player's rule for melodic noodling, which tune-ness leaves at 50-70%
  of its chunks.
- **Hub tunes properly:** cluster each tune's settings and score the main
  version, in place of the blunt per-setting charge.
- **Walking starts back:** once a tune is named, find where it began (starts
  are a median 9 s late on night 137); it matters for auto-segmenting
  recordings, not for the live display.
- **The aligner's cost model** (item 4 below) for the near misses.
- **Tune-ness on the board:** the follower reads notes, not pitch tracks, so
  it does not yet compute it; `lab listen` does.
- **A night from the app's recorder,** labelled, as the next held-out test.

**The plan, as of 2026-09-29**, merged with `053 files/raising-accuracy.md`
(which holds the field survey, the miss analysis and the ten angles in
detail), in order:

1. **Finish measuring the aligner.** (The full corpus is done: 0.932 at 30 s,
   above.) Shortlist recall, which is now the ceiling on both candidate
   sets. A sloppy start: windows beginning up to 20 s before the labelled start, so
   the query opens on the previous tune or the chat, to size how much of the
   gain survives not being handed the boundary (done: within 5 s keeps nearly
   everything). Retune set decoding for the aligner's scores (done: harmless at
   beta 0.01, worth nothing measurable). The player's (measured at 30 s:
   +2/-0 at cost 0.02, 1.2% of tunes played away from every setting's key) key allowance: a tune may be played in
   another key than its settings, tried outward round the circle of fifths
   (the written key, then one fifth either way, then two, and never further;
   a G tune is played in D or A, not A-flat), each step costing a little, so
   the written key stays the strong default and a wrong tune does not get
   twelve chances at a lucky match. Its runs also say how often this session
   plays a tune in another key than every setting.
   *Corpus re-pulled 2026-09-29 (afternoon):* the player finished labelling
   recording 140 (instance 499, 2026-09-17), which had 25 scored segments and
   now has 86, and night 138 went from 37 to 62: 588 scored segments. The
   same pull fetched a newer thesession.org dump (23,317 tunes, was 23,307);
   indexes and aligner sequences are still built from the old one. Every
   item-1 number is on the original 502 segment ids.
2. **A night none of this was tuned on.** The player is labelling a recent
   night. Replay it raw on the board (the board never reads the labels; they
   only score it afterwards), with today's baseline, the three-tracker fusion
   and the aligner on the board, and give the player the timeline to read
   against what was played; the bench on its labelled segments beside it.
3. **The aligner on the board: is this still the same tune?** Done
   2026-09-30: the follower, 0.908 right at the end and 84.5% within 30 s
   over eight nights against fuse3's 0.815 and 14.3% (see "The follower").
   Left: tunes new to the session (a full-corpus fallback when nothing
   scores well), the false starts on a night never heard (the player's
   ground truth), and a display for players on top. The player's
   framing (2026-09-29): live, one tune simply becomes another without
   warning, so for every incoming chunk of notes the logger asks whether it
   agrees with the tune it already believes, or whether a new tune has
   begun. Answered well, the late start of item 1's offset test never
   happens.
   - **Agreement, per chunk.** The aligner already scores each chunk
     (32 eighths or 24 pitch changes) on its own. While the tune continues,
     each new chunk matches the current tune; after a change, chunks stop
     matching it and start matching something else. That drop is the
     evidence, and it is cheap to watch continuously.
   - **Where in the tune we are.** A matched chunk also says where in the
     tune it matched, so the logger can follow the part it is in, see the end
     of the last part, and count passes.
   - **Hints that make a change more likely at a given moment**, from the
     player: the tune has been played through three times already; the last
     chunk was in its final part; it has gone on about as long as it usually
     does. Durations and passes per tune come from the labelled nights at
     this session. The hints lower how much disagreement it takes to call a
     change; they do not call one on their own, because a tune played twice
     instead of three times must still be caught on the audio.
   - **Which tune follows**, at the moment of change, is the set-decoding
     prior (item 1's retuning), and a tune played in another key must not
     read as a change (item 1's key allowance).
   - **Measured on the bench first**: stream each labelled set through chunk
     by chunk and score how many seconds after the real change it is noticed,
     changes called that did not happen (a variation, a badly heard part), and
     changes missed; with and without each hint, paired. Then on the board,
     with the display's hold and short list re-measured on top.
   - **Night 140's hard cases, from the player**: false starts that never
     became tunes (a few chunks of a new tune, then nothing: not a tune);
     The Old Copperplate and The New Copperplate, which are close enough
     that the new tune's chunks half-match the old; and a set that goes from
     jigs to reels (the rhythm changing is an extra signal).
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

> Pre-spec implementation plan for the Ceol Listen lab steel thread. Written 2026-09-21 after the design conversation in [053 files/design-conversation.md](053%20files/design-conversation.md); revised 2026-09-22 to add the task bench, boundary detection, and the chunk/window split. Step 1 of the plan rewrites this file into the spec proper.

# Ceol Listen — lab steel thread (spec 053)

## Context

Ceol Listen is a new subproject: recognise which tune is playing in a recording of a session, built as an ensemble of small "experts" writing to a shared blackboard, with a replay harness that scores runs against the human-segmented eval set from spec 050. The conversation settled the milieu (board, typed observations, provenance, runs, VoI scheduling, hypothesis lifecycle, lab/runtime split, eval-first corpus). This plan builds the **steel thread**: the simplest set of components that exercises every one of those concepts end to end against the real eval set. It is not expected to be accurate. It is expected to be runnable, inspectable per component, and to make the next improvement measurable.

Two loops, not one. The **ensemble loop** (board, experts, runs, eval) is slow and answers "is the whole system better". The **bench loop** answers "does this idea have any promise" for one narrowly defined task, over cached features, in seconds. Candidates that score on the bench graduate into experts. Nothing gets into the ensemble because it seemed reasonable.

Decisions already made by the user: corpus = public thesession.org dump; code = `lab/` package in this repo; board store = SQLite under `lab/data/`; prod DB read-only queries and local AWS creds are available; boundary detection is not assumed to come from energy, it comes off the bench.

Prod eval set today (queried): 8 segmented recordings (ids 1, 2, 3, 4, 5, 138, 139, 140), 455 segments, 274 distinct tunes (all have ABC), 15.6 labelled hours, median segment 110 s, one trailing implicit end of 5,475 s. Session 1 repertoire: 1,279 `session_tune` rows. Masters are mp3 44.1k stereo, 350–430 MB each (two are m4a). Disk: 237 GB free.

## Design decisions

- **Runs are the unit of provenance.** A run = named config applied to one recording over a time range/segment set. Every observation and hypothesis event is keyed by run, carries expert name + version + params + input observation ids + the audio window actually read + wall-clock cost. `lab run --from RUN_ID` re-executes a stored config verbatim.
- **DAG over observation types, not experts.** Experts declare `consumes`/`produces` types. Several experts may produce the same type. Driver is reactive: after each arrival chunk, any expert whose consumed types got new observations runs, at most once per chunk (bounds feedback loops, which are allowed by construction).
- **Arrival chunks and analysis windows are different things.** Arrival chunks are how audio lands on the board and what advances the virtual clock; live, they are the upload granularity and a hard floor on latency. Analysis windows are what each expert reads: each declares its own window length and hop on a fixed grid, reads any range of audio up to the clock, and stamps the window it used. A pitch tracker reads 10 s on a 2 s hop; a boundary detector reads 30 s either side; a matcher reads the last 48 notes regardless of time. Both chunk length and window params are run-config variables meant to be swept.
- **Task bench before ensemble.** A task is a named target plus a scorer, cut from the same eight nights. A candidate is any function from cached features over a window to a prediction, rule-based or learned. All candidates are scored with leave-one-night-out splits because nights share room and players. A candidate graduates into an expert by wrapping; its bench score is recorded as the reason it is there.
- **Boundaries are first-class evidence.** Two distinct problems the ground truth separates: music versus not (gaps between sets) and tune changes inside a set (no silence at all). The assembler expects its confident tune to stop: it opens a new span on a `boundary` observation and carries a duration prior (median segment 110 s, three times through AABB, expected length by tune type).
- **Two producers of one type from day one** (`pitch_pyin`, `pitch_yin`) so disagreement is visible in the board dump. No neural transcriber in the steel thread; it plugs in later as one more producer of `note_events`.
- **Logged order is ground truth, never evidence.** The manifest stores the night's logged tune order, but the repertoire prior only uses `session_tune` and tunes *confirmed on the board*. A future "oracle-previous-tune" expert can simulate human confirmation of earlier segments without leaking the current one.
- **Implicit ends are not music/no-music ground truth.** `end_ms NULL` means "until the next segment starts", so an implicit end at the close of a set absorbs the chatter after it. Inside a set they are accurate tune boundaries. Music-activity labels use only explicit ends; the region after an implicit end is excluded from that task.
- **Slice lazily.** No per-segment clips. One derived `mono22k.wav` per recording (exact seeks, hashable). ~475 MB per 3 h night, ~3.8 GB total.
- **Feature and transcription caches.** Bench features (mel, chroma, RMS, onset strength on a 100 ms grid) are computed once per recording. Expert outputs are cached on `(expert, version, params, audio sha1, window)` so downstream experiments never re-run pyin.
- **Eval = user-facing metrics with uncertainty**: identification (time-to-first-correct, time-to-stable-correct, top-1/top-5, flips, calibration, cost per audio minute) and segmentation (boundary recall/precision at a tolerance, false boundaries per hour, music-activity frame accuracy). Wilson CIs on proportions because 455 segments is small.
- **One venv.** `venv/bin/pip install -r lab/requirements.txt`. Render only installs root `requirements.txt`, so lab deps never deploy. Lab is excluded from root pytest collection and coverage, but `make lint` still covers it.
- **Branch**: `053-ceol-listen-lab` off current `production` (the user works on `production`; master is 51 behind).

## Layout

```
lab/
  README.md, requirements.txt (numpy scipy librosa>=0.10 soundfile scikit-learn), pytest.ini (own; no --cov)
  __main__.py, cli.py         `venv/bin/python -m lab <cmd>`: pull prepare index bench run eval diff runs board transcribe timeline
  env.py, paths.py            load_dotenv + sys.path repo root (jobs/ pattern); lab/data path helpers
  configs/                    null.json, baseline.json, no-prior.json
  audio/chunks.py             ChunkSource protocol, Chunk, WavChunkSource(start,end,chunk_ms); virtual clock; AudioStore.read(t0,t1)
  audio/prepare.py            master -> mono22k.wav + sha1 (ffmpeg pipe pattern from recording.compute_peaks)
  corpus/pull.py              prod -> lab/data: manifests, masters (resumable), tunes.csv
  corpus/tunes_csv.py         stream tunes.csv -> Setting(tune_id, setting_id, name, type, mode, abc)
  corpus/abc_pitch.py         ABC -> [(midi, eighths)]; K:/mode -> key sig; accidentals persist to bar; ornaments/chords/grace stripped
  corpus/index.py             interval 5-gram inverted index, candidate sets (all | repertoire | eval_tunes), pickle + meta.json
  bench/features.py           per-recording feature cache on a 100 ms grid: mel(64), chroma(12), rms_db, onset_strength -> features.npz
  bench/tasks.py              Task protocol + labels from manifests: music_activity, boundary (later: tune_pair)
  bench/candidates/           one file per idea; Candidate protocol: name, version, params, needs (feature names), predict(features, t_grid) -> scores
  bench/score.py              leave-one-night-out driver, task scorers, bench_result rows, leaderboard
  board/schema.sql, board.py, types.py   SQLite DDL; Board (append/query/hypothesis writes); BoardView (read-only per expert)
  experts/base.py             Expert protocol, WindowSpec, Window, Observation, cache helper, CandidateExpert (wraps a bench candidate)
  experts/{music_energy,boundary_novelty,pitch_pyin,pitch_yin,notes,intervals,matcher,prior,assembler}.py
  engine/registry.py, scheduler.py, run.py   name->class; reactive loop + window grid + VoI hook; run lifecycle + re-execution
  eval/ground_truth.py, metrics.py, segmentation.py, report.py
  inspect/dump.py, abcish.py
  tests/                      pure-python unit tests: abc parser, index self-lookup, chunk source + window grid, metrics, scheduler, task labels
  data/  (gitignored)         recordings/<id>/{manifest.json,master.*,mono22k.wav,mono22k.sha1,features.npz}, corpus/tunes.csv, index/*.pkl, board.sqlite, bench/<task>/<candidate>-<version>.json, runs/<run_id>/{config.json,eval.json,eval.md}
```

## Reused code

- `recording.py`: `get_s3_client()` :100, `get_s3_bucket()` :110, `check_configured()` :128, `download_recording()` :234 (pattern; we add `.part` + rename), `_ffmpeg_exe()` :67, `probe_audio()` :410, the streaming s16le decode in `compute_peaks()` :486.
- `services/tune_merge_scan_service.py`: `DUMP_TUNES_URL` :53, `USER_AGENT` :50, `_open_dump()` :249, csv parsing in `_fetch_dump()` :274.
- `scripts/import_recording.py` :142–151: the `--database-url` guard (refuse empty string; print target DB).
- `recording_routes.py` :1282–1291: the resolved-view export query, reused verbatim in `pull.py`.
- `database.py` :66 `TUNE_TYPE_BEATS`, :85 `count_eighth_notes_in_bar` as the reference for duration tokenising.

## Task bench (`lab bench ...`)

**Features** (`lab bench features --recordings N`): one `features.npz` per recording on a 100 ms grid: `mel` (64 bands, dB), `chroma` (12), `rms_db`, `onset_strength`, plus `t_ms`. Keyed by the wav sha1 and a features version. Everything a candidate reads comes from here; a candidate that needs a new feature adds it to `features.py` with a version bump.

**Tasks** (`bench/tasks.py`), labels cut from manifests:

| Task | Target per grid point | Label source | Scorer |
|---|---|---|---|
| `music_activity` | 1 if a tune is playing | inside any segment = 1; from an explicit end to the next start = 0; from an implicit end to the next start = excluded; before first start / after last explicit end = 0 | frame accuracy, precision/recall, per night |
| `boundary` | boundary within ±`tol` (default 3 s) of this point | every segment start; every explicit end; not implicit ends (they equal the next start) | recall and precision at tolerance, false boundaries per hour, and a peak-picking threshold sweep (PR curve) |
| `tune_pair` (later) | which of two confusable tunes | segments of tunes sharing many 5-grams | accuracy |

**Candidates** (`bench/candidates/*.py`): `name`, `version`, `params`, `needs: tuple[feature, ...]`, `predict(features, t_ms) -> np.ndarray` of scores on the grid; learned candidates also implement `fit(features_by_night, labels_by_night)`. First batch, deliberately mixed so the bench shows its range:

- `music_energy`: `rms_db` above a running floor and `onset_strength` above a threshold. The baseline expected to be beaten.
- `music_mel_lr`: logistic regression on mel frames with ±1 s context. First learned candidate.
- `boundary_novelty`: Foote novelty on a chroma self-similarity matrix, kernel 16–32 s. The classic intra-set cue.
- `boundary_keychange`: chroma histogram over the trailing 30 s versus the leading 30 s, cosine distance.
- `boundary_mel_lr`: logistic regression on mel deltas around the point, trained on ±3 s positives.
- Placeholders declared but not built now: `boundary_embedding` (probe on a pretrained audio embedding), `boundary_transcription` (matcher stopped matching), `music_embedding`.

**Scoring** (`lab bench run --task boundary --candidate boundary_novelty [--params k=v]`): leave-one-night-out over the prepared recordings; learned candidates fit on seven nights and predict the eighth; rule candidates just predict. Writes `bench/<task>/<candidate>-<version>.json` and a `bench_result` row (task, candidate, version, params, features_version, per-night and pooled metrics, git sha, created_at). `lab bench leaderboard --task boundary` prints candidates ranked with per-night spread. `lab bench plot` is deliberately absent; the JSON is enough for now.

**Graduation**: `experts/base.py` has `CandidateExpert`, which wraps a bench candidate as an expert producing `music_activity` or `boundary` from the same features computed live over its declared window. The expert's `params` record the bench result id. The steel thread graduates `music_energy` and `boundary_novelty` immediately so the ensemble has one producer of each type; the bench is where their replacements come from.

## Board schema (SQLite, `lab/data/board.sqlite`)

- `run(run_id PK, name, recording_id, config_json, git_sha, created_at, finished_at, status running|done|failed|scratch, audio_ms, wall_ms, parent_run_id)`
- `observation(obs_id PK autoinc, run_id, type, t_start_ms, t_end_ms, clock_ms, expert, expert_version, params_json, inputs_json, payload_json, cost_ms, cached)` + index `(run_id, type, t_start_ms)`. `t_start_ms/t_end_ms` is the window the expert actually read.
- `hypothesis(hyp_id PK, run_id, t_start_ms, t_end_ms NULL while open, status proposed|superseded|withdrawn|confirmed, opened_clock_ms, closed_clock_ms, superseded_by, opened_by boundary|first_match|rival)`
- `hypothesis_event(event_id PK, run_id, hyp_id, clock_ms, event proposed|updated|superseded|withdrawn|confirmed, ranked_json top-10 [{tune_id, setting_id, conf, evidence}], top1_tune_id, top1_conf, obs_id -> the hypothesis_update observation)`
- `eval_segment(run_id, recording_id, segment_id, gt_tune_id, seg_start_ms, seg_end_ms, capped, evaluated, ttfc_ms, ttsc_ms, top1_end, top5_end, flips, end_conf, cost_ms, detail_json, PK(run_id, segment_id))`
- `eval_boundary(run_id, recording_id, gt_t_ms, kind start|explicit_end, matched_t_ms NULL, error_ms NULL, PK(run_id, recording_id, gt_t_ms))` plus false positives stored in `run`-level eval JSON
- `bench_result(result_id PK, task, candidate, version, params_json, features_version, split, metrics_json, git_sha, created_at)`
- `expert_cache(cache_key PK = sha1(expert|version|params|audio_sha1|t_start|t_end), expert, expert_version, payload_json, cost_ms, created_at)`

Audio samples never go in SQLite: `audio_chunk` payload is `{sha1, sr, n_samples}` and the BoardView's `AudioStore` serves any `(t0, t1)` up to the clock from the wav.

Observation types: `audio_chunk`, `music_activity`, `boundary`, `pitch_track`, `note_events`, `interval_sequence`, `tune_match`, `tune_prior`, `hypothesis_update`, `scheduler_skip`.

## Expert interface and driver

```python
@dataclass(frozen=True)
class WindowSpec: length_ms: int; hop_ms: int; lookahead_ms: int = 0   # grid-aligned; lookahead delays emission

class Expert(Protocol):
    name: str; version: str; consumes: tuple[str, ...]; produces: tuple[str, ...]
    cost: float            # relative, per second of audio (1 trivial … 10 pyin)
    params: dict           # from run config; stamped on every observation
    window: WindowSpec | None   # None = event-driven (runs on new upstream observations, reads what it needs)
    def process(self, view: BoardView, window: Window) -> list[Observation]: ...
```

BoardView: `audio(t0, t1)` (any range up to the clock), `new(type)` (since this expert last ran), `query(type, t0, t1)`, `latest(type)`, `manifest`, `config`, `open_hypothesis()`, `confirmed_tune_ids()`, `audio_sha1`, `cached(expert, window, fn)`.

Driver (`engine/scheduler.py`): experts ordered by topological sort over types (cycles tolerated, ties by config order). Per arrival chunk: append `audio_chunk`, clock = chunk end. Windowed experts run once for every grid window whose `t_end + lookahead <= clock` that they have not yet produced. Event-driven experts run when `consumes ∩ dirty` is non-empty. Each expert runs at most once per chunk; `Scheduler.should_run` may skip it, logging a `scheduler_skip` observation with the reason. Newly produced types become the next `dirty`; the loop ends when nothing new lands.

VoI hook: `should_run(expert, view, window) -> Decision(run, reason)`. Config `"scheduler": {"rule": "skip_expensive_when_confident", "cost_threshold": 5, "conf_threshold": 0.9, "min_evidence_s": 20}` or `{"rule": "always"}`. A `boundary` observation resets the skip (confidence is no longer about the current span).

Run config (`lab/configs/baseline.json`): `name, chunk_ms (arrival), sr, candidate_set, experts:[{name, params, window}], scheduler`. CLI adds `--recording`, `--segments 5-6` or `--range mm:ss-mm:ss`; the selection is written into `config_json` so `--from` is exact. Sweeps are just several configs; `lab diff` compares them.

## Steel-thread experts (dependency order)

| Expert | consumes → produces | Window | Algorithm | Known weakness (what to look at) |
|---|---|---|---|---|
| chunk source | — → `audio_chunk` | arrival `chunk_ms` (2 s default) | `WavChunkSource`; clock = chunk end | arrival chunk = latency floor |
| `music_energy` (cost 1, graduated baseline) | audio_chunk → `music_activity {score, is_music}` | 3 s / 1 s | bench candidate over live features | loud talk passes; quiet airs fail; expected to be replaced off the bench |
| `boundary_novelty` (cost 2, graduated baseline) | audio_chunk → `boundary {t_ms, strength, kind}` | 60 s / 2 s, lookahead 15 s | Foote novelty on chroma SSM; emits when a peak clears threshold | needs 15 s of lookahead so it is late by design; misses same-key same-tempo changes |
| `pitch_pyin` (cost 10) | audio_chunk → `pitch_track {source, hop, times_ms[], f0_hz[], voiced_prob[]}` | 10 s / 2 s | `librosa.pyin(fmin=130, fmax=1400, sr=22050, frame_length=2048, hop=256)`, cached; only the newest 2 s is emitted | heterophony: locks onto loudest instrument/harmonic; octave errors on rolls |
| `pitch_yin` (cost 1) | audio_chunk → `pitch_track` | 10 s / 2 s | `librosa.yin`, voiced from aperiodicity threshold | no voicing model; hallucinates through chatter |
| `notes` | pitch_track → `note_events {source, notes:[{t0_ms,t1_ms,midi,conf}]}` | event-driven | median-filter f0, hz→midi, round, drop voiced<0.5, RLE, keep ≥60 ms; one output per configured source | cuts/rolls fragment notes; repeated same pitch fuses |
| `intervals` | note_events → `interval_sequence {source, intervals[], note_t0_ms[], n_notes}` | event-driven | semitone diffs, clip ±12, last 48 notes | one dropped note shifts one interval |
| `matcher` | interval_sequence → `tune_match {source, candidates:[{tune_id, setting_id, score, hits, n_grams_queried}]}` | event-driven | 5-gram lookups in inverted index, vote per tune (best setting), `score = hits/n_queried × mean idf`, top 20 | 5-gram collisions on scale runs; no rhythm/tempo |
| `prior` | music_activity, hypothesis_update → `tune_prior {weights:{tune_id:w}, default_w, basis}` | event-driven | `repertoire_weight` (20) for session_tune ids, ×`played_tonight_weight` (0.2) for board-confirmed tunes | near-tautological on this eval set (all 274 GT tunes in repertoire) |
| `assembler` | tune_match, tune_prior, music_activity, boundary → `hypothesis_update` + hypothesis rows | event-driven | accumulate `E[tune]=Σscore` since span opened; `p ∝ exp(E/T)·prior_w` over candidates + `__other__` mass; `T = base/(1+evidence_s/30)`; **change hazard** grows with elapsed span time against the expected length for the top-1's tune type; lifecycle: first match → `proposed`; each chunk → `updated`; `boundary` → close current (`confirmed` if conf ≥ 0.9 else `withdrawn`), open new span `opened_by=boundary`; top-1 change → old `superseded`, new `proposed`; ≥4 s non-music → close | hand-set `__other__`, T schedule and hazard; a late boundary (lookahead) means the new span opens after the tune already changed, so identification restarts late |

## Corpus pull (`lab pull --database-url "$PROD_URL" [--recordings 1,2] [--skip-audio] [--refresh-corpus]`)

Connect with `options="-c default_transaction_read_only=on -c timezone=utc"`. Default set = recordings with ≥1 resolved segment. Per recording write `manifest.json`: recording row (id, session_instance_id, label, storage_key, mime_type, duration_ms, sample_rate, channels, started_at), session_id/date/name, segments (export query + `recording_tune_segment_id` + `implicit_trailing`), repertoire snapshot (`session_tune ⋈ tune` for the session), logged order (`session_instance_tune` incl. `record_type` breaks; ground truth only), `pulled_at`, `source_db`. Audio: `head_object` size, skip if `master.<ext>` matches, else `download_fileobj` to `.part` and rename. Always `storage_key`. `tunes.csv` via `_open_dump`, skipped if <7 days old.

`lab prepare --recordings N`: `ffmpeg -i master -ac 1 -ar 22050 -f wav mono22k.wav` + sha1 sidecar, then `lab bench features` for it.

## Corpus index (`lab index --candidate-set repertoire|all|eval_tunes --recording N`)

`abc_pitch.parse_abc(abc, mode) -> [Note(midi, eighths) | None(rest)]`: tokenizer skips `!..!`, `+..+`, `{..}`, `"..."`, `~`, decorations, bar/repeat marks, `(3` markers, ties/slurs, `%` comments, `\` continuation; chords → first note; rests break n-gram windows; `K:`/inline `[K:]` and csv `mode` → key signature (maj/ion, dor, mix, min/aeo, lyd, phr, loc); accidentals persist to bar end; `C..B`=60..71, `c..b`=72..83 with `,`/`'`. Repeats not expanded. Index: intervals → every 5-gram → `postings[gram] = [(tune_id, setting_id)]` dedup per setting, `df`, `n_tunes`, names. Pickled to `lab/data/index/<set>-n5-v<parser_version>.pkl` + `meta.json` (dump date, parse failures listed). Run config records the index file sha1.

## Eval (`lab eval RUN`, `lab diff A B`)

**Identification.** Ground truth from manifest: skip `tune_id NULL` (reason `no_tune_id`) and segments <10 s (`too_short`); cap implicit trailing ends at 600 s (`capped=1`); only segments intersecting the replayed range, partial coverage flagged. "Answer at clock t" = latest non-withdrawn hypothesis event with `clock_ms ≤ t` whose span overlaps t. Per segment: `ttfc_ms`, `ttsc_ms`, `top1_end`, `top5_end`, `flips`, `end_conf`, `cost_ms`, skip counts. Aggregate: n evaluated/skipped/capped; top-1/top-5 with Wilson 95% CI; "found within 30 s / 60 s" with CI plus `n_never`; flips distribution; calibration bins of 0.1 with n, accuracy, mean conf, ECE; cost/min total and per expert.

**Segmentation** (`eval/segmentation.py`, tune identity ignored). Ground-truth boundaries = segment starts + explicit ends. Predicted boundaries = `boundary` observations (and, separately, hypothesis span opens/closes, so the assembler's own segmentation is scored too). Metrics: recall and precision at ±3 s (and ±1 s, ±5 s), false boundaries per hour, median absolute error of matched boundaries, and detection latency (clock at emission minus true boundary, which exposes lookahead). Music activity: frame accuracy over the trustworthy regions only, as defined in the bench task.

Output `runs/<id>/eval.json` + `eval.md` (identification tables, segmentation table, calibration, cost by expert, per-segment table), upsert `eval_segment` and `eval_boundary`. `diff`: aggregates side by side with deltas and both CIs, per-expert cost delta, per-segment fixed/broken and ttfc moves >10 s, boundary recall/precision deltas; refuses runs with different segment sets unless `--intersection`.

## Inspection CLI

- `lab runs [--recording N]` — id, name, recording, range, status, audio/wall minutes, top-1 and boundary F1 if evaluated.
- `lab board RUN [--type T,..] [--range] [--expert E] [--json]` — observations in append order with `expert@version window cost cached inputs=[..]` and a per-type payload summary.
- `lab transcribe --recording N (--segment K | --range) [--source pitch_pyin|pitch_yin] [--match]` — ephemeral `scratch` run through the same driver, prints ABC-ish text; `--match` prints the matcher's top-10 for that window. The "is this part doing what we expect" tool.
- `lab timeline RUN [--segment K]` — per GT segment: ground truth line, boundary marks (true and predicted, with error), then every hypothesis event with `*` where top-1 is correct, then that segment's metrics. Read this first.
- `lab bench leaderboard --task T` — candidates ranked, per-night spread, params.

## Repo hygiene

- `pytest.ini`: add `lab` to `norecursedirs`; add `--cov-config=.coveragerc` to addopts.
- New `.coveragerc`: `[run] omit = lab/*, venv/*` (coverage's `source=.` reports never-imported files at 0%; without this `lab/` sinks `make test` under 80%).
- `lab/pytest.ini`: `[pytest] testpaths = tests`, `pythonpath = ..`, no coverage. Makefile targets `lab-install`, `lab-test`; `lint`/`format` unchanged (they cover `lab/` on purpose).
- `.gitignore`: `/lab/data/` (anchored, matching the existing `/data/` convention).
- `CLAUDE.md`: one Feature Index line → spec 053 + `lab/README.md`.

## Implementation steps (each verifiable)

1. Branch `053-ceol-listen-lab`. Write `specs/changes/inprogress/053-ceol-listen-lab.md` in spec 050's voice: intent, the two loops, design decisions, observation-type table, board schema, expert contract + window grid + driver, bench (tasks, candidates, graduation), runs/provenance, eval metrics, lab vs runtime, "logged order is not evidence", "implicit ends are not activity labels", status. Milieu description, not task list.
2. Hygiene: `.gitignore`, `.coveragerc`, `pytest.ini`, Makefile targets, `lab/requirements.txt`, `lab/pytest.ini`, `lab/README.md`, `env.py`, `paths.py`, `__main__.py`/`cli.py` skeleton. Verify `make test` and `make lint` still pass; `pip install -r lab/requirements.txt`; `import librosa, soundfile, sklearn`.
3. `corpus/tunes_csv.py`, `corpus/abc_pitch.py` + tests (modes, accidental persistence, octaves, chords, grace notes, rests). Verify parse rate over the dump >99%.
4. `corpus/pull.py` + `lab pull`. Verify manifest for recording 2 has 59 segments and 1,279 repertoire rows; masters match S3 sizes; second run is a no-op.
5. `audio/prepare.py`, `audio/chunks.py` (+ `AudioStore.read(t0, t1)`, window grid helper) + `lab prepare`. Verify wav duration matches `duration_ms` within 1 s; unit tests for chunk count and for the set of grid windows completed by a given clock with lookahead.
6. `bench/features.py`, `bench/tasks.py` + tests for label cutting (explicit vs implicit ends, exclusion regions, boundary tolerance). Verify `features.npz` grid length matches duration; label counts per night printed and sane (boundaries ≈ segments + explicit ends).
7. `bench/candidates/` first batch + `bench/score.py` + `lab bench run|leaderboard`. Verify: `music_energy` and `music_mel_lr` scored leave-one-night-out on `music_activity`; `boundary_novelty`, `boundary_keychange`, `boundary_mel_lr` on `boundary` with a PR sweep; leaderboard prints with per-night spread. Any ordering is fine; the point is that five ideas were scored in minutes.
8. `corpus/index.py` + `lab index`. Verify self-lookup: a known setting's 5-grams return its own tune at rank 1.
9. `board/`, `experts/base.py` (incl. `CandidateExpert`), `engine/` with `configs/null.json` (chunk source only). Verify a run over recording 2 segment 5 produces N `audio_chunk` rows; `lab board` lists them; `lab run --from` reproduces with `parent_run_id`.
10. Graduate `music_energy` and `boundary_novelty`; `pitch_pyin`, `pitch_yin`, `notes`, `intervals` + `lab transcribe`. Verify `boundary` observations appear with the expected lookahead delay; ABC-ish output for a known segment is human-comparable; rerun hits cache (`cached=1`); pyin windows are 10 s on a 2 s hop in the board dump.
11. `matcher` + `lab transcribe --match`. Verify on `eval_tunes` index that some segments show the GT tune in the top-10 (plumbing, not accuracy).
12. `prior`, `assembler` (with boundary handling and change hazard), hypothesis tables + `lab timeline`. Verify lifecycle events with changing confidences; a span closes and a new one opens at a predicted boundary (`opened_by=boundary`); `scheduler_skip` rows appear once confidence crosses the threshold and stop after a boundary.
13. `eval/` incl. `segmentation.py` + `lab eval` + `lab diff`. Verify `eval.md` has every identification and segmentation metric with counts; `no-prior.json` diffed against baseline shows deltas and fixed/broken segments; a config with `chunk_ms: 1000` diffed against 2000 shows the latency/quality movement.
14. Batch: baseline over all 8 recordings (overnight; pyin ≈ 5–15 s per audio minute → 1.5–4 h), eval each, aggregate table over 455 segments and all boundaries.

## Verification

```bash
venv/bin/pip install -r lab/requirements.txt
venv/bin/python -m lab pull --database-url "$PROD_URL" --recordings 2 --skip-audio
venv/bin/python -m lab pull --database-url "$PROD_URL" --recordings 2
venv/bin/python -m lab prepare --recordings 2                      # wav + features.npz
venv/bin/python -m lab bench run --task boundary --candidate boundary_novelty
venv/bin/python -m lab bench run --task music_activity --candidate music_mel_lr
venv/bin/python -m lab bench leaderboard --task boundary            # bench loop: ideas scored in minutes, night-wise
venv/bin/python -m lab index --candidate-set repertoire --recording 2
venv/bin/python -m lab run --config lab/configs/baseline.json --recording 2 --segments 5-6   # R1
venv/bin/python -m lab timeline R1                                  # lifecycle + boundaries + sharpening; partial replay
venv/bin/python -m lab board R1 --type pitch_track --range 12:00-12:10   # two producers, same type; 10 s windows on 2 s hop
venv/bin/python -m lab board R1 --type boundary                     # graduated candidate emitting with lookahead
venv/bin/python -m lab board R1 --type scheduler_skip               # VoI hook fired, reset by boundary
venv/bin/python -m lab board R1 --json | head                       # provenance incl. window on every row
venv/bin/python -m lab eval R1                                      # identification + segmentation tables
venv/bin/python -m lab run --config lab/configs/no-prior.json --recording 2 --segments 5-6   # R2
venv/bin/python -m lab diff R1 R2                                   # non-audio evidence measurable
venv/bin/python -m lab run --from R1                                # stored config re-executed
make test && make lint && (cd lab && ../venv/bin/python -m pytest)
```

## Risks

- **pyin speed**: mitigated by the cache, `--segments`, and 10 s windows on a 2 s hop (pyin's HMM sees context; cost is 5× a non-overlapping pass, so the cache matters more). `pitch_yin` is the fast iteration default if needed.
- **Heterophony**: expect low single-digit n-gram hits per chunk. That is the measurement the lab exists to make. Follow-ups, each as one more producer: pitch-class (mod 12) intervals, multi-pitch tracker, rhythm-aware matcher.
- **Boundary detection may need a learned model**: the bench is built so that finding this out is cheap. Learned candidates with ~900 boundaries across 8 nights are small-data; leave-one-night-out keeps the estimate honest but wide. More segmented nights are the fix.
- **Bench labels lean on segment marks**: human marks are ±1 s, so tolerances under 2 s are noise; implicit ends are excluded from activity labels by construction.
- **Lookahead makes boundaries late**: the assembler reopens spans after the change. A fast low-precision detector plus a slow high-precision one is the eventual pattern, and the type system already allows two producers.
- **librosa + scikit-learn weight**: ~300 MB in the venv; local only.
- **Prod access**: read-only transaction enforced; a dedicated read-only DB user is still preferable.

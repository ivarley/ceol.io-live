# Ceol Listen lab

The offline environment for tune recognition (spec 053:
`specs/changes/inprogress/053-ceol-listen-lab.md`). The spec holds the
design, the method ("How the lab is worked") and every result, including the
ones that failed. This file is the operating manual.

Not deployed, not covered by the app's test suite, not imported by the app.
Same venv, own extra dependencies, own tests. `make lint` does cover it.

```bash
make lab-install                                   # numpy, scipy, librosa, soundfile, scikit-learn into ./venv
make lab-test                                      # lab/tests via lab/pytest.ini
venv/bin/python -m lab --help
```

Below, `lab` means `venv/bin/python -m lab`.

## Secrets and production

`lab/.env` holds the production database URL (`PROD_DB_URL`) and the AWS keys
for the audio. It is gitignored (`/lab/.env`) and must never be committed.
`lab/env.py` loads it over the root `.env`.

Production is only ever read. The pull opens its connection with
`default_transaction_read_only=on`, and nothing in the lab writes to
production. A wrong label is fixed by a person in the app's segmenter
(`/admin/recordings`), then re-pulled.

## Data

Everything under `lab/data/` (gitignored). Set `LAB_DATA_DIR` to put it elsewhere.

```bash
# 1. Pull the corpus from production, read-only. AWS_* in lab/.env for the audio.
lab pull --database-url "$PROD_DB_URL" --recordings 2 --skip-audio   # manifests + tunes.csv
lab pull --database-url "$PROD_DB_URL" --recordings 2                # + master audio

# 2. Derive the working audio and bench features
lab prepare --recordings 2

# 3. Build the corpus indexes, plain and as runs of eighths
lab index --candidate-set repertoire -n 6 --fold-octaves
lab index --candidate-set repertoire -n 6 --fold-octaves --particalized
```

The corpus is eight nights at one session: recordings 1, 2, 3, 4, 5, 138,
139 and 140. After exclusions that is 502 scored segments. Re-pulling after a
label fix gives the corrected segment a new id.

Checked in, because a person made them and nothing can regenerate them:

| Path | What |
|---|---|
| `lab/annotations/r{rec}-s{seg}.json` | hand labels from the viewer: `labels` (pitch, one octave, `t0`/`t1` seconds from the segment start, `midi`, `from`), and `pulse` (`beats` and `downbeats` in seconds, `grouping` = eighth notes per drawn beat, `eighths_per_bar`, `bar_anchored`, a free-text `note`) |
| `lab/exclusions.json` | segments not scored, each with who decided, when and why. Rules at the top: exclude for what the audio is, never for how the recogniser did |
| `lab/configs/*.json` | board configurations. `baseline.json` is the current live pipeline |

## The two loops

### Bench: does the tune come back from the index

The retrieval bench is where most ideas are tested. It transcribes each
segment, looks the notes up, optionally applies the session's transitions,
and scores top-1, top-5 and mean reciprocal rank. Pitch tracks are cached,
so a full pass over 502 segments takes minutes.

The headline configuration (0.896 top-1, 0.932 top-5 on 2026-09-26 with parser version 2 and the key filter, which is on by default, about four minutes with pitch tracks cached; indexes rebuild with `lab index --candidate-set repertoire -n 6 --fold-octaves [--particalized]`):

```bash
lab bench retrieval --frontend yin --fold-octaves --particalized --fusion sum \
    -n 6 --seconds 120 --prior set_viterbi --beta 0.15 --candidate-set repertoire
```

- `--prior none` is the audio alone.
- `sequence` is an oracle, handed the true previous tune.
- `sequence_self` chains the system's own top answer forward, which is what
  a live system can do.
- `set_viterbi` decodes a whole set at once.
- `prior_only` is the no-audio control.
- `--type-filter oracle` sizes what a tune-type classifier would be worth.
- `--param K=V` passes front-end parameters, for example
  `--param trough_threshold=0.5`.

Each saved result keeps every segment's rank, so two of them pair:

```bash
lab bench pair lab/data/bench/tune_retrieval/A.json lab/data/bench/tune_retrieval/B.json [--list]
```

prints top-1 and top-5 before and after, newly right / newly wrong with the
sign test, and top-1 by tune type; `--list` names the segments that changed.
Results saved before 2026-09-27 have no rows; re-run them.

Variants that are not flags, such as the transition model's modes
(`SequenceModel.MODE`, `UNSEEN`, `GATE`), are swept from a short script that
sets the class attributes and calls `lab.bench.retrieval.run_retrieval`,
which returns `(result, rows)`. Its per-segment `rows` give the paired
comparison; `lab.bench.retrieval.pair_results` does the pairing.

Component benches against the hand labels:

```bash
lab bench pitch --frontend yin,salience_viterbi   # frame-level pitch-class accuracy
lab bench pulse                                   # period, meter, beat phase, bar phase vs drawn beats
```

The older task benches (music activity, boundaries) run leave-one-night-out:

```bash
lab bench run --task boundary --candidate boundary_novelty
lab bench leaderboard --task boundary
```

### Board: the live pipeline, replayed

A run replays a recording through the experts as if it were arriving live
and records every observation and hypothesis. Always name board runs
`<config>-r<recording>` so they can be pooled:

```bash
lab run --config lab/configs/baseline.json --recording 2 --name baseline-r2 --quiet
lab eval <run_id>                 # one run
lab timeline <run_id>             # read it segment by segment
lab diff <run_a> <run_b>          # two runs of the same night
```

A finding needs several nights. Run each night in parallel, then pool and
pair with `lab compare`:

```bash
for r in 1 2 3 4; do echo "live-x $r"; done | \
  xargs -P 4 -n 2 sh -c 'venv/bin/python -m lab run --config /path/to/$0.json --recording $1 --name $0-r$1 --quiet'
lab compare baseline live-x --nights 1,2,3,4            # pooled metrics, then +won/-lost and a sign test
lab compare baseline live-x --nights 1,2,3,4 --record   # also the final record, revisions included
```

A whole night takes a few minutes to tens of minutes. The engine commits
each observation so parallel runs do not block each other on SQLite's write
lock. Other heavy processes on the machine, such as simulators and builds,
slow it noticeably.

What a player would have seen, replayed from runs already made (seconds, not
a new board run): a new top guess shown at once from `--show-conf`, otherwise
once it has been top for `--hold-s`, and a short list of candidates from
`--list-floor` while nothing is sure:

```bash
lab display keyw20 --hold-s 2 --show-conf 1.1 --list-floor 0.05
lab display keyw20 --sweep          # show-conf x hold, each paired against the control
lab display keyw20 --calibrate      # category thresholds fitted leave-one-night-out
```

Board metrics per segment:

- **top-1 and top-5 at end:** the answer shown when the tune ends.
- **right within 30s / 60s:** time to first correct.
- **never right**
- **flips:** how often the shown answer changed.

A change that raises top-1 and doubles flips is not an improvement.

## Looking at one segment

```bash
lab view --recording 2 --segment 117
lab view --recording 2 --range 23:50-25:26 --frontend salience_viterbi
```

The viewer shows the audio, the piano roll of heard notes, and the tune's
notation. Heard notes that belong to a phrase the real tune also has are
drawn in a different colour; above about 20 shared phrases the tune is
identified six times in seven, and below ten it never is.

It also shows the estimated beat grid, and a stave of what was heard as runs
of eighths. The stave is engraved by abcjs, follows the tempo map, and is
synced to the piano roll's zoom and pan.

Modes:

| Key | Mode |
|---|---|
| `1` | listen |
| `2` | edit |
| `3` | accept (box-drag over notes that are right) |
| `4` | draw (click an eighth between two grid lines at the pitch you hear; again to remove) |
| `5` | erase |
| `6` | beats (click to draw a beat; shift-click marks a bar line) |

Other keys:

| Key | Action |
|---|---|
| Tab | switch between draw and beats |
| space | play / pause |
| `,` / `.` | back / forward three seconds |
| `r` | replay the view |
| `Home` | go to the start |
| `l` | loop on / off |
| `s` | sing the labels (the offset slider shifts them against the music, by ear) |
| `g` | show / hide the eighth-note grid |
| `+` / `-` | zoom |
| arrows | pan, or move the selected label |
| cmd-S | save |
| cmd-Z | undo |

- Drag in the strip above the ruler to draw a loop.
- Set the meter dropdown before drawing beats. It records how many eighth
  notes are in one drawn beat and in one bar: reel in 2 or 4, jig, slip jig
  9/8, slide 12/8, polka.
- Saving writes `lab/annotations/`.

Other inspection tools:

```bash
lab trace-set --recording 2 --segment 117     # one set: heard, shaped, matched, expected, decided
lab transcribe --recording 2 --segment 5 --source pitch_pyin --match
lab board <run_id> --type pitch_track --range 12:00-12:10
lab suspects                                  # segments whose audio does not sound like a tune
lab runs
```

`lab suspects` ranks segments by pulse strength and in-key fraction. It
finds mislabelled noise between sets. It cannot see a transcription that is
consistently a fifth out, because those notes are still in the key.

## Working in here

- Throwaway scripts and experiment configs go in a scratch directory outside
  the repo. Do not put them in `lab/data/`, because `make lint` runs
  `flake8 .` and walks it.
- Before committing, run `make lab-test` and the flake8 half of `make lint`
  (`flake8 . --exclude=venv,env,htmlcov --ignore=E501,W503,F403,F405,E402,E712`).
  The `black --check` half fails across the whole repo today, lab or not.
- A result goes into the spec, in the section it belongs to, with its scope
  and paired numbers, and negatives too. When a parameter was chosen by
  measurement, the comment next to it gives the numbers.

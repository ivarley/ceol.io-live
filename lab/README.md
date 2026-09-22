# Ceol Listen lab

The offline environment for tune recognition (spec 053:
`specs/changes/inprogress/053-ceol-listen-lab.md`). Read the spec first; this
file is the operating manual.

Not deployed, not covered by the app's test suite, not imported by the app.
Same venv, own extra dependencies, own tests.

```bash
make lab-install                                   # numpy, scipy, librosa, soundfile, scikit-learn into ./venv
make lab-test                                      # lab/tests via lab/pytest.ini
venv/bin/python -m lab --help
```

## Data

Everything under `lab/data/` (gitignored). Set `LAB_DATA_DIR` to put it elsewhere.

```bash
# 1. Pull the corpus from production, read-only. AWS_* in .env for the audio.
venv/bin/python -m lab pull --database-url "$PROD_URL" --recordings 2 --skip-audio   # manifests + tunes.csv
venv/bin/python -m lab pull --database-url "$PROD_URL" --recordings 2                # + master audio

# 2. Derive the working audio and bench features
venv/bin/python -m lab prepare --recordings 2

# 3. Build a corpus index
venv/bin/python -m lab index --candidate-set repertoire --recording 2
```

## The two loops

```bash
# Bench: score an idea for one task, leave-one-night-out, in seconds
venv/bin/python -m lab bench run --task boundary --candidate boundary_novelty
venv/bin/python -m lab bench leaderboard --task boundary

# Ensemble: replay a range through the board with a config, then score it
venv/bin/python -m lab run --config lab/configs/baseline.json --recording 2 --segments 5-6
venv/bin/python -m lab timeline <run_id>
venv/bin/python -m lab eval <run_id>
venv/bin/python -m lab diff <run_a> <run_b>
```

## Looking at one part

```bash
# Play a segment with the notes it heard drawn over it. Notes belonging to a
# phrase the real tune also has are coloured differently, which is the thing
# worth watching: above ~20 shared phrases it identifies the tune six times
# in seven, below ten it never does.
venv/bin/python -m lab view --recording 2 --segment 117
venv/bin/python -m lab view --recording 2 --range 23:50-25:26 --frontend salience_viterbi

# One set, stage by stage: heard, shaped, matched, expected, decided
venv/bin/python -m lab trace-set --recording 2 --segment 117
```


```bash
venv/bin/python -m lab board <run_id> --type pitch_track --range 12:00-12:10
venv/bin/python -m lab transcribe --recording 2 --segment 5 --source pitch_pyin --match
venv/bin/python -m lab runs
```

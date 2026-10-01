# Working in the lab

Read `lab/README.md` (how to run things) and the spec
`specs/changes/inprogress/053-ceol-listen-lab.md` (design, "How the lab is
worked", and every result so far) before changing anything here. The spec's
"Where it stands" and "Still open" sections are the current state.

## The lab and the app (2026-10-01)

The lab was merged into the app branch on 2026-10-01 and the detector is to
be extracted into a package the app's listening service uses (`specs/changes/
inprogress/053 files/listen-on-the-server.md`). Until that package exists,
`lab/` is the one implementation; once it does, the lab's tests become its
agreement tests. Lab experiments still run from this worktree, with its venv
and `lab/data`.

## Where the lab lives

In its own worktree, `~/Local/code/ceol.io-053-listen` on branch
`053-ceol-listen-lab`, with its own `venv` (`requirements.txt`,
`requirements-test.txt` and `lab/requirements.txt`), so the lab's audio stack
never touches the app's environment and app work never lands on this branch.
`lab/data` (about 40GB) and `lab/.env` are untracked and live only here. App
work happens in the other worktrees, never in this one.

## Hard rules

- Production is read-only. Never write to it, and never commit `lab/.env`
  (production URL and AWS keys; gitignored as `/lab/.env`).
- No result without its scope and a paired comparison against what it
  replaces: newly right, newly wrong, sign test. Use `lab compare` for the
  board and `lab.tools.compare.sign_test` for bench scripts.
- If a bug could have touched a measurement, re-run the old configuration,
  confirm it reproduces its old number exactly, then re-measure. If a number
  already reported to the user was wrong, say so plainly and correct the
  spec.
- The bench and the board must call the same implementation for shared steps
  (`regrid_notes`, `fuse`, `SequenceModel`, `prior_weight`). A new shared
  step gets one implementation and an agreement test in `test_engine.py`.
- Scratch scripts and experiment configs go outside the repo, never under
  `lab/data/`, because `flake8 .` walks it.
- Write every result into the spec, including negatives. Commit messages are
  long-form and carry the numbers.
- A bench number is on tunes cut to their labelled boundaries, from the
  session's repertoire, on nights every setting was tuned on. Say so whenever
  one is quoted; the board on a raw night, and a night never tuned on, are
  the numbers that stand for the product.

## Working with the player

The user plays at this session and knows the tunes and the players. Most of
the ideas that moved accuracy came from them saying what was musically wrong
with the output. Treat those statements as hypotheses to measure, not as
settled. Report candidly when one does not measure out.

- **"Bring up rec N seg K"** means (re)start the viewer in the background on
  port 8420 with `--no-open`, killing whatever holds the port first:
  `lab view --recording N --segment K --port 8420 --no-open`. They reload
  their own tab.
- **Their hand labels are the ground truth for components.** After they
  annotate, re-read `lab/annotations/r{N}-s{K}.json` and score against it
  with `lab bench pitch` or `lab bench pulse`.
- **A mislabelled segment is fixed by them in production,** then re-pulled.
  A segment that is not a fair test goes into `lab/exclusions.json` only on
  their decision, with their reason.
- **Session facts are per session.** Tune transitions, settings and keys hold
  at this session and not across sessions.

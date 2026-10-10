# Finding a night's tunes on the server, and what a session prefers

Spec 053. Agreed with the product owner on 2026-10-07: the post-hoc tune
finding the lab has been running (`lab drafts --blind --merged --apply`) runs on
the listening service, started from the segmenter by an admin; live listening
comes first; admins can see every background job; the page that started one
shows where it has got to. And the listening service, live or not, prefers each
session's own tunes, then popular ones, then the rest.

## What a session prefers (the tiers)

Measured in the lab (spec 053, "A young session, and the production rule"):
one whole-corpus index for every session; each tune the session has logged
before the night is its own; popular tunes (at least 100 thesession.org
tunebooks, about 2,300) are a second tier with half an outside tune's
discount; the rest of the corpus is outside. A session with no history has the
popular tunes as its own. Over nine nights a session with eight nights of
history then names 659 of 689 right against 654 with none and 662 with its
full history.

Until now the deployed service used the lab's repertoire index, which is this
one session's tunes, for everyone.

- The phone names the night: `{"type": "start", ..., "instance_id": N}`.
- The service asks the app for the session's tunes logged before that night
  (`GET /api/session-instances/<id>/known-tunes`, with the phone's own token,
  the one it already checks against `/api/me`), and listens with them as the
  first tier. No instance: no first tier (popular tunes as its own).
- The popular list (`corpus/tune_popularity.csv`) joins the service's data
  files in the bucket (`listen.data`).

## Find tunes: the job

### From the segmenter

On a night with no tunes logged, an admin sees **Find the tunes automatically**.
It queues a job and the page shows it from then on, polling:

- *Waiting* — how long, and how many jobs are ahead.
- *Running* — the phase (listening, following the sets, putting the tunes in),
  how far through the audio, how long it has run.
- *Paused* — a night is being listened to live, which comes first; how long it
  has been paused.
- *Done* — N tunes in M sets, K need a check; the list reloads with them.
- *Failed* — why; **Try again**.

A job can be cancelled while waiting or running. Undo after it is done is the
segmenter's own: remove what it logged (rows the listener logged that nobody
has confirmed or corrected), offered beside the result.

### The job record

`listen_job` (schema 061): kind (`find_tunes`), the recording, who asked,
status (`queued` | `running` | `paused` | `done` | `failed` | `cancelled`),
phase and progress (ms of audio heard of the total), the worker that holds it
and its heartbeat, and the times: queued, started, finished, and the seconds
spent running and spent paused, so "waited", "ran" and "paused for live" can
each be shown. A summary of the result (tunes, sets, needing a check) and an
error. A running job whose heartbeat is older than two minutes is taken to have
died with its worker and goes back to the queue (at most three attempts).

### The worker: the listening service

The shared listening service runs one job at a time in the background:

1. Claims the oldest queued job (`POST /api/listen-jobs/claim`, the service's
   own token), getting the recording's audio URL (presigned), its length, the
   session's tunes before the night, and the session's keys for them.
2. Fetches and decodes the audio to 22,050 Hz mono (ffmpeg, as the app's
   ingest does).
3. Listens to it all (`lab.tools.listen`, the tiers above), then drafts the log
   from what it showed, follows each set, joins and tidies the sets, ends them
   on their held notes, and works out each tune's confidence (the lab's
   `drafts` and `analysis.confidence`, the same code `lab drafts` runs).
4. Reports progress every few seconds (which is also its heartbeat), and
   posts the drafts (`POST /api/listen-jobs/<id>/result`); the app logs and
   places them as one transaction, as `source='listen'` with their confidence
   and model (schema 060), attributed to the admin who asked.

**Live listening comes first.** While any live stream is open the job pauses
between steps (a step is 4 s of audio), and says so; it resumes when the last
stream closes. One live night and a background job would otherwise share the
service's two CPUs.

### Admin visibility

`/admin/listen-jobs`: every job, newest first, with its recording and night,
who asked, status and phase, how long it waited, ran and was paused, its
result or error; cancel and retry. The service's `/health` reports the job it
holds.

### Not in this

- Nights with tunes already logged (the meter-log drafting, `lab drafts`
  without `--blind`, and merging machine tunes into a hand-written log).
- Anyone but admins.
- A second opinion over each drafted tune's whole stretch (spec 053, "A second
  opinion over the whole tune"), to measure first.

## Deploying

In this order:

1. Run `schema/061_listen_job.sql` in production.
2. Set `LISTEN_JOB_TOKEN` to the same new secret on the web app and on
   `ceol-listen` (unset on either, the jobs never run: the app refuses the
   worker's calls and the service never asks).
3. Upload the service's two new data files from the lab's worktree:
   `venv/bin/python -m listen.data upload` (`corpus/tune_popularity.csv` and
   `corpus/tunes.csv` join the indexes in the bucket).
4. Bring the lab branch's service code to production (the tiers, the job
   worker, `lab.tools.find_tunes`) and deploy both; the service's build gains
   `imageio-ffmpeg`.
5. A new iOS build sends the night with its stream; until then live listening
   on the service has no first tier (popular tunes as the session's own), which
   is the brand-new-session case, not today's hard-wired repertoire.

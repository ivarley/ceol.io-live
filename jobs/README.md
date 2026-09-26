# Jobs Directory

This directory contains scheduled job scripts for the application.

## Scripts

### check_active_sessions.py
**Production cron job** that runs every 15 minutes (at :14, :29, :44, :59) to manage active session instances.

- Activates sessions when they enter their active window
- Deactivates sessions when they leave their active window
- Updates people's current location based on active sessions

**Do not modify this file for testing.** Use `test_active_sessions.py` instead.

### process_pending_recordings.py
**Manual tool, not a cron job.** It finishes recording ingests nobody is working
on (spec 050) — the same sweep the web service runs on its own.

It was declared as a cron in `render.yaml` and never created, so it never ran.
The reason given for it was wrong anyway: it assumed a free-tier web service that
idles out after ~15 minutes, but `ceol.io-live` is on starter and does not idle.
What actually interrupts an ingest is the process restarting — a deploy, an OOM,
or gunicorn recycling a worker at `max_requests`.

So the sweep lives in the web service now: `services/recording_ingest.py`'s
`start_sweeper()`, started from `gunicorn.conf.py`'s `post_fork`. Every event
that can interrupt an ingest is followed by a worker booting, which makes the
fork itself the recovery trigger — a killed transcode resumes seconds later
rather than waiting out a cron window, and it costs nothing. A 10-minute tick
after that covers the one case a restart doesn't: a run that stops heartbeating
without its process dying.

Use this script to run a sweep by hand (a Render shell, or locally against a real
database). It calls the same `sweep_once()` the web service does.

```bash
python3 jobs/process_pending_recordings.py            # sweep one recording
python3 jobs/process_pending_recordings.py --limit 5  # clearing a backlog
```

- Runs the ingest **synchronously** — here the work is the point.
- Takes 1 per run by default; two transcodes at once share the box's memory.
- Gives up after 3 attempts and marks the row `failed`, so an unreadable file
  fails visibly instead of being retried forever. An explicit Retry in the UI
  resets that budget.

**Needs the `AWS_*` variables**, unlike the other jobs here: without object
storage it can download nothing. It says so and exits non-zero rather than
sweeping and quietly achieving nothing.

### sync_thesession_merges.py
**Weekly thesession.org merge sync** (spec 031) — also not a cron service of its
own. `check_active_sessions.py` calls its `run_weekly_if_due()` at the end of
every run; that cron already fires four times an hour, so it passes through the
Monday 06:00 UTC window every week without a second service to pay for.

The gate is `is_due()`: Monday, 06:00 UTC, and no run started in the last 6 days.
That last check is what stops all four of that hour's invocations from starting a
run, and it recovers a week the window was missed.

Run it standalone for an on-demand sync — it ignores the schedule when you do:

```bash
python3 jobs/sync_thesession_merges.py
```

The admin merge page (`/admin/tunes/merge`) can also trigger a run.

### test_active_sessions.py
**Development testing wrapper** for the active session cron job.

Provides flexible testing with:
- Database selection (test or production)
- Time simulation
- Dry-run mode
- Predefined scenarios
- Test data generation

See [Cron Testing](../specs/current/services/active-sessions-cron-testing.md) for full documentation.

**Quick examples:**
```bash
# Basic test
python3 jobs/test_active_sessions.py

# Set up test data
python3 jobs/test_active_sessions.py --setup-test-data

# Dry run against production
python3 jobs/test_active_sessions.py --prod-db --dry-run

# Simulate evening sessions
python3 jobs/test_active_sessions.py --scenario evening
```

### test_scenarios.py
**Test data generator** that creates sample sessions for testing.

Creates 6 different scenarios:
- Evening sessions (7pm Thursday)
- Morning sessions (9am Wednesday)
- Overlapping sessions (Friday 8pm and 9pm)
- Different timezone (NYC Tuesday)
- Future sessions (Saturday 2pm)
- Custom buffer times (Sunday 3pm)

Can be run directly:
```bash
python3 jobs/test_scenarios.py
```

Or via the test wrapper:
```bash
python3 jobs/test_active_sessions.py --setup-test-data
```

## Documentation

- **[Cron Testing](../specs/current/services/active-sessions-cron-testing.md)** - Comprehensive guide for testing the cron job locally
  - Setup instructions
  - Usage examples
  - Testing scenarios
  - Troubleshooting

## Production Deployment

Ceol has exactly **one** cron service, `ceol-io-active-sessions`, and everything
scheduled hangs off it or off the web service. That is deliberate: cron services
cost money, and both of the other scheduled things here were once declared in
`render.yaml` and silently never created.

`render.yaml` is documentation only — Render does not apply it, and adding a
service to it creates nothing. Create cron services in the dashboard, then mirror
them into the file.

```yaml
- type: cron
  name: ceol-io-active-sessions
  env: python
  schedule: "14,29,44,59 * * * *"
  buildCommand: "pip install -r requirements.txt"
  startCommand: "python3 jobs/check_active_sessions.py"
```

What runs where:

| Work | Where it runs | Trigger |
|---|---|---|
| Active sessions + auto-create | `ceol-io-active-sessions` cron | `14,29,44,59 * * * *` |
| thesession.org merge sync | same cron, at the end | gated to Mondays 06:00 UTC, ≥6 days since last |
| Recording ingest sweep | `ceol.io-live` web service | `post_fork` on every worker boot, then every 10 min |

## Development Workflow

1. **Make changes to `active_session_manager.py`**
2. **Test locally:** `python3 jobs/test_active_sessions.py`
3. **Test edge cases with time simulation**
4. **Dry run against production:** `python3 jobs/test_active_sessions.py --prod-db --dry-run`
5. **Deploy and monitor**

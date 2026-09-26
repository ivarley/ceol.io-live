"""Gunicorn settings for the web service.

The default (`gunicorn app:app`, no arguments) is a SINGLE synchronous worker,
which serves exactly one request at a time — every page, API call and static
asset queues behind whatever is in front of it. That was measurable in
production: four parallel requests for the same session page came back in a
perfect staircase (0.9s, 1.5s, 2.1s, 2.8s) while the instance sat at 0.0002 of
its 0.5 CPU limit and the database at 1-2 connections. Nothing was busy; things
were merely waiting in line.

So: threads, not processes. The work is I/O-bound (waiting on Postgres), which
is exactly what gthread is for, and threads share the interpreter rather than
forking another ~160MB copy of it into a 512MB box.

Start the service with:  gunicorn -c gunicorn.conf.py app:app
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"

# 2 x 4 = 8 concurrent requests. Two workers so a single wedged request can't
# take the whole service down, four threads each because they spend nearly all
# their time blocked on the database rather than holding the GIL.
worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
threads = int(os.environ.get("WEB_THREADS", 4))

# Keep the DB pool (see database.py) meaningfully larger than one connection per
# thread would need at peak, but the pool is per-worker: workers * PGPOOL_MAX is
# the real ceiling against Postgres. Raise these together, never one alone.

timeout = 60
graceful_timeout = 30
keepalive = 5

# Bound any slow leak without a visible restart: jitter stops all workers from
# recycling on the same request.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")


def post_fork(server, worker):
    """Each forked worker builds its own connection pool, then starts sweeping.

    database.py creates the pool lazily on first use, so a pool inherited across
    a fork would share sockets between processes. Clearing it here makes that
    impossible rather than merely unlikely.

    The recording-ingest sweeper (spec 050) starts here too. A worker forking is
    precisely the event it exists to recover from -- deploy, OOM, max_requests
    recycle -- so booting one is the right moment to go looking for an ingest
    that was killed mid-transcode. This hook is also the reason the sweeper does
    not run in the dev server, in tests, or in the cron process: they import the
    module but never fork a gunicorn worker.
    """
    from database import close_db_pool

    close_db_pool()

    from services.recording_ingest import start_sweeper

    start_sweeper()


def worker_exit(server, worker):
    from database import close_db_pool

    close_db_pool()

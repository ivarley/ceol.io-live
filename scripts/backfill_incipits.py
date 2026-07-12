"""Backfill tune_setting.incipit_abc in the local test DB after seeding.

The seed file ships full ABC but empty incipits, while the app computes an
incipit whenever it caches a setting — so a freshly seeded DB renders no
notation in the tune drawer / offline bundle (which bundle ONLY incipits).
Run the same production function over the seed rows so seeded state matches
what the app would have produced. Invoked by setup_local_db.sh after every
seed load; safe to re-run (only touches rows with an empty incipit).
"""

import os
import sys

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import extract_abc_incipit  # noqa: E402  (path set up above)

conn = psycopg2.connect(
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
    dbname=os.environ.get("PGDATABASE", "ceol_test"),
    user=os.environ.get("PGUSER", "test_user"),
    password=os.environ.get("PGPASSWORD", "test_password"),
)
cur = conn.cursor()
cur.execute(
    """SELECT ts.setting_id, ts.abc, t.tune_type
       FROM tune_setting ts JOIN tune t USING (tune_id)
       WHERE COALESCE(ts.incipit_abc, '') = '' AND COALESCE(ts.abc, '') <> ''"""
)
rows = cur.fetchall()
for setting_id, abc, tune_type in rows:
    cur.execute(
        "UPDATE tune_setting SET incipit_abc = %s WHERE setting_id = %s",
        (extract_abc_incipit(abc, tune_type), setting_id),
    )
conn.commit()
print(f"backfilled incipits for {len(rows)} settings")

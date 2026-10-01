# The listening service

A phone streams a session's audio here; every 4 s it answers with what tune
the detector thinks is playing. The detector is the lab's
(`lab/tools/listen.py`: `Models` loaded once, a `Listener` per stream), the
one measured in spec 053; the design is
`specs/changes/inprogress/053 files/listen-on-the-server.md`. The protocol
is in the docstring of `listen/service.py`.

This is the spike: one service, a shared token, no app page yet. It exists
to measure a real instance before the native recorder is built.

## Locally

Needs the lab's environment (its venv has the pitch trackers) and data:

```bash
LAB_DATA_DIR=~/Local/code/ceol.io-053-listen/lab/data PYTHONPATH=. \
  ~/Local/code/ceol.io-053-listen/venv/bin/python -m uvicorn listen.service:app --port 8440

# another terminal: three minutes of night 137, double speed, one deliberate drop
LAB_DATA_DIR=~/Local/code/ceol.io-053-listen/lab/data PYTHONPATH=. \
  ~/Local/code/ceol.io-053-listen/venv/bin/python -m listen.client ws://localhost:8440/listen \
  --recording 137 --start-min 8 --minutes 3 --speed 2 --drop-at 60
```

On 2026-10-01 that named The Roaring Barmaid by 16 s and The Rose in the
Heather from 88 s, as `lab listen` does; each state reached the client a
median 0.4 s after its audio was sent (the first 3.3 s, the models loading);
after the drop the stream resumed at exactly 60.0 s; the saved
`audio.flac` was the full 180.0 s.

`GET /health` says whether the models are loaded, how many streams are open
and the process's peak memory.

## On Render

1. **Data in S3.** The indexes and the aligner's sequences (about 76 MB) are
   not in the repo. From the main checkout, with the lab's data and the AWS
   credentials from the lab's `.env` (this writes to the recordings bucket,
   under `listen-data/v1/`):

   ```bash
   set -a; . ~/Local/code/ceol.io-053-listen/lab/.env; set +a
   LAB_DATA_DIR=~/Local/code/ceol.io-053-listen/lab/data venv/bin/python -m listen.data upload
   ```

2. **A new Web Service** in the dashboard, from this repo and the branch that
   carries `listen/`:

   | | |
   |---|---|
   | Runtime | Python |
   | Build command | `pip install -r listen/requirements.txt && pip install --no-deps basic-pitch==0.4.0` |
   | Start command | `uvicorn listen.service:app --host 0.0.0.0 --port $PORT` |
   | Health check path | `/health` |
   | Instance | 4 GB (measured peak on a laptop CPU: 3.0-3.4 GB with all three trackers) |

   Environment: `PYTHON_VERSION=3.11.0`; `LISTEN_TOKEN` (any long random
   string; clients send it); `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
   `AWS_S3_BUCKET`, `AWS_S3_REGION` (the same as the web service's, for the
   data download).

   Basic Pitch is installed with `--no-deps` because on Linux it requires all
   of TensorFlow; here it runs through ONNX Runtime, which it picks by itself
   when that is the only backend installed. PyTorch comes from its CPU index
   (pinned in `listen/requirements.txt`) because the default Linux wheels
   carry gigabytes of CUDA.

3. **Measure it:**

   ```bash
   PYTHONPATH=. ~/Local/code/ceol.io-053-listen/venv/bin/python -m listen.client \
     wss://<service>.onrender.com/listen --token <LISTEN_TOKEN> \
     --file <any session recording> --start-min 8 --minutes 10
   ```

   and read `/health`. The numbers that decide the next step: each 4 s step's
   compute time against 4 s, and peak memory against the instance's 4 GB.

Mirror the service in `render.yaml` once it exists in the dashboard, not before
(see the note at the top of that file).

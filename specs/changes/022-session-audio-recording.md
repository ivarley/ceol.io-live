# 022 Session Audio Recording

Record audio at live Irish music sessions and store it in the cloud. This is Stage 1 of a longer-term goal of automated tune detection from recorded audio. This stage proves that audio can be reliably captured from multiple devices at a session and stored, with a data model that supports future analysis.

## Design Decisions

- **Storage:** AWS S3 (effectively free at expected scale of ~50 hours/month)
- **Chunking:** Simple single recorder, 30-second chunks, no overlap (Irish tunes repeat 2-3x so chunk boundaries aren't critical)
- **Audio format:** WebM/Opus at 64kbps mono (~29MB/hour)
- **Sources:** Both live recording from device microphone and upload of complete audio files (MP3, WAV, etc.)

## Data Model

Four new tables (the fourth is defined but not populated in Stage 1).

### `recording`

One continuous recording from one device at one session instance. A person can have multiple separate recordings per session (e.g. leave and return), so there is no unique constraint on `(session_instance_id, person_id)`.

| Column | Type | Notes |
|--------|------|-------|
| `recording_id` | SERIAL PRIMARY KEY | |
| `session_instance_id` | INTEGER NOT NULL | FK → `session_instance` |
| `person_id` | INTEGER NOT NULL | FK → `person` |
| `source` | VARCHAR(10) NOT NULL | `live` or `upload` — distinguishes real-time recordings from uploaded files |
| `status` | VARCHAR(20) NOT NULL | `started`, `recording`, `paused`, `stopped`, `failed` |
| `device_info` | JSONB | User-agent, device name, audio capabilities |
| `format` | VARCHAR(50) | e.g. `audio/webm;codecs=opus` |
| `sample_rate` | INTEGER | e.g. 48000 |
| `channels` | INTEGER | e.g. 1 (mono) |
| `bitrate` | INTEGER | e.g. 64000 |
| `s3_prefix` | VARCHAR(500) | S3 key prefix for all chunks, e.g. `recordings/{recording_id}/` |
| `total_chunks` | INTEGER DEFAULT 0 | Count of successfully uploaded chunks |
| `total_duration_ms` | BIGINT DEFAULT 0 | Total duration in milliseconds |
| `total_size_bytes` | BIGINT DEFAULT 0 | Total file size across all chunks |
| `client_started_at` | TIMESTAMPTZ | Device's wall-clock time when recording began (from `new Date().toISOString()`) |
| `created_date` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |
| `created_by` | INTEGER | FK → `person` |
| `updated_date` | TIMESTAMPTZ | |
| `updated_by` | INTEGER | FK → `person` |

Chunk absolute times are derived as `client_started_at + start_timestamp_ms`.

### `recording_chunk`

Individual 30-second audio chunks. Unique on `(recording_id, sequence_number)`.

| Column | Type | Notes |
|--------|------|-------|
| `recording_chunk_id` | SERIAL PRIMARY KEY | |
| `recording_id` | INTEGER NOT NULL | FK → `recording` |
| `sequence_number` | INTEGER NOT NULL | 0-indexed chunk sequence |
| `start_timestamp_ms` | BIGINT NOT NULL | Milliseconds since recording start |
| `end_timestamp_ms` | BIGINT NOT NULL | Milliseconds since recording start |
| `s3_key` | VARCHAR(500) NOT NULL | Full S3 object key |
| `file_size_bytes` | INTEGER | |
| `upload_status` | VARCHAR(20) NOT NULL | `pending`, `uploading`, `uploaded`, `failed` |
| `checksum` | VARCHAR(64) | SHA-256 of the chunk data |
| `created_date` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

Unique constraint: `(recording_id, sequence_number)`.

### `recording_event`

Lifecycle events for debugging and analysis.

| Column | Type | Notes |
|--------|------|-------|
| `recording_event_id` | SERIAL PRIMARY KEY | |
| `recording_id` | INTEGER NOT NULL | FK → `recording` |
| `event_type` | VARCHAR(30) NOT NULL | `start`, `pause`, `resume`, `stop`, `error`, `chunk_gap` |
| `event_data` | JSONB | Additional context (error messages, gap duration, etc.) |
| `client_timestamp` | TIMESTAMPTZ | Device's wall-clock time of the event |
| `created_date` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

### `recording_tune_segment` (future — define schema only, do not populate)

Links time ranges in a recording to detected tunes. This table supports the future tune-detection feature.

| Column | Type | Notes |
|--------|------|-------|
| `recording_tune_segment_id` | SERIAL PRIMARY KEY | |
| `recording_id` | INTEGER NOT NULL | FK → `recording` |
| `tune_id` | INTEGER | FK → `tune` (nullable until identified) |
| `start_timestamp_ms` | BIGINT NOT NULL | Milliseconds since recording start |
| `end_timestamp_ms` | BIGINT NOT NULL | Milliseconds since recording start |
| `confidence` | DECIMAL(5,4) | Detection confidence 0.0000–1.0000 |
| `detection_method` | VARCHAR(50) | Algorithm/model used |
| `detection_metadata` | JSONB | Additional detection details |
| `created_date` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

All tables should have corresponding history tables following the existing audit trail pattern.

## API Endpoints

All endpoints in `api_routes.py`.

### `POST /api/session_instance/<id>/recordings` — Start recording

Creates a `recording` row and returns the recording ID and S3 prefix. Called when the user taps Record.

**Request body:**
```json
{
  "device_info": { "userAgent": "...", "label": "iPhone 14" },
  "format": "audio/webm;codecs=opus",
  "sample_rate": 48000,
  "channels": 1,
  "bitrate": 64000,
  "client_started_at": "2026-02-27T20:30:00.000Z"
}
```

**Response:** `201` with `{ "recording_id": 42, "s3_prefix": "recordings/42/" }`

### `POST /api/recordings/<id>/chunks` — Upload chunk

Multipart upload of a single audio chunk. Server uploads to S3 and creates a `recording_chunk` row.

**Form data:**
- `audio` — the audio blob
- `sequence_number` — 0-indexed
- `start_timestamp_ms` — ms since recording start
- `end_timestamp_ms` — ms since recording start
- `checksum` — SHA-256 hex

**Response:** `201` with `{ "recording_chunk_id": 123, "s3_key": "recordings/42/chunk_000.webm" }`

### `PUT /api/recordings/<id>/status` — Pause/resume/stop

Updates the recording status and creates a `recording_event`.

**Request body:**
```json
{
  "status": "paused",
  "client_timestamp": "2026-02-27T21:00:00.000Z"
}
```

**Response:** `200` with updated recording object.

### `GET /api/session_instance/<id>/recordings` — List recordings

Returns all recordings for a session instance, with chunk counts and durations.

**Response:** `200` with array of recording summaries.

### `GET /api/recordings/<id>/playback` — Get presigned URLs

Generates S3 presigned URLs for all chunks in sequence order, enabling client-side playback.

**Response:**
```json
{
  "recording_id": 42,
  "chunks": [
    { "sequence_number": 0, "url": "https://s3...", "start_ms": 0, "end_ms": 30000 },
    { "sequence_number": 1, "url": "https://s3...", "start_ms": 30000, "end_ms": 60000 }
  ]
}
```

### `POST /api/session_instance/<id>/recordings/upload` — Upload complete audio file

Accepts a complete audio file (MP3, WAV, M4A, etc.) and processes it into the same chunked format as a live recording.

**Form data:**
- `audio` — the audio file
- `client_started_at` — (optional) when the recording was originally made

**Processing steps:**
1. Create a `recording` row with `source = 'upload'` and `status = 'started'`
2. Use `pydub` to read the audio file and split into 30-second chunks
3. Upload each chunk to S3
4. Create `recording_chunk` rows with computed timestamps (0–30000ms, 30000–60000ms, etc.)
5. Update recording status to `stopped` and set aggregate totals

Processing is synchronous for Stage 1 (fine for files up to ~1 hour).

**Response:** `201` with completed recording object.

## Server Module: `recording.py`

New module handling all S3 interaction and audio processing.

**Functions:**
- `upload_chunk_to_s3(recording_id, sequence_number, audio_data)` — uploads a chunk and returns the S3 key
- `generate_presigned_url(s3_key, expiry=3600)` — generates a presigned GET URL
- `get_recording_timeline(recording_id)` — returns ordered chunks with presigned URLs
- `chunk_audio_file(file_path)` — uses `pydub` to split an uploaded file into 30-second chunks; returns list of `{ "sequence_number": int, "start_ms": int, "end_ms": int, "data": bytes }`

**Environment variables:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET`
- `AWS_S3_REGION`

**Dependencies:**
- `boto3` — AWS S3 client
- `pydub` — audio file reading/chunking (uses ffmpeg under the hood)
- `ffmpeg` — system package, available on Render.com via `apt`

## Client-Side: `SessionRecorder` JS Class

A JavaScript class managing the recording lifecycle in the browser.

### Audio Capture

```javascript
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false,
    channelCount: 1,
    sampleRate: 48000
  }
});

const recorder = new MediaRecorder(stream, {
  mimeType: 'audio/webm;codecs=opus',
  audioBitsPerSecond: 64000
});

recorder.start(30000); // 30-second timeslice
```

Audio constraints disable all processing to preserve raw audio for future analysis.

### Upload Queue

- Chunks are queued for upload as `dataavailable` events fire
- Upload with 3x retry and exponential backoff (1s, 2s, 4s)
- Track upload progress per chunk
- On permanent failure, log a `recording_event` with type `chunk_gap`

### Background Handling

- `visibilitychange` event handler: when tab is backgrounded, call `recorder.requestData()` to flush any buffered audio, then upload the partial chunk
- When tab returns to foreground, resume normal chunking

### WakeLock

Request a `WakeLock` via the Screen Wake Lock API to prevent the screen from turning off during active recording. Release on stop/pause.

```javascript
let wakeLock = null;
async function requestWakeLock() {
  if ('wakeLock' in navigator) {
    wakeLock = await navigator.wakeLock.request('screen');
  }
}
```

## UI

All UI lives on the session instance detail page.

### Record Button

- Visible when the session is active, or for admin users at any time
- Microphone icon button, consistent with existing UI style
- Tapping starts the recording flow (requests microphone permission on first use)

### Recording Status Indicator

- Pulsing red dot animation while recording
- Elapsed time counter (MM:SS)
- Chunk upload progress: "Uploading chunk 3/3..." or "All chunks uploaded"
- Connection status indicator

### Controls

- **Pause/Resume** — toggles recording, creates lifecycle events
- **Stop** — ends the recording, flushes final chunk, updates status

### Playback Section

- Listed below the tune log on the session instance detail page
- Shows all recordings for the instance with: recorder name, duration, date, source badge (`live` / `upload`)
- Play button generates presigned URLs and plays chunks in sequence
- Upload button to add a pre-recorded audio file

## Stage 1 Scope

**In scope:**
- Database schema (all 4 tables + history tables)
- API endpoints (all 6)
- Client-side recording (`SessionRecorder` class)
- S3 upload and storage
- Basic sequential playback via presigned URLs
- File upload and chunking

**Not in scope (future stages):**
- Tune detection / `recording_tune_segment` population
- Waveform visualization
- Synchronized multi-recording playback
- Offline queue (IndexedDB) for poor connectivity
- Storage lifecycle / cleanup policies
- Automatic format conversion for live recordings

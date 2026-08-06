<script>
  /**
   * Recordings for one session instance (spec 050, schema/053).
   *
   * The admin page at /admin/recordings does this across every session in the
   * system; this is the same job scoped to the night you are already looking at,
   * for the person who actually made the recording. Session and instance are
   * therefore not choices here — they are the log this modal was opened from,
   * which removes the two fields most likely to be got wrong.
   *
   * The upload is the same three calls as the admin page, and for the same
   * reason: the audio goes browser -> S3 directly, never through Flask, because
   * a three-hour master is ~350MB. Ingest (waveform + playback proxy) then runs
   * server-side for minutes, so the row appears immediately and reports its
   * stage while it fills itself in.
   */
  import { onDestroy } from 'svelte'

  let { sessionInstanceId, onclose } = $props()

  let recordings = $state([])
  let tuneCount = $state(0)
  let loading = $state(true)
  let error = $state('')

  // Upload form
  let file = $state(null)
  let label = $state('')
  let uploading = $state(false)
  let progress = $state(0)
  let stage = $state('')
  let steps = $state([])
  let stepAt = $state(null)
  let stepStatus = $state('processing')

  let pollTimer = null
  onDestroy(() => clearTimeout(pollTimer))

  function humanSize(bytes) {
    if (!bytes) return ''
    return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${(bytes / 1e6).toFixed(1)} MB`
  }

  function humanDuration(ms) {
    const total = Math.round((ms || 0) / 1000)
    const h = Math.floor(total / 3600)
    const m = Math.floor((total % 3600) / 60)
    const s = total % 60
    return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
             : `${m}:${String(s).padStart(2, '0')}`
  }

  async function load() {
    loading = true
    try {
      const res = await fetch(`/api/session-instances/${sessionInstanceId}/recordings`)
      const data = await res.json()
      if (!data.success) throw new Error(data.error || 'Could not load recordings')
      recordings = data.recordings || []
      tuneCount = data.tune_count || 0
      // Anything mid-ingest keeps the list honest without a manual refresh.
      if (recordings.some((r) => r.status && r.status !== 'ready')) {
        pollTimer = setTimeout(load, 4000)
      }
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }
  load()

  function pickFile(event) {
    error = ''
    file = event.target.files?.[0] || null
  }

  function putToS3(url, contentType, blob) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('PUT', url, true)
      // Signed into the URL, so it must match byte for byte.
      xhr.setRequestHeader('Content-Type', contentType)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) progress = (e.loaded / e.total) * 100
      }
      xhr.onload = () =>
        (xhr.status >= 200 && xhr.status < 300)
          ? resolve()
          : reject(new Error(`Object storage rejected the upload (HTTP ${xhr.status})`))
      // status 0 with no body is a blocked CORS preflight, which the browser
      // refuses to describe. Name the likely cause rather than "failed".
      xhr.onerror = () => reject(new Error(
        'The upload could not reach object storage. The bucket may be missing its CORS rule.'
      ))
      xhr.send(blob)
    })
  }

  async function pollIngest(recordingId) {
    const res = await fetch(`/api/recordings/${recordingId}/status`)
    const data = await res.json()
    if (!data.success) throw new Error(data.error || 'Lost track of that recording')
    steps = data.steps || []
    stepAt = data.step
    stepStatus = data.status
    if (data.status === 'ready') {
      stage = ''
      uploading = false
      file = null
      label = ''
      await load()
      return
    }
    if (data.status === 'failed') throw new Error(data.status_detail || 'Processing failed')
    if (data.stalled) throw new Error('Processing stopped partway — try again from this list.')
    stage = data.status_detail || 'working'
    pollTimer = setTimeout(() => pollIngest(recordingId).catch(fail), 3000)
  }

  function fail(e) {
    error = e.message
    uploading = false
    stage = ''
  }

  async function upload() {
    if (!file) return
    error = ''
    uploading = true
    progress = 0
    stage = 'Preparing…'
    steps = []
    stepAt = null

    try {
      const signRes = await fetch('/api/recordings/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_instance_id: sessionInstanceId, filename: file.name })
      })
      const signed = await signRes.json()
      if (!signRes.ok || !signed.success) throw new Error(signed.error || 'Could not prepare the upload')

      stage = 'Uploading…'
      await putToS3(signed.upload_url, signed.content_type, file)

      // Whatever the browser can read off the file's own metadata. Provisional:
      // ingest replaces it with the container's real duration.
      let durationMs = null
      try {
        durationMs = await new Promise((resolve) => {
          const url = URL.createObjectURL(file)
          const probe = new Audio()
          probe.preload = 'metadata'
          probe.onloadedmetadata = () => {
            URL.revokeObjectURL(url)
            resolve(isFinite(probe.duration) && probe.duration > 0 ? Math.round(probe.duration * 1000) : null)
          }
          probe.onerror = () => { URL.revokeObjectURL(url); resolve(null) }
          setTimeout(() => resolve(null), 5000)
          probe.src = url
        })
      } catch { /* not fatal — the server reads plenty the browser cannot */ }

      stage = 'Registering…'
      const createRes = await fetch('/api/recordings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_instance_id: sessionInstanceId,
          storage_key: signed.storage_key,
          label: label.trim() || null,
          duration_ms: durationMs
        })
      })
      const created = await createRes.json()
      if (!createRes.ok || !created.success) throw new Error(created.error || 'Could not register the recording')

      await load()               // the new row shows straight away, mid-ingest
      stage = 'Processing…'
      await pollIngest(created.recording_id)
    } catch (e) {
      fail(e)
    }
  }

  async function remove(recording) {
    const placed = recording.segment_count || 0
    const warning = placed
      ? `Delete “${recording.label}”?\n\nThis also deletes the ${placed} tune placement${placed === 1 ? '' : 's'}`
        + ' marked on it, and removes the audio from storage.\n\nThis cannot be undone.'
      : `Delete “${recording.label}”?\n\nNothing has been marked on it yet. The audio is removed from storage.`
        + '\n\nThis cannot be undone.'
    if (!window.confirm(warning)) return

    error = ''
    try {
      const res = await fetch(`/api/recordings/${recording.recording_id}`, { method: 'DELETE' })
      const data = await res.json()
      if (!data.success) throw new Error(data.error || 'Could not delete that recording')
      if (data.storage_warning) error = data.storage_warning
      await load()
    } catch (e) {
      error = e.message
    }
  }

  async function retry(recording) {
    error = ''
    try {
      const res = await fetch(`/api/recordings/${recording.recording_id}/reprocess`, { method: 'POST' })
      const data = await res.json()
      if (!data.success) throw new Error(data.error || 'Could not restart processing')
      await load()
    } catch (e) {
      error = e.message
    }
  }
</script>

<div class="drawer-scrim" role="button" tabindex="-1" aria-label="Close"
     onclick={onclose} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onclose()}></div>

<div class="assign-modal rec-modal" role="dialog" aria-modal="true" aria-label="Recordings">
  <div class="assign-head">Recordings</div>

  <div class="rec-body">
    {#if loading && !recordings.length}
      <p class="rec-empty">Loading…</p>
    {:else if !recordings.length}
      <p class="rec-empty">No audio uploaded for this night yet.</p>
    {/if}

    {#each recordings as r (r.recording_id)}
      <div class="rec-item">
        <div class="rec-name">{r.label || `recording ${r.recording_id}`}</div>
        <div class="rec-meta">
          {#if r.status === 'ready'}
            {humanDuration(r.duration_ms)}
            {#if r.file_size_bytes}· {humanSize(r.file_size_bytes)}{/if}
            · <b>{r.segment_count}</b> of {tuneCount} tunes placed
          {:else if r.status === 'failed'}
            <span class="rec-failed">Processing failed — {r.status_detail || 'no detail recorded'}</span>
          {:else}
            <span class="rec-working">Processing… {r.status_detail || ''}</span>
          {/if}
        </div>
        <div class="rec-actions">
          {#if r.status === 'ready'}
            <a class="hx-act" href={`/admin/recordings/${r.recording_id}/segment`}>Add timestamps</a>
          {:else if r.status === 'failed'}
            <button class="hx-act" onclick={() => retry(r)}>Retry</button>
          {/if}
          <button class="hx-act rec-danger" onclick={() => remove(r)}>Delete</button>
        </div>
      </div>
    {/each}
  </div>

  <div class="rec-upload">
    <!-- No session or date field: this modal belongs to one log, which is the
         whole reason it exists separately from the admin page. -->
    {#if uploading}
      <div class="rec-progress"><div class="rec-bar" style={`width:${progress}%`}></div></div>
      {#if steps.length && stepAt !== null}
        <ol class="rec-steps">
          {#each steps as s, i}
            <li class="rec-step {i < stepAt ? 'done' : i > stepAt ? 'todo' : (stepStatus === 'failed' ? 'failed' : 'current')}">
              <span class="rec-dot"></span>
            </li>
          {/each}
        </ol>
      {/if}
      <p class="rec-stage">{stage}</p>
    {:else}
      <input type="file" accept=".mp3,.m4a,.mp4,.aac,.wav,.ogg,.opus,.flac,.webm,audio/*" onchange={pickFile} />
      {#if file}
        <input class="rec-label" type="text" placeholder="Label (optional)" bind:value={label} />
        <button class="hx-act rec-go" onclick={upload}>Upload {humanSize(file.size)}</button>
      {/if}
    {/if}
  </div>

  {#if error}<p class="rec-error">{error}</p>{/if}

  <button class="hx-act rec-close" onclick={onclose}>Close</button>
</div>

<style>
  .rec-modal { width: min(94vw, 460px); max-height: 80vh; }
  .rec-body { overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
  .rec-empty { color: var(--muted); margin: 4px 0; font-size: 13px; }

  .rec-item {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .rec-name { font-weight: 600; font-size: 14px; overflow-wrap: anywhere; }
  .rec-meta { font-size: 12px; color: var(--muted); }
  .rec-failed { color: var(--danger, #dc3545); }
  .rec-working { font-style: italic; }
  .rec-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 2px; }
  .rec-danger { color: var(--danger, #dc3545); }

  .rec-upload {
    border-top: 1px solid var(--border);
    padding-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .rec-label {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 7px;
    color: var(--text);
    padding: 6px 8px;
    font: inherit;
  }
  .rec-go { align-self: flex-start; }

  .rec-progress { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
  .rec-bar { height: 100%; background: var(--accent); transition: width 0.2s ease; }
  .rec-stage { font-size: 12px; color: var(--muted); margin: 0; }

  /* Same stage model as the admin page, dots only — the sentence below says
     which stage, and a modal this narrow has no room for six labels. */
  .rec-steps { display: flex; list-style: none; margin: 0; padding: 0; }
  .rec-step { flex: 1 1 0; position: relative; }
  .rec-step::before {
    content: "";
    position: absolute;
    top: calc((10px - 2px) / 2);
    right: 50%;
    left: -50%;
    height: 2px;
    background: var(--border);
  }
  .rec-step:first-child::before { display: none; }
  .rec-step.done::before, .rec-step.current::before { background: var(--accent); }
  .rec-step.failed::before { background: var(--danger, #dc3545); }
  .rec-dot {
    position: relative;
    z-index: 1;
    display: block;
    box-sizing: border-box;
    width: 10px;
    height: 10px;
    margin: 0 auto;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--panel);
  }
  .rec-step.done .rec-dot { border-color: var(--accent); background: var(--accent); }
  .rec-step.current .rec-dot { border-color: var(--accent); }
  .rec-step.failed .rec-dot { border-color: var(--danger, #dc3545); background: var(--danger, #dc3545); }

  .rec-error { color: var(--danger, #dc3545); font-size: 12px; margin: 0; }
  .rec-close { align-self: flex-end; }
</style>

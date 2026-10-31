<script>
  // i18n-converted
  // Spec 061 stage 2: the web can hear. A plain page: it streams what this device
  // hears (or a recording file) to the listening service and shows the answers as
  // they arrive, with everything the browser did along the way in a log, because
  // this stage is for finding out what a phone at a session really does.
  import { onDestroy } from 'svelte'
  import { t, tuneTypeName, formatNumber } from '../lib/i18n/index.js'
  import { ListenLink, SAMPLE_RATE } from './link.js'
  import { startCapture } from './capture.js'

  let source = $state('mic')
  let file = $state(null)
  let running = $state(false)
  let starting = $state(false)
  let status = $state('idle')
  let statusDetail = $state('')
  let clockS = $state(0)
  let backlogS = $state(0)
  let level = $state(0)
  let answers = $state(0)
  let current = $state(null) // the last state
  let log = $state([]) // [{at, text}]
  let copied = $state(false)

  let link = null
  let capture = null
  let startedAt = 0
  let tick = null

  const STATUS = {
    idle: () => t('Not listening'),
    connecting: () => t('Connecting…'),
    live: () => t('Connected'),
    reconnecting: () => t('Reconnecting…'),
    refused: () => t('Not allowed'),
    stopped: () => t('Stopped'),
  }

  function clock(s) {
    const total = Math.max(0, Math.floor(s))
    const h = Math.floor(total / 3600)
    const m = Math.floor((total % 3600) / 60)
    const sec = String(total % 60).padStart(2, '0')
    return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
  }

  function note(text) {
    const at = startedAt ? (performance.now() - startedAt) / 1000 : 0
    log = [...log.slice(-499), { at, text }]
  }

  async function connect() {
    const r = await fetch('/api/listen/connection', { credentials: 'same-origin' })
    const body = await r.json().catch(() => ({}))
    if (r.status === 401 || r.status === 403) {
      const e = new Error(body.message || t("You can't listen on Ceol's server."))
      e.refused = true
      throw e
    }
    if (!r.ok || !body.success) throw new Error(body.message || `HTTP ${r.status}`)
    return body
  }

  const onOnline = () => {
    note(t('Back online.'))
    link && link.nudge()
  }
  const onOffline = () => note(t('Offline.'))

  async function start() {
    if (source === 'file' && !file) return
    starting = true
    log = []
    current = null
    answers = 0
    startedAt = performance.now()
    link = new ListenLink({
      connect,
      streamId: crypto.randomUUID(),
      onState: (m) => {
        current = m
        answers += 1
      },
      onStatus: (s, detail) => {
        status = s
        statusDetail = detail || ''
        if (s === 'refused') note(detail || t("You can't listen on Ceol's server."))
      },
      onEvent: note,
    })
    try {
      capture = await startCapture({
        source: source === 'mic' ? 'mic' : file,
        onChunk: (offset, pcm) => link.push(offset, pcm),
        onLevel: (l) => (level = l),
        onEvent: note,
        onEnded: () => {
          note(t('The file has finished.'))
          stop()
        },
      })
    } catch (e) {
      note(source === 'mic' ? t("Couldn't use the microphone: {error}", { error: e.message }) : t("Couldn't play the file: {error}", { error: e.message }))
      link = null
      starting = false
      return
    }
    link.start()
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    tick = setInterval(() => {
      clockS = capture ? capture.captured() / SAMPLE_RATE : 0
      backlogS = link ? link.backlog() / SAMPLE_RATE : 0
    }, 500)
    running = true
    starting = false
  }

  async function stop() {
    if (!running) return
    running = false
    clearInterval(tick)
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    if (link) {
      const s = link.stats
      note(t('Stopped. Answers: {states}. Reconnects: {reconnects}. Gaps: {skips}.', { states: s.states, reconnects: s.reconnects, skips: s.skips }))
      link.stop()
    }
    if (capture) await capture.stop()
    capture = null
    level = 0
  }

  async function copyLog() {
    const text = log.map((l) => `${clock(l.at)}  ${l.text}`).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      copied = true
      setTimeout(() => (copied = false), 2000)
    } catch {}
  }

  onDestroy(() => {
    stop()
  })

  const shownTune = $derived(current && current.shown != null ? (current.top || []).find((x) => x.tune_id === current.shown) : null)
  const shownName = $derived(
    current && current.shown != null
      ? (shownTune && shownTune.name) || ((current.history || []).find((h) => h.tune_id === current.shown) || {}).name || `#${current.shown}`
      : null
  )
  const pct = (p) => formatNumber(p, { style: 'percent', maximumFractionDigits: 0 })
</script>

<div class="lt">
  <h1 class="lt-title">{t('Listen test')}</h1>
  <p class="lt-intro">{t("Sends what this device hears to Ceol's server, and shows what the server thinks is playing. Keep this page open and the screen on.")}</p>

  <div class="kit-group">
    <div class="kit-check-field">
      <label class="kit-check-label" for="lt-mic">
        <input type="radio" id="lt-mic" name="lt-source" value="mic" bind:group={source} disabled={running || starting} />
        {t('The microphone')}
      </label>
    </div>
    <div class="kit-check-field">
      <label class="kit-check-label" for="lt-file">
        <input type="radio" id="lt-file" name="lt-source" value="file" bind:group={source} disabled={running || starting} />
        {t('A recording file')}
      </label>
    </div>
    {#if source === 'file'}
      <div class="kit-field">
        <input type="file" id="lt-file-input" accept="audio/*" disabled={running || starting} onchange={(e) => (file = e.currentTarget.files[0] || null)} />
      </div>
    {/if}
  </div>

  {#if running}
    <button type="button" class="lt-button lt-stop" id="lt-stop" onclick={stop}>{t('Stop')}</button>
  {:else}
    <button type="button" class="lt-button" id="lt-start" onclick={start} disabled={starting || (source === 'file' && !file)}>
      {starting ? t('Starting…') : t('Start Listening')}
    </button>
  {/if}

  <h3 class="kit-group-head">{t('Connection')}</h3>
  <div class="kit-group" id="lt-status">
    <div class="kit-field">
      <span class="kit-field-label">{t('Server')}</span>
      <span class="kit-field-value" class:lt-warn={status === 'reconnecting' || status === 'refused'} id="lt-connection">
        {(STATUS[status] || STATUS.idle)()}{statusDetail && status === 'reconnecting' ? ` (${statusDetail})` : ''}
      </span>
    </div>
    <div class="kit-field">
      <span class="kit-field-label">{t('Time listening')}</span>
      <span class="kit-field-value lt-num" id="lt-clock">{clock(clockS)}</span>
    </div>
    <div class="kit-field">
      <span class="kit-field-label">{t('Still to send')}</span>
      <span class="kit-field-value lt-num" class:lt-warn={backlogS > 10} id="lt-backlog">{t('{seconds}s', { seconds: backlogS.toFixed(1) })}</span>
    </div>
    <div class="kit-field">
      <span class="kit-field-label">{t('Level')}</span>
      <span class="lt-level" aria-hidden="true"><span style:width="{Math.min(100, Math.round(level * 400))}%"></span></span>
    </div>
    <div class="kit-field">
      <span class="kit-field-label">{t('Answers')}</span>
      <span class="kit-field-value lt-num" id="lt-answers">{answers}</span>
    </div>
  </div>

  <h3 class="kit-group-head">{t('Playing now')}</h3>
  <div class="kit-group" id="lt-now">
    {#if !current}
      <div class="kit-field"><span class="kit-field-value is-empty">{t('The first answer comes after a few seconds of audio.')}</span></div>
    {:else}
      <div class="kit-field">
        <span class="kit-field-label lt-shown" id="lt-shown">{shownName || t('No tune yet')}</span>
        {#if shownTune}<span class="kit-field-value lt-num">{pct(shownTune.p)}</span>{/if}
      </div>
      {#each current.top || [] as tune (tune.tune_id)}
        <div class="kit-field lt-top">
          <span class="kit-field-label">{tune.name || `#${tune.tune_id}`} <span class="lt-type">{tuneTypeName(tune.type) || ''}</span></span>
          <span class="kit-field-value lt-num">{pct(tune.p)}</span>
        </div>
      {/each}
      <div class="kit-field lt-top">
        <span class="kit-field-label">{t('Not a tune')}</span>
        <span class="kit-field-value lt-num">{pct(current.none || 0)}</span>
      </div>
      <p class="kit-field-help lt-meta">
        {t('At {clock}. Sounds like a tune: {tuneness}. Answered {lag}s behind, in {compute}s.', {
          clock: clock((current.t_ms || 0) / 1000),
          tuneness: pct(current.tuneness || 0),
          lag: ((current.lag_ms || 0) / 1000).toFixed(1),
          compute: ((current.compute_ms || 0) / 1000).toFixed(1),
        })}
      </p>
    {/if}
  </div>

  {#if current && (current.history || []).length}
    <h3 class="kit-group-head">{t('Heard so far')}</h3>
    <div class="kit-group" id="lt-history">
      {#each [...current.history].reverse() as h (h.from_ms + ':' + h.tune_id)}
        <div class="kit-field">
          <span class="kit-field-label">{h.name || `#${h.tune_id}`}</span>
          <span class="kit-field-value lt-num">{clock(h.from_ms / 1000)}</span>
        </div>
      {/each}
    </div>
  {/if}

  <h3 class="kit-group-head lt-log-head">
    {t('What happened')}
    {#if log.length}
      <button type="button" class="lt-copy" onclick={copyLog}>{copied ? t('Copied') : t('Copy')}</button>
    {/if}
  </h3>
  <div class="kit-group lt-log" id="lt-log">
    {#each log as line, i (i)}
      <div class="lt-log-line"><span class="lt-num lt-log-at">{clock(line.at)}</span> {line.text}</div>
    {:else}
      <div class="kit-field"><span class="kit-field-value is-empty">{t('Nothing yet.')}</span></div>
    {/each}
  </div>
</div>

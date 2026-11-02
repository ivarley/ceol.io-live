<script>
  // i18n-converted
  // Listen (spec 061 stage 3): the certainty meter as the iPhone shows it, in Ad-hoc
  // mode. It says what is playing and how sure it is; you can tap the right tune, say
  // none of them is, and once it is sure, say it is wrong or the tune has changed.
  // When sure, the tune's place in your tunebook, and from an "Add a tune" search the
  // one thing that search was for: add it to the session's list, or log it.
  //
  // The browser streams what it hears to the listening service (the stage 2 link and
  // capture, ../listentest/), which decides. Nothing is recorded or logged unless you
  // say so. Recent Tunes Heard is kept in this browser.
  import { onDestroy } from 'svelte'
  import { t, formatDate, formatNumber, tuneTypeName } from '../lib/i18n/index.js'
  import { ListenLink, SAMPLE_RATE } from '../listentest/link.js'
  import { startCapture } from '../listentest/capture.js'
  import { Meter, bar, candidates, addRecent, loadRecent, saveRecent } from './meter.js'
  import TunebookBox from './TunebookBox.svelte'

  let { payload = {} } = $props()
  const context = $derived(payload.context || null)

  let phase = $state('idle') // idle | starting | running
  let status = $state('idle') // the link's: connecting | live | reconnecting | refused | stopped
  let error = $state('')
  let clockS = $state(0)
  let backlogS = $state(0)
  let lagS = $state(0)
  let version = $state(0) // bumped whenever the meter changes
  let recent = $state(loadRecent())
  let action = $state('idle') // the context action: idle | busy | done | failed
  let actionError = $state('')
  let actionFor = $state(null) // the tune the action was done for
  let elsewhere = $state(null) // thesession.org's page for a tune, when a new tab was blocked

  const meter = new Meter()
  let link = null
  let capture = null
  let tick = null

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

  function remember(c) {
    recent = addRecent(recent, { tune_id: c.tune_id, name: c.name || null, type: c.type || null, heard_at: Date.now() })
    saveRecent(recent)
  }

  function received(s) {
    const sure = meter.received(s)
    if (sure) remember(sure)
    lagS = (s.lag_ms || 0) / 1000
    version++
  }

  const onOnline = () => link && link.nudge()

  async function start() {
    if (phase !== 'idle') return
    phase = 'starting'
    error = ''
    status = 'connecting'
    link = new ListenLink({
      connect,
      streamId: crypto.randomUUID(),
      instanceId: context && context.kind === 'night' ? context.instance_id : null,
      onState: received,
      onStatus: (s, detail) => {
        status = s
        if (s === 'refused') error = detail || t("You can't listen on Ceol's server.")
      },
    })
    try {
      capture = await startCapture({
        source: 'mic',
        onChunk: (offset, pcm) => link.push(offset, pcm),
      })
    } catch (e) {
      error =
        e && e.name === 'NotAllowedError'
          ? t('Ceol needs the microphone to listen. Allow it in your browser’s settings for this site.')
          : t("Couldn't use the microphone: {error}", { error: e.message })
      link = null
      phase = 'idle'
      status = 'idle'
      return
    }
    link.start()
    window.addEventListener('online', onOnline)
    tick = setInterval(() => {
      clockS = capture ? capture.captured() / SAMPLE_RATE : 0
      backlogS = link ? link.backlog() / SAMPLE_RATE : 0
    }, 500)
    phase = 'running'
  }

  async function stop() {
    if (phase !== 'running') return
    phase = 'idle'
    clearInterval(tick)
    window.removeEventListener('online', onOnline)
    if (link) link.stop()
    link = null
    if (capture) await capture.stop()
    capture = null
    clockS = 0
    backlogS = 0
    Object.assign(meter, new Meter())
    status = 'idle'
    version++
  }

  function send(message) {
    if (message && link) link.send(message)
    version++
  }

  function tapThis(c) {
    send(meter.tapThis(c.tune_id))
    remember(c)
  }

  async function doAction(tuneId, name) {
    if (!context || action === 'busy') return
    action = 'busy'
    actionError = ''
    actionFor = tuneId
    try {
      let r
      if (context.kind === 'session') {
        r = await fetch(`/api/sessions/${context.session_path}/tunes`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ thesession_id: tuneId }),
        })
      } else {
        r = await fetch(`/api/live/instances/${context.instance_id}/ops`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ op_id: crypto.randomUUID(), op_type: 'add_tune', tune_id: tuneId, name }),
        })
      }
      const body = await r.json().catch(() => ({}))
      // 409: it is on the session's list already, which is what was wanted
      if ((r.ok && body.success !== false && !body.rejected) || (context.kind === 'session' && r.status === 409)) {
        action = 'done'
      } else {
        action = 'failed'
        actionError = body.reason || body.message || body.error || t("That wasn't saved. Try again.")
      }
    } catch {
      action = 'failed'
      actionError = t("Couldn't reach Ceol, so that wasn't saved. Check your connection and try again.")
    }
  }

  // The app-wide tune sheet (base.html loads it on every page), for a tune Ceol holds.
  // The listener knows every tune on thesession.org, and Ceol imports one only when
  // someone adds it, so a tune it doesn't hold yet opens on thesession.org instead.
  async function openTune(tuneId) {
    elsewhere = null
    let held = true
    try {
      held = (await fetch(`/api/tunes/${tuneId}/detail`, { credentials: 'same-origin' })).status !== 404
    } catch {}
    if (held && window.TuneDetailModal) {
      window.TuneDetailModal.show({ tuneId })
      return
    }
    const url = `https://thesession.org/tunes/${tuneId}`
    // not 'noopener', which makes open() return null even when the tab opened
    const tab = window.open(url, '_blank')
    if (tab) {
      tab.opener = null
      return
    }
    // a blocked new tab: leaving this page would stop the listening
    if (phase === 'running') elsewhere = url
    else window.location.href = url
  }

  function clearRecent() {
    recent = []
    saveRecent(recent)
  }

  onDestroy(() => {
    stop()
  })

  function clock(s) {
    const total = Math.max(0, Math.floor(s))
    const h = Math.floor(total / 3600)
    const m = Math.floor((total % 3600) / 60)
    const sec = String(total % 60).padStart(2, '0')
    return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
  }
  const pct = (p) => formatNumber(p || 0, { style: 'percent', maximumFractionDigits: 0 })
  const tuneName = (c) => c.name || t('Tune {id}', { id: c.tune_id })

  function heardAt(ms) {
    const d = new Date(ms)
    const time = formatDate(d, { hour: '2-digit', minute: '2-digit' })
    if (d.toDateString() === new Date().toDateString()) return t('Today, {time}', { time })
    return formatDate(d, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  }

  // What the meter shows. The Meter is a plain object; `version` is bumped after
  // every change to it, so this follows it.
  const view = $derived.by(() => {
    version
    const s = meter.state
    const sureId = meter.confirmed
    const mine = s && sureId != null ? (s.top || []).find((c) => c.tune_id === sureId) : null
    return {
      showing: meter.showing,
      state: s,
      rows: s ? candidates(s) : [],
      wasName: meter.wasName,
      changed: meter.mayHaveChanged,
      sureId,
      sureName: meter.confirmedName || (sureId != null ? t('Tune {id}', { id: sureId }) : ''),
      sureType: meter.confirmedType,
      sureNew: !!(mine && mine.outside && context && context.kind === 'night'),
    }
  })
  const showing = $derived(view.showing)
  const state = $derived(view.state)
  const rows = $derived(view.rows)
  const wasName = $derived(view.wasName)
  const changed = $derived(view.changed)
  const sureId = $derived(view.sureId)
  const sureName = $derived(view.sureName)
  const sureType = $derived(view.sureType)
  const sureNew = $derived(view.sureNew)

  // A new sure tune: the context action starts over.
  $effect(() => {
    if (sureId != null && sureId !== actionFor && action !== 'busy') {
      action = 'idle'
      actionError = ''
    }
  })

  const linkText = $derived.by(() => {
    if (status === 'connecting') return t('Connecting to the listener…')
    if (status === 'reconnecting') return t('Reconnecting to the listener…')
    if (status === 'refused') return t('Not allowed to listen')
    if (backlogS > 8 || lagS > 8) return t('Catching up, {n} s behind', { n: Math.round(Math.max(backlogS, lagS)) })
    return t('Listening')
  })

  const contextTitle = $derived(
    !context
      ? ''
      : context.kind === 'night'
        ? t('{session}, {date}', { session: context.session_name, date: formatDate(context.date, { weekday: 'short', day: 'numeric', month: 'short' }) })
        : context.session_name
  )
</script>

<div class="lp">
  {#if context}
    <a class="lp-back" href={context.back} id="lp-back">‹ {t('Back to {where}', { where: contextTitle })}</a>
  {/if}
  <div class="lp-head">
    <h1 class="lp-title">{phase === 'running' ? t('Listening') : t('Listen')}</h1>
    {#if phase === 'running'}
      <button type="button" class="lp-stop" id="lp-stop" onclick={stop}>{t('Stop')}</button>
    {/if}
  </div>

  {#if phase !== 'running'}
    <p class="lp-intro">{t('Tell me what tune is playing. Nothing is logged unless you say so.')}</p>
    <p class="lp-note">{t("Ceol's server does the listening. Keep this page open and the screen on.")}</p>
    {#if error}<p class="lp-error" role="alert" id="lp-error">{error}</p>{/if}
    <button type="button" class="lp-start" id="lp-start" onclick={start} disabled={phase === 'starting'}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8.5a6.5 6.5 0 1 1 13 0c0 6-6 6-6 10a3.5 3.5 0 1 1-7 0" /><path d="M15 8.5a2.5 2.5 0 0 0-5 0v1a2 2 0 1 1 0 4" /></svg>
      {phase === 'starting' ? t('Starting…') : t('Start Listening')}
    </button>
  {:else}
    <div class="lp-status">
      <span class="lp-dot" class:is-off={status !== 'live'} aria-hidden="true"></span>
      <span class="lp-num">{clock(clockS)}</span>
      {#if state && state.tuneness != null}
        <span class="lp-tuneness">{t('sounds like a tune {n}%', { n: Math.round(state.tuneness * 100) })}</span>
      {/if}
    </div>
    <p class="lp-linktext" class:lp-warn={status === 'reconnecting' || status === 'refused'} id="lp-link">{linkText}</p>
    {#if error}<p class="lp-error" role="alert">{error}</p>{/if}

    <div class="lp-meter" id="lp-meter" data-showing={showing}>
      {#if showing === 'waiting'}
        <p class="lp-big"><span class="lp-spinner" aria-hidden="true"></span>{t('Starting up…')}</p>
      {:else if showing === 'noTune'}
        <p class="lp-big">{t('No tune playing')}</p>
        <p class="lp-sub lp-num">{pct(state.none)}</p>
      {:else if showing === 'figuring'}
        <p class="lp-big"><span class="lp-spinner" aria-hidden="true"></span>{t('Figuring out the tune…')}</p>
        {#if changed && wasName}
          <p class="lp-sub">{t('The tune may have changed (was {name}).', { name: wasName })}</p>
        {/if}
        <div class="lp-rows" id="lp-candidates">
          {#each rows as c (c.tune_id)}
            <button type="button" class="lp-row" class:is-weak={c.weak} class:is-shown={c.tune_id === state.shown && !changed} onclick={() => tapThis(c)}>
              <span class="lp-row-text">
                <span class="lp-row-name">{tuneName(c)}</span>
                <span class="lp-row-meta">
                  {[tuneTypeName(c.type), c.outside && context && context.kind === 'night' ? t('new to this session') : null, pct(c.p)].filter(Boolean).join(' · ')}
                </span>
              </span>
              <span class="lp-bar" role="img" aria-label={t('{n} percent', { n: Math.round(c.p * 100) })}>
                {#each bar(c.p) as cell, i (i)}<span class="lp-cell is-{cell}"></span>{/each}
              </span>
            </button>
          {/each}
        </div>
        <button type="button" class="lp-none" id="lp-none" disabled={!rows.length} onclick={() => send(meter.tapNone())}>{t('None of these')}</button>
      {:else}
        <div class="lp-sure" id="lp-sure">
          <svg class="lp-check" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M7.5 12.5l3 3 6-6.5" /></svg>
          <span class="lp-sure-text">
            <span class="lp-sure-name" id="lp-sure-name">{sureName}</span>
            {#if sureType || sureNew}
              <span class="lp-row-meta">{[tuneTypeName(sureType), sureNew ? t('new to this session') : null].filter(Boolean).join(' · ')}</span>
            {/if}
          </span>
        </div>
        <div class="lp-sure-taps">
          <button type="button" id="lp-wrong" onclick={() => send(meter.wrongTune())}>{t('Wrong tune')}</button>
          <button type="button" id="lp-changed" onclick={() => send(meter.tuneChanged())}>{t('Tune changed')}</button>
        </div>

        {#key sureId}
          <TunebookBox tuneId={sureId} />
        {/key}

        {#if context}
          <button type="button" class="lp-action" id="lp-action" class:is-done={action === 'done'} disabled={action === 'busy' || action === 'done'} onclick={() => doAction(sureId, sureName)}>
            {#if context.kind === 'session'}
              {action === 'done' ? '✓ ' + t("Added to this session's tune list") : t("Add To This Session's Tune List")}
            {:else}
              {action === 'done' ? '✓ ' + t('Logged') : t('Log This Tune')}
            {/if}
          </button>
          {#if actionError}<p class="lp-error" role="alert">{actionError}</p>{/if}
        {/if}
        <button type="button" class="lp-link" id="lp-open" onclick={() => openTune(sureId)}>{t('Open the tune')}</button>
      {/if}
    </div>

    {#if state && (state.history || []).length}
      <h3 class="kit-group-head">{t('Shown so far')}</h3>
      <div class="lp-history">
        {#each [...state.history].reverse() as h (h.from_ms + ':' + h.tune_id)}
          <div class="lp-history-line"><span class="lp-num">{clock(h.from_ms / 1000)}</span> · {h.name || t('Tune {id}', { id: h.tune_id })}</div>
        {/each}
      </div>
    {/if}
  {/if}

  {#if elsewhere}
    <p class="lp-note" id="lp-elsewhere"><a href={elsewhere} target="_blank" rel="noopener">{t('Open this tune on thesession.org')}</a></p>
  {/if}

  <div class="lp-recent-head">
    <h3 class="kit-group-head">{t('Recent Tunes Heard')}</h3>
    {#if recent.length}<button type="button" class="lp-link" id="lp-recent-clear" onclick={clearRecent}>{t('Clear')}</button>{/if}
  </div>
  <div class="lp-recent" id="lp-recent">
    {#each recent as r (r.heard_at + ':' + r.tune_id)}
      <button type="button" class="lp-recent-row" onclick={() => openTune(r.tune_id)}>
        <span class="lp-row-text">
          <span class="lp-row-name">{r.name || t('Tune {id}', { id: r.tune_id })}</span>
          <span class="lp-row-meta">{heardAt(r.heard_at)}</span>
        </span>
        {#if r.type}<span class="lp-type">{tuneTypeName(r.type)}</span>{/if}
      </button>
    {:else}
      <p class="lp-empty">{t('Nothing heard yet. Tunes the meter is sure of will be listed here.')}</p>
    {/each}
  </div>
</div>

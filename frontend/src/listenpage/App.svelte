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
  import { t, formatDate, tuneTypeName } from '../lib/i18n/index.js'
  import { addRecent, loadRecent, saveRecent } from './meter.js'
  import { Listening, openTune as openTuneSheet } from './listening.svelte.js'
  import MeterView from './MeterView.svelte'
  import TunebookBox from './TunebookBox.svelte'

  let { payload = {} } = $props()
  const context = $derived(payload.context || null)

  let recent = $state(loadRecent())
  let action = $state('idle') // the context action: idle | busy | done | failed
  let actionError = $state('')
  let actionFor = $state(null) // the tune the action was done for
  let elsewhere = $state(null) // thesession.org's page for a tune, when a new tab was blocked

  function remember(c) {
    recent = addRecent(recent, { tune_id: c.tune_id, name: c.name || null, type: c.type || null, heard_at: Date.now() })
    saveRecent(recent)
  }

  const listening = new Listening({ onSure: (pick) => remember(pick.tune) })
  const phase = $derived(listening.phase)

  function start() {
    return listening.start({ instanceId: context && context.kind === 'night' ? context.instance_id : null })
  }

  function tapThis(c) {
    listening.send(listening.meter.tapThis(c.tune_id))
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

  async function openTune(tuneId) {
    elsewhere = null
    elsewhere = await openTuneSheet(tuneId, { listening: phase === 'running' })
  }

  function clearRecent() {
    recent = []
    saveRecent(recent)
  }

  onDestroy(() => {
    listening.stop()
  })

  function heardAt(ms) {
    const d = new Date(ms)
    const time = formatDate(d, { hour: '2-digit', minute: '2-digit' })
    if (d.toDateString() === new Date().toDateString()) return t('Today, {time}', { time })
    return formatDate(d, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  }

  // A new sure tune: the context action starts over.
  $effect(() => {
    listening.version
    const sureId = listening.meter.confirmed
    if (sureId != null && sureId !== actionFor && action !== 'busy') {
      action = 'idle'
      actionError = ''
    }
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
      <button type="button" class="lp-stop" id="lp-stop" onclick={() => listening.stop()}>{t('Stop')}</button>
    {/if}
  </div>

  {#if phase !== 'running'}
    <p class="lp-intro">{t('Tell me what tune is playing. Nothing is logged unless you say so.')}</p>
    <p class="lp-note">{t("Ceol's server does the listening. Keep this page open and the screen on.")}</p>
    {#if listening.error}<p class="lp-error" role="alert" id="lp-error">{listening.error}</p>{/if}
    <button type="button" class="lp-start" id="lp-start" onclick={start} disabled={phase === 'starting'}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8.5a6.5 6.5 0 1 1 13 0c0 6-6 6-6 10a3.5 3.5 0 1 1-7 0" /><path d="M15 8.5a2.5 2.5 0 0 0-5 0v1a2 2 0 1 1 0 4" /></svg>
      {phase === 'starting' ? t('Starting…') : t('Start Listening')}
    </button>
  {:else}
    <MeterView {listening} night={!!context && context.kind === 'night'} onTapThis={tapThis}>
      {#snippet sure(tune)}
        {#key tune.id}
          <TunebookBox tuneId={tune.id} />
        {/key}

        {#if context}
          <button type="button" class="lp-action" id="lp-action" class:is-done={action === 'done'} disabled={action === 'busy' || action === 'done'} onclick={() => doAction(tune.id, tune.name)}>
            {#if context.kind === 'session'}
              {action === 'done' ? '✓ ' + t("Added to this session's tune list") : t("Add To This Session's Tune List")}
            {:else}
              {action === 'done' ? '✓ ' + t('Logged') : t('Log This Tune')}
            {/if}
          </button>
          {#if actionError}<p class="lp-error" role="alert">{actionError}</p>{/if}
        {/if}
        <button type="button" class="lp-link" id="lp-open" onclick={() => openTune(tune.id)}>{t('Open the tune')}</button>
      {/snippet}
    </MeterView>
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

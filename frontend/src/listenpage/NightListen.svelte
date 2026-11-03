<script>
  // i18n-converted
  // Listen on a night's logger: Log mode (spec 061 stage 4). The meter logs the tunes it
  // is sure of to this night, through the logger's own ops (the page passes onLog,
  // onRemove and onEndSet), so the rows arrive like any other logger's and several
  // phones, of either kind, can log one night together. As on the iPhone
  // (NightRecorder.swift):
  //   - a tune it is sure of at 100% is logged by itself when "Log automatically at
  //     100%" is on; otherwise "Log This Tune" logs it, and so does tapping a candidate;
  //   - before logging, the night's latest set is checked: if it already ends with the
  //     tune (last or second-to-last), someone else logged it, and no row is added;
  //   - the tune logged last, sure again, is not logged twice, and no tune is logged by
  //     itself twice within ten minutes;
  //   - "Wrong tune" takes back the row this page added (not someone else's);
  //   - a long enough stretch of no tune ends the set (by itself with the switch on,
  //     or with "End the set").
  // "Stop logging" goes on listening in Ad-hoc mode: the sure tune's place in your
  // list, nothing logged. While it listens, a strip in the logger's dock says so, and
  // opens the meter.
  //
  // Recording (stage 5): for those who manage the session's recordings, "Listen and
  // log" first offers "Record this night" (on, as on the iPhone). With it on, Ceol's
  // server keeps the sound it is sent and files it as the night's recording when the
  // listening stops (listen/recording.py); the browser keeps none. It goes on through
  // "Stop logging": it is the night's.
  import { onDestroy } from 'svelte'
  import { Dialog, Sheet } from '../lib/index.js'
  import { t, tc } from '../lib/i18n/index.js'
  import { latestSetEndsWith } from './meter.js'
  import { Listening, clock, openTune as openTuneSheet } from './listening.svelte.js'
  import MeterView from './MeterView.svelte'
  import TunebookBox from './TunebookBox.svelte'
  import './page.css'

  let {
    instanceId,
    title = '', // the night, as "Logging tunes to {night}" names it
    ordered = [], // the night's rows in order, as the logger shows them
    canLog = true, // may log to this night now (signed in with the right, not marked complete)
    canRecord = false, // may file a recording under this night (manages the session's recordings)
    onLog = () => null, // (tune) => {row} | {already: true} | null
    onRemove = () => {}, // (row) the row this page added
    onEndSet = () => {},
    running = $bindable(false), // the microphone is on
    logging = $bindable(false), // Log mode
  } = $props()

  const AUTO_KEY = 'ceol.listenLogsAt100'
  function loadAuto() {
    try {
      return globalThis.localStorage.getItem(AUTO_KEY) !== '0'
    } catch {
      return true
    }
  }
  let logsAt100 = $state(loadAuto())
  function setAuto(on) {
    logsAt100 = on
    try {
      globalThis.localStorage.setItem(AUTO_KEY, on ? '1' : '0')
    } catch {}
  }

  let open = $state(false)
  let askStopLogging = $state(false)
  let askStop = $state(false)
  let elsewhere = $state(null)
  let failed = $state('') // a log that didn't go
  let recordNight = $state(true)

  const listening = new Listening({
    onSure: (pick) => {
      if (pick.log && logsAt100 && logging) logTune(pick.tune)
    },
    onState: () => {
      if (logsAt100 && logging && listening.meter.canEndSet(ordered)) onEndSet()
    },
  })

  $effect(() => {
    running = listening.phase !== 'idle'
  })

  // Marked complete (or the right gone) while logging: logging stops, listening goes on.
  $effect(() => {
    if (!canLog && logging) stopLogging()
  })

  // Leaving the page stops the microphone: ask first.
  $effect(() => {
    if (!running) return
    const warn = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  })

  /** "Listen and log": start listening to this night, or log again after "Stop logging".
   * Someone who may record it first sees the start, with "Record this night". */
  export async function begin() {
    open = true
    logging = canLog
    if (listening.phase === 'idle' && !(canRecord && canLog)) await startListening()
  }

  async function startListening() {
    logging = canLog
    await listening.start({ instanceId, record: canRecord && canLog && recordNight, title })
    if (listening.phase === 'idle') logging = false // the microphone was refused
  }

  /** Show the meter (the search's Listen link, while listening). */
  export function show() {
    open = true
  }

  function logTune(c) {
    const meter = listening.meter
    if (!logging || meter.logged === c.tune_id) return
    failed = ''
    if (latestSetEndsWith(c.tune_id, ordered)) {
      meter.markLogged(c.tune_id, null)
    } else {
      const r = onLog({ tune_id: c.tune_id, name: c.name || null, type: c.type || null })
      if (!r) {
        failed = t("That wasn't logged. Try again.")
        return
      }
      meter.markLogged(c.tune_id, r.already ? null : r.row)
    }
    listening.version++
  }

  function tapThis(c) {
    listening.send(listening.meter.tapThis(c.tune_id))
    logTune(c)
  }

  function wrong() {
    const meter = listening.meter
    const row = meter.confirmed != null && meter.confirmed === meter.logged ? meter.loggedRow : null
    listening.send(meter.wrongTune())
    if (row) onRemove(row)
  }

  function stopLogging() {
    logging = false
    listening.meter.forgetLogged()
    listening.version++
  }

  async function stop() {
    open = false
    logging = false
    await listening.stop()
  }

  async function openTune(tuneId) {
    elsewhere = await openTuneSheet(tuneId, { listening: running })
  }

  onDestroy(() => {
    listening.stop()
  })

  const view = $derived.by(() => {
    listening.version
    const meter = listening.meter
    const showing = meter.showing
    let headline
    if (listening.error) headline = listening.error
    else if (showing === 'waiting') headline = t('Starting up…')
    else if (showing === 'noTune') headline = t('No tune playing')
    else if (showing === 'figuring') headline = t('Figuring out the tune…')
    else headline = meter.confirmedName || t('Tune {id}', { id: meter.confirmed })
    return {
      showing,
      headline,
      sureId: meter.confirmed,
      logged: meter.logged,
      canEndSet: logging && meter.canEndSet(ordered),
    }
  })
</script>

{#if running}
  <div class="nl-strip" id="nl-strip">
    <button type="button" class="nl-open" onclick={() => (open = true)} aria-label={t('Listening, {what}. Show the meter.', { what: view.headline })}>
      <span class="lp-dot" class:is-off={listening.status !== 'live'} aria-hidden="true"></span>
      <span class="nl-text">
        <span class="nl-headline">{view.headline}</span>
        <span class="nl-sub lp-num">{clock(listening.clockS)} · {logging ? t('Logging') : listening.linkText}{listening.recording === 'on' ? ` · ${tc('now', 'Recording')}` : ''}</span>
      </span>
    </button>
    {#if view.canEndSet}
      <button type="button" class="nl-endset" id="nl-endset" onclick={onEndSet}>{t('End set')}</button>
    {/if}
  </div>
{/if}

<Sheet bind:open title={running ? t('Listening') : t('Listen')} cancelLabel={t('Close')} desktop="dock">
  <div class="nl-sheet">
    {#if logging}
      <div class="nl-logging" id="nl-logging">
        <span>{t('Logging tunes to {night}', { night: title })}</span>
        {#if running}
          <button type="button" class="lp-link" id="nl-stop-logging" onclick={() => (askStopLogging = true)}>{t('Stop logging')}</button>
        {/if}
      </div>
    {/if}

    {#if !running}
      {#if listening.error}<p class="lp-error" role="alert" id="nl-error">{listening.error}</p>{/if}
      <p class="lp-note">{t("Ceol's server does the listening. Keep this page open and the screen on.")}</p>
      {#if canRecord && canLog}
        <label class="nl-option">
          <input type="checkbox" id="nl-record" bind:checked={recordNight} />
          {t('Record this night')}
        </label>
        {#if recordNight}
          <p class="lp-note">{t("Ceol's server keeps the sound and, when you stop, adds it to this night's recordings.")}</p>
        {/if}
      {/if}
      <button type="button" class="lp-start" id="nl-start" onclick={startListening} disabled={listening.phase === 'starting'}>
        {listening.phase === 'starting' ? t('Starting…') : t('Start Listening')}
      </button>
    {:else}
      {#if listening.recording === 'on'}
        <p class="nl-recording" id="nl-recording"><span class="nl-rec-dot" aria-hidden="true"></span>{t("Recording this night on Ceol's server")}</p>
      {:else if listening.recording === 'refused'}
        <p class="lp-error" id="nl-not-recording">{t("This night isn't being recorded: Ceol's server couldn't add it to the night's recordings.")}</p>
      {/if}
      <MeterView {listening} night onTapThis={tapThis} onWrong={wrong}>
        {#snippet noTune()}
          {#if view.canEndSet}
            <button type="button" class="lp-action" id="nl-endset-big" onclick={onEndSet}>{t('End the set')}</button>
          {/if}
        {/snippet}
        {#snippet sure(tune)}
          {#if logging}
            {#if view.logged === tune.id}
              <p class="nl-logged" id="nl-logged">✓ {t('Logged to the night')}</p>
            {:else}
              <button type="button" class="lp-action" id="nl-log" onclick={() => logTune({ tune_id: tune.id, name: tune.name, type: tune.type })}>{t('Log This Tune')}</button>
            {/if}
            {#if failed}<p class="lp-error" role="alert">{failed}</p>{/if}
          {:else}
            {#key tune.id}
              <TunebookBox tuneId={tune.id} />
            {/key}
            <button type="button" class="lp-link" id="nl-open-tune" onclick={() => openTune(tune.id)}>{t('Open the tune')}</button>
            {#if elsewhere}
              <p class="lp-note"><a href={elsewhere} target="_blank" rel="noopener">{t('Open this tune on thesession.org')}</a></p>
            {/if}
          {/if}
        {/snippet}
      </MeterView>

      <label class="nl-option" class:is-off={!logging}>
        <input type="checkbox" id="nl-auto" checked={logsAt100 && logging} disabled={!logging} onchange={(e) => setAuto(e.currentTarget.checked)} />
        {t('Log automatically at 100%')}
      </label>

      <div class="nl-foot">
        {#if !logging && canLog}
          <button type="button" class="lp-link" id="nl-log-again" onclick={begin}>{t('Log to this night')}</button>
        {/if}
        <button type="button" class="lp-stop" id="nl-stop" onclick={() => (askStop = true)}>{t('Stop Listening')}</button>
      </div>
    {/if}
  </div>
</Sheet>

<Dialog
  bind:open={askStopLogging}
  title={t('Stop logging these tunes to {night} and just show them instead?', { night: title })}
  confirmLabel={t('Stop logging')}
  onConfirm={stopLogging} />

<Dialog
  bind:open={askStop}
  title={logging ? t('Stop listening to this night?') : t('Stop listening?')}
  description={listening.recording === 'on' ? t("The recording so far is added to this night's recordings.") : ''}
  confirmLabel={t('Stop Listening')}
  onConfirm={stop} />

<style>
  .nl-strip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--header-bg, #1f2a22);
    border-top: 1px solid var(--border-color, #444);
  }
  .nl-open {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    min-width: 0;
    padding: 4px 0;
    font: inherit;
    text-align: left;
    color: inherit;
    background: none;
    border: none;
    cursor: pointer;
  }
  .nl-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .nl-headline {
    font-weight: 600;
    color: var(--text-color, #e8e8e8);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .nl-sub {
    font-size: 0.8rem;
    color: var(--secondary-text, #888);
  }
  .nl-endset {
    flex: none;
    font: inherit;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 6px 12px;
    color: #fff;
    background: var(--primary-fill, #4a8049);
    border: none;
    border-radius: 999px;
    cursor: pointer;
  }
  .nl-sheet {
    padding: 4px 16px 32px;
  }
  .nl-logging {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
    margin: 8px 0 12px;
    font-weight: 600;
    color: var(--text-color, #e8e8e8);
    background: var(--header-bg, rgba(255, 255, 255, 0.05));
    border-radius: var(--r, 8px);
  }
  .nl-recording {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 10px;
    font-size: 0.9rem;
    color: var(--secondary-text, #888);
  }
  .nl-rec-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--danger, #d9534f);
  }
  .nl-logged {
    margin: 0 0 8px;
    font-weight: 600;
    color: var(--success, #65b464);
  }
  .nl-option {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 4px 0 12px;
    font-size: 0.9rem;
    color: var(--secondary-text, #888);
  }
  .nl-option.is-off {
    opacity: 0.6;
  }
  .nl-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 12px;
  }
  .nl-foot .lp-stop {
    margin-left: auto;
  }
</style>

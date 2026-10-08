<script>
  // i18n-converted
  // "Find the tunes automatically" (spec 053, "053 files/find-tunes-on-the-
  // server.md"): on a night with nothing logged, a system admin queues the
  // listening service to find the tunes from the recording, and this panel
  // shows where it has got to -- waiting, running (and through what), paused
  // while a night is listened to live, done or failed -- until the tunes it
  // found are in the log. Hidden from anyone else: the job API answers 403.
  import { onMount } from 'svelte'
  import { t, tn } from '../lib/index.js'

  let {
    recordingId,
    tunesCount = 0,
    listenCount = 0, // tunes the listener logged that nobody has confirmed yet
    onfound = () => {}, // the job finished: reload the log
    ontunes = () => {}, // (tunes): the log after an undo
    // 'panel' is the whole thing. 'bar' is the phone's stand-in while the panel
    // is tucked away behind the ⋯ button: a thin progress line, shown only while
    // a job is waiting, running or paused, that opens the panel when tapped.
    variant = 'panel',
    onopen = () => {},
  } = $props()

  const POLL_MS = 5000
  const ACTIVE = ['queued', 'running', 'paused']
  let job = $state(null)
  let allowed = $state(false)
  let busy = $state(false)
  let error = $state(null)
  let timer = null

  async function call(path, method = 'GET') {
    const res = await fetch(path, { method, credentials: 'same-origin' })
    const body = await res.json().catch(() => ({}))
    if (res.status === 403) return { forbidden: true }
    if (!res.ok || !body.success) throw new Error(body.error || `HTTP ${res.status}`)
    return body
  }

  async function load() {
    try {
      const body = await call(`/api/recordings/${recordingId}/find-tunes`)
      if (body.forbidden) return
      allowed = true
      const was = job?.status
      job = body.job
      if (was && ACTIVE.includes(was) && job?.status === 'done') onfound()
    } catch (err) {
      error = err.message
    }
    schedule()
  }

  function schedule() {
    clearTimeout(timer)
    if (job && ACTIVE.includes(job.status)) timer = setTimeout(load, POLL_MS)
  }

  async function act(path, method = 'POST') {
    busy = true
    error = null
    try {
      const body = await call(path, method)
      if (body.job !== undefined) job = body.job
      if (body.tunes) ontunes(body.tunes)
    } catch (err) {
      error = err.message
    } finally {
      busy = false
    }
    schedule()
  }

  // Only a night with nothing logged, or with the listener's unchecked tunes,
  // has anything to show here; any other page makes no request for it.
  onMount(() => {
    if (tunesCount === 0 || listenCount > 0) load()
    return () => clearTimeout(timer)
  })

  function clock(s) {
    if (s == null) return '—'
    s = Math.round(s)
    if (s < 60) return t('{n} s', { n: s })
    const m = Math.floor(s / 60)
    if (m < 60) return t('{m} min {s} s', { m, s: s % 60 })
    return t('{h} h {m} min', { h: Math.floor(m / 60), m: m % 60 })
  }

  const phaseLabel = (phase) =>
    ({
      fetching: t('fetching the recording'),
      listening: t('listening'),
      following: t('following the sets'),
      finishing: t('putting the tunes in'),
    })[phase] || t('starting')

  const percent = $derived(
    job?.phase === 'listening' && job.total_ms ? Math.round((100 * (job.heard_ms || 0)) / job.total_ms) : Math.round(100 * (job?.progress || 0)),
  )
  const show = $derived(
    allowed && (tunesCount === 0 || (job && ACTIVE.includes(job.status)) || (job?.status === 'done' && listenCount > 0)),
  )
</script>

{#if variant === 'bar'}
  {#if allowed && job && ACTIVE.includes(job.status)}
    {@const label =
      job.status === 'queued'
        ? t('Waiting to start')
        : job.status === 'paused'
          ? t('Paused while a night is being listened to live')
          : `${t('Finding the tunes: {phase}', { phase: phaseLabel(job.phase) })} ${percent}%`}
    <button type="button" class="ft-thin" class:is-paused={job.status !== 'running'} onclick={onopen} aria-label={label} title={label}>
      <span class="ft-bar"><span style="width:{job.status === 'queued' ? 0 : percent}%"></span></span>
    </button>
  {/if}
{:else if show}
  <div class="ft" class:is-active={job && ACTIVE.includes(job.status)}>
    {#if !job || job.status === 'cancelled' || (job.status === 'done' && tunesCount === 0)}
      <p class="ft-line">{t('Nothing is logged for this night yet.')}</p>
      <button type="button" class="ft-go" disabled={busy || tunesCount > 0} onclick={() => act(`/api/recordings/${recordingId}/find-tunes`)}>
        {t('Find the tunes automatically')}
      </button>
      <p class="ft-note">{t('The listening service hears the whole recording and logs what it finds; you check the ones it is unsure of.')}</p>
    {:else if job.status === 'queued'}
      <p class="ft-line">
        {t('Waiting to start')} · {t('waited {time}', { time: clock(job.waited_s) })}{#if job.jobs_ahead}
          · {tn(job.jobs_ahead, '{n} job ahead', '{n} jobs ahead')}{/if}
      </p>
      <button type="button" disabled={busy} onclick={() => act(`/api/listen-jobs/${job.listen_job_id}/cancel`)}>{t('Cancel')}</button>
    {:else if job.status === 'running' || job.status === 'paused'}
      <p class="ft-line">
        {#if job.status === 'paused'}
          {t('Paused while a night is being listened to live')}
        {:else}
          {t('Finding the tunes: {phase}', { phase: phaseLabel(job.phase) })}
        {/if}
      </p>
      <div class="ft-bar"><div style="width:{percent}%"></div></div>
      <p class="ft-note">
        {phaseLabel(job.phase)} {percent}% · {t('running {time}', { time: clock(job.running_s) })}{#if job.paused_s}
          · {t('paused {time}', { time: clock(job.paused_s) })}{/if} · {t('waited {time}', { time: clock(job.waited_s) })}
      </p>
      <button type="button" disabled={busy} onclick={() => act(`/api/listen-jobs/${job.listen_job_id}/cancel`)}>{t('Cancel')}</button>
    {:else if job.status === 'done'}
      <p class="ft-line">
        {tn(job.result?.logged ?? job.result?.tunes ?? 0, 'Found {n} tune', 'Found {n} tunes')}
        · {tn(job.result?.sets ?? 0, 'in {n} set', 'in {n} sets')}{#if job.result?.need_check}
          · {tn(job.result.need_check, '{n} needs a check', '{n} need a check')}{/if}
      </p>
      <p class="ft-note">
        {t('took {time}', { time: clock(job.running_s) })}{#if job.paused_s} · {t('paused {time}', { time: clock(job.paused_s) })}{/if}
        · {t('waited {time}', { time: clock(job.waited_s) })}
      </p>
      <button type="button" class="danger" disabled={busy} onclick={() => act(`/api/recordings/${recordingId}/find-tunes/undo`)}>
        {t('Remove what it logged')}
      </button>
    {:else if job.status === 'failed'}
      <p class="ft-line ft-error">{t("Couldn't find the tunes: {error}", { error: job.error || '' })}</p>
      <button type="button" disabled={busy} onclick={() => act(`/api/listen-jobs/${job.listen_job_id}/retry`)}>{t('Try again')}</button>
    {/if}
    {#if error}<p class="ft-line ft-error">{error}</p>{/if}
  </div>
{/if}

<style>
  .ft {
    border: 1px solid var(--border-color, #444);
    border-radius: 8px;
    padding: 8px 10px;
    margin-bottom: 8px;
    font-size: 0.85rem;
  }
  .ft.is-active {
    border-color: #e0b341;
  }
  .ft-line {
    margin: 0 0 6px;
    color: var(--text-color, #e0e0e0);
  }
  .ft-note {
    margin: 4px 0 6px;
    color: var(--disabled-text, #888);
    font-size: 0.78rem;
  }
  .ft-error {
    color: var(--danger, #e06c6c);
  }
  .ft-bar {
    height: 6px;
    background: var(--border-color, #444);
    border-radius: 3px;
    overflow: hidden;
  }
  .ft-bar div,
  .ft-bar span {
    display: block;
    height: 100%;
    background: #e0b341;
  }
  /* The bar form: 4px to look at, a taller strip to tap. */
  .ft-thin {
    display: block;
    width: 100%;
    padding: 4px 0;
    margin: 0 0 2px;
    background: none;
    border: 0;
    cursor: pointer;
  }
  .ft-thin .ft-bar {
    display: block;
    height: 4px;
    border-radius: 2px;
  }
  .ft-thin.is-paused .ft-bar span {
    opacity: 0.5;
  }
  .ft button {
    background: none;
    border: 1px solid var(--border-color, #444);
    border-radius: 5px;
    color: var(--text-color, #e0e0e0);
    padding: 2px 10px;
  }
  .ft button.ft-go {
    border-color: #e0b341;
    color: #e0b341;
  }
  .ft button.danger {
    color: var(--danger, #e06c6c);
  }
</style>

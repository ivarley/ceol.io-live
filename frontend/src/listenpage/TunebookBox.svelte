<script>
  // i18n-converted
  // The sure tune's place in your tunebook, as the iPhone's meter shows it
  // (TunesViews.swift, TunebookBox): not on your list, add it as To Learn / Learning /
  // Learned; on it, its status (tap another to change it) and, while To Learn, how
  // many times you have heard it.
  //
  // The add goes through POST /api/my-tunes with the tune as a thesession.org id: the
  // listener's ids are thesession.org's, and a tune Ceol doesn't hold yet is imported
  // on the way. Changes after that are My Tunes ops, as the tunebook's own are.
  import { t, tn } from '../lib/i18n/index.js'

  let { tuneId } = $props()

  const STATUSES = [
    { value: 'want to learn', label: () => t('To Learn') },
    { value: 'learning', label: () => t('Learning') },
    { value: 'learned', label: () => t('Learned') },
  ]

  let phase = $state('loading') // loading | off | on | failed
  let status = $state(null)
  let heard = $state(0)
  let saving = $state(false)
  let error = $state('')
  let seq = 0

  $effect(() => {
    load(tuneId)
  })

  async function load(id) {
    const mine = ++seq
    phase = 'loading'
    error = ''
    try {
      const r = await fetch(`/api/tunes/${id}/detail`, { credentials: 'same-origin' })
      if (mine !== seq) return
      // A tune Ceol doesn't hold yet is on nobody's list.
      if (r.status === 404) {
        phase = 'off'
        return
      }
      const body = await r.json()
      if (mine !== seq) return
      const pts = body.session_tune && body.session_tune.person_tune_status
      if (pts && pts.on_list) {
        status = pts.learn_status
        heard = pts.heard_count || 0
        phase = 'on'
      } else {
        phase = 'off'
      }
    } catch {
      if (mine === seq) phase = 'failed'
    }
  }

  function failed(e, body) {
    error = (body && (body.message || body.error)) || (e ? t("Couldn't reach Ceol, so that wasn't saved. Check your connection and try again.") : t("That wasn't saved. Try again."))
  }

  async function add(value) {
    if (saving) return
    saving = true
    error = ''
    try {
      const r = await fetch('/api/my-tunes', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thesession_id: tuneId, learn_status: value }),
      })
      const body = await r.json().catch(() => ({}))
      // 409: it was on your list already (added elsewhere since this loaded)
      const pt = body.person_tune
      if ((r.ok && body.success) || (r.status === 409 && pt)) {
        status = (pt && pt.learn_status) || value
        heard = (pt && pt.heard_count) || 1
        phase = 'on'
      } else {
        failed(null, body)
      }
    } catch (e) {
      failed(e)
    } finally {
      saving = false
    }
  }

  async function op(fields) {
    const r = await fetch('/api/my-tunes/ops', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ op_id: crypto.randomUUID(), tune_id: tuneId, ...fields }),
    })
    const body = await r.json().catch(() => ({}))
    if (!r.ok || body.success === false) {
      const e = new Error('rejected')
      e.body = body
      throw e
    }
  }

  async function setStatus(value) {
    if (saving || value === status) return
    const was = status
    status = value
    saving = true
    error = ''
    try {
      await op({ type: 'set_status', learn_status: value })
    } catch (e) {
      status = was
      failed(e.body ? null : e, e.body)
    } finally {
      saving = false
    }
  }

  async function setHeard(n) {
    if (saving || n < 0 || n > 999) return
    const was = heard
    heard = n
    saving = true
    error = ''
    try {
      await op({ type: 'set_heard', heard_count: n })
    } catch (e) {
      heard = was
      failed(e.body ? null : e, e.body)
    } finally {
      saving = false
    }
  }
</script>

<div class="lp-tunebook" class:is-on={phase === 'on'} id="lp-tunebook">
  {#if phase === 'loading'}
    <p class="lp-tunebook-head">{t('Loading…')}</p>
  {:else if phase === 'failed'}
    <p class="lp-tunebook-head">{t("Couldn't check your list.")}</p>
    <button type="button" class="lp-link" onclick={() => load(tuneId)}>{t('Try again')}</button>
  {:else}
    <p class="lp-tunebook-head">{phase === 'on' ? t('This tune is on your list as') : t('Add this tune to your list as')}</p>
    <div class="lp-seg" role="group">
      {#each STATUSES as s (s.value)}
        <button
          type="button"
          class:active={phase === 'on' && status === s.value}
          aria-pressed={phase === 'on' && status === s.value}
          disabled={saving}
          onclick={() => (phase === 'on' ? setStatus(s.value) : add(s.value))}>{s.label()}</button>
      {/each}
    </div>
    {#if phase === 'on' && status === 'want to learn'}
      <div class="lp-heard">
        <span>{tn(heard, 'Heard it once', 'Heard it {n} times')}</span>
        <span class="lp-stepper">
          <button type="button" aria-label={t('One fewer')} disabled={saving || heard <= 0} onclick={() => setHeard(heard - 1)}>−</button>
          <button type="button" aria-label={t('One more')} disabled={saving || heard >= 999} onclick={() => setHeard(heard + 1)}>+</button>
        </span>
      </div>
    {/if}
  {/if}
  {#if error}<p class="lp-error" role="alert">{error}</p>{/if}
</div>

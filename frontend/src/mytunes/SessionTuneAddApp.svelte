<script>
  // i18n-converted
  // Add-to-session-tunes pane: the same shell + deep search as the My Tunes add pane
  // (mobile slide-in / desktop split pane), but scoped to a session's repertoire —
  // tunes already in THIS session dim and sort last, and the configure phase asks
  // the session questions instead: alias ("we call this"), and under Advanced a
  // specific setting and the key the session plays it in. Bundled into the
  // sessionpage bundle as a child of its App, driven via bind:this + open().
  import { Chevron, Chip, ServerError, t, tn, tuneTypeName } from '../lib/index.js'
  import { failText } from './labels.js'
  import TuneSearch from '../TuneSearch.svelte'
  import Incipit from '../Incipit.svelte'
  import { createPaneState } from './pane.svelte.js'

  // Same list the legacy add page offered.
  const KEYS = [
    'Amajor', 'Aminor', 'Adorian', 'Amixolydian', 'Bminor', 'Cmajor', 'Dmajor', 'Dminor',
    'Eminor', 'Fmajor', 'Gmajor', 'Dmixolydian', 'Bmixolydian', 'Edorian', 'Gdorian',
    'Gminor', 'Ddorian', 'Cdorian', 'Fdorian', 'Gmixolydian', 'Emajor', 'Bdorian', 'Emixolydian',
  ]

  const pane = createPaneState()
  let sessionPath = $state('')
  let config = $state({ searchScope: {} })
  let picked = $state(null) // null = search phase; else {tune_id?, thesession_id?, name, tune_type, ...}
  let initialQuery = $state('')
  let history = $state([]) // search recall (MRU), kept across open/close for the page's lifetime

  // Configure-phase state.
  let alias = $state('')
  let advancedOpen = $state(false)
  let settingRaw = $state('')
  let settingError = $state('')
  let keyChoice = $state('')
  let submitting = $state(false)
  let errorMsg = $state('')

  // Page callbacks (set via open()).
  let onAdded = () => {}
  let onAlready = () => {}
  let onClosed = () => {}

  export function open(opts = {}) {
    sessionPath = opts.sessionPath || ''
    config = { searchScope: { session: sessionPath } }
    initialQuery = opts.query || ''
    onAdded = opts.onAdded || (() => {})
    onAlready = opts.onAlready || (() => {})
    onClosed = opts.onClosed || (() => {})
    resetConfigPhase()
    picked = null
    pane.open()
  }

  export function close() {
    const cb = onClosed
    pane.close(() => {
      picked = null
      cb()
    })
  }

  export function isOpen() {
    return pane.visible
  }

  function resetConfigPhase() {
    alias = ''
    advancedOpen = false
    settingRaw = ''
    settingError = ''
    keyChoice = ''
    submitting = false
    errorMsg = ''
  }

  function remember(q) {
    const v = (q || '').trim()
    if (!v) return
    history = [v, ...history.filter((x) => x !== v)].slice(0, 20)
  }

  // A search pick lands here (TuneSearch onAdd). Returning false tells TuneSearch the
  // "add" was deferred, so it never clears itself — the query survives "Not this one?".
  function pick(payload, name, result) {
    if (result?.in_session) {
      // Already in this session's repertoire: not an add — hand off to the page.
      const tid = payload.tune_id ?? payload.thesession_id
      close()
      onAlready(tid, name)
      return false
    }
    picked = {
      ...payload,
      tunebook_count: result?.tunebook_count,
      incipit_image: result?.incipit_image ?? null,
      can_render: result?.can_render ?? false,
    }
    resetConfigPhase()
    // A setting chosen in the preview's pager prefills Advanced (visible, editable) —
    // the existing submit path saves it as the session's setting and imports/caches it.
    if (payload.setting_id != null) {
      settingRaw = String(payload.setting_id)
      advancedOpen = true
    }
    return false
  }

  function backToSearch() {
    picked = null
    errorMsg = ''
  }

  // ---- setting field (Advanced) ----
  function parseSettingId(input) {
    const text = (input || '').trim()
    if (!text) return { ok: true, id: null }
    if (/^\d+$/.test(text)) return { ok: true, id: parseInt(text, 10) }
    if (text.includes('thesession.org')) {
      const qm = text.match(/[?&]setting=(\d+)/)
      if (qm) return { ok: true, id: parseInt(qm[1], 10) }
      const hm = text.match(/#setting(\d+)/)
      if (hm) return { ok: true, id: parseInt(hm[1], 10) }
    }
    return { ok: false, id: null }
  }

  async function submit() {
    if (submitting) return
    errorMsg = ''
    const s = parseSettingId(settingRaw)
    if (!s.ok) {
      settingError = t('Enter a setting number or paste a thesession.org URL.')
      advancedOpen = true
      return
    }
    settingError = ''
    if (!navigator.onLine) {
      errorMsg = t('You are offline. Session tunes can only be added online.')
      return
    }
    submitting = true
    const tuneId = picked.tune_id ?? picked.thesession_id
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/tunes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          tune_id: picked.tune_id ?? null,
          thesession_id: picked.thesession_id ?? null,
          alias: alias.trim() || null,
          setting_id: s.id,
          key: keyChoice || null,
        }),
      })
      const j = await res.json().catch(() => ({}))
      const finalId = j.tune_id ?? tuneId
      if (res.status === 409) {
        close()
        onAlready(finalId, picked.name)
        return
      }
      if (!res.ok || !j.success) throw new ServerError(j.error || j.message)
      close()
      onAdded(finalId, picked.name)
    } catch (e) {
      errorMsg = failText(e, t('add the tune to the session'))
      submitting = false
    }
  }
</script>

{#if pane.visible}
  <div class="mt-add-backdrop" class:mt-open={pane.shown} onclick={close} aria-hidden="true"></div>
  <div class="mt-add-pane" class:mt-open={pane.shown} role="dialog" aria-label={t('Add a tune to this session')}>
    {#if !picked}
      <TuneSearch
        {config}
        variant="modal"
        title={t('Search for a tune')}
        allowAsIs={false}
        actionLabel={t('＋ Add This Tune')}
        dimInSession={true}
        {initialQuery}
        {history}
        onRemember={remember}
        onAdd={pick}
        onClose={close}
      />
    {:else}
      <div class="deep-head">
        <button class="mt-back" onclick={backToSearch} aria-label={t('Back to search')}><Chevron dir="left" size={18} /></button>
        <span class="deep-title">{t('Add to Session')}</span>
        <button class="deep-done" onclick={close}>{t('Cancel')}</button>
      </div>
      <div class="mt-config">
        <div class="deep-card mt-picked">
          <div class="deep-card-head">
            <span class="deep-name">{picked.name}</span>
            <span class="deep-type">{tuneTypeName(picked.tune_type) || ''}</span>
          </div>
          {#if picked.tune_id != null && (picked.incipit_image || picked.can_render)}
            <div class="deep-staff">
              <Incipit {config} tuneId={picked.tune_id} image={picked.incipit_image} canRender={picked.can_render} />
            </div>
          {/if}
          <div class="deep-meta">
            {#if picked.thesession_id != null && picked.tune_id == null}
              <Chip label={t('importing from thesession.org')} styled={false} chipClass="deep-badge" />
            {/if}
            {#if picked.tunebook_count != null}
              <span class="deep-books">{tn(picked.tunebook_count, '{n} tunebook', '{n} tunebooks')}</span>
            {/if}
          </div>
          <button class="mt-change" onclick={backToSearch}>{t('Not this one? Back to search')}</button>
        </div>

        <div class="mt-section">
          <label class="mt-label" for="st-add-alias">{t('We call this (optional)')}</label>
          <input
            id="st-add-alias"
            class="mt-setting"
            maxlength="255"
            placeholder={t('Local name for this tune, if different')}
            bind:value={alias}
          />
        </div>

        <div class="mt-section">
          <button class="mt-advanced-toggle" onclick={() => (advancedOpen = !advancedOpen)}>
            <Chevron dir={advancedOpen ? "down" : "right"} size={14} /> {t('Advanced')}
          </button>
          {#if advancedOpen}
            <div class="mt-advanced">
              <label class="mt-label" for="st-add-setting">{t('Setting (optional)')}</label>
              <input
                id="st-add-setting"
                class="mt-setting"
                placeholder={t('Setting number or thesession.org URL')}
                bind:value={settingRaw}
                oninput={() => (settingError = '')}
              />
              <p class="mt-help">{t('If the session plays a specific setting of the tune, paste its URL or setting number.')}</p>
              {#if settingError}<p class="mt-error">{settingError}</p>{/if}
              <label class="mt-label" for="st-add-key">{t('Key (optional)')}</label>
              <select id="st-add-key" class="mt-setting" bind:value={keyChoice}>
                <option value="">{t('(not specified)')}</option>
                {#each KEYS as k}
                  <option value={k}>{k}</option>
                {/each}
              </select>
              <p class="mt-help">{t('The key the session typically plays this tune in.')}</p>
            </div>
          {/if}
        </div>

        {#if errorMsg}<p class="mt-error">{errorMsg}</p>{/if}
        <button class="mt-submit" disabled={submitting} onclick={submit}>
          {submitting ? t('Adding…') : t('Add to Session')}
        </button>
      </div>
    {/if}
  </div>
{/if}

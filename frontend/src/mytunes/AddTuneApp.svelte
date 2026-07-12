<script>
  // Add-to-My-Tunes pane (mobile slide-in / desktop split pane). Phase 1 is the SAME
  // deep search the live logger uses (TuneSearch.svelte — local catalog + thesession.org
  // remote + paste-a-URL); picking a tune swaps the pane to the configure phase:
  // instrument statuses (collapsed roll-up like the detail modal), notes, and an
  // Advanced setting field. Mounted once by my_tunes.html; the page opens/closes it
  // through the exported open()/close() (window.MyTunesAddPane).
  import { Chip, Seg } from '../lib/index.js'
  import TuneSearch from '../TuneSearch.svelte'
  import Incipit from '../Incipit.svelte'
  import { createPaneState } from './pane.svelte.js'

  // Personal flavor of the live search API (same request/response shapes).
  const config = { searchApiBase: '/api/my-tunes' }

  const STATUSES = ['want to learn', 'learning', 'learned']
  const LABELS = { 'want to learn': 'Want To Learn', learning: 'Learning', learned: 'Learned' }

  const pane = createPaneState()
  let picked = $state(null) // null = search phase; else {tune_id?, thesession_id?, name, tune_type, ...}
  let instruments = $state([]) // the person's instruments [{instrument, is_auto}], from the page
  let initialQuery = $state('')
  let history = $state([]) // search recall (MRU), kept across open/close for the page's lifetime

  // Configure-phase state.
  let baseStatus = $state('want to learn')
  let instOpen = $state(false)
  let instChoices = $state({}) // instrument -> status ('want to learn'|...|null). Missing key = default.
  let notes = $state('')
  let advancedOpen = $state(false)
  let settingRaw = $state('')
  let settingError = $state('')
  let submitting = $state(false)
  let errorMsg = $state('')

  // Page callbacks (set via open()).
  let onAdded = () => {}
  let onAlready = () => {}
  let onClosed = () => {}

  export function open(opts = {}) {
    instruments = opts.instruments || []
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
    baseStatus = 'want to learn'
    instOpen = false
    instChoices = {}
    notes = ''
    advancedOpen = false
    settingRaw = ''
    settingError = ''
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
    if (result?.on_list) {
      // Already on the list: not an add — hand off to the page to show/highlight it.
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
    // the existing submit path imports/caches it server-side.
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

  // ---- instrument status choices (mirrors the detail modal's roll-up semantics) ----
  // Auto instruments follow the base status unless the user picks an override here;
  // manual instruments start untracked and only get a status if explicitly chosen.
  function effectiveStatus(inst) {
    if (inst.instrument in instChoices) return instChoices[inst.instrument]
    return inst.is_auto ? baseStatus : null
  }
  function tapInstStatus(inst, status) {
    const current = effectiveStatus(inst)
    if (current === status) {
      // Tapping the active status: manual untracks; auto falls back to following base.
      if (inst.is_auto) delete instChoices[inst.instrument]
      else instChoices[inst.instrument] = null
    } else if (inst.is_auto && status === baseStatus) {
      delete instChoices[inst.instrument] // choosing the base status = just follow it
    } else {
      instChoices[inst.instrument] = status
    }
    instChoices = { ...instChoices }
  }
  // Overrides worth persisting after the add: anything that diverges from what the
  // base add would produce on its own (auto follows base, manual stays untracked).
  function instrumentOverrides() {
    const ops = []
    for (const inst of instruments) {
      const chosen = inst.instrument in instChoices ? instChoices[inst.instrument] : undefined
      if (chosen === undefined) continue
      if (inst.is_auto && chosen === baseStatus) continue
      if (!inst.is_auto && chosen === null) continue
      ops.push({ instrument: inst.instrument, status: chosen })
    }
    return ops
  }

  // ---- setting field (Advanced) ----
  function parseSettingId(input) {
    const t = (input || '').trim()
    if (!t) return { ok: true, id: null }
    if (/^\d+$/.test(t)) return { ok: true, id: parseInt(t, 10) }
    if (t.includes('thesession.org')) {
      const qm = t.match(/[?&]setting=(\d+)/)
      if (qm) return { ok: true, id: parseInt(qm[1], 10) }
      const hm = t.match(/#setting(\d+)/)
      if (hm) return { ok: true, id: parseInt(hm[1], 10) }
    }
    return { ok: false, id: null }
  }

  // ---- submit ----
  // Plain catalog adds ride the offline op-queue (same path as the detail modal);
  // a thesession import or a specific setting needs the classic POST (online-only:
  // the server fetches from thesession.org / caches the setting).
  function submitOp(op) {
    if (window.MyTunesOffline) return window.MyTunesOffline.submit(op)
    return fetch('/api/my-tunes/ops', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(op),
    }).then(async (res) => {
      const j = await res.json().catch(() => ({}))
      if (!res.ok || j.success === false) throw new Error(j.error || `op failed: ${res.status}`)
      return j
    })
  }

  async function applyInstrumentOverrides(tuneId) {
    for (const o of instrumentOverrides()) {
      await submitOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: o.instrument, status: o.status })
    }
  }

  async function submit() {
    if (submitting) return
    errorMsg = ''
    const s = parseSettingId(settingRaw)
    if (!s.ok) {
      settingError = 'Enter a setting number or paste a thesession.org URL.'
      advancedOpen = true
      return
    }
    settingError = ''
    submitting = true
    const tuneId = picked.tune_id ?? picked.thesession_id
    const noteText = notes.trim()
    try {
      if (picked.thesession_id != null || s.id != null) {
        if (!navigator.onLine) {
          throw new Error(
            picked.thesession_id != null
              ? 'You are offline. Tunes from thesession.org can only be added online.'
              : 'You are offline. A specific setting can only be saved online.'
          )
        }
        const res = await fetch('/api/my-tunes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            tune_id: picked.tune_id ?? null,
            thesession_id: picked.thesession_id ?? null,
            learn_status: baseStatus,
            notes: noteText || null,
            setting_id: s.id,
          }),
        })
        const j = await res.json().catch(() => ({}))
        const finalId = j.person_tune?.tune_id ?? j.redirect_to_tune_id ?? tuneId
        if (res.status === 409) {
          close()
          onAlready(finalId, picked.name)
          return
        }
        if (!res.ok || !j.success) throw new Error(j.error || 'Could not add the tune.')
        await applyInstrumentOverrides(finalId)
        close()
        onAdded(finalId, picked.name)
      } else {
        await submitOp({
          type: 'add',
          tune_id: tuneId,
          learn_status: baseStatus,
          name: picked.name,
          tune_type: picked.tune_type,
        })
        if (noteText) await submitOp({ type: 'set_notes', tune_id: tuneId, notes: noteText })
        await applyInstrumentOverrides(tuneId)
        close()
        onAdded(tuneId, picked.name)
      }
    } catch (e) {
      errorMsg = e?.message || 'Could not add the tune. Please try again.'
      submitting = false
    }
  }
</script>

{#if pane.visible}
  <div class="mt-add-backdrop" class:mt-open={pane.shown} onclick={close} aria-hidden="true"></div>
  <div class="mt-add-pane" class:mt-open={pane.shown} role="dialog" aria-label="Add a tune to My Tunes">
    {#if !picked}
      <TuneSearch
        {config}
        variant="modal"
        title="Search for a tune"
        allowAsIs={false}
        actionLabel="＋ Add This Tune"
        dimOnList={true}
        {initialQuery}
        {history}
        onRemember={remember}
        onAdd={pick}
        onClose={close}
      />
    {:else}
      <div class="deep-head">
        <button class="mt-back" onclick={backToSearch} aria-label="Back to search">‹</button>
        <span class="deep-title">Add to My Tunes</span>
        <button class="deep-done" onclick={close}>Cancel</button>
      </div>
      <div class="mt-config">
        <div class="deep-card mt-picked">
          <div class="deep-card-head">
            <span class="deep-name">{picked.name}</span>
            <span class="deep-type">{picked.tune_type || ''}</span>
          </div>
          {#if picked.tune_id != null && (picked.incipit_image || picked.can_render)}
            <div class="deep-staff">
              <Incipit {config} tuneId={picked.tune_id} image={picked.incipit_image} canRender={picked.can_render} />
            </div>
          {/if}
          <div class="deep-meta">
            {#if picked.thesession_id != null && picked.tune_id == null}
              <Chip label="importing from thesession.org" styled={false} chipClass="deep-badge" />
            {/if}
            {#if picked.tunebook_count != null}
              <span class="deep-books">{picked.tunebook_count} tunebooks</span>
            {/if}
          </div>
          <button class="mt-change" onclick={backToSearch}>Not this one? Back to search</button>
        </div>

        <div class="mt-section">
          <div class="tsc-label-line mt-label">Add as</div>
          <Seg
            options={STATUSES.map((st) => ({ id: st, label: LABELS[st] }))}
            value={baseStatus}
            idAttr="data-status"
            styled={false}
            segClass="tunebook-status-seg"
            optClass="tunebook-status-opt"
            onSelect={(st) => (baseStatus = st)} />
          {#if instruments.length >= 2}
            <button class="tsc-expand-link mt-expand" onclick={() => (instOpen = !instOpen)}>
              {instOpen ? 'Hide Instruments' : 'View By Instrument'}
            </button>
            {#if instOpen}
              <div class="tsc-instruments">
                {#each instruments as inst (inst.instrument)}
                  <div class="tsc-block tsc-inst-block">
                    <div class="tsc-label-line mt-label">
                      {inst.instrument}
                      {#if !inst.is_auto}<Chip label="manual" styled={false} chipClass="mt-manual-badge" />{/if}
                      {#if effectiveStatus(inst) === null}<Chip label="not tracking" styled={false} chipClass="mt-untracked" />{/if}
                    </div>
                    <Seg
                      options={STATUSES.map((st) => ({ id: st, label: LABELS[st] }))}
                      value={effectiveStatus(inst)}
                      idAttr="data-status"
                      styled={false}
                      segClass="tunebook-status-seg"
                      optClass="tunebook-status-opt"
                      onSelect={(st) => tapInstStatus(inst, st)} />
                  </div>
                {/each}
              </div>
            {/if}
          {/if}
        </div>

        <div class="mt-section">
          <label class="mt-label" for="mt-add-notes">Notes</label>
          <textarea
            id="mt-add-notes"
            class="mt-notes"
            placeholder="Add any notes about this tune…"
            bind:value={notes}
          ></textarea>
        </div>

        <div class="mt-section">
          <button class="mt-advanced-toggle" onclick={() => (advancedOpen = !advancedOpen)}>
            {advancedOpen ? '▾' : '▸'} Advanced
          </button>
          {#if advancedOpen}
            <div class="mt-advanced">
              <label class="mt-label" for="mt-add-setting">Setting (optional)</label>
              <input
                id="mt-add-setting"
                class="mt-setting"
                placeholder="Setting number or thesession.org URL"
                bind:value={settingRaw}
                oninput={() => (settingError = '')}
              />
              <p class="mt-help">If you play a specific setting of the tune, paste its URL or setting number.</p>
              {#if settingError}<p class="mt-error">{settingError}</p>{/if}
            </div>
          {/if}
        </div>

        {#if errorMsg}<p class="mt-error">{errorMsg}</p>{/if}
        <button class="mt-submit" disabled={submitting} onclick={submit}>
          {submitting ? 'Adding…' : `Add to My Tunes`}
        </button>
      </div>
    {/if}
  </div>
{/if}

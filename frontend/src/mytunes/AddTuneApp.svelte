<script>
  // Add-to-My-Tunes pane (mobile slide-in / desktop split pane). ONE screen past the
  // search: the deep search (TuneSearch.svelte — local catalog + thesession.org remote
  // + paste-a-URL) opens TunePreview on tap, and the preview's footer hosts the add
  // form (AddTuneForm: status + instrument roll-up + notes; the settings PAGER is the
  // setting control). The ＋ rail on result cards adds instantly with defaults
  // ('want to learn', no notes, no setting). Mounted once by the page; opened/closed
  // through the exported open()/close().
  import TuneSearch from '../TuneSearch.svelte'
  import AddTuneForm from './AddTuneForm.svelte'
  import SyncPane from './SyncPane.svelte'
  import { createPaneState } from './pane.svelte.js'

  // Personal flavor of the live search API (same request/response shapes).
  // offlineSearchFallback: offline, the deep search falls back to the CeolOffline
  // bundle mirror (tunebook + popular) — the parity the legacy add page had.
  const config = { searchApiBase: '/api/my-tunes', offlineSearchFallback: true }

  const pane = createPaneState()
  let syncMode = $state(false) // tunebook-sync view (the folded-away /my-tunes/sync page)
  let thesessionUserId = $state(null) // saved thesession.org member ID, from the page payload
  let instruments = $state([]) // the person's instruments [{instrument, is_auto}], from the page
  let initialQuery = $state('')
  let history = $state([]) // search recall (MRU), kept across open/close for the page's lifetime
  let searchError = $state('') // quick-add failure banner (shown in the search phase)
  let quickAddBusy = false // in-flight guard: a ＋ double-tap must not double-enqueue

  // Page callbacks (set via open()).
  let onAdded = () => {}
  let onAlready = () => {}
  let onClosed = () => {}
  let onSynced = () => {}

  export function open(opts = {}) {
    instruments = opts.instruments || []
    initialQuery = opts.query || ''
    thesessionUserId = opts.thesessionUserId ?? null
    onAdded = opts.onAdded || (() => {})
    onAlready = opts.onAlready || (() => {})
    onClosed = opts.onClosed || (() => {})
    onSynced = opts.onSynced || (() => {})
    searchError = ''
    syncMode = !!opts.sync // open straight into the sync view (?sync=1 landing)
    pane.open()
  }

  export function close() {
    const cb = onClosed
    pane.close(() => {
      syncMode = false
      cb()
    })
  }

  export function isOpen() {
    return pane.visible
  }

  function remember(q) {
    const v = (q || '').trim()
    if (!v) return
    history = [v, ...history.filter((x) => x !== v)].slice(0, 20)
  }

  // ---- the add engine (shared by quick-add and the preview form) -----------------
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

  async function applyOverrides(tuneId, overrides) {
    for (const o of overrides) {
      await submitOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: o.instrument, status: o.status })
    }
  }

  // target: {tune_id, thesession_id, name, tune_type}. Returns {finalId, already, applied};
  // throws Error(message) on failure — the aftermath (close/land) is the caller's.
  // NOTE: a thesession target carries the thesession id in BOTH tune_id and
  // thesession_id (the server folds them) — keep that shape.
  // `already` is not a failure: the tune was on the list before this add. The server
  // still applies the setting (and notes, when the row had none) that the form
  // collected and reports them as `applied`, so the landing toast can say so — a
  // pasted link can't tell you up front that the tune is already yours.
  async function performAdd(target, { status, notes, settingId, overrides }) {
    const tuneId = target.tune_id ?? target.thesession_id
    if (target.thesession_id != null || settingId != null) {
      if (!navigator.onLine) {
        throw new Error(
          target.thesession_id != null
            ? 'You are offline. Tunes from thesession.org can only be added online.'
            : 'You are offline. A specific setting can only be saved online.'
        )
      }
      const res = await fetch('/api/my-tunes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          tune_id: target.thesession_id != null ? null : target.tune_id,
          thesession_id: target.thesession_id,
          learn_status: status,
          notes: notes || null,
          setting_id: settingId,
        }),
      })
      const j = await res.json().catch(() => ({}))
      const finalId = j.person_tune?.tune_id ?? j.redirect_to_tune_id ?? tuneId
      if (res.status === 409) return { finalId, already: true, applied: j.applied || {} }
      if (!res.ok || !j.success) throw new Error(j.error || 'Could not add the tune.')
      await applyOverrides(finalId, overrides)
      return { finalId, already: false }
    }
    await submitOp({ type: 'add', tune_id: tuneId, learn_status: status, name: target.name, tune_type: target.tune_type })
    if (notes) await submitOp({ type: 'set_notes', tune_id: tuneId, notes })
    await applyOverrides(tuneId, overrides)
    return { finalId: tuneId, already: false }
  }

  // ---- quick add (the ＋ rail / ⌘Enter): hard defaults, straight to the page ------
  // TuneSearch's onAdd only ever fires from the quick paths here — the preview's
  // default action button is replaced by the footer form (which submits itself).
  async function doQuickAdd(target, name) {
    try {
      const { finalId, already, applied } = await performAdd(target, {
        status: 'want to learn',
        notes: '',
        settingId: null,
        overrides: [],
      })
      close()
      already ? onAlready(finalId, name, applied) : onAdded(finalId, name)
    } catch (e) {
      searchError = e?.message || 'Could not add the tune. Please try again.'
    } finally {
      quickAddBusy = false
    }
  }
  function quickAdd(payload, name, result) {
    if (result?.on_list) {
      // Already on the list: not an add — hand off to the page to show/highlight it.
      close()
      onAlready(payload.tune_id ?? payload.thesession_id, name)
      return false
    }
    if (quickAddBusy) return false
    quickAddBusy = true
    searchError = ''
    doQuickAdd(
      { tune_id: payload.tune_id, thesession_id: payload.thesession_id ?? null, name, tune_type: payload.tune_type },
      name
    )
    return false // TuneSearch keeps its query; the pane closes itself on success
  }

  // ---- preview-form add: the configured values, resolved like previewAction ------
  async function previewSubmit(item, data, chosenSettingId, vals) {
    const name = data?.name ?? item.r.name
    const tune_type = data?.tune_type ?? item.r.tune_type
    // A remote result that resolved to a local tune adds locally; an unresolved
    // (or failed-load) remote stays a thesession import.
    const isImport = item.remote && !(data && data.is_local !== false)
    const target = isImport
      ? { tune_id: item.r.tune_id, thesession_id: item.r.tune_id, name, tune_type }
      : { tune_id: data?.tune_id ?? item.r.tune_id, thesession_id: null, name, tune_type }
    const { finalId, already, applied } = await performAdd(target, { ...vals, settingId: chosenSettingId })
    close()
    already ? onAlready(finalId, name, applied) : onAdded(finalId, name)
  }

  // ---- already-on-the-list actions (the panel that replaces the add form) --------
  // Both act on the viewer's EXISTING row, keyed by the person_tune_id the preview
  // payload carries, and both land on the page the way an add does.
  async function putPersonTune(ptid, body) {
    const res = await fetch(`/api/my-tunes/${ptid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    })
    const j = await res.json().catch(() => ({}))
    if (!res.ok || !j.success) throw new Error(j.error || 'That change could not be saved.')
    return j
  }

  // Adopt the setting the pager is on. Online-only: the server imports the setting's
  // notation when it isn't in our catalog yet (the pager pages thesession.org's list).
  async function updateSetting(item, data, chosenSettingId) {
    const pt = data?.person_tune
    if (!pt?.person_tune_id || chosenSettingId == null) return
    if (!navigator.onLine) throw new Error('You are offline. A specific setting can only be saved online.')
    await putPersonTune(pt.person_tune_id, { setting_id: chosenSettingId })
    const finalId = data?.tune_id ?? item.r.tune_id
    close()
    onAlready(finalId, data?.name ?? item.r.name, { setting_id: chosenSettingId })
  }

  // "I heard it again": bump the count, leave the setting (and everything else) alone.
  async function heardAgain(item, data) {
    const pt = data?.person_tune
    if (!pt?.person_tune_id) return
    const finalId = data?.tune_id ?? item.r.tune_id
    const name = data?.name ?? item.r.name
    if (!navigator.onLine) {
      // Offline the op-queue owns it — heard_count is an ABSOLUTE set, so a replay
      // can't double-count (spec 024's op vocabulary).
      await submitOp({ type: 'set_heard', tune_id: finalId, heard_count: (pt.heard_count ?? 0) + 1 })
      close()
      onAlready(finalId, name, { heard_count: (pt.heard_count ?? 0) + 1 })
      return
    }
    const res = await fetch(`/api/my-tunes/${pt.person_tune_id}/heard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
    })
    const j = await res.json().catch(() => ({}))
    if (!res.ok || !j.success) throw new Error(j.error || 'Could not update the heard count.')
    close()
    onAlready(finalId, name, { heard_count: j.heard_count ?? j.new_count })
  }
</script>

{#if pane.visible}
  <div class="mt-add-backdrop" class:mt-open={pane.shown} onclick={close} aria-hidden="true"></div>
  <div class="mt-add-pane" class:mt-open={pane.shown} role="dialog" aria-label="Add a tune to My Tunes">
    {#if syncMode}
      <SyncPane
        {thesessionUserId}
        onBack={() => (syncMode = false)}
        onClose={close}
        {onSynced}
      />
    {:else}
      <TuneSearch
        {config}
        variant="modal"
        title="Search for a tune"
        allowAsIs={false}
        dimOnList={true}
        {initialQuery}
        {history}
        onRemember={remember}
        onAdd={quickAdd}
        onClose={close}
      >
        {#snippet notice()}
          {#if searchError}<p class="mt-error mt-search-error">{searchError}</p>{/if}
          <!-- The folded-away sync page's new home: quiet one-liner, search stays primary. -->
          <button class="mt-sync-link" onclick={() => (syncMode = true)}>
            Have a tunebook on thesession.org? <span>Sync it here</span>
          </button>
        {/snippet}
        {#snippet previewFooter(item, data, chosenSettingId)}
          <!-- Keyed on the RESULT identity (not `data`): stable across the async preview
               load and settings backfill, but remounts fresh on ‹ › steps — notes typed
               for tune A can never leak onto tune B. -->
          {#key `${item.remote ? 'ts' : 'l'}:${item.r.tune_id}`}
            <AddTuneForm
              {instruments}
              {chosenSettingId}
              onList={!!(data?.person_tune?.on_list ?? item.r.on_list)}
              existing={data?.person_tune ?? null}
              onShowExisting={() => {
                close()
                onAlready(data?.tune_id ?? item.r.tune_id, data?.name ?? item.r.name)
              }}
              onCancel={close}
              onUpdateSetting={() => updateSetting(item, data, chosenSettingId)}
              onHeardAgain={() => heardAgain(item, data)}
              onSubmit={(vals) => previewSubmit(item, data, chosenSettingId, vals)}
            />
          {/key}
        {/snippet}
      </TuneSearch>
    {/if}
  </div>
{/if}

<script>
  // Tunebook sync view inside the add pane (folded-away /my-tunes/sync page):
  // fetch the person's thesession.org tunebook and add everything not already on
  // the list. Three sub-phases: form -> progress (indeterminate) -> results.
  import { Seg } from '../lib/index.js'
  import { STATUS_LABELS } from '../mylist.js'

  let {
    thesessionUserId = null, // saved person.thesession_user_id (null = never set)
    onBack, // back to the search phase
    onClose, // close the whole pane
    onSynced = () => {}, // fired on success so the page can refresh its list
  } = $props()

  const STATUSES = ['want to learn', 'learning', 'learned']
  const LABELS = STATUS_LABELS

  let savedId = $state(thesessionUserId) // cleared via the x to enter a different ID
  let inputId = $state('')
  let saveToProfile = $state(true)
  let learnStatus = $state('want to learn')
  let phase = $state('form') // 'form' | 'progress' | 'results'
  let errorMsg = $state('')
  let results = $state(null)

  function clearSavedId() {
    savedId = null
    inputId = ''
  }

  async function startSync() {
    const id = savedId != null ? Number(savedId) : parseInt(inputId, 10)
    if (!id || id < 1) {
      errorMsg = 'Please enter a valid thesession.org user ID.'
      return
    }
    if (!navigator.onLine) {
      errorMsg = 'You are offline. Sync requires an internet connection.'
      return
    }
    errorMsg = ''
    phase = 'progress'
    try {
      // Save the ID to the profile first (best-effort, same as the legacy page).
      if (savedId == null && saveToProfile) {
        await fetch('/api/person/me', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ thesession_user_id: id }),
        }).catch(() => {})
      }
      const res = await fetch('/api/my-tunes/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ thesession_user_id: id, learn_status: learnStatus }),
      })
      const j = await res.json().catch(() => ({}))
      if (!res.ok || j.success === false) {
        throw new Error(j.error || j.message || 'An error occurred during sync.')
      }
      results = j.results || {}
      if (savedId == null && saveToProfile) savedId = id
      phase = 'results'
      onSynced(results)
    } catch (e) {
      errorMsg = e?.message || 'An error occurred during sync.'
      phase = 'form'
    }
  }

  function syncAgain() {
    results = null
    errorMsg = ''
    phase = 'form'
  }
</script>

<div class="deep-head">
  <button class="mt-back" onclick={onBack} aria-label="Back to search">‹</button>
  <span class="deep-title">Sync from TheSession.org</span>
  <button class="deep-done" onclick={onClose}>Done</button>
</div>

<div class="mt-config mt-sync">
  {#if phase === 'form'}
    <p class="mt-sync-blurb">
      Imports your thesession.org tunebook: tunes you don't have yet are added, and
      tunes already on your list keep their current status.
    </p>

    {#if savedId != null}
      <div class="mt-section">
        <div class="mt-sync-saved">
          <span class="mt-label">TheSession.org ID:</span>
          <span class="mt-sync-saved-id">{savedId}</span>
          <button class="mt-sync-clear" onclick={clearSavedId} title="Use a different ID" aria-label="Use a different ID">✕</button>
        </div>
      </div>
    {:else}
      <div class="mt-section">
        <label class="mt-label" for="mt-sync-userid">TheSession.org ID</label>
        <input
          id="mt-sync-userid"
          class="mt-setting"
          type="number"
          min="1"
          placeholder="Enter your thesession.org user ID"
          bind:value={inputId}
          oninput={() => (errorMsg = '')}
        />
        <p class="mt-help">
          Find it in your thesession.org profile URL: thesession.org/members/<strong>YOUR_ID</strong>
        </p>
        <label class="mt-sync-save">
          <input type="checkbox" bind:checked={saveToProfile} />
          Save to my profile
        </label>
      </div>
    {/if}

    <div class="mt-section">
      <div class="tsc-label-line mt-label">Add new tunes as</div>
      <Seg
        options={STATUSES.map((st) => ({ id: st, label: LABELS[st] }))}
        value={learnStatus}
        idAttr="data-status"
        styled={false}
        segClass="tunebook-status-seg"
        optClass="tunebook-status-opt"
        onSelect={(st) => (learnStatus = st)} />
    </div>

    {#if errorMsg}<p class="mt-error">{errorMsg}</p>{/if}
    <button class="mt-submit" onclick={startSync}>Start Sync</button>
  {:else if phase === 'progress'}
    <div class="mt-sync-progress">
      <div class="mt-sync-bar"><div class="mt-sync-bar-fill"></div></div>
      <p class="mt-sync-status">Syncing your tunes from TheSession.org…</p>
      <p class="mt-help">Large tunebooks can take a minute.</p>
    </div>
  {:else}
    <div class="mt-sync-done">Sync complete!</div>
    <div class="mt-sync-stats">
      <div class="mt-sync-stat">
        <span class="mt-sync-stat-value">{results.tunes_fetched || 0}</span>
        <span class="mt-sync-stat-label">Tunes Fetched</span>
      </div>
      <div class="mt-sync-stat">
        <span class="mt-sync-stat-value">{results.person_tunes_added || 0}</span>
        <span class="mt-sync-stat-label">Tunes Added</span>
      </div>
      <div class="mt-sync-stat">
        <span class="mt-sync-stat-value">{results.person_tunes_skipped || 0}</span>
        <span class="mt-sync-stat-label">Already in Collection</span>
      </div>
      <div class="mt-sync-stat">
        <span class="mt-sync-stat-value">{results.tunes_created || 0}</span>
        <span class="mt-sync-stat-label">New Tune Records</span>
      </div>
    </div>
    {#if (results.errors || []).length}
      <div class="mt-section">
        <div class="mt-error">Errors encountered:</div>
        <ul class="mt-sync-errors">
          {#each results.errors as err}
            <li>{err}</li>
          {/each}
        </ul>
      </div>
    {/if}
    <button class="mt-submit" onclick={onClose}>View My Tunes</button>
    <button class="mt-sync-again" onclick={syncAgain}>Sync Again</button>
  {/if}
</div>

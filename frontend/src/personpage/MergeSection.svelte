<script>
  // i18n-converted
  // Danger-zone person merge (spec 040, system-admin only). Two-step flow in a
  // kit Sheet: pick the duplicate from a GLOBAL people list (this is admin
  // cleanup — deliberately NOT the session-scoped PersonPicker), then review
  // the server's preview (per-table moves, every colliding row's field-merge
  // outcome, profile fills/discards, account situation) before a final
  // destructive Dialog. The page's person survives by default; Swap flips
  // direction without leaving the sheet.
  let { person, personId } = $props()

  import { Chevron, Dialog, Sheet, SearchField, List, Chip, LoadError, toast, toastFailure, ServerError, t, tn } from '../lib/index.js'

  let open = $state(false)
  let step = $state('pick') // 'pick' | 'preview'
  let people = $state(null) // null = loading
  let peopleFailed = $state(false)
  let query = $state('')
  let active = $state(-1)

  let otherId = $state(null) // the picked duplicate person
  let winnerId = $state(null)
  let preview = $state(null) // null = loading
  let previewError = $state(null)
  let survivingUserId = $state(null)
  let confirmOpen = $state(false)
  let busy = $state(false)

  const loserId = $derived(winnerId === personId ? otherId : personId)

  function openSheet() {
    step = 'pick'
    query = ''
    otherId = null
    preview = null
    open = true
    if (!people) loadPeople()
  }

  function loadPeople() {
    peopleFailed = false
    fetch('/api/admin/people')
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new Error(data.error || 'Failed to load people')
        people = data.people.filter((p) => p.person_id !== personId)
      })
      .catch((e) => {
        console.error('Error loading people:', e)
        peopleFailed = true
      })
  }

  const q = $derived(query.trim().toLowerCase())
  const matches = $derived(
    !people
      ? []
      : people.filter(
          (p) =>
            !q ||
            (p.name || '').toLowerCase().includes(q) ||
            (p.email || '').toLowerCase().includes(q) ||
            (p.username || '').toLowerCase().includes(q)
        )
  )

  function pick(p) {
    otherId = p.person_id
    winnerId = personId // page person survives by default
    loadPreview()
  }

  function swap() {
    winnerId = winnerId === personId ? otherId : personId
    loadPreview()
  }

  function loadPreview() {
    step = 'preview'
    preview = null
    previewError = null
    survivingUserId = null
    fetch('/api/admin/people/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loser_person_id: loserId, winner_person_id: winnerId, confirm: false }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.error || '')
        preview = data
        // pre-select the survivor's account when only one needs no choice
        if (!data.accounts.needs_choice) {
          survivingUserId = null
        }
      })
      .catch((e) => {
        console.error('Merge preview failed:', e)
        // a server explanation is worth showing; a network/parse failure is not
        previewError = (e instanceof ServerError && e.message) || t("Couldn't build the merge preview.")
      })
  }

  // Returns the request so the confirm Dialog stays open and busy until it
  // settles; false keeps it open after a failure (toasted) for a retry.
  function executeMerge() {
    busy = true
    return fetch('/api/admin/people/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        loser_person_id: loserId,
        winner_person_id: winnerId,
        confirm: true,
        surviving_user_id: survivingUserId,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.error || '')
        toast(t('People merged'), 'success')
        // land on the survivor — a reload if they're this page, else navigate
        setTimeout(() => {
          if (winnerId === personId) window.location.reload()
          else window.location.href = `/admin/people/${winnerId}`
        }, 600)
        return true
      })
      .catch((e) => {
        busy = false
        toastFailure(t('merge these people'), e)
        return false
      })
  }

  const canConfirm = $derived(
    !!preview && !busy && (!preview.accounts.needs_choice || survivingUserId != null)
  )

  // Humanized table labels for the moves list.
  const MOVE_LABELS = {
    person_tune: (n) => tn(n, '{n} tunebook entry', '{n} tunebook entries'),
    person_instrument: (n) => tn(n, '{n} instrument', '{n} instruments'),
    person_tune_instrument: (n) => tn(n, '{n} per-instrument tune status', '{n} per-instrument tune statuses'),
    session_person: (n) => tn(n, '{n} session membership', '{n} session memberships'),
    session_instance_person: (n) => tn(n, '{n} attendance record', '{n} attendance records'),
    session_logger_color: (n) => tn(n, '{n} logger color', '{n} logger colors'),
    set_starter_attributions: (n) => tn(n, '{n} set-starter attribution', '{n} set-starter attributions'),
    recordings: (n) => tn(n, '{n} recording', '{n} recordings'),
    referred_by_pointers: (n) => tn(n, '{n} referral pointer', '{n} referral pointers'),
  }
  const moveLines = $derived(
    !preview
      ? []
      : Object.entries(preview.moves)
          .filter(([, n]) => n > 0)
          .map(([k, n]) => (MOVE_LABELS[k] ? MOVE_LABELS[k](n) : `${n} ${k}`))
  )

  // Per-collision compact diff: only fields where the three-way values differ.
  function diffRows(entry) {
    const rows = []
    for (const [field, merged] of Object.entries(entry.result)) {
      const w = entry.winner[field]
      const l = entry.loser[field]
      if (w === merged && l === merged) continue
      if (w == null && l == null && merged == null) continue
      rows.push({ field, winner: fmt(w), loser: fmt(l), merged: fmt(merged) })
    }
    return rows
  }
  const fmt = (v) =>
    v == null ? '—' : v === true ? t('yes') : v === false ? t('no') : String(v).slice(0, 60)

  const collisionCount = $derived(
    !preview
      ? 0
      : ['person_tune', 'person_instrument', 'session_person', 'session_instance_person'].reduce(
          (n, k) => n + preview.collisions[k].length,
          0
        )
  )
</script>

<h6 class="text-danger mt-4">{t('Merge with another person')}</h6>
<p class="text-muted">
  {t('If {name} exists twice in the database, merge the duplicate into this record. All tunes, attendance, memberships and attributions move to the survivor; the duplicate is deleted. This cannot be undone.', { name: person.name })}
</p>
<button type="button" class="btn btn-outline-danger" id="merge-person-btn" onclick={openSheet}>
  {t('Merge…')}
</button>

<Sheet bind:open title={step === 'pick' ? t('Merge with which person?') : t('Review merge')}>
  {#if step === 'pick'}
    <SearchField bind:value={query} placeholder={t('Search name, email or username…')} debounce={0} />
    {#if peopleFailed}
      <LoadError message={t("Couldn't load the people list.")} onRetry={loadPeople} />
    {:else if !people}
      <p class="ms-empty">{t('Loading people…')}</p>
    {:else}
      <List items={matches.slice(0, 50)} bind:active onSelect={pick}>
        {#snippet row(item)}
          <span class="ms-row">
            <span class="ms-name">{item.name}</span>
            {#if item.username}<Chip label={item.username} />{/if}
            <span class="ms-meta">
              {item.email || t('no email')}
              {#if item.session_count} · {tn(item.session_count, '{n} session', '{n} sessions')}{/if}
              {#if item.tune_count} · {tn(item.tune_count, '{n} tune', '{n} tunes')}{/if}
            </span>
          </span>
        {/snippet}
      </List>
      {#if matches.length === 0}
        <p class="ms-empty">{t('No one matches.')}</p>
      {:else if matches.length > 50}
        <p class="ms-empty">{t('Showing first 50 — keep typing to narrow.')}</p>
      {/if}
    {/if}
  {:else if previewError}
    <button type="button" class="ms-back" onclick={() => (step = 'pick')}><Chevron dir="left" size={14} /> {t('Back to list')}</button>
    <LoadError message={previewError} onRetry={loadPreview} />
  {:else if !preview}
    <p class="ms-empty">{t('Building preview…')}</p>
  {:else}
    <button type="button" class="ms-back" onclick={() => (step = 'pick')}><Chevron dir="left" size={14} /> {t('Back to list')}</button>
    <div class="ms-direction">
      <div class="ms-person ms-loser">
        <span class="ms-fate">{t('Merged away')}</span>
        <strong>{preview.loser.name}</strong>
        <span class="ms-meta">{preview.loser.email || t('no email')}</span>
        {#if preview.loser.account}<Chip label={preview.loser.account.username} />{/if}
      </div>
      <div class="ms-arrow">→</div>
      <div class="ms-person ms-winner">
        <span class="ms-fate">{t('Survives')}</span>
        <strong>{preview.winner.name}</strong>
        <span class="ms-meta">{preview.winner.email || t('no email')}</span>
        {#if preview.winner.account}<Chip label={preview.winner.account.username} />{/if}
      </div>
    </div>
    <button type="button" class="btn btn-sm btn-outline-secondary ms-swap" onclick={swap}>
      ⇄ {t('Swap direction')}
    </button>

    {#if preview.warnings.length}
      <div class="alert alert-warning ms-block">
        <ul class="mb-0 ps-3">
          {#each preview.warnings as w}<li>{w}</li>{/each}
        </ul>
      </div>
    {/if}

    {#if preview.accounts.needs_choice}
      <div class="ms-block ms-accounts">
        <h6>{t('Which login account survives?')}</h6>
        {#each [preview.winner, preview.loser] as p}
          <label class="ms-account">
            <input
              type="radio"
              name="surviving-account"
              value={p.account.user_id}
              checked={survivingUserId === p.account.user_id}
              onchange={() => (survivingUserId = p.account.user_id)}
            />
            <span
              ><strong>{p.account.username}</strong> ({p.account.user_email}) — {t("{name}'s account", { name: p.name })}</span
            >
          </label>
        {/each}
        <p class="ms-meta">{t('The other account is deleted; its activity is re-attributed to the survivor.')}</p>
      </div>
    {/if}

    <div class="ms-block">
      <h6>{t('Will move to {name}', { name: preview.winner.name })}</h6>
      {#if moveLines.length}
        <ul class="ps-3 mb-0">
          {#each moveLines as line}<li>{line}</li>{/each}
        </ul>
      {:else}
        <p class="ms-meta mb-0">{t('Nothing — the duplicate has no linked records.')}</p>
      {/if}
    </div>

    {#if collisionCount}
      <div class="ms-block">
        <h6>{t('Overlapping records ({n}) — merged field by field', { n: collisionCount })}</h6>

        {#each preview.collisions.person_tune as c}
          <div class="ms-collision">
            <strong>{c.tune_name}</strong> <span class="ms-meta">{t('(tunebook)')}</span>
            <table class="ms-diff">
              <tbody>
                {#each diffRows(c) as r}
                  <tr><td>{r.field}</td><td>{r.winner}</td><td>{r.loser}</td><td>→ {r.merged}</td></tr>
                {/each}
                {#each c.instrument_overrides as o}
                  <tr
                    ><td>{o.instrument}</td><td>{fmt(o.winner_status)}</td><td>{fmt(o.loser_status)}</td><td
                      >→ {o.result.status}</td
                    ></tr
                  >
                {/each}
              </tbody>
            </table>
          </div>
        {/each}

        {#each preview.collisions.person_instrument as c}
          <div class="ms-collision">
            <strong>{c.instrument}</strong> <span class="ms-meta">{t('(instrument)')}</span>
            <table class="ms-diff"><tbody>
              {#each diffRows(c) as r}
                <tr><td>{r.field}</td><td>{r.winner}</td><td>{r.loser}</td><td>→ {r.merged}</td></tr>
              {/each}
            </tbody></table>
          </div>
        {/each}

        {#each preview.collisions.session_person as c}
          <div class="ms-collision">
            <strong>{c.session_name}</strong> <span class="ms-meta">{t('(membership)')}</span>
            <table class="ms-diff"><tbody>
              {#each diffRows(c) as r}
                <tr><td>{r.field}</td><td>{r.winner}</td><td>{r.loser}</td><td>→ {r.merged}</td></tr>
              {/each}
            </tbody></table>
          </div>
        {/each}

        {#each preview.collisions.session_instance_person as c}
          <div class="ms-collision">
            <strong>{c.session_name} · {c.date}</strong> <span class="ms-meta">{t('(attendance)')}</span>
            <table class="ms-diff"><tbody>
              {#each diffRows(c) as r}
                <tr><td>{r.field}</td><td>{r.winner}</td><td>{r.loser}</td><td>→ {r.merged}</td></tr>
              {/each}
            </tbody></table>
          </div>
        {/each}
      </div>
    {/if}

    {#if Object.keys(preview.profile.fills).length}
      <div class="ms-block">
        <h6>{t('Profile fields inherited from the duplicate')}</h6>
        <ul class="ps-3 mb-0">
          {#each Object.entries(preview.profile.fills) as [field, value]}
            <li>{field}: {value}</li>
          {/each}
        </ul>
      </div>
    {/if}
  {/if}

  {#snippet footer()}
    {#if step === 'preview' && preview}
      <button
        type="button"
        class="btn btn-danger w-100"
        disabled={!canConfirm}
        onclick={() => (confirmOpen = true)}
      >
        {t('Merge {loser} into {winner}…', { loser: preview.loser.name, winner: preview.winner.name })}
      </button>
    {/if}
  {/snippet}
</Sheet>

<Dialog
  bind:open={confirmOpen}
  title={t('Merge these people?')}
  description={preview
    ? t("{loser} will be deleted and everything they're linked to re-attributed to {winner}. This cannot be undone.", { loser: preview.loser.name, winner: preview.winner.name })
    : ''}
  confirmLabel={t('Merge people')}
  busyLabel={t('Merging…')}
  destructive={true}
  onConfirm={executeMerge}
/>

<style>
  .ms-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    width: 100%;
    flex-wrap: wrap;
  }
  .ms-name {
    font-weight: 500;
  }
  .ms-meta {
    font-size: 0.8rem;
    opacity: 0.65;
  }
  .ms-empty {
    opacity: 0.6;
    padding: 0.8rem 0.2rem;
    margin: 0;
  }
  .ms-back {
    display: block;
    background: none;
    border: 0;
    padding: 0.4rem 0.2rem;
    margin-bottom: 0.3rem;
    cursor: pointer;
    color: inherit;
    font: inherit;
    opacity: 0.85;
  }
  .ms-back:hover {
    opacity: 1;
    text-decoration: underline;
  }
  .ms-direction {
    display: flex;
    align-items: stretch;
    gap: 0.6rem;
    margin-bottom: 0.5rem;
  }
  .ms-person {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.6rem;
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }
  .ms-winner {
    border-color: var(--success, #28a745);
  }
  .ms-loser {
    border-color: var(--danger, #dc3545);
  }
  .ms-fate {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.6;
  }
  .ms-arrow {
    align-self: center;
    font-size: 1.2rem;
    opacity: 0.6;
  }
  .ms-swap {
    margin-bottom: 0.8rem;
  }
  .ms-block {
    margin: 0.9rem 0;
  }
  .ms-block h6 {
    margin-bottom: 0.35rem;
  }
  .ms-accounts .ms-account {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    margin: 0.25rem 0;
  }
  .ms-collision {
    margin: 0.6rem 0;
  }
  .ms-diff {
    width: 100%;
    font-size: 0.82rem;
    margin-top: 0.2rem;
  }
  .ms-diff td {
    padding: 0.15rem 0.5rem 0.15rem 0;
    border-bottom: 1px solid var(--border-color);
    vertical-align: top;
  }
  .ms-diff td:first-child {
    opacity: 0.7;
    white-space: nowrap;
  }
</style>

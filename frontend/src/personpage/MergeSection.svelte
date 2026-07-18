<script>
  // Danger-zone person merge (spec 040, system-admin only). Two-step flow in a
  // kit Sheet: pick the duplicate from a GLOBAL people list (this is admin
  // cleanup — deliberately NOT the session-scoped PersonPicker), then review
  // the server's preview (per-table moves, every colliding row's field-merge
  // outcome, profile fills/discards, account situation) before a final
  // destructive Dialog. The page's person survives by default; Swap flips
  // direction without leaving the sheet.
  let { person, personId } = $props()

  import { Dialog, Sheet, SearchField, List, Chip, toast } from '../lib/index.js'

  let open = $state(false)
  let step = $state('pick') // 'pick' | 'preview'
  let people = $state(null) // null = loading
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
    if (!people) {
      fetch('/api/admin/people')
        .then((r) => r.json())
        .then((data) => {
          if (!data.success) throw new Error(data.error || 'Failed to load people')
          people = data.people.filter((p) => p.person_id !== personId)
        })
        .catch((e) => {
          toast('Error loading people: ' + e.message, 'error')
          open = false
        })
    }
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
        if (!data.success) throw new Error(data.error || 'Preview failed')
        preview = data
        // pre-select the survivor's account when only one needs no choice
        if (!data.accounts.needs_choice) {
          survivingUserId = null
        }
      })
      .catch((e) => {
        previewError = e.message
      })
  }

  function executeMerge() {
    busy = true
    fetch('/api/admin/people/merge', {
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
        if (!data.success) throw new Error(data.error || 'Merge failed')
        toast('People merged', 'success')
        // land on the survivor — a reload if they're this page, else navigate
        setTimeout(() => {
          if (winnerId === personId) window.location.reload()
          else window.location.href = `/admin/people/${winnerId}`
        }, 600)
      })
      .catch((e) => {
        busy = false
        toast('Merge failed: ' + e.message, 'error')
      })
  }

  const canConfirm = $derived(
    !!preview && !busy && (!preview.accounts.needs_choice || survivingUserId != null)
  )

  // Humanized table labels for the moves list.
  const MOVE_LABELS = {
    person_tune: 'tunebook entries',
    person_instrument: 'instruments',
    person_tune_instrument: 'per-instrument tune statuses',
    session_person: 'session memberships',
    session_instance_person: 'attendance records',
    session_logger_color: 'logger colors',
    set_starter_attributions: 'set-starter attributions',
    recordings: 'recordings',
    referred_by_pointers: 'referral pointers',
  }
  const moveLines = $derived(
    !preview
      ? []
      : Object.entries(preview.moves)
          .filter(([, n]) => n > 0)
          .map(([k, n]) => `${n} ${MOVE_LABELS[k] || k}`)
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
    v == null ? '—' : v === true ? 'yes' : v === false ? 'no' : String(v).slice(0, 60)

  const collisionCount = $derived(
    !preview
      ? 0
      : ['person_tune', 'person_instrument', 'session_person', 'session_instance_person'].reduce(
          (n, k) => n + preview.collisions[k].length,
          0
        )
  )
</script>

<h6 class="text-danger mt-4">Merge with another person</h6>
<p class="text-muted">
  If {person.name} exists twice in the database, merge the duplicate into this record. All
  tunes, attendance, memberships and attributions move to the survivor; the duplicate is
  deleted. This cannot be undone.
</p>
<button type="button" class="btn btn-outline-danger" id="merge-person-btn" onclick={openSheet}>
  Merge…
</button>

<Sheet bind:open title={step === 'pick' ? 'Merge with which person?' : 'Review merge'}>
  {#if step === 'pick'}
    <SearchField bind:value={query} placeholder="Search name, email or username…" debounce={0} />
    {#if !people}
      <p class="ms-empty">Loading people…</p>
    {:else}
      <List items={matches.slice(0, 50)} bind:active onSelect={pick}>
        {#snippet row(item)}
          <span class="ms-row">
            <span class="ms-name">{item.name}</span>
            {#if item.username}<Chip label={item.username} />{/if}
            <span class="ms-meta">
              {item.email || 'no email'}
              {#if item.session_count} · {item.session_count} sessions{/if}
              {#if item.tune_count} · {item.tune_count} tunes{/if}
            </span>
          </span>
        {/snippet}
      </List>
      {#if matches.length === 0}
        <p class="ms-empty">No one matches.</p>
      {:else if matches.length > 50}
        <p class="ms-empty">Showing first 50 — keep typing to narrow.</p>
      {/if}
    {/if}
  {:else if previewError}
    <button type="button" class="ms-back" onclick={() => (step = 'pick')}>‹ Back to list</button>
    <div class="alert alert-danger">{previewError}</div>
  {:else if !preview}
    <p class="ms-empty">Building preview…</p>
  {:else}
    <button type="button" class="ms-back" onclick={() => (step = 'pick')}>‹ Back to list</button>
    <div class="ms-direction">
      <div class="ms-person ms-loser">
        <span class="ms-fate">Merged away</span>
        <strong>{preview.loser.name}</strong>
        <span class="ms-meta">{preview.loser.email || 'no email'}</span>
        {#if preview.loser.account}<Chip label={preview.loser.account.username} />{/if}
      </div>
      <div class="ms-arrow">→</div>
      <div class="ms-person ms-winner">
        <span class="ms-fate">Survives</span>
        <strong>{preview.winner.name}</strong>
        <span class="ms-meta">{preview.winner.email || 'no email'}</span>
        {#if preview.winner.account}<Chip label={preview.winner.account.username} />{/if}
      </div>
    </div>
    <button type="button" class="btn btn-sm btn-outline-secondary ms-swap" onclick={swap}>
      ⇄ Swap direction
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
        <h6>Which login account survives?</h6>
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
              ><strong>{p.account.username}</strong> ({p.account.user_email}) — {p.name}'s
              account</span
            >
          </label>
        {/each}
        <p class="ms-meta">The other account is deleted; its activity is re-attributed to the survivor.</p>
      </div>
    {/if}

    <div class="ms-block">
      <h6>Will move to {preview.winner.name}</h6>
      {#if moveLines.length}
        <ul class="ps-3 mb-0">
          {#each moveLines as line}<li>{line}</li>{/each}
        </ul>
      {:else}
        <p class="ms-meta mb-0">Nothing — the duplicate has no linked records.</p>
      {/if}
    </div>

    {#if collisionCount}
      <div class="ms-block">
        <h6>Overlapping records ({collisionCount}) — merged field by field</h6>

        {#each preview.collisions.person_tune as c}
          <div class="ms-collision">
            <strong>{c.tune_name}</strong> <span class="ms-meta">(tunebook)</span>
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
            <strong>{c.instrument}</strong> <span class="ms-meta">(instrument)</span>
            <table class="ms-diff"><tbody>
              {#each diffRows(c) as r}
                <tr><td>{r.field}</td><td>{r.winner}</td><td>{r.loser}</td><td>→ {r.merged}</td></tr>
              {/each}
            </tbody></table>
          </div>
        {/each}

        {#each preview.collisions.session_person as c}
          <div class="ms-collision">
            <strong>{c.session_name}</strong> <span class="ms-meta">(membership)</span>
            <table class="ms-diff"><tbody>
              {#each diffRows(c) as r}
                <tr><td>{r.field}</td><td>{r.winner}</td><td>{r.loser}</td><td>→ {r.merged}</td></tr>
              {/each}
            </tbody></table>
          </div>
        {/each}

        {#each preview.collisions.session_instance_person as c}
          <div class="ms-collision">
            <strong>{c.session_name} · {c.date}</strong> <span class="ms-meta">(attendance)</span>
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
        <h6>Profile fields inherited from the duplicate</h6>
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
        Merge {preview.loser.name} into {preview.winner.name}…
      </button>
    {/if}
  {/snippet}
</Sheet>

<Dialog
  bind:open={confirmOpen}
  title="Merge these people?"
  description={preview
    ? `${preview.loser.name} will be deleted and everything they're linked to re-attributed to ${preview.winner.name}. This cannot be undone.`
    : ''}
  confirmLabel="Merge people"
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

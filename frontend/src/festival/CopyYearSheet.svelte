<script>
  // "Copy to a new year" (spec 056). One form, two entry points: a year's admin
  // Details tab (source = that year) and the festival picker's "Add a year"
  // (source = the most recent year). The server copies the venue, timezone,
  // settings and the admins; this form only asks what changes: the year, its
  // dates and its name. POST /api/sessions/<source>/copy-year.
  import { untrack } from 'svelte'
  import { Sheet } from '../lib/index.js'
  import { nudgeRange } from './dates.js'

  let {
    open = $bindable(false),
    festival, // { place: { slug, name }, years: [{ year, path, ... }] }
    source, // the year copied from: { path, year, initiation_date, termination_date }
    navigate = (url) => window.location.assign(url),
  } = $props()

  const taken = $derived(new Set((festival?.years || []).map((y) => y.year)))
  const latest = $derived(Math.max(...(festival?.years || []).map((y) => y.year), source?.year || 0))

  let yearText = $state('')
  let start = $state('')
  let end = $state('')
  let name = $state('')
  let datesEdited = $state(false)
  let nameEdited = $state(false)
  let error = $state('')
  let saving = $state(false)

  // Every open starts from the defaults: the year after the latest, the source's
  // dates moved to it, "{festival} {year}".
  // Depends on `open` alone: the body reads the edited flags, which must not re-run it.
  $effect(() => {
    if (!open) return
    untrack(() => {
      datesEdited = false
      nameEdited = false
      error = ''
      saving = false
      setYear(String(latest + 1))
    })
  })

  const year = $derived(/^\d{4}$/.test(yearText.trim()) ? Number(yearText.trim()) : null)

  function setYear(text) {
    yearText = text
    const y = /^\d{4}$/.test(text.trim()) ? Number(text.trim()) : null
    if (y == null) return
    if (!datesEdited) {
      const moved = nudgeRange(source?.initiation_date, source?.termination_date, y)
      start = moved.start || ''
      end = moved.end || moved.start || ''
    }
    if (!nameEdited) name = `${festival?.place?.name || ''} ${y}`.trim()
  }

  function validate() {
    if (year == null) return 'Year must be four digits, like 2026'
    if (taken.has(year)) return `${festival.place.name} already has ${year}`
    if (!start || !end) return 'First and last day are both required'
    if (end < start) return "The last day can't be before the first"
    return ''
  }

  async function save() {
    error = validate()
    if (error) return
    saving = true
    try {
      const resp = await fetch(`/api/sessions/${source.path}/copy-year`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ year, initiation_date: start, termination_date: end, name: name.trim() }),
      })
      const data = await resp.json()
      if (resp.ok && data.success) {
        navigate(`/admin/sessions/${data.path}`)
        return
      }
      error = data.message || data.error || "Couldn't copy the year. Try again."
    } catch {
      error = "Couldn't copy the year. Check your connection and try again."
    }
    saving = false
  }
</script>

<Sheet bind:open title="Copy to a new year" compact>
  <form class="copy-year-form" id="copyYearForm" onsubmit={(e) => { e.preventDefault(); save() }}>
    <p class="copy-year-from">From {festival?.place?.name} {source?.year}: venue, timezone, settings and admins.</p>
    <div class="kit-group">
      <div class="kit-field">
        <label for="copyYearYear">Year</label>
        <input id="copyYearYear" type="text" inputmode="numeric" maxlength="4" value={yearText}
          oninput={(e) => setYear(e.currentTarget.value)} />
      </div>
      <div class="kit-field">
        <label for="copyYearStart">First day</label>
        <input id="copyYearStart" type="date" bind:value={start} oninput={() => (datesEdited = true)} />
      </div>
      <div class="kit-field">
        <label for="copyYearEnd">Last day</label>
        <input id="copyYearEnd" type="date" bind:value={end} oninput={() => (datesEdited = true)} />
      </div>
      <div class="kit-field">
        <label for="copyYearName">Name</label>
        <input id="copyYearName" type="text" bind:value={name} oninput={() => (nameEdited = true)} />
      </div>
      <div class="kit-field">
        <span class="copy-year-label">Web address</span>
        <code class="copy-year-path" id="copyYearPath">/sessions/{festival?.place?.slug}/{year ?? '…'}</code>
      </div>
    </div>
    {#if error}
      <div class="copy-year-error" role="alert">{error}</div>
    {/if}
    <button type="submit" class="copy-year-save" id="copyYearSave" disabled={saving}>
      {saving ? 'Copying…' : `Create ${year ?? 'year'}`}
    </button>
  </form>
</Sheet>

<style>
  .copy-year-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .copy-year-from {
    margin: 0;
    font-size: 0.85rem;
    color: var(--secondary-text, #888);
  }

  .copy-year-form .kit-group {
    margin-bottom: 0;
  }

  .copy-year-label {
    flex: none;
  }

  /* theme.css gives every <code> a light-theme chip; this is a value, not code. */
  .copy-year-path {
    margin-left: auto;
    font-size: 0.82rem;
    color: var(--text-color, #e0e0e0);
    background: transparent;
    padding: 0;
  }

  .copy-year-error {
    font-size: 0.85rem;
    color: var(--danger, #dc3545);
  }

  .copy-year-save {
    width: 100%;
    padding: 12px 16px;
    font: inherit;
    font-weight: 600;
    color: #fff;
    background: var(--primary-fill, #4a8049);
    border: none;
    border-radius: var(--r, 8px);
    cursor: pointer;
  }

  .copy-year-save:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>

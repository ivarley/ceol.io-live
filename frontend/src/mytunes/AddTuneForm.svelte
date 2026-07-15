<script>
  // The add form living in TunePreview's footer (My Tunes pane): "Add as" +
  // per-instrument roll-up + collapsed notes + the add button. Owns ALL per-tune
  // form state — the parent keys this component on the previewed tune's identity,
  // so stepping ‹ › to another tune remounts it fresh (no notes leaking across).
  import { Chip, Seg } from '../lib/index.js'

  let {
    instruments = [], // the person's instruments [{instrument, is_auto}]
    onList = false, // tune already on the list: show the hand-off button, no form
    onSubmit, // async ({status, notes, overrides}) — throws Error(message) on failure
    onShowExisting = () => {}, // on-list hand-off (close pane + highlight on the page)
  } = $props()

  const STATUSES = ['want to learn', 'learning', 'learned']
  const LABELS = { 'want to learn': 'Want To Learn', learning: 'Learning', learned: 'Learned' }

  let baseStatus = $state('want to learn')
  let instOpen = $state(false)
  let instChoices = $state({}) // instrument -> status ('want to learn'|...|null). Missing key = default.
  let notes = $state('')
  let notesOpen = $state(false) // notes fold out on demand — keeps the footer compact
  let submitting = $state(false)
  let errorMsg = $state('')

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

  async function handleSubmit() {
    if (submitting) return
    errorMsg = ''
    submitting = true
    try {
      await onSubmit({ status: baseStatus, notes: notes.trim(), overrides: instrumentOverrides() })
      // success closes the pane; this component unmounts with it
    } catch (e) {
      errorMsg = e?.message || 'Could not add the tune. Please try again.'
      submitting = false
    }
  }
</script>

{#if onList}
  <button class="pv-action mt-onlist" onclick={onShowExisting}>★ Already on your list — show it</button>
{:else}
  <div class="mt-form">
    <div class="mt-form-row">
      <span class="mt-label">Add as</span>
      {#if instruments.length >= 2}
        <button class="tsc-expand-link mt-expand" onclick={() => (instOpen = !instOpen)}>
          {instOpen ? 'Hide Instruments' : 'By Instrument'}
        </button>
      {/if}
    </div>
    <Seg
      options={STATUSES.map((st) => ({ id: st, label: LABELS[st] }))}
      value={baseStatus}
      idAttr="data-status"
      styled={false}
      segClass="tunebook-status-seg"
      optClass="tunebook-status-opt"
      onSelect={(st) => (baseStatus = st)} />
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

    {#if notesOpen}
      <!-- svelte-ignore a11y_autofocus -->
      <textarea
        class="mt-notes"
        placeholder="Add any notes about this tune…"
        autofocus
        bind:value={notes}
      ></textarea>
    {:else}
      <button class="mt-note-toggle" onclick={() => (notesOpen = true)}>＋ Add note</button>
    {/if}

    {#if errorMsg}<p class="mt-error">{errorMsg}</p>{/if}
    <button class="pv-action mt-submit" disabled={submitting} onclick={handleSubmit}>
      {submitting ? 'Adding…' : '＋ Add to My Tunes'}
    </button>
  </div>
{/if}

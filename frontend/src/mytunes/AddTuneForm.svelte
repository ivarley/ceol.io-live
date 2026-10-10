<script>
  // i18n-converted
  // The add form living in TunePreview's footer (My Tunes pane): "Add as" +
  // per-instrument roll-up + collapsed notes + the add button. Owns ALL per-tune
  // form state — the parent keys this component on the previewed tune's identity,
  // so stepping ‹ › to another tune remounts it fresh (no notes leaking across).
  import { Chip, Seg, t, instrumentName } from '../lib/index.js'
  import { statusLabel as LABEL, failText } from './labels.js'

  let {
    instruments = [], // the person's instruments [{instrument, is_auto}]
    onList = false, // tune already on the list: the on-list panel replaces the form
    // The viewer's own row when onList — {learn_status, setting_id, heard_count}, from
    // the preview payload. A pasted link can land here without ever having said "add".
    existing = null,
    chosenSettingId = null, // the setting the pager is on, when the user pointed at one
    onSubmit, // async ({status, notes, overrides}) — throws Error(message) on failure
    onShowExisting = () => {}, // on-list hand-off (close pane + highlight on the page)
    onUpdateSetting, // async () — adopt chosenSettingId as the setting I play
    onHeardAgain, // async () — bump heard_count, leaving the setting alone
    onCancel = () => {}, // walk away unchanged (just closes the pane)
  } = $props()

  const STATUSES = ['want to learn', 'learning', 'learned']

  // ---- already-on-the-list panel ------------------------------------------------
  // Offering "Update Setting" only makes sense when the user actually pointed at a
  // setting AND it isn't the one already recorded — otherwise there is nothing to update.
  const settingDiffers = $derived(chosenSettingId != null && chosenSettingId !== (existing?.setting_id ?? null))
  const statusLabel = $derived(existing?.learn_status ? LABEL(existing.learn_status) : null)
  const heardCount = $derived(existing?.heard_count ?? 0)
  let onListBusy = $state('') // '' | 'setting' | 'heard' — which on-list action is in flight
  let onListError = $state('')

  async function runOnListAction(kind, fn) {
    if (onListBusy) return
    onListError = ''
    onListBusy = kind
    try {
      await fn()
      // success closes the pane; this component unmounts with it
    } catch (e) {
      onListError = failText(e, kind === 'heard' ? t('update the heard count') : t('update your setting'))
      onListBusy = ''
    }
  }

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
      errorMsg = failText(e, t('add the tune'))
      submitting = false
    }
  }
</script>

{#if onList}
  <!-- Already yours: not an add. Say so (with the status, so the panel answers "what do
       I have on this tune?"), and offer only what's actually left to do here. -->
  <div class="mt-onlist-panel">
    <button class="mt-onlist-head" onclick={onShowExisting} title={t('Show this tune on your list')}>
      <span class="mt-onlist-star">★</span> {t('Already on your list')}
      {#if statusLabel}<span class="mt-onlist-status">{statusLabel}</span>{/if}
    </button>
    {#if settingDiffers}
      <p class="mt-onlist-ask">
        {#if existing?.setting_id != null}
          {t('You play setting')} <strong>#{existing.setting_id}</strong> — {t('this link points at')}
          <strong>#{chosenSettingId}</strong>. {t('Update it?')}
        {:else}
          {t("You haven't picked a setting yet.")} {t('Use')} <strong>#{chosenSettingId}</strong>?
        {/if}
      </p>
    {/if}
    {#if onListError}<p class="mt-error">{onListError}</p>{/if}
    <div class="mt-onlist-actions">
      {#if settingDiffers}
        <button
          class="pv-action mt-onlist-primary"
          disabled={!!onListBusy}
          onclick={() => runOnListAction('setting', () => onUpdateSetting())}>
          {onListBusy === 'setting' ? t('Updating…') : t('Update Setting')}
        </button>
      {/if}
      <button
        class="pv-action mt-onlist-secondary"
        disabled={!!onListBusy}
        onclick={() => runOnListAction('heard', () => onHeardAgain())}>
        {onListBusy === 'heard' ? t('Saving…') : heardCount ? t('I Heard It Again ({n})', { n: heardCount }) : t('I Heard It Again')}
      </button>
      <button class="pv-action mt-onlist-cancel" disabled={!!onListBusy} onclick={onCancel}>{t('Cancel')}</button>
    </div>
  </div>
{:else}
  <div class="mt-form">
    <div class="mt-form-row">
      <span class="mt-label">{t('Add as')}</span>
      {#if instruments.length >= 2}
        <button class="tsc-expand-link mt-expand" onclick={() => (instOpen = !instOpen)}>
          {instOpen ? t('Hide Instruments') : t('By Instrument')}
        </button>
      {/if}
    </div>
    <Seg
      options={STATUSES.map((st) => ({ id: st, label: LABEL(st) }))}
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
              {instrumentName(inst.instrument)}
              {#if !inst.is_auto}<Chip label={t('manual')} styled={false} chipClass="mt-manual-badge" />{/if}
              {#if effectiveStatus(inst) === null}<Chip label={t('not tracking')} styled={false} chipClass="mt-untracked" />{/if}
            </div>
            <Seg
              options={STATUSES.map((st) => ({ id: st, label: LABEL(st) }))}
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
        placeholder={t('Add any notes about this tune…')}
        autofocus
        bind:value={notes}
      ></textarea>
    {:else}
      <button class="mt-note-toggle" onclick={() => (notesOpen = true)}>＋ {t('Add note')}</button>
    {/if}

    {#if errorMsg}<p class="mt-error">{errorMsg}</p>{/if}
    <button class="pv-action mt-submit" disabled={submitting} onclick={handleSubmit}>
      {submitting ? t('Adding…') : t('＋ Add to My Tunes')}
    </button>
  </div>
{/if}

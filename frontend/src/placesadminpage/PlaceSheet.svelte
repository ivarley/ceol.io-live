<script>
  // i18n-converted
  // Edit a place, or add one (spec 055 "Places admin page"). A changed slug is a
  // rename: every session path under it moves and the old addresses redirect.
  import { untrack } from 'svelte'
  import { Dialog, Sheet, toast, t, tn } from '../lib/index.js'
  import { canDelete, parentOptions } from './logic.js'

  let {
    open = $bindable(false),
    place = null, // null: add a place
    places = [],
    onSaved = () => {}, // (payload) after any successful write
  } = $props()

  let name = $state('')
  let slug = $state('')
  let area = $state('')
  let country = $state('')
  let parentId = $state('')
  let error = $state('')
  let saving = $state(false)
  let confirmDelete = $state(false)

  $effect(() => {
    if (!open) return
    untrack(() => {
      name = place?.name || ''
      slug = place?.slug || ''
      area = place?.area || ''
      country = place?.country || ''
      parentId = place?.parent ? String(place.parent.place_id) : ''
      error = ''
      saving = false
    })
  })

  const isFestival = $derived(place?.kind === 'festival')
  const options = $derived(parentOptions(places, place))
  const renaming = $derived(!!place && slug.trim() && slug.trim() !== place.slug)

  async function send(method, url, body) {
    const resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || data.message || t('Something went wrong'))
    return data
  }

  async function save() {
    error = ''
    saving = true
    const body = {
      name: name.trim(),
      slug: slug.trim(),
      area: area.trim(),
      country: country.trim(),
      parent_place_id: parentId ? Number(parentId) : null,
    }
    try {
      const data = place
        ? await send('PUT', `/api/admin/places/${place.place_id}`, body)
        : await send('POST', '/api/admin/places', body)
      const moved = data.moved?.length
      toast(moved ? tn(moved, 'Saved; {n} path moved', 'Saved; {n} paths moved') : t('Saved'), 'success')
      open = false
      onSaved(data)
    } catch (e) {
      error = e.message
    }
    saving = false
  }

  async function remove() {
    try {
      const data = await send('DELETE', `/api/admin/places/${place.place_id}`)
      toast(t('Deleted {name}', { name: place.name }), 'success')
      open = false
      onSaved(data)
    } catch (e) {
      toast(e.message, 'error')
      return false
    }
  }
</script>

<Sheet bind:open title={place ? t('Edit {name}', { name: place.name }) : t('Add a place')} compact>
  <form class="place-form" id="placeForm" onsubmit={(e) => { e.preventDefault(); save() }}>
    <div class="kit-group">
      <div class="kit-field">
        <label for="placeName">{t('Name')}</label>
        <input id="placeName" type="text" bind:value={name} placeholder={t('Required')} />
      </div>
      <div class="kit-field">
        <label for="placeSlug">{t('Slug')}</label>
        <input id="placeSlug" type="text" bind:value={slug} placeholder={place ? '' : t('From the name')} />
      </div>
      {#if !isFestival}
        <div class="kit-field">
          <label for="placeArea">{t('State / area')}</label>
          <input id="placeArea" type="text" bind:value={area} />
        </div>
        <div class="kit-field">
          <label for="placeCountry">{t('Country')}</label>
          <input id="placeCountry" type="text" bind:value={country} />
        </div>
      {/if}
      <div class="kit-field">
        <label for="placeParent">{isFestival ? t('Town') : t('Inside')}</label>
        <select id="placeParent" bind:value={parentId}>
          {#if !isFestival}<option value="">{t('Nothing (top level)')}</option>{/if}
          {#each options as p (p.place_id)}
            <option value={String(p.place_id)}>{p.name}{p.area ? `, ${p.area}` : ''}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if renaming}
      <p class="place-note" id="placeRenameNote">
        {tn(place.paths, 'Renaming moves {n} session from {from} to {to}. Old links keep working.', 'Renaming moves {n} sessions from {from} to {to}. Old links keep working.', { from: `/sessions/${place.slug}/…`, to: `/sessions/${slug.trim()}/…` })}
      </p>
    {/if}
    {#if error}
      <div class="place-error" role="alert">{error}</div>
    {/if}

    <button type="submit" class="place-save" id="placeSave" disabled={saving}>
      {saving ? t('Saving…') : place ? t('Save') : t('Add place')}
    </button>
    {#if place && canDelete(place)}
      <button type="button" class="place-delete" id="placeDelete" onclick={() => (confirmDelete = true)}>
        {t('Delete {name}', { name: place.name })}
      </button>
    {/if}
  </form>
</Sheet>

<Dialog
  bind:open={confirmDelete}
  title={t('Delete {name}?', { name: place?.name })}
  description={t('Nothing uses this place, so nothing else changes.')}
  confirmLabel={t('Delete place')}
  busyLabel={t('Deleting…')}
  destructive
  onConfirm={remove} />

<style>
  .place-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .place-form .kit-group {
    margin-bottom: 0;
  }

  .place-note {
    margin: 0;
    font-size: 0.85rem;
    color: var(--secondary-text, #888);
  }

  .place-error {
    font-size: 0.85rem;
    color: var(--danger, #dc3545);
  }

  .place-save {
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

  .place-save:disabled {
    opacity: 0.6;
  }

  .place-delete {
    padding: 8px;
    font: inherit;
    color: var(--danger, #dc3545);
    background: none;
    border: none;
    cursor: pointer;
  }
</style>

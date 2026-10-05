<script>
  // The Places admin page (spec 055): every town, metro and festival prefix, with
  // the sessions that use it. Site admins edit names and geography, set parents
  // (Conroe inside Houston), add metros that have no sessions of their own, rename
  // slugs (paths move, old links redirect) and delete places nothing uses.
  import { untrack } from 'svelte'
  import { SearchField } from '../lib/index.js'
  import PlaceSheet from './PlaceSheet.svelte'
  import { matchesPlace } from './logic.js'

  let { pageData } = $props()

  let places = $state(untrack(() => pageData.places || []))
  let query = $state('')
  let editing = $state(null)
  let sheetOpen = $state(false)

  const shown = $derived(places.filter((p) => matchesPlace(p, query)))

  function edit(place) {
    editing = place
    sheetOpen = true
  }

  function saved(data) {
    if (data?.places) places = data.places
  }
</script>

<div class="places-admin">
  <div class="places-toolbar">
    <SearchField bind:value={query} placeholder="Search places" wrapperClass="places-search-wrap" debounce={0} />
    <button type="button" class="places-add" id="places-add" onclick={() => edit(null)}>Add a place</button>
  </div>

  <p class="places-count" id="places-count">{shown.length} {shown.length === 1 ? 'place' : 'places'}</p>

  <table class="places-table" id="places-table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Address</th>
        <th>Inside</th>
        <th>Area</th>
        <th class="num">Sessions</th>
      </tr>
    </thead>
    <tbody>
      {#each shown as p (p.place_id)}
        <tr class="place-row" data-slug={p.slug} onclick={() => edit(p)}>
          <td>
            {p.name}
            {#if p.kind === 'festival'}<span class="place-kind">Festival</span>{/if}
          </td>
          <td><a href="/sessions/{p.slug}" onclick={(e) => e.stopPropagation()}>/{p.slug}</a></td>
          <td>{p.parent?.name || ''}</td>
          <td>{[p.area, p.country].filter(Boolean).join(', ')}</td>
          <td class="num">{p.kind === 'festival' ? p.paths : p.town_sessions}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<PlaceSheet bind:open={sheetOpen} place={editing} {places} onSaved={saved} />

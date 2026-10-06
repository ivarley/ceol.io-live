<script>
  // The year beside a festival's name on a year's page (spec 056): a <select> of
  // the festival's years that navigates on change, or just the year when there is
  // only one.
  let {
    festival, // { place, years: [{ year, path }] } — years oldest first
    currentPath,
    hrefFor = (path) => `/sessions/${path}`,
    navigate = (url) => window.location.assign(url),
  } = $props()

  const years = $derived(festival?.years || [])
  const current = $derived(years.find((y) => y.path === currentPath))
</script>

{#if years.length >= 2}
  <select
    class="festival-year-select"
    id="festival-year-select"
    aria-label="{festival.place.name}: year"
    value={currentPath}
    onchange={(e) => navigate(hrefFor(e.currentTarget.value))}>
    {#each [...years].reverse() as y (y.path)}
      <option value={y.path}>{y.year}</option>
    {/each}
  </select>
{:else if current}
  <span class="festival-year-text">{current.year}</span>
{/if}

<style>
  .festival-year-select {
    font: inherit;
    color: inherit;
    background: transparent;
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r, 8px);
    padding: 0 4px;
    cursor: pointer;
  }

  .festival-year-select option {
    background: var(--bg-color, #1a1a1a);
    color: var(--text-color, #e0e0e0);
  }
</style>

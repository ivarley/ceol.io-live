<script>
  // The festival picker (spec 056): the festival's name, then one line per year —
  // upcoming first, then past years newest first (the server's order) — with the
  // dates and how many of its sessions have logged tunes. Admins of the latest
  // year get "Add a year", which copies from that year.
  import CopyYearSheet from '../festival/CopyYearSheet.svelte'
  import { formatRange } from './logic.js'

  let { pageData } = $props()

  const place = pageData.place
  const years = pageData.years || []
  const canAdd = !!pageData.permissions?.can_add_year
  // CopyYearSheet wants the years and the source; the source is the latest year.
  const festival = { place, years }
  let copyOpen = $state(false)

  const today = new Date().toISOString().slice(0, 10)
  const isUpcoming = (y) => y.initiation_date && y.initiation_date > today
</script>

<div class="festival-page">
  <h1 class="festival-heading">{place.name}</h1>

  {#if years.length}
    <ul class="festival-years" id="festival-years">
      {#each years as y (y.path)}
        <li class="festival-year">
          <a href="/sessions/{y.path}" class="festival-year-link">
            <span class="festival-year-number">{y.year}</span>
            <span class="festival-year-dates">{formatRange(y.initiation_date, y.termination_date)}</span>
            <span class="festival-year-count">
              {#if isUpcoming(y)}Coming up{:else}{y.logged_instances} {y.logged_instances === 1 ? 'session' : 'sessions'} logged{/if}
            </span>
          </a>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="festival-empty">No years yet.</p>
  {/if}

  {#if canAdd && pageData.latest}
    <button type="button" class="festival-add-year" id="festival-add-year" onclick={() => (copyOpen = true)}>
      Add a year
    </button>
    <CopyYearSheet bind:open={copyOpen} {festival} source={pageData.latest} />
  {/if}
</div>

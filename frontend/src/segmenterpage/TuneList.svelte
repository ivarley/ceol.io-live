<script>
  // The night's log, grouped into sets, with each tune's placement (spec 050).
  // The highlighted row is the CURSOR: the tune the mark key will place. Set
  // ends are called out because those are the only tunes that need an explicit
  // end typed -- every other end is implied by the next tune's start.
  import { formatTime, formatDuration, groupIntoSets, setColor } from './logic.js'

  let {
    tunes = [],
    segments = new Map(),
    cursorIndex = 0,
    onpick = () => {},
    onseek = () => {},
    onclear = () => {},
  } = $props()

  const sets = $derived(groupIntoSets(tunes))
  const indexById = $derived(new Map(tunes.map((t, i) => [t.session_instance_tune_id, i])))
  const cursorId = $derived(tunes[cursorIndex]?.session_instance_tune_id ?? null)

  let listEl = $state(null)

  // Keep the cursor row on screen as it advances. `nearest` rather than
  // `center` so ordinary keyboard stepping doesn't jerk the whole list.
  $effect(() => {
    if (cursorId == null || !listEl) return
    const row = listEl.querySelector(`[data-tune-id="${cursorId}"]`)
    if (row) row.scrollIntoView({ block: 'nearest' })
  })
</script>

<div class="tl" bind:this={listEl}>
  {#each sets as set (set.setNumber)}
    <div class="tl-set">
      <div class="tl-set-head">
        <span class="tl-swatch" style="background:{setColor(set.setNumber)}"></span>
        Set {set.setNumber}
      </div>
      {#each set.tunes as tune (tune.session_instance_tune_id)}
        {@const seg = segments.get(tune.session_instance_tune_id)}
        {@const idx = indexById.get(tune.session_instance_tune_id)}
        <div
          class="tl-row"
          class:is-cursor={tune.session_instance_tune_id === cursorId}
          class:is-placed={!!seg}
          data-tune-id={tune.session_instance_tune_id}
        >
          <button class="tl-main" type="button" onclick={() => onpick(idx)}>
            <span class="tl-name">{tune.name}</span>
            {#if tune.tune_type}<span class="tl-type">{tune.tune_type}</span>{/if}
          </button>

          <!-- The set-end badge is a jump once the tune is placed: the end is
               the one time in a set you cannot reach from the list otherwise
               (the time column jumps to starts), and it is exactly where you
               go to check or re-place it. Unplaced, there is nothing to jump
               to, so it stays the label it always was. A sibling of .tl-main
               rather than inside it, because a button cannot hold a button. -->
          {#if tune.is_set_end}
            {#if seg}
              <button
                class="tl-endmark is-jump"
                type="button"
                title="Ends at {formatTime(seg.endMs, { millis: true })}{seg.explicitEnd ? '' : ' (implied by the next tune)'} — jump there"
                onclick={() => onseek(seg.endMs)}
              >end</button>
            {:else}
              <span class="tl-endmark" title="Last tune of the set — needs an explicit end">end</span>
            {/if}
          {/if}

          {#if seg}
            <button
              class="tl-time"
              type="button"
              title="Jump to {formatTime(seg.startMs, { millis: true })}"
              onclick={() => onseek(seg.startMs)}
            >
              {formatTime(seg.startMs)}
              <span class="tl-dur" class:is-implicit={!seg.explicitEnd}>
                {formatDuration(seg.endMs - seg.startMs)}{seg.explicitEnd ? '' : '~'}
              </span>
            </button>
            <button class="tl-clear" type="button" title="Unplace this tune" onclick={() => onclear(idx)}>×</button>
          {:else}
            <span class="tl-unplaced">—</span>
          {/if}
        </div>
      {/each}
    </div>
  {/each}

  {#if !tunes.length}
    <p class="tl-empty">This session instance has no logged tunes, so there is nothing to place.</p>
  {/if}
</div>

<style>
  .tl {
    overflow-y: auto;
    padding-right: 4px;
  }
  .tl-set {
    margin-bottom: 10px;
  }
  .tl-set-head {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--disabled-text, #888);
    padding: 4px 2px;
    position: sticky;
    top: 0;
    background: var(--bg-color, #1a1a1a);
    z-index: 1;
  }
  .tl-swatch {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    flex: none;
  }
  .tl-row {
    display: flex;
    align-items: center;
    gap: 4px;
    border-radius: 5px;
    border: 1px solid transparent;
    padding: 1px 2px;
  }
  .tl-row.is-placed .tl-name {
    color: var(--text-color, #e0e0e0);
  }
  .tl-row:not(.is-placed) .tl-name {
    color: var(--gray, #adb4c0);
  }
  .tl-row.is-cursor {
    border-color: var(--warning, #f5c842);
    background: rgba(245, 200, 66, 0.1);
  }
  .tl-main {
    /* Was flex:1 — the end badge now sits outside it and carries the auto
       margin instead, so the badge still reads as attached to the name while
       the time column stays hard right. */
    flex: 0 1 auto;
    display: flex;
    align-items: baseline;
    gap: 7px;
    min-width: 0;
    background: none;
    border: 0;
    color: inherit;
    text-align: left;
    padding: 5px 4px;
    cursor: pointer;
    font: inherit;
  }
  .tl-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tl-type {
    font-size: 0.68rem;
    color: var(--disabled-text, #888);
    flex: none;
  }
  .tl-endmark {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--warning, #f5c842);
    background: none;
    border: 1px solid currentColor;
    border-radius: 3px;
    padding: 0 3px;
    flex: none;
    font-family: inherit;
  }
  .tl-endmark.is-jump {
    cursor: pointer;
  }
  .tl-endmark.is-jump:hover {
    background: rgba(245, 200, 66, 0.18);
  }
  .tl-time {
    flex: none;
    /* Pushes the time column hard right whatever sits to its left — with or
       without an end badge, placed or not. */
    margin-left: auto;
    font-family: var(--font-family-monospace, monospace);
    font-size: 0.75rem;
    background: none;
    border: 0;
    color: var(--primary, #4da6ff);
    cursor: pointer;
    padding: 2px 4px;
    text-align: right;
  }
  .tl-dur {
    display: block;
    font-size: 0.65rem;
    color: var(--disabled-text, #888);
  }
  .tl-dur.is-implicit {
    font-style: italic;
  }
  .tl-clear {
    flex: none;
    background: none;
    border: 0;
    color: var(--disabled-text, #888);
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 2px 5px;
  }
  .tl-clear:hover {
    color: var(--danger, #e85a5a);
  }
  .tl-unplaced {
    flex: none;
    margin-left: auto;
    color: #555;
    padding: 2px 10px;
    font-size: 0.8rem;
  }
  .tl-empty {
    color: var(--disabled-text, #888);
    padding: 12px 4px;
  }
</style>

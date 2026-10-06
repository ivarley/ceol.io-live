<script>
  // i18n-converted
  // The night's log, grouped into sets, with each tune's placement (spec 050).
  // The highlighted row is the CURSOR: the tune the mark key will place. Set
  // ends are called out because those are the only tunes that need an explicit
  // end typed -- every other end is implied by the next tune's start.
  import { formatTime, formatDuration, groupIntoSets, setColor } from './logic.js'
  import { t, tuneTypeName } from '../lib/index.js'

  let {
    tunes = [],
    segments = new Map(),
    cursorIndex = 0,
    onpick = () => {},
    onseek = () => {},
    onclear = () => {},
    onname = () => {}, // a tune's name needs (re)matching: say which tune it was
    onunlog = () => {}, // take a tune out of the log altogether (spec 050)
    oninsert = () => {}, // (index, 'before' | 'after'): add a tune next to this one
    onnewset = () => {}, // (index | null): open a new set after this tune's set
    revealId = null, // a tune to scroll into view (a row just logged from the audio)
  } = $props()

  // The row whose menu is open: tapping a linked tune's name moves the cursor
  // there AND shows the log's own edits under it (edit / add before / add after
  // / remove), the way a tap on a row does in the live logger. Tapping the
  // name again, or any action, closes it. An unlinked row skips the menu:
  // naming it is the one thing it needs, and it already had the × for removal.
  let menuId = $state(null)

  function tapName(idx, id) {
    onpick(idx)
    menuId = menuId === id ? null : id
  }

  function act(fn) {
    menuId = null
    fn()
  }

  const sets = $derived(groupIntoSets(tunes))
  const indexById = $derived(new Map(tunes.map((tune, i) => [tune.session_instance_tune_id, i])))
  const cursorId = $derived(tunes[cursorIndex]?.session_instance_tune_id ?? null)

  let listEl = $state(null)

  // Keep the cursor row on screen as it advances. `nearest` rather than
  // `center` so ordinary keyboard stepping doesn't jerk the whole list.
  $effect(() => {
    if (cursorId == null || !listEl) return
    const row = listEl.querySelector(`[data-tune-id="${cursorId}"]`)
    if (row) row.scrollIntoView({ block: 'nearest' })
  })

  // A tune the mark key just logged has no cursor to follow it (logging mode
  // has none), and it lands at the end of a long list -- out of sight, one
  // scroll away from the tap that names it. Bring it to the bottom edge, so it
  // is the last thing in view and the next thing under the thumb.
  $effect(() => {
    if (revealId == null || !listEl) return
    const row = listEl.querySelector(`[data-tune-id="${revealId}"]`)
    if (row) row.scrollIntoView({ block: 'end' })
  })
</script>

<div class="tl" bind:this={listEl}>
  {#each sets as set (set.setNumber)}
    <div class="tl-set">
      <div class="tl-set-head">
        <span class="tl-swatch" style="background:{setColor(set.setNumber)}"></span>
        {t('Set {n}', { n: set.setNumber })}
      </div>
      {#each set.tunes as tune (tune.session_instance_tune_id)}
        {@const seg = segments.get(tune.session_instance_tune_id)}
        {@const idx = indexById.get(tune.session_instance_tune_id)}
        <div
          class="tl-row"
          class:is-cursor={tune.session_instance_tune_id === cursorId}
          class:is-placed={!!seg}
          class:is-pending={!!tune.segment?.pending}
          class:has-menu={tune.session_instance_tune_id === menuId}
          data-tune-id={tune.session_instance_tune_id}
        >
          {#if tune.tune_id == null}
            <!-- Not linked to a catalog tune -- the segmenter's own "Gan Ainm", or a
                 name typed on the night that matched nothing. The name is the way
                 to say which tune it was; the cursor still moves with the row's
                 time column and the arrow keys. -->
            <button
              class="tl-main tl-main-unlinked"
              type="button"
              title={t('Not linked to a tune yet — tap to search for it')}
              onclick={() => onname(idx)}
            >
              <span class="tl-name is-unlinked">{tune.name || 'Gan Ainm'}</span>
              <span class="tl-type">{t('name it')}</span>
            </button>
          {:else}
            <button
              class="tl-main"
              type="button"
              title={t('Put the cursor here — and edit, add beside, or remove this tune')}
              aria-expanded={tune.session_instance_tune_id === menuId}
              onclick={() => tapName(idx, tune.session_instance_tune_id)}
            >
              <span class="tl-name">{tune.name}</span>
              {#if tune.tune_type}<span class="tl-type">{tuneTypeName(tune.tune_type)}</span>{/if}
            </button>
          {/if}

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
                title={seg.explicitEnd
                  ? t('Ends at {time} — jump there', { time: formatTime(seg.endMs, { millis: true }) })
                  : t('Ends at {time} (implied by the next tune) — jump there', { time: formatTime(seg.endMs, { millis: true }) })}
                onclick={() => onseek(seg.endMs)}
              >{t('end')}</button>
            {:else}
              <span class="tl-endmark" title={t('Last tune of the set — needs an explicit end')}>{t('end')}</span>
            {/if}
          {/if}

          {#if seg}
            <button
              class="tl-time"
              type="button"
              title={tune.segment?.pending
                ? t('Jump to {time} — saved on this device, waiting to sync', { time: formatTime(seg.startMs, { millis: true }) })
                : t('Jump to {time}', { time: formatTime(seg.startMs, { millis: true }) })}
              onclick={() => onseek(seg.startMs)}
            >
              {formatTime(seg.startMs)}
              <span class="tl-dur" class:is-implicit={!seg.explicitEnd}>
                {formatDuration(seg.endMs - seg.startMs)}{seg.explicitEnd ? '' : '~'}
              </span>
            </button>
            {#if tune.source === 'segmenter'}
              <!-- The tool logged this tune itself; unplacing it would leave a
                   nameless row with no time, which is nothing. Taking it back
                   out of the log is what × means here. -->
              <button class="tl-clear" type="button" title={t('Remove this tune from the log')} onclick={() => onunlog(idx)}>×</button>
            {:else}
              <button class="tl-clear" type="button" title={t('Unplace this tune')} onclick={() => onclear(idx)}>×</button>
            {/if}
          {:else}
            <span class="tl-unplaced">—</span>
          {/if}
        </div>
        {#if tune.session_instance_tune_id === menuId}
          <!-- The log's own edits for this row, the live logger's row actions in
               miniature. Edit is the same re-match the name-it tap runs; before
               and after add a tune beside this one, unplaced, for the mark key
               to place; remove takes it out of the log (not just its time). -->
          <div class="tl-actions" role="group" aria-label={t('Edit this tune')}>
            <button type="button" onclick={() => act(() => onname(idx))}>✎ {t('Edit')}</button>
            <button type="button" onclick={() => act(() => oninsert(idx, 'before'))}>＋ {t('Before')}</button>
            <button type="button" onclick={() => act(() => oninsert(idx, 'after'))}>＋ {t('After')}</button>
            <button type="button" class="danger" onclick={() => act(() => onunlog(idx))}>🗑 {t('Remove')}</button>
          </div>
        {/if}
      {/each}
    </div>
    <!-- The gap after a set: a new set starts here. Anchored on the set's last
         tune, so the server puts the tune after it and a break on each side. -->
    <button
      class="tl-newset"
      type="button"
      title={t('Start a new set here')}
      onclick={() => act(() => onnewset(indexById.get(set.tunes[set.tunes.length - 1].session_instance_tune_id)))}
    >＋ {t('new set')}</button>
  {/each}

  {#if !tunes.length}
    <p class="tl-empty">{t('This session instance has no logged tunes, so there is nothing to place.')}</p>
    <button class="tl-newset" type="button" title={t('Log the first tune')} onclick={() => onnewset(null)}>＋ {t('add a tune')}</button>
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
  .tl-name.is-unlinked {
    font-style: italic;
    color: var(--warning, #f5c842);
  }
  .tl-main-unlinked .tl-type {
    color: var(--warning, #f5c842);
    opacity: 0.8;
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
    color: var(--primary, #65b464);
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
  /* A mark the server has not seen yet (offline queue): the connection dot's orange. */
  .tl-row.is-pending .tl-time {
    color: #e0a23e;
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
  .tl-row.has-menu {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 5px 5px 0 0;
  }
  .tl-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    padding: 3px 6px 8px;
    margin-bottom: 2px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 0 0 5px 5px;
  }
  .tl-actions button {
    font: inherit;
    font-size: 0.78rem;
    line-height: 1;
    padding: 6px 9px;
    background: var(--bg-color, #1a1a1a);
    border: 1px solid var(--border-color, #3a3a3a);
    border-radius: 6px;
    color: var(--text-color, #e0e0e0);
    cursor: pointer;
    white-space: nowrap;
  }
  .tl-actions button:hover {
    border-color: var(--primary, #65b464);
  }
  .tl-actions button.danger {
    color: var(--danger, #e85a5a);
  }
  .tl-actions button.danger:hover {
    border-color: var(--danger, #e85a5a);
  }
  /* The seam between sets: quiet until wanted, a line with a label on it. */
  .tl-newset {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    margin: -4px 0 8px;
    padding: 2px 4px;
    background: none;
    border: 0;
    color: var(--disabled-text, #888);
    font: inherit;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    opacity: 0.55;
  }
  .tl-newset::before,
  .tl-newset::after {
    content: '';
    flex: 1;
    height: 1px;
    background: currentColor;
    opacity: 0.4;
  }
  .tl-newset:hover,
  .tl-newset:focus-visible {
    opacity: 1;
    color: var(--primary, #65b464);
  }
</style>

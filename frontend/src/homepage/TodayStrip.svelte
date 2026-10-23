<script>
  // i18n-converted
  // The Today card (spec 052 §B2). Present only when a session is on today.
  //
  // At a festival there can be several, and the thing you need to see is THAT
  // THERE ARE SEVERAL. So more than one is a horizontal scroll-snap strip with the
  // next card peeking past the right edge and page dots beneath — not a stack,
  // which hides the count, and not a vertical list, which buries This Week.
  //
  // The whole card opens the log, and it carries a View button that does the same.
  // Both, because the card is the bigger target on a phone and the button is the
  // one people look for. The button stops propagation so a tap is one navigation,
  // not two.
  //
  // Several nights of ONE session on the day (a festival's rooms) are one card for the
  // session — "12 sessions today, 4 on now", naming the rooms on now — that opens the
  // day's list (logic.js nightItems). Twelve cards were a strip nobody could page
  // through to find their room.
  import {
    statusLabel,
    todaySubtitle,
    tallyLabel,
    sessionStatus,
    sessionInstanceHref,
    homeTitle,
    nightItems,
    groupStatus,
    groupStatusLabel,
    groupSubtitle,
    groupTally,
  } from './logic.js'
  import { t } from '../lib/index.js'

  let { sessions = [] } = $props()

  let stripEl = $state(null)
  let current = $state(0)

  const items = $derived(nightItems(sessions))
  const multi = $derived(items.length > 1)

  function onScroll() {
    if (!stripEl || !stripEl.firstElementChild) return
    const step = stripEl.firstElementChild.offsetWidth + 10
    current = step > 0 ? Math.round(stripEl.scrollLeft / step) : 0
  }

  function open(href, event) {
    if (!href) return
    event?.stopPropagation()
    window.location.href = href
  }
</script>

{#snippet card(status, label, chip, name, sub, tally, muted, href)}
  <!-- A div, not a button: it contains the View button, and interactive
       content inside a button is invalid HTML (the same rule that gave Row
       its `as` prop). Keyboard users get the View button, which is real. -->
  <div
    class="today-card"
    data-status={status}
    role="group"
    aria-label={label}
    onclick={(e) => open(href, e)}>
    <div class="today-top">
      <span class="today-eyebrow">{t('Today')}</span>
      <span class="today-chip" data-status={status}>{chip}</span>
    </div>
    <div class="today-name">{name}</div>
    <div class="today-sub">{sub}</div>
    <div class="today-tally" class:muted>{tally}</div>
    <div class="today-actions">
      <a class="today-view" {href} onclick={(e) => e.stopPropagation()}>{t('View')}</a>
    </div>
  </div>
{/snippet}

{#if items.length}
  <div class="today-wrap" id="home-today">
    <div
      class="today-strip"
      class:multi
      bind:this={stripEl}
      onscroll={multi ? onScroll : undefined}>
      {#each items as item (item.key)}
        {#if item.kind === 'group'}
          {@render card(
            groupStatus(item),
            item.name,
            groupStatusLabel(item),
            item.name,
            groupSubtitle(item),
            groupTally(item),
            !item.liveRooms.length && !item.tunesLogged,
            item.href
          )}
        {:else}
          {@const session = item.night}
          {@render card(
            sessionStatus(session),
            homeTitle(session),
            statusLabel(session),
            homeTitle(session),
            todaySubtitle(session),
            tallyLabel(session),
            !session.tunes_logged,
            sessionInstanceHref(session)
          )}
        {/if}
      {/each}
    </div>
    {#if multi}
      <div class="today-dots" aria-hidden="true">
        {#each items as item, i (item.key)}
          <span class:on={i === current}></span>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .today-wrap {
    margin-bottom: var(--sp-4, 16px);
  }

  /* The strip is the multi-session case; with one card it is an ordinary block,
     so a single session does not get scroll affordances it cannot use. */
  .today-strip {
    display: flex;
    gap: 10px;
  }
  .today-strip.multi {
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    /* Room for the card's shadow, which a clipped overflow would shave off. */
    padding-bottom: 4px;
  }
  .today-strip.multi::-webkit-scrollbar {
    display: none;
  }
  .today-strip > :global(*) {
    flex: 1 0 100%;
    scroll-snap-align: start;
  }
  /* 88% leaves the next card peeking, which is the whole point of the strip: it
     says "there is another one" without a label saying so. */
  .today-strip.multi > :global(*) {
    flex: 0 0 88%;
  }

  /* On a wide screen a percentage stops being the right unit: 88% of 1240px is a
     card a thousand pixels wide holding three short lines, and the peek lands off
     the edge of the window. Cap it, and the strip reads the same at every width. */
  @media (min-width: 700px) {
    .today-strip > :global(*) {
      max-width: 520px;
    }
    .today-strip.multi > :global(*) {
      flex: 0 0 520px;
    }
  }

  .today-card {
    cursor: pointer;
    text-align: left;
    background: var(--dropdown-bg);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--primary);
    border-radius: 10px;
    padding: 1rem 1.15rem 1.1rem;
    color: var(--text-color);
    min-width: 0;
  }
  .today-card[data-status='finished'] {
    border-left-color: var(--border-color);
  }
  .today-card:hover {
    border-color: var(--primary);
  }

  .today-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 0.35rem;
  }
  .today-eyebrow {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.6;
  }
  .today-chip {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid var(--border-color);
    white-space: nowrap;
  }
  .today-chip[data-status='live'] {
    color: var(--primary);
    border-color: var(--primary);
  }
  .today-chip[data-status='finished'] {
    opacity: 0.65;
  }

  .today-name {
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    font-size: 1.2rem;
    line-height: 1.25;
    /* Two lines, then ellipsis: a long session name must not push the tally and
       the button off a card whose neighbours are all the same height. */
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .today-sub {
    font-size: 0.88rem;
    opacity: 0.75;
    margin-top: 0.15rem;
  }
  .today-tally {
    font-size: 0.88rem;
    margin-top: 0.5rem;
    color: var(--primary);
  }
  .today-tally.muted {
    color: inherit;
    opacity: 0.55;
  }

  .today-actions {
    margin-top: 0.85rem;
  }
  .today-view {
    display: inline-block;
    background: var(--primary-fill);
    color: #fff;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 500;
    text-decoration: none;
  }
  .today-view:hover {
    text-decoration: none;
    color: #fff;
    opacity: 0.92;
  }

  .today-dots {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-top: 8px;
  }
  .today-dots span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--border-color);
  }
  .today-dots span.on {
    background: var(--primary-fill);
  }
</style>

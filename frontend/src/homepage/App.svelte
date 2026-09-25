<script>
  // Home (spec 052 §B8 Stage 4). The page renders serializers.build_home_payload —
  // byte for byte the GET /api/home body — so the web Home and a native Home screen
  // are looking at one document.
  //
  // Order is the prototype's, and it is not the old page's: Today first when there
  // IS a today, then This week, Learning, and the work you left unfinished. The old
  // page led with the tune counts, which are the least time-sensitive thing on it.
  //
  // Legacy DOM hooks kept on purpose (spec 035's contract discipline): .home-greeting,
  // #stat-learning, #stat-want-to-learn, .session-item, .session-name, .empty-state.
  // e2e/mobile/home.mobile.spec.ts selects on them, and Stage 0 wrote those tests
  // precisely so this migration could be checked rather than eyeballed.
  import { Row, SectionHeader } from '../lib/index.js'
  import TodayStrip from './TodayStrip.svelte'
  import {
    todaysSessions,
    weekSubtitle,
    dowOf,
    domOf,
    continueItems,
    editedLabel,
    adjustedCounts,
  } from './logic.js'

  let { payload } = $props()

  const todayStr = $derived(payload?.today || null)
  const upcoming = $derived(payload?.upcoming_sessions || [])
  const today = $derived(todaysSessions(upcoming, todayStr))
  const unfinished = $derived(continueItems(payload))
  const suggested = $derived(payload?.suggested_tune || null)

  // The counts start at the server's numbers and are corrected once the offline
  // queue has been read (see applyOfflineAdjustment below). They are $state rather
  // than $derived for exactly that reason.
  let learning = $state(payload?.learning_count || 0)
  let wantToLearn = $state(payload?.want_to_learn_count || 0)

  const learnTotal = $derived(learning + wantToLearn)

  const MY_TUNES = '/my-tunes?sortType=heard&sortDir=desc&sortType2=popularity&sortDir2=desc'

  async function applyOfflineAdjustment() {
    // Offline agreement: the home counts come from the server, so an unsynced
    // change made on the My Tunes page would leave the two screens disagreeing
    // about the same tunes. Replay the queue against the cached list. Every step
    // is allowed to fail — this is a cosmetic reconciliation, and an offline page
    // that throws here would lose the counts it already has.
    try {
      if (!window.MyTunesOffline) return
      const ops = await window.MyTunesOffline.pending()
      if (!ops || !ops.length) return
      let tunes = []
      try {
        const res = await fetch('/api/my-tunes?per_page=2000&sort=alpha-asc')
        if (res.ok) tunes = (await res.json()).tunes || []
      } catch {
        tunes = []
      }
      const statusByTuneId = {}
      for (const t of tunes) statusByTuneId[t.tune_id] = t.learn_status
      const next = adjustedCounts({ learning, wantToLearn }, ops, statusByTuneId)
      learning = next.learning
      wantToLearn = next.wantToLearn
    } catch {
      /* leave the server's numbers in place */
    }
  }

  $effect(() => {
    applyOfflineAdjustment()
  })
</script>

<div class="home-greeting">
  Welcome back, <strong>{payload?.viewer?.first_name || 'there'}</strong>
</div>

<TodayStrip sessions={today} />

<section class="home-section" id="home-week">
  <SectionHeader title="This week" level={2} headerClass="home-sechead">
    {#snippet icon()}
      <svg viewBox="0 0 24 24" aria-hidden="true" class="home-icon">
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <line x1="3" y1="10" x2="21" y2="10" />
        <line x1="8" y1="3" x2="8" y2="7" />
        <line x1="16" y1="3" x2="16" y2="7" />
      </svg>
    {/snippet}
  </SectionHeader>

  {#if upcoming.length}
    <div class="home-list">
      {#each upcoming as session (session.session_instance_id)}
        <!-- Two destinations in one row: the night (this instance's log) and the
             session it belongs to. So the row cannot be an <a> — an anchor inside an
             anchor is invalid, and browsers disagree about which one a click means.
             `as="div"` is Row's escape hatch for exactly that, and both destinations
             stay REAL links: focusable, middle-clickable, with a URL in the status
             bar. A span with a click handler would be none of those. -->
        <Row
          as="div"
          styled={false}
          rowClass="session-item"
          subtitle={weekSubtitle(session, todayStr)}>
          {#snippet lead()}
            <!-- Covers the whole row (it is absolutely positioned against
                 .session-item), sitting UNDER the name so the name wins its own
                 clicks. Rendered here only because Row has no slot of its own for
                 it; it is not part of the date block. It carries a label because a
                 link with no text is a link screen readers cannot announce. -->
            <a
              class="week-open"
              href={`/sessions/${session.path}/${session.date}`}
              aria-label={`Log for ${session.name}, ${weekSubtitle(session, todayStr)}`}
            ></a>
            <div class="session-date">
              <div class="session-date-day">{dowOf(session.date)}</div>
              <div class="session-date-num">{domOf(session.date)}</div>
            </div>
          {/snippet}
          {#snippet titleContent()}
            <a class="session-name" href={`/sessions/${session.path}`}>{session.name}</a>
          {/snippet}
          {#snippet trailing()}
            {#if session.date === todayStr}
              <span class="home-badge" class:live={session.is_active}>
                {session.is_active ? 'Live' : 'Today'}
              </span>
            {:else if session.log_complete_date}
              <span class="badge-logged">Logged</span>
            {/if}
          {/snippet}
        </Row>
      {/each}
    </div>
  {:else}
    <div class="empty-state">No sessions scheduled this week.</div>
  {/if}
</section>

<section class="home-section" id="home-learning">
  <SectionHeader title="Learning" level={2} seeAllHref="/my-tunes" headerClass="home-sechead">
    {#snippet icon()}
      <svg viewBox="0 0 24 24" aria-hidden="true" class="home-icon">
        <path d="M9 18V5l11-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="17" cy="16" r="3" />
      </svg>
    {/snippet}
  </SectionHeader>

  <div class="tune-stats">
    <a href={`/my-tunes?status=learning&${MY_TUNES.split('?')[1]}`} class="tune-stat">
      <span class="tune-stat-number" id="stat-learning">{learning}</span>
      <span class="tune-stat-label">Learning</span>
    </a>
    <a href={`/my-tunes?status=want+to+learn&${MY_TUNES.split('?')[1]}`} class="tune-stat">
      <span class="tune-stat-number" id="stat-want-to-learn">{wantToLearn}</span>
      <span class="tune-stat-label">To Learn</span>
    </a>
  </div>

  {#if suggested}
    <div class="suggested-tune">
      <span class="label-text">{learnTotal === 0 ? 'A' : 'Another'} tune to learn:</span>
      <a href={`/my-tunes?add=1&q=${encodeURIComponent(suggested.name)}`}>{suggested.name}</a>
      {#if suggested.tune_type}<span class="tune-type">({suggested.tune_type})</span>{/if}
    </div>
  {/if}
</section>

{#if unfinished.length}
  <section class="home-section" id="home-continue">
    <SectionHeader title="Pick up where you left off" level={2} headerClass="home-sechead">
      {#snippet icon()}
        <svg viewBox="0 0 24 24" aria-hidden="true" class="home-icon">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
      {/snippet}
    </SectionHeader>

    <div class="home-list">
      {#each unfinished as item (item.key)}
        <Row
          styled={false}
          rowClass="session-item"
          href={item.href}
          subtitle={`${item.detail}${item.lastEdit ? ` · edited ${editedLabel(item.lastEdit, payload?.current_year)}` : ''}`}>
          {#snippet lead()}
            <div class="session-date">
              <div class="session-date-day">{dowOf(item.date)}</div>
              <div class="session-date-num">{domOf(item.date)}</div>
            </div>
          {/snippet}
          {#snippet titleContent()}
            <span class="session-name">{item.title}</span>
          {/snippet}
        </Row>
      {/each}
    </div>
  </section>
{/if}

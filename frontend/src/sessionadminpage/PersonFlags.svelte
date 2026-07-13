<script>
  /**
   * The seven states a person can be in at a session (spec 034), as one fixed icon row.
   *
   * ALWAYS all seven, in the same order, lit or dimmed. That's the point: a scannable column
   * where a missing state is visible as an absence rather than as nothing at all. Chips only
   * render when true, so "not confirmed" and "no data" looked identical — and `confirmed` is
   * the field that decides who can see the roster, so it must never be invisible.
   *
   * Icons are inline SVG because FontAwesome is NOT loaded on this page (the <i class="fas">
   * elsewhere in this template render as nothing).
   */
  let { person } = $props()

  const isVisitor = $derived(person.relationship === 'visitor')

  // [key, lit?, label] -- label doubles as the tooltip.
  const flags = $derived([
    ['user', !!person.username, person.username ? `User account: ${person.username}` : 'No user account'],
    ['confirmed', !!person.confirmed, person.confirmed
      ? 'Confirmed — can see this session’s people and attendance'
      : 'Not confirmed — cannot see this session’s people'],
    ['member', !isVisitor, isVisitor ? 'Not a member' : 'Member — this is one of their sessions'],
    ['visitor', isVisitor, isVisitor ? 'Visitor — came, but it isn’t their session' : 'Not a visitor'],
    ['archived', !!person.archived, person.archived ? 'Archived — hidden from default lists' : 'Not archived'],
    ['session-admin', !!person.is_admin, person.is_admin ? 'Session admin' : 'Not a session admin'],
    ['system-admin', !!person.is_system_admin, person.is_system_admin ? 'System admin' : 'Not a system admin'],
  ])
</script>

<span class="pf" role="img" aria-label="Status flags">
  {#each flags as [key, lit, label] (key)}
    <span class="pf-i" class:on={lit} class:off={!lit} title={label} data-flag={key} data-on={lit}>
      <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
        {#if key === 'user'}
          <!-- account -->
          <path fill="currentColor" d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-4.4 0-8 2.2-8 5v1h16v-1c0-2.8-3.6-5-8-5Z" />
        {:else if key === 'confirmed'}
          <!-- vouched-for: shield + tick -->
          <path fill="currentColor" d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Zm-1 13-3.5-3.5 1.4-1.4L11 12.2l4.1-4.1 1.4 1.4L11 15Z" />
        {:else if key === 'member'}
          <!-- one of THEIR sessions: home -->
          <path fill="currentColor" d="M12 3 2 12h3v9h6v-6h2v6h6v-9h3L12 3Z" />
        {:else if key === 'visitor'}
          <!-- came, but it isn't theirs: suitcase -->
          <path fill="currentColor" d="M9 4a2 2 0 0 0-2 2v1H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3V6a2 2 0 0 0-2-2H9Zm0 2h6v1H9V6Z" />
        {:else if key === 'archived'}
          <!-- moved away: archive box -->
          <path fill="currentColor" d="M3 3h18v4H3V3Zm1 6h16v12H4V9Zm5 3v2h6v-2H9Z" />
        {:else if key === 'session-admin'}
          <!-- runs this session: key -->
          <path fill="currentColor" d="M14 2a6 6 0 0 0-5.7 7.9L2 16.2V22h5.8l1.6-1.6V18h2.4l1.6-1.6v-2.5l.6-.6A6 6 0 1 0 14 2Zm2.5 3.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z" />
        {:else}
          <!-- runs the whole site: crown -->
          <path fill="currentColor" d="M3 7l3.5 3L12 4l5.5 6L21 7l-2 12H5L3 7Z" />
        {/if}
      </svg>
    </span>
  {/each}
</span>

<style>
  .pf {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    white-space: nowrap;
  }
  .pf-i {
    display: inline-flex;
    line-height: 0;
    color: var(--text-color);
  }
  /* Dimmed, not absent -- an unlit icon is the information. */
  .pf-i.off { opacity: 0.16; }
  .pf-i.on { opacity: 1; }

  /*
    One hue per flag, so a row is readable by colour before you read the shapes. Deliberately
    NOT theme variables: --primary and friends shift between light and dark, and these need to
    stay distinguishable from EACH OTHER, which matters more than matching the palette. These
    are mid-tone and sit legibly on both #fff and #1a1a1a.
  */
  .pf-i.on[data-flag='user'] { color: var(--primary); }              /* blue   — has an account */
  .pf-i.on[data-flag='confirmed'] { color: #2ea86b; }                /* green  — vouched for */
  .pf-i.on[data-flag='member'] { color: #8b5cf6; }                   /* violet — one of their sessions */
  .pf-i.on[data-flag='visitor'] { color: #e8a33d; }                  /* amber  — came, not theirs */
  .pf-i.on[data-flag='archived'] { color: #8a95a8; }                 /* grey   — gone */
  .pf-i.on[data-flag='session-admin'] { color: #14b8a6; }            /* teal   — runs this session */
  .pf-i.on[data-flag='system-admin'] { color: #e05252; }             /* red    — runs the site */
</style>

<script>
  // i18n-converted
  // Sessions tab (admin flavour only): every session this person is associated with,
  // with the role they hold at each. It is a READ-ONLY view. The controls the old tab
  // carried -- leaving, the admin toggle, adding to a session -- live on the session's
  // own admin People tab and its role sheet (spec 052 §B1), which each row links to.
  //
  // `relationship` and `is_admin` are orthogonal axes: you can be an admin of a session
  // you only visit. The chips filter on each independently, so an admin row still shows
  // under Member or Visitor. The badge is derived here from the two flags, not from the
  // server's English `role` string, so it comes out in the reader's language.
  import { Chip, Row, t } from '../lib/index.js'

  let { sessions = [] } = $props()

  let filter = $state(null) // null = unfiltered; click the active chip to clear

  const FILTERS = [
    { id: 'admin', label: t('Admin') },
    { id: 'member', label: t('Member') },
    { id: 'visitor', label: t('Visitor') },
  ]

  function pickFilter(id) {
    filter = filter === id ? null : id
  }

  const isVisible = (s) => {
    if (!filter) return true
    if (filter === 'admin') return !!s.is_admin
    return s.relationship === filter
  }

  const roleLabel = (s) => (s.is_admin ? t('Admin') : s.relationship === 'visitor' ? t('Visitor') : t('Member'))

  const subtitleOf = (s) => [s.place?.name, s.location_name].filter(Boolean).join(' · ')

  const visible = $derived(sessions.filter(isVisible))
</script>

<div class="person-sessions" id="person-sessions">
  {#if sessions.length}
    <div class="person-sessions-filters" role="group" aria-label={t('Filter sessions')}>
      {#each FILTERS as f (f.id)}
        <Chip
          label={f.label}
          active={filter === f.id}
          variant={filter === f.id ? 'primary' : 'default'}
          onclick={() => pickFilter(f.id)}
          data-session-filter={f.id} />
      {/each}
    </div>
    <div class="person-sessions-list">
      <!-- Two destinations in one row (the session and its admin page), so the row is a
           div with real links inside rather than an <a>. -->
      {#each visible as s (s.session_path)}
        <Row as="div" rowClass="person-session-row" subtitle={subtitleOf(s)} data-session-path={s.session_path}>
          {#snippet titleContent()}
            <a href="/sessions/{s.session_path}" class="person-session-name">{s.session_name}</a>
          {/snippet}
          {#snippet trailing()}
            {#if !s.confirmed}
              <span class="person-session-note">{t('Unconfirmed')}</span>
            {/if}
            {#if s.archived}
              <span class="person-session-note">{t('Archived')}</span>
            {/if}
            <Chip label={roleLabel(s)} variant={s.is_admin ? 'primary' : 'default'} chipClass="session-role-badge" />
            <a href="/admin/sessions/{s.session_path}/people" class="person-session-manage">{t('Manage')}</a>
          {/snippet}
        </Row>
      {/each}
    </div>
    {#if !visible.length}
      <div class="empty-state">{t('No sessions found.')}</div>
    {/if}
  {:else}
    <div class="empty-state">{t('No sessions associated with this person.')}</div>
  {/if}
</div>

<style>
  .person-sessions {
    margin-top: var(--sp-3, 12px);
  }
  .person-sessions-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: var(--sp-3, 12px);
  }
  .person-session-name {
    color: inherit;
    text-decoration: none;
    font-weight: 500;
  }
  .person-session-name:hover {
    color: var(--primary);
  }
  .person-session-note {
    font-size: 0.82rem;
    color: var(--text-muted, #6c757d);
  }
  .person-session-manage {
    font-size: 0.85rem;
    color: var(--primary);
    text-decoration: none;
  }
  .person-session-manage:hover {
    text-decoration: underline;
  }
  .empty-state {
    color: var(--text-muted, #6c757d);
    padding: var(--sp-3, 12px) 0;
  }
</style>

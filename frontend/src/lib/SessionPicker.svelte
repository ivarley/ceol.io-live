<script>
  // Pick one of MY sessions (spec 037) — the tune drawer's "At a different session ..."
  // row, which re-scopes the Session tab so you can see what another session you play at
  // does with the same tune.
  //
  // Same idiom as PersonPicker: Sheet + SearchField + List, with the whole list handed in
  // as a prop and filtered locally (there is no server search — a person has a handful of
  // sessions, not thousands). Imports the primitives directly rather than through the kit
  // barrel, to avoid an index.js -> SessionPicker -> index.js cycle.
  import Sheet from './Sheet.svelte'
  import SearchField from './SearchField.svelte'
  import List from './List.svelte'

  let {
    open = $bindable(false),
    // [{path, name, relationship}] — from GET /api/my-sessions.
    sessions = [],
    // The session already in scope; it's pointless to offer it, so it's filtered out.
    currentPath = null,
    title = 'At a different session',
    onSelect = () => {},
    onClose = () => {},
  } = $props()

  let query = $state('')
  let active = $state(-1)

  const q = $derived(query.trim().toLowerCase())

  // Visitor sessions are excluded: a session you dropped into once on holiday isn't one
  // whose repertoire you have anything to say about. (spec 034 — relationship is
  // 'member' | 'visitor'.)
  const mine = $derived(
    (sessions || []).filter((s) => s.relationship !== 'visitor' && s.path !== currentPath)
  )
  const items = $derived(!q ? mine : mine.filter((s) => (s.name || '').toLowerCase().includes(q)))

  function pick(session) {
    if (!session) return
    onSelect(session)
    close()
  }

  function close() {
    open = false
    query = ''
    active = -1
    onClose()
  }
</script>

<Sheet bind:open {title} desktop="dock" onCancel={close}>
  {#if mine.length > 6}
    <SearchField bind:value={query} placeholder="Find a session" />
  {/if}

  <List items={items} bind:active onSelect={pick}>
    {#snippet row(item)}
      <span class="sp-row">
        <span class="sp-name">{item.name}</span>
        <span class="sp-path">{item.path}</span>
      </span>
    {/snippet}
  </List>

  {#if !items.length}
    <div class="sp-empty">
      {#if !mine.length}
        You're not a member of any other session.
      {:else}
        No session matches “{query}”.
      {/if}
    </div>
  {/if}
</Sheet>

<style>
  .sp-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    min-width: 0;
  }
  .sp-name {
    font-weight: 500;
  }
  .sp-path {
    font-size: 12px;
    color: var(--secondary-text, #888);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sp-empty {
    padding: 16px 4px;
    font-size: 13px;
    color: var(--secondary-text, #888);
  }
</style>

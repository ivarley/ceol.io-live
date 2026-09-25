<script>
  // Who this page is about (spec 052 §B12).
  //
  // It replaces an h1 reading "Profile: Ian Varley" — 36px of a 664px screen
  // spent telling you your own name, on the one page in the app where you
  // already know it. This says the same thing in the shape iOS uses at the top
  // of Settings: initials, name, a quiet line of context, and the control that
  // acts on all of it.
  //
  // It carries the Edit control because that is what Edit edits. The old button
  // floated alone above the first card with nothing anchoring it to anything.
  let {
    name = '',
    subtitle = '',
    isAdmin = false,
    editMode = false,
    canEdit = true,
    onEdit = () => {},
    onSave = () => {},
    onCancel = () => {},
  } = $props()

  // Two letters from the name, which is all an avatar needs when there is no
  // photo to show. "Ian Varley" -> IV; a single name -> its first letter.
  const initials = $derived.by(() => {
    const parts = String(name).trim().split(/\s+/).filter(Boolean)
    if (!parts.length) return '?'
    if (parts.length === 1) return parts[0][0].toUpperCase()
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  })
</script>

<header class="pd-identity" id="identity-header">
  <span class="pd-avatar" aria-hidden="true">{initials}</span>
  <span class="pd-identity-text">
    <span class="pd-name" id="identity-name">
      {name}
      {#if isAdmin}<span class="pd-admin-badge admin-indicator">admin</span>{/if}
    </span>
    {#if subtitle}<span class="pd-subtitle">{subtitle}</span>{/if}
  </span>

  {#if canEdit}
    <span class="pd-identity-actions edit-controls">
      {#if editMode}
        <button type="button" id="cancel-btn" class="pd-action" onclick={onCancel}>Cancel</button>
        <button type="button" id="save-btn" class="pd-action pd-action-strong" onclick={onSave}>Save</button>
      {:else}
        <button type="button" id="edit-btn" class="pd-action" onclick={onEdit}>Edit</button>
      {/if}
    </span>
  {/if}
</header>

<style>
  .pd-identity {
    display: flex;
    align-items: center;
    gap: var(--sp-3, 12px);
    padding: var(--sp-4, 16px) var(--sp-3, 12px) var(--sp-5, 20px);
  }

  /* --primary-fill, not --primary: this is a surface with text on it (§B10). */
  .pd-avatar {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--primary-fill, #4a8049);
    color: #fff;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  .pd-identity-text {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .pd-name {
    font-size: 1.35rem;
    font-weight: 600;
    line-height: 1.2;
    color: var(--text-color, #e0e0e0);
    /* One line: without this the admin badge drops below the name as soon as the
       actions widen, which they do the moment you press Edit. */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pd-admin-badge {
    margin-left: var(--sp-2, 8px);
    padding: 2px 7px;
    border-radius: 999px;
    background: var(--primary-fill, #4a8049);
    color: #fff;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    vertical-align: middle;
  }

  .pd-subtitle {
    font-size: 0.85rem;
    color: var(--secondary-text, #888);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Text buttons at the trailing edge, the way a sheet header carries Cancel and
     Done — not a filled green rectangle floating above the content. */
  .pd-identity-actions {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: var(--sp-3, 12px);
  }

  .pd-action {
    padding: 0;
    font: inherit;
    font-size: 0.95rem;
    color: var(--primary, #65b464);
    background: none;
    border: none;
    cursor: pointer;
    white-space: nowrap;
  }

  .pd-action-strong {
    font-weight: 600;
  }

  .pd-action:hover {
    opacity: 0.85;
  }
</style>

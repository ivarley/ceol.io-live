<script>
  /**
   * The session role badge, and the sheet that changes it (spec 034, Changes 1 & 2).
   *
   * Both this and the join prompt used to be Jinja in the shell, with App.svelte reaching
   * into the shell DOM to wire the click. They're Svelte now.
   *
   * The badge shows Admin / Member / Visitor. `is_admin` is a separate axis from
   * `relationship` -- an admin is still a member or a visitor underneath, and setting your
   * own relationship must never disturb your admin rights. So the badge shows "Admin" (it's
   * the more consequential fact) while the sheet edits the relationship beneath it.
   *
   * You can't grant yourself Admin, obviously. You CAN set your own member/visitor: it says
   * whose session this is, and that's a claim about your own life.
   */
  import { Sheet, Seg, Chip, Dialog, toast } from '../lib/index.js'

  let { sessionPath, permissions } = $props()

  let relationship = $state(permissions.relationship) // 'member' | 'visitor'
  let draft = $state(permissions.relationship)
  let open = $state(false)
  let saving = $state(false)

  // Leaving lived on /me, in a list of every session you belong to (spec 052 §B1).
  // That list duplicated the Sessions tab, so it is gone, and the one control it
  // carried that had no other home moved here — to the session you would be leaving,
  // which is where you are when you decide to.
  let leaveOpen = $state(false)
  let leaving = $state(false)

  async function leaveSession() {
    leaving = true
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/leave`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new Error(data.message || 'Could not leave')
      // A full reload, not a local tidy-up: leaving changes the People tab, the role
      // badge and whether the tunes count as yours — most of the page.
      window.location.reload()
    } catch (e) {
      leaving = false
      leaveOpen = false
      toast(e.message || 'Could not leave this session', 'error')
    }
  }

  const isAdmin = permissions.is_session_admin
  const label = $derived(isAdmin ? 'Admin' : relationship === 'visitor' ? 'Visitor' : 'Member')
  const variant = $derived(isAdmin ? 'primary' : relationship === 'visitor' ? 'warning' : 'success')

  const OPTIONS = [
    { id: 'member', label: 'I attend this session' },
    { id: 'visitor', label: "I've just visited" },
  ]

  function openSheet() {
    draft = relationship
    open = true
  }

  async function save() {
    if (draft === relationship) { open = false; return }
    saving = true
    try {
      const res = await fetch(
        `/api/sessions/${sessionPath}/people/${permissions.person_id}/relationship`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ relationship: draft }),
        }
      )
      const data = await res.json()
      if (!res.ok || !data.success) throw new Error(data.message || 'Could not save')
      relationship = draft
      open = false
      toast(
        draft === 'member'
          ? 'This is now one of your sessions.'
          : "Marked as a session you've visited.",
        'success'
      )
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      saving = false
    }
  }
</script>

{#if relationship}
  <Chip label={label} {variant} onclick={openSheet} title="Change your relationship to this session" />
{/if}

<Sheet bind:open title="Your relationship to this session" onCancel={() => (open = false)}>
  <p class="sr-lead">
    This decides whether the session's tunes count as <strong>yours</strong> — in your tune
    stats, and in "played at my sessions".
  </p>

  <Seg options={OPTIONS} value={draft} onSelect={(id) => (draft = id)} idAttr="data-relationship" />

  <p class="sr-note">
    {#if draft === 'member'}
      Its tunes and history count as one of your sessions.
    {:else}
      You came, but it isn't one of your sessions — its tunes won't count as yours. The
      specific nights you were there still do.
    {/if}
  </p>

  {#if isAdmin}
    <p class="sr-note">You're an admin here. That doesn't change either way.</p>
  {/if}

  <button type="button" class="sr-leave" id="leave-session-btn" onclick={() => (leaveOpen = true)}>
    Leave this session
  </button>

  {#snippet footer()}
    <button class="sr-save" onclick={save} disabled={saving}>Save</button>
  {/snippet}
</Sheet>

<!-- Confirmed, because what leaving costs is not obvious from the outside. The
     answer is nothing you logged, which is worth saying rather than assuming. -->
<Dialog
  bind:open={leaveOpen}
  title="Leave this session?"
  confirmLabel={leaving ? 'Leaving…' : 'Leave'}
  onConfirm={leaveSession}>
  <p>
    You'll stop seeing it on your home page and its tunes will no longer count as
    yours. Everything you logged there stays exactly where it is, and you can join
    again whenever you like.
  </p>
</Dialog>

<style>
  .sr-lead { margin: 0 0 1rem; }
  .sr-note { font-size: 0.85rem; opacity: 0.72; margin: 0.8rem 0 0; }
  .sr-save {
    width: 100%;
    padding: 0.5rem 0.9rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--primary-fill);
    color: #fff;
    font: inherit;
    cursor: pointer;
  }
  .sr-save:disabled { opacity: 0.5; cursor: default; }

  /* Quiet: this is the one destructive thing in the sheet, and it is not why
     anybody opened it. */
  .sr-leave {
    margin-top: 1.25rem;
    padding: 0;
    background: none;
    border: none;
    font: inherit;
    font-size: 0.9rem;
    color: var(--danger, #e85a5a);
    cursor: pointer;
  }

  .sr-leave:hover { text-decoration: underline; }
</style>

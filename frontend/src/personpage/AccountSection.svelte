<script>
  // The account actions, on your own profile only (spec 052 §B8 Stage 5).
  //
  // These four lived in the hamburger menu. The tab bar that replaces it has room
  // for four destinations and no room for a menu, so they move here first — the
  // plan is explicit that Me absorbs them BEFORE the hamburger goes, because a
  // destination that exists in neither place is a feature quietly deleted.
  //
  // Only on /me. An admin looking at somebody else's profile must not be offered
  // "Log Out" under their name.
  //
  // Share is NOT here any more. It gives a link and a QR for the page you are
  // looking at, so parking it on one particular page made it mean "share your
  // profile" half the time and something else the rest. It is a header control now
  // (spec 052 §B1), present on every screen.
  //
  // Delete account (spec 054) is last and on its own, the way iOS puts it: the one
  // thing here you cannot take back. You confirm by typing your email, which a stray
  // tap cannot do. System admins do not see it — the server refuses them, because
  // removing an admin is another admin's decision, not a button.
  import { Chevron, Dialog, Row, toast } from '../lib/index.js'

  let { isSystemAdmin = false, personName = '', userEmail = '' } = $props()

  let confirmOpen = $state(false)
  let typed = $state('')
  const matches = $derived(!!userEmail && typed.trim().toLowerCase() === userEmail.trim().toLowerCase())

  function openConfirm() {
    typed = ''
    confirmOpen = true
  }

  async function deleteAccount() {
    try {
      const res = await fetch('/api/me/delete-account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ confirm_email: typed }),
      })
      const json = await res.json().catch(() => ({}))
      if (!res.ok || !json.success) {
        toast(json.error || 'Your account could not be deleted.', 'error')
        return
      }
      // Signed out now; home shows the server's "Your account has been deleted."
      window.location.href = '/'
    } catch {
      toast("Couldn't reach the server, so nothing was deleted.", 'error')
    }
  }
</script>

<section class="account-section" id="account-section">
  <div class="account-list kit-group">
    {#if isSystemAdmin}
      <Row styled={false} rowClass="kit-field account-row" href="/admin" title="Admin" id="account-admin">
        {#snippet trailing()}<Chevron class="kit-chev" />{/snippet}
      </Row>
    {/if}

    <Row styled={false} rowClass="kit-field account-row" href="/help" title="Help" id="account-help">
      {#snippet trailing()}<Chevron class="kit-chev" />{/snippet}
    </Row>

    <Row
      styled={false}
      rowClass="kit-field account-row account-row-out"
      href="/logout"
      title="Log Out"
      id="account-logout" />
  </div>
  {#if userEmail && !isSystemAdmin}
    <div class="account-list account-danger kit-group">
      <Row
        styled={false}
        rowClass="kit-field account-row account-row-out"
        onclick={openConfirm}
        title="Delete Account"
        id="account-delete" />
    </div>
  {/if}
  {#if personName}
    <p class="account-who">Signed in as {personName}</p>
  {/if}
</section>

<Dialog
  bind:open={confirmOpen}
  title="Delete your account?"
  confirmLabel="Delete account"
  destructive={true}
  confirmDisabled={!matches}
  onConfirm={deleteAccount}>
  <div class="delete-body" id="account-delete-dialog">
    <p>
      This deletes your login, your tune list and instruments, and your contact details,
      straight away. It can't be undone.
    </p>
    <p>
      Your name stays on the sessions you were part of, as it would for anyone a session
      admin adds, and the tunes logged at those sessions stay in their logs.
    </p>
    <label for="account-delete-email">Type <strong>{userEmail}</strong> to confirm</label>
    <input
      id="account-delete-email"
      class="form-control"
      type="email"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      bind:value={typed} />
  </div>
</Dialog>

<style>
  .account-section {
    /* A little more than the 20px between groups: these are somewhere to go, not
       more of your details. */
    margin: var(--sp-3, 12px) 0 var(--sp-4, 16px);
    padding: 0 var(--sp-3, 12px);
  }

  /* These are grouped-table rows like everything else on the page now. They used
     to be bare rows under a hairline, which made the one list on the screen that
     was not in a card. */
  .account-list :global(.account-row) {
    color: var(--text-color);
    text-decoration: none;
  }

  .account-list :global(.account-row:hover) {
    color: var(--text-color);
    text-decoration: none;
  }

  /* Row renders the title into .kit-row-title, so that is what has to pick up the
     label column's weight rather than shrinking to a caption. */
  .account-list :global(.kit-row-body) {
    flex: 1 1 auto;
    min-width: 0;
  }

  /* Log Out is the one destructive-ish action in the list, and the last one. */
  .account-list :global(.account-row-out),
  .account-list :global(.account-row-out:hover) {
    color: var(--danger, #dc3545);
  }

  .account-list :global(.account-row-out:hover) {
    opacity: 0.85;
  }

  .account-danger {
    margin-top: var(--sp-4, 16px);
  }

  .delete-body p {
    margin: 0 0 var(--sp-2, 8px);
  }

  .delete-body label {
    display: block;
    margin: var(--sp-3, 12px) 0 var(--sp-1, 4px);
    font-size: 0.9rem;
    overflow-wrap: anywhere;
  }

  .account-who {
    margin: var(--sp-3, 12px) 0 0;
    padding-left: var(--sp-3, 12px);
    font-size: 0.8rem;
    color: var(--secondary-text, #888);
  }
</style>

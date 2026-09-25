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
  import { Row } from '../lib/index.js'

  let { isSystemAdmin = false, personName = '' } = $props()

</script>

<section class="account-section" id="account-section">
  <div class="account-list kit-group">
    {#if isSystemAdmin}
      <Row styled={false} rowClass="kit-field account-row" href="/admin" title="Admin" id="account-admin">
        {#snippet trailing()}<span class="kit-chev" aria-hidden="true">›</span>{/snippet}
      </Row>
    {/if}

    <Row styled={false} rowClass="kit-field account-row" href="/help" title="Help" id="account-help">
      {#snippet trailing()}<span class="kit-chev" aria-hidden="true">›</span>{/snippet}
    </Row>

    <Row
      styled={false}
      rowClass="kit-field account-row account-row-out"
      href="/logout"
      title="Log Out"
      id="account-logout" />
  </div>
  {#if personName}
    <p class="account-who">Signed in as {personName}</p>
  {/if}
</section>

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

  .account-who {
    margin: var(--sp-3, 12px) 0 0;
    padding-left: var(--sp-3, 12px);
    font-size: 0.8rem;
    color: var(--secondary-text, #888);
  }
</style>

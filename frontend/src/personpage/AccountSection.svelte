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
  <h2 class="account-heading">Account</h2>
  <div class="account-list">
    {#if isSystemAdmin}
      <Row styled={false} rowClass="account-row" href="/admin" title="Admin" id="account-admin">
        {#snippet trailing()}<span class="account-chev" aria-hidden="true">›</span>{/snippet}
      </Row>
    {/if}

    <Row styled={false} rowClass="account-row" href="/help" title="Help" id="account-help">
      {#snippet trailing()}<span class="account-chev" aria-hidden="true">›</span>{/snippet}
    </Row>

    <Row
      styled={false}
      rowClass="account-row account-row-out"
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
    margin: 2rem 0 1rem;
  }

  .account-heading {
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    font-size: 1.05rem;
    margin: 0 0 0.5rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .account-list :global(.account-row) {
    width: 100%;
    padding: 0.85rem 0.25rem;
    color: var(--text-color);
    text-decoration: none;
    text-align: left;
    background: none;
    border: none;
  }

  .account-list :global(.account-row + .account-row) {
    border-top: 1px solid var(--border-color);
  }

  .account-list :global(.account-row:hover) {
    color: var(--primary);
    text-decoration: none;
  }

  /* Log Out is the one destructive-ish action in the list, and the last one. */
  .account-list :global(.account-row-out) {
    color: var(--danger, #dc3545);
  }

  .account-list :global(.account-row-out:hover) {
    color: var(--danger, #dc3545);
    opacity: 0.85;
  }

  .account-chev {
    opacity: 0.4;
    font-size: 1.2rem;
    line-height: 1;
  }

  .account-who {
    margin: 0.75rem 0 0;
    font-size: 0.85rem;
    opacity: 0.55;
  }
</style>

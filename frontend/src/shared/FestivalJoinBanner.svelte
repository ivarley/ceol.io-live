<script>
  // i18n-converted
  /**
   * "Are you at {festival}?" (spec 056): a festival year's join prompt.
   *
   * A bright full-width strip under the band of the year's page and of each of its
   * nights, for whoever doesn't belong to the year yet. The QR code at a festival's door
   * lands on a night, not on the session's page, so the night asks too. One tap joins as a
   * member with no local-or-visiting question (nobody is local to a festival, and only
   * membership puts the festival's days on Home). Signed out, the strip goes to sign-in
   * and comes back here.
   */
  import { toast, ServerError, t } from '../lib/index.js'

  let { sessionPath, name, signedIn = false, onJoined = () => {} } = $props()

  let joining = $state(false)

  const loginHref = $derived(
    typeof location === 'undefined'
      ? '/login'
      : `/login?next=${encodeURIComponent(location.pathname + location.search)}`
  )

  async function join() {
    if (joining) return
    joining = true
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relationship: 'member' }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new ServerError(data.message || data.error)
      toast(t('Added. A session admin can confirm you to show you who else plays here.'), 'success')
      onJoined()
    } catch (e) {
      toast(
        e instanceof ServerError
          ? t("Couldn't add you to this session. Try again.")
          : t("Couldn't add you to this session. Check your connection and try again."),
        'error'
      )
      joining = false
    }
  }
</script>

{#if signedIn}
  <button class="fjb" type="button" onclick={join} disabled={joining}>
    <span class="fjb-text">
      <strong>{t('Are you at {name}?', { name })}</strong>
      <span>{joining ? t('Adding…') : t('Tap to add it to your sessions')}</span>
    </span>
    <span class="fjb-chevron" aria-hidden="true">›</span>
  </button>
{:else}
  <a class="fjb" href={loginHref}>
    <span class="fjb-text">
      <strong>{t('Are you at {name}?', { name })}</strong>
      <span>{t('Sign in to add it to your sessions')}</span>
    </span>
    <span class="fjb-chevron" aria-hidden="true">›</span>
  </a>
{/if}

<style>
  .fjb {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    box-sizing: border-box;
    margin: 6px 0 10px;
    padding: 12px 14px;
    border: 0;
    border-radius: 8px;
    background: var(--warning, #f5c842);
    color: #1a1a1a;
    font: inherit;
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }
  .fjb:hover,
  .fjb:visited {
    color: #1a1a1a;
    text-decoration: none;
  }
  .fjb:hover {
    filter: brightness(1.06);
  }
  .fjb:disabled {
    opacity: 0.7;
    cursor: default;
  }
  .fjb-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1 1 auto;
    min-width: 0;
  }
  .fjb-text strong {
    font-size: 17px;
    font-weight: 600;
  }
  .fjb-text span {
    font-size: 14px;
    opacity: 0.85;
  }
  .fjb-chevron {
    font-size: 22px;
    line-height: 1;
    opacity: 0.7;
  }
</style>

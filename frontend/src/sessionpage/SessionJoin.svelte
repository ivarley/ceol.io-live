<script>
  /**
   * "Do you attend this session?" (spec 034, Change 1).
   *
   * ONE question -- "Are you a local, or just visiting?" -- because there is only one axis
   * left. (The original spec had a second question, regular-vs-occasional; that distinction
   * was cut: it ranked people, it rotted, and it decided nothing. Sort order now comes from
   * actual attendance.)
   *
   * Joining lands you UNCONFIRMED, so it does not show you the session's people. That is the
   * point: people-visibility is granted by the session, never claimed by joining it. We say
   * so plainly rather than letting the missing tab be a mystery.
   */
  import { Sheet, toast } from '../lib/index.js'

  let { sessionPath } = $props()

  let open = $state(false)
  let joining = $state(false)

  async function join(relationship) {
    if (joining) return
    joining = true
    try {
      const res = await fetch(`/api/sessions/${sessionPath}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relationship }),
      })
      const data = await res.json()
      if (!res.ok || !data.success) throw new Error(data.message || 'Could not join')
      toast('Added. A session admin can confirm you to show you who else plays here.', 'success')
      // Membership is part of the server-rendered permissions block, so repaint from the
      // server. (We deliberately do NOT bounce to /people any more: a new joiner is
      // unconfirmed and can't see it, so that redirect would land on a 403.)
      setTimeout(() => window.location.reload(), 900)
    } catch (e) {
      toast(e.message, 'error')
      joining = false
      open = false
    }
  }
</script>

<div class="sj">
  <p>
    Do you attend this session?
    <button class="sj-link" onclick={() => (open = true)} disabled={joining}>
      {joining ? 'Adding…' : 'Yes, Add Me'}
    </button>
  </p>
</div>

<!--
  A Sheet, not a Dialog: a Dialog has exactly two outcomes (confirm / cancel), and cancel is
  also what Escape and a scrim-tap do. Wiring "Just visiting" to cancel would mean pressing
  Escape silently joined you as a visitor. This has three outcomes -- local, visiting, and
  walk away -- so the two choices are buttons and Cancel means cancel.
-->
<Sheet bind:open title="Are you a local, or just visiting?" onCancel={() => (open = false)}>
  <button class="sj-choice" onclick={() => join('member')} disabled={joining}>
    <strong>I'm local</strong>
    <span>This is one of my sessions. Its tunes count towards my stats and history.</span>
  </button>
  <button class="sj-choice" onclick={() => join('visitor')} disabled={joining}>
    <strong>Just visiting</strong>
    <span>Record that I came, without making the session mine.</span>
  </button>
</Sheet>

<style>
  .sj {
    background-color: var(--info-bg, #e7f3ff);
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 10px;
    border: 1px solid var(--info-border, #b3d9ff);
  }
  .sj p { margin: 0; color: var(--info-text, #004085); }
  .sj-link {
    background: none;
    border: 0;
    padding: 0;
    color: var(--primary, #0056b3);
    font: inherit;
    font-weight: 500;
    text-decoration: underline;
    cursor: pointer;
  }
  .sj-link:disabled { opacity: 0.6; cursor: default; }

  .sj-choice {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.8rem 0.9rem;
    margin-bottom: 0.6rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: var(--r, 8px);
    background: var(--bg-secondary, transparent);
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .sj-choice:hover { border-color: var(--primary, #007bff); }
  .sj-choice:disabled { opacity: 0.5; cursor: default; }
  .sj-choice strong { display: block; margin-bottom: 0.15rem; }
  .sj-choice span { font-size: 0.85rem; opacity: 0.75; }
</style>

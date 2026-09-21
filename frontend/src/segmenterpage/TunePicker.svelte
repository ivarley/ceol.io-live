<script>
  // "Which tune was this?" for a tune the segmenter logged from the audio (spec
  // 050 "Logging while segmenting"). The search itself is the live logger's own
  // TuneSearch -- catalog search, thesession.org, paste-a-URL, the preview with
  // its settings pager, "log as-is" -- unchanged, inside the same slide-in pane
  // shell the My Tunes and session-tunes add panes use. Nothing here decides what
  // a pick means: onPick gets TuneSearch's payload and the tune being named, and
  // the segmenter does the write. The pane floats over the tool, so the audio
  // keeps playing underneath; closing it without picking leaves the tune as it
  // was.
  import TuneSearch from '../TuneSearch.svelte'
  import { createPaneState } from '../mytunes/pane.svelte.js'

  let { config, onPick, onClosed = () => {} } = $props()

  const pane = createPaneState('sg-pick-open')
  let target = $state(null) // the tune being named
  let initialQuery = $state('')
  let history = $state([]) // search recall (MRU) for the page's lifetime
  let busy = $state(false)
  let errorMsg = $state('')

  export function open(tune) {
    target = tune
    // A tune logged on the night with a real name but no link seeds the search
    // with that name; the segmenter's own placeholder seeds nothing.
    initialQuery = tune?.tune_id == null && tune?.name && tune.name !== 'Gan Ainm' ? tune.name : ''
    errorMsg = ''
    busy = false
    pane.open()
  }

  export function close() {
    pane.close(() => {
      target = null
      onClosed()
    })
  }

  export function isOpen() {
    return pane.visible
  }

  function remember(q) {
    const v = (q || '').trim()
    if (!v) return
    history = [v, ...history.filter((x) => x !== v)].slice(0, 20)
  }

  // TuneSearch's terminal action. Returning false keeps its search intact while
  // the write is in flight, so a failure leaves the user where they were.
  function pick(payload, name) {
    if (busy || !target) return false
    busy = true
    errorMsg = ''
    Promise.resolve(onPick(target, payload, name)).then(
      (ok) => {
        busy = false
        if (ok !== false) close()
      },
      (err) => {
        busy = false
        errorMsg = err?.message || 'Could not save that tune.'
      },
    )
    return false
  }
</script>

{#if pane.visible}
  <div class="mt-add-backdrop" class:mt-open={pane.shown} onclick={close} aria-hidden="true"></div>
  <div class="mt-add-pane sg-pick" class:mt-open={pane.shown} role="dialog" aria-label="Which tune was this?">
    {#if errorMsg}<p class="mt-error sg-pick-error">{errorMsg}</p>{/if}
    <TuneSearch
      {config}
      variant="modal"
      title="Which tune was this?"
      allowAsIs={true}
      actionLabel="＋ Log This Tune"
      {initialQuery}
      {history}
      onRemember={remember}
      onAdd={pick}
      onClose={close}
    />
  </div>
{/if}

<style>
  .sg-pick-error {
    margin: 8px 14px 0;
  }
</style>

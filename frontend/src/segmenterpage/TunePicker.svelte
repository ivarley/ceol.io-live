<script>
  // "Which tune was this?" for a tune the segmenter logged from the audio, and
  // "which tune goes here?" for one added from the log (spec 050 "Logging while
  // segmenting"). The search itself is the live logger's own TuneSearch --
  // catalog search, thesession.org, paste-a-URL, the preview with its settings
  // pager, "log as-is" -- unchanged, inside the same slide-in pane shell the My
  // Tunes and session-tunes add panes use. Nothing here decides what a pick
  // means: onPick gets TuneSearch's payload and whatever `target` open() was
  // given (the tune being named, or where a new one goes), and the segmenter
  // does the write. The pane floats over the tool, so the audio keeps playing
  // underneath; closing it without picking changes nothing.
  import TuneSearch from '../TuneSearch.svelte'
  import { createPaneState } from '../mytunes/pane.svelte.js'

  let { config, onPick, onClosed = () => {} } = $props()

  const pane = createPaneState('sg-pick-open')
  let target = $state(null) // what the pick is for: handed back to onPick untouched
  let initialQuery = $state('')
  let title = $state('Which tune was this?')
  let actionLabel = $state('＋ Log This Tune')
  // The set's tune type, as the live logger passes it: a soft ranking
  // preference, so a reel's neighbours come up reels first.
  let preferType = $state(null)
  let history = $state([]) // search recall (MRU) for the page's lifetime
  let busy = $state(false)
  let errorMsg = $state('')

  export function open(what, opts = {}) {
    target = what
    preferType = opts.preferType ?? null
    initialQuery = opts.initialQuery ?? ''
    title = opts.title ?? 'Which tune was this?'
    actionLabel = opts.actionLabel ?? '＋ Log This Tune'
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
  <div class="mt-add-pane sg-pick" class:mt-open={pane.shown} role="dialog" aria-label={title}>
    {#if errorMsg}<p class="mt-error sg-pick-error">{errorMsg}</p>{/if}
    <TuneSearch
      {config}
      variant="modal"
      {title}
      allowAsIs={true}
      {actionLabel}
      {initialQuery}
      {preferType}
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

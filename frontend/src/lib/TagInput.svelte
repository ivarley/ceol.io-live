<script>
  // TagInput (spec 042): a one-word-tag editor modeled on IrishTune.info's Tag-it
  // box — chips with an ✕, an input beneath, and space / enter / comma to commit
  // the current token. Backspace on an empty input removes the last chip. Tags are
  // normalized on commit (one word, lowercased) and de-duplicated.
  //
  // `tags` is $bindable — the parent owns the array; this component only ever
  // reassigns it (never mutates in place) so Svelte reactivity holds.
  import Chip from './Chip.svelte'

  let {
    tags = $bindable([]),
    disabled = false,
    placeholder = 'Add tags…',
    // Single-tag normalizer. The drawer passes logic.js's normalizeTag so the
    // client matches the server; the default here keeps standalone use sane.
    normalize = (raw) => String(raw ?? '').trim().toLowerCase().replace(/\s+/g, '-'),
    // Fires when focus leaves the whole component (after committing any draft) —
    // the drawer uses this to auto-save the tags on blur.
    onblur = () => {},
    inputId = null,
    ...rest
  } = $props()

  let draft = $state('')
  let inputEl = $state(null)
  let boxEl = $state(null)

  function commit(raw) {
    const tag = normalize(raw)
    draft = ''
    if (!tag) return
    if (!tags.includes(tag)) tags = [...tags, tag]
  }

  function removeAt(i) {
    if (disabled) return
    tags = tags.filter((_, j) => j !== i)
  }

  function onKeydown(e) {
    if (disabled) return
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
      // These three all mean "that's a whole tag". Never let a space/comma land
      // in the draft — tags are one word.
      e.preventDefault()
      commit(draft)
    } else if (e.key === 'Backspace' && draft === '' && tags.length) {
      e.preventDefault()
      tags = tags.slice(0, -1)
    }
  }

  // Focus leaving the whole component (not just moving between the input and a
  // chip's ✕) commits any draft and notifies the parent — this is the "blur" the
  // drawer auto-saves on. relatedTarget is the element receiving focus.
  function onFocusOut(e) {
    if (boxEl && e.relatedTarget && boxEl.contains(e.relatedTarget)) return
    if (draft.trim()) commit(draft)
    onblur()
  }

  // Clicking anywhere in the box lands focus in the input, like Tag-it.
  function focusInput() {
    if (!disabled) inputEl?.focus()
  }
</script>

<div
  bind:this={boxEl}
  class="kit-taginput"
  class:disabled
  role="group"
  aria-label="Tags"
  onclick={focusInput}
  onfocusout={onFocusOut}
  {...rest}
>
  {#each tags as tag, i (tag)}
    <Chip label={tag} variant="primary" dismissible={!disabled} onDismiss={() => removeAt(i)} />
  {/each}
  <input
    bind:this={inputEl}
    id={inputId}
    class="kit-taginput-field"
    type="text"
    autocomplete="off"
    autocapitalize="none"
    spellcheck="false"
    {placeholder}
    {disabled}
    bind:value={draft}
    onkeydown={onKeydown}
    onblur={() => { if (draft.trim()) commit(draft) }}
  />
</div>

<style>
  .kit-taginput {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--sp-1, 4px);
    padding: var(--sp-1, 4px) var(--sp-2, 8px);
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r-md, 6px);
    background: var(--input-bg, var(--bg-color, #2a2e35));
    cursor: text;
    min-height: 2rem;
  }
  .kit-taginput.disabled {
    opacity: 0.6;
    cursor: default;
  }
  .kit-taginput-field {
    flex: 1 1 6rem;
    min-width: 6rem;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text-color, #e8e8e8);
    font: inherit;
    font-size: 0.8rem;
    padding: 2px 0;
  }
  .kit-taginput-field::placeholder {
    color: var(--text-muted, #8a8f98);
    font-size: 0.8rem;
  }
  /* Tag pills: shorter, squarer, and a darker blue than the shared Chip primary —
     scoped to this component so other Chip uses are untouched. */
  .kit-taginput :global(.kit-chip--styled) {
    padding: 0 6px;
    font-size: 0.78rem;
    line-height: 1.5;
    border-radius: 3px;
  }
  .kit-taginput :global(.kit-chip-primary) {
    background: #1e40af;
    border-color: #1e40af;
  }
  .kit-taginput :global(.kit-chip-primary .kit-x) {
    opacity: 0.85;
  }
</style>

<script>
  // i18n-converted
  // ExportBar: the actions of export mode, fixed to the bottom of the page where
  // the logger's selection bar and a thumb already are. Format, Download with a
  // live count, Done. On a phone it stands where the tab bar was (the page gets
  // `body.has-export-bar` while the bar is mounted: that hides the tab bar and
  // reserves room under the list, so the last rows stay reachable).
  //
  // The bar owns no data. The page passes the pluralized button label, the note
  // under the format, and the handlers; `format` is bound so the page can send it.
  import Seg from './Seg.svelte'
  import { t } from './i18n/index.js'

  let {
    label = '', // the Download button's text, already pluralized by the page
    format = $bindable('json'),
    note = '', // what this format contains
    disabled = false, // nothing to export (an empty list, the wrong tab)
    reason = '', // why, when disabled
    progress = null, // text shown on the button while it works ("Preparing notation 3 of 40")
    busy = false,
    onDownload = () => {},
    onDone = () => {},
  } = $props()

  const FORMAT_OPTIONS = [
    { id: 'json', label: t('JSON') },
    { id: 'csv', label: t('CSV') },
    { id: 'pdf', label: t('PDF') },
  ]

  $effect(() => {
    document.body.classList.add('has-export-bar')
    return () => document.body.classList.remove('has-export-bar')
  })
</script>

<div class="kit-export-bar" id="export-bar" role="region" aria-label={t('Export')}>
  <div class="kit-export-bar-row kit-export-bar-format">
    <Seg
      options={FORMAT_OPTIONS}
      value={format}
      idAttr="data-format"
      styled={false}
      segClass="kit-export-fmt"
      optClass="kit-export-fmt-opt"
      role="group"
      aria-label={t('Format')}
      onSelect={(v) => (format = v)} />
    <span class="kit-export-bar-note">{disabled && reason ? reason : note}</span>
  </div>
  <div class="kit-export-bar-row kit-export-bar-actions">
    <button
      type="button"
      class="kit-export-download"
      id="export-download"
      disabled={disabled || busy}
      aria-busy={busy}
      onclick={onDownload}>{busy && progress ? progress : busy ? t('Preparing…') : label}</button>
    <button type="button" class="kit-export-done" id="export-done" onclick={onDone}>{t('Done')}</button>
  </div>
</div>

<style>
  .kit-export-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    /* Over the page and the phone tab bar (1040), under sheets and the tune drawer (1050+). */
    z-index: 1045;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px 12px calc(10px + env(safe-area-inset-bottom, 0px));
    background: var(--header-bg, #2d2d2d);
    border-top: 1px solid var(--border-color, #444);
    font-size: 14px;
  }
  .kit-export-bar-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .kit-export-bar-note {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    line-height: 1.3;
    color: var(--text-muted, #888);
  }
  /* The format segment: the page's own filter-button look, so it reads as a sibling
     of the status and sort segments above it. */
  :global(.kit-export-fmt) {
    display: flex;
    flex: none;
  }
  :global(.kit-export-fmt-opt) {
    padding: 8px 14px;
    border: 1px solid var(--border-color, #444);
    background: var(--bg-color, #1a1a1a);
    color: var(--text-color, #e0e0e0);
    font: inherit;
    font-size: 14px;
    margin-left: -1px;
    white-space: nowrap;
  }
  :global(.kit-export-fmt-opt:first-child) {
    border-radius: var(--r-sm, 4px) 0 0 var(--r-sm, 4px);
    margin-left: 0;
  }
  :global(.kit-export-fmt-opt:last-child) {
    border-radius: 0 var(--r-sm, 4px) var(--r-sm, 4px) 0;
  }
  :global(.kit-export-fmt-opt:hover) {
    background: var(--hover-bg, #3d3d3d);
  }
  :global(.kit-export-fmt-opt.active) {
    background: var(--primary-fill, #4a8049);
    border-color: var(--primary-fill, #4a8049);
    color: #fff;
    position: relative;
    z-index: 1;
  }
  .kit-export-download {
    flex: 1;
    min-width: 0;
    padding: 11px 14px;
    border-radius: var(--r, 8px);
    border: 0;
    background: var(--primary-fill, #4a8049);
    color: #fff;
    font: inherit;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kit-export-download:hover:not(:disabled) {
    background: var(--primary-fill-hover, #437342);
  }
  .kit-export-download:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .kit-export-done {
    flex: none;
    padding: 10px 14px;
    border-radius: var(--r, 8px);
    border: 1px solid var(--border-color, #444);
    background: var(--input-bg, #2d2d2d);
    color: var(--text-color, #e0e0e0);
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  .kit-export-done:hover {
    background: var(--hover-bg, #3d3d3d);
  }
  @media (min-width: 769px) {
    .kit-export-bar {
      flex-direction: row;
      align-items: center;
      gap: 14px;
      padding: 10px 22px 12px;
    }
    .kit-export-bar-format {
      flex: 1;
    }
    .kit-export-bar-actions {
      flex: none;
    }
    .kit-export-download {
      flex: none;
      min-width: 230px;
    }
  }
  /* Room under the page for the bar, and no tab bar beneath it: the bar is the way out. */
  :global(body.has-export-bar) {
    padding-bottom: 150px;
  }
  :global(body.has-export-bar .tab-bar) {
    display: none;
  }
  @media (min-width: 769px) {
    :global(body.has-export-bar) {
      padding-bottom: 90px;
    }
  }
</style>

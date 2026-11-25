<script>
  // i18n-converted
  // ExportBanner: the strip at the top of a page in export mode. It names the mode
  // and what it covers, in the accent wash the tab bar already uses for the active
  // tab, so the page reads as "the same page, in a mode" rather than a new screen.
  // The actions live in ExportBar at the bottom; this only says where you are and
  // offers the way out.
  import { t } from './i18n/index.js'

  let {
    label = t('Exporting'), // what is being exported ("Exporting Austin Celtic Session")
    hint = '', // one sentence on what to do
    onLeave = () => {},
  } = $props()
</script>

<div class="kit-export-banner" role="status" id="export-banner">
  <span class="kit-export-banner-label">{label}</span>
  {#if hint}<span class="kit-export-banner-hint">{hint}</span>{/if}
  <button type="button" class="kit-export-banner-leave" id="export-leave" onclick={onLeave}>{t('Leave')}</button>
</div>

<style>
  .kit-export-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    margin: 0 0 10px;
    background: rgba(101, 180, 100, 0.16);
    border-bottom: 1px solid var(--primary-fill, #4a8049);
    font-size: 13.5px;
    line-height: 1.35;
  }
  .kit-export-banner-label {
    font-weight: 600;
    color: var(--primary, #65b464);
    white-space: nowrap;
  }
  .kit-export-banner-hint {
    flex: 1;
    min-width: 0;
    color: var(--text-color, #e0e0e0);
  }
  .kit-export-banner-leave {
    margin-left: auto;
    flex: none;
    font: inherit;
    font-size: 13px;
    padding: 4px 9px;
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r-sm, 4px);
    background: none;
    color: var(--text-color, #e0e0e0);
    cursor: pointer;
    white-space: nowrap;
  }
  .kit-export-banner-leave:hover {
    background: var(--hover-bg, #3d3d3d);
  }
</style>

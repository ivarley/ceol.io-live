<script>
  // i18n-converted
  // The export chooser (/export): Profile → Export my data. Three choices. My Tunes
  // goes straight to your list in export mode; Session Tunes and Session Logs first
  // ask which session (your sessions, then every session on Ceol), then go to that
  // session's tab in export mode. The export itself happens on those pages, with
  // their own filters: this page only picks what.
  import { Chevron, List, SearchField, Sheet, t } from '../lib/index.js'
  import { MY_TUNES_EXPORT, matchSessions, pickerSections, sessionExportHref } from './links.js'

  let { pageData = null } = $props()

  const sections = $derived(pickerSections(pageData?.my_sessions, pageData?.all_sessions))

  // Which tab the open picker is for: 'tunes' | 'logs' | null (closed).
  let pickerFor = $state(null)
  let query = $state('')
  let active = $state(-1)

  const q = $derived(query.trim().toLowerCase())
  const mine = $derived(matchSessions(sections.mine, q))
  const rest = $derived(matchSessions(sections.rest, q))
  // One list for the keyboard: yours first, then the rest, with a divider between.
  const items = $derived([...mine.map((s) => ({ ...s, _mine: true })), ...rest])

  const pickerTitle = $derived(pickerFor === 'logs' ? t('Which session’s logs?') : t('Which session’s tunes?'))

  function openPicker(tab) {
    pickerFor = tab
    query = ''
    active = -1
  }
  function closePicker() {
    pickerFor = null
    query = ''
    active = -1
  }
  function pick(session) {
    if (!session || !pickerFor) return
    const href = sessionExportHref(session.path, pickerFor)
    closePicker()
    if (href) window.location.assign(href)
  }
</script>

<div class="export-page">
  <h1 class="export-title">{t('Export')}</h1>
  <p class="export-intro">{t('Pick what to export. The next page has the usual filters; set them, then choose a format.')}</p>

  <div class="export-choices">
    <a class="export-choice" href={MY_TUNES_EXPORT} id="export-my-tunes">
      <span class="export-choice-head">
        <span class="export-choice-title">{t('My Tunes')}</span>
        <Chevron class="kit-chev" />
      </span>
      <span class="export-choice-desc">{t('Your tune list, with status, tags, notes and the setting you play.')}</span>
    </a>

    <button type="button" class="export-choice" id="export-session-tunes" onclick={() => openPicker('tunes')}>
      <span class="export-choice-head">
        <span class="export-choice-title">{t('Session Tunes')}</span>
        <Chevron class="kit-chev" />
      </span>
      <span class="export-choice-desc">{t('Everything a session plays, with its names and settings.')}</span>
      <span class="export-choice-pick">{t('Choose a session')}</span>
    </button>

    <button type="button" class="export-choice" id="export-session-logs" onclick={() => openPicker('logs')}>
      <span class="export-choice-head">
        <span class="export-choice-title">{t('Session Logs')}</span>
        <Chevron class="kit-chev" />
      </span>
      <span class="export-choice-desc">{t('Nights at a session, set by set.')}</span>
      <span class="export-choice-pick">{t('Choose a session')}</span>
    </button>
  </div>

  <p class="export-foot">{t('The two session pickers list your sessions first, then any session on Ceol.')}</p>
</div>

<Sheet open={pickerFor !== null} title={pickerTitle} desktop="dock" onCancel={closePicker}>
  <SearchField bind:value={query} placeholder={t('Find a session')} />

  <List {items} bind:active onSelect={pick}>
    {#snippet row(item)}
      {#if item._mine && mine[0] === item || (!item._mine && rest[0] && rest[0].path === item.path)}
        <span class="ep-section">{item._mine ? t('Your sessions') : t('All sessions')}</span>
      {/if}
      <span class="ep-row">
        <span class="ep-name">{item.name}</span>
        {#if item.place}<span class="ep-place">{item.place}</span>{/if}
      </span>
    {/snippet}
  </List>

  {#if !items.length}
    <div class="ep-empty">{t('No session matches “{query}”.', { query })}</div>
  {/if}
</Sheet>

<style>
  .export-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 6px;
  }
  .export-intro,
  .export-foot {
    color: var(--text-muted, #888);
    font-size: 14px;
    margin: 0 0 16px;
  }
  .export-foot {
    margin: 14px 0 0;
    font-size: 12.5px;
  }
  .export-choices {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .export-choice {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    width: 100%;
    padding: 14px;
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r-lg, 10px);
    background: var(--input-bg, #2d2d2d);
    color: var(--text-color, #e0e0e0);
    text-decoration: none;
    text-align: left;
    font: inherit;
    cursor: pointer;
  }
  .export-choice:hover {
    background: var(--hover-bg, #3d3d3d);
    text-decoration: none;
    color: var(--text-color, #e0e0e0);
  }
  .export-choice-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .export-choice-title {
    font-size: 16px;
    font-weight: 600;
  }
  .export-choice-head :global(.kit-chev) {
    color: var(--primary, #65b464);
  }
  .export-choice-desc {
    color: var(--text-muted, #888);
    font-size: 13.5px;
    line-height: 1.4;
  }
  .export-choice-pick {
    display: inline-block;
    align-self: flex-start;
    margin-top: 2px;
    padding: 7px 10px;
    border: 1px solid var(--border-color, #444);
    border-radius: var(--r-sm, 6px);
    background: var(--bg-color, #1a1a1a);
    font-size: 14px;
    color: var(--primary, #65b464);
  }
  .ep-section {
    display: block;
    width: 100%;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted, #888);
    margin: 0 0 6px;
  }
  .ep-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    min-width: 0;
  }
  .ep-name {
    font-weight: 500;
  }
  .ep-place {
    font-size: 12px;
    color: var(--secondary-text, #888);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ep-empty {
    padding: 16px 4px;
    font-size: 13px;
    color: var(--secondary-text, #888);
  }
</style>

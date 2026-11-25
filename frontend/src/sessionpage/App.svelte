<script>
  // i18n-converted
  // The session-detail page view (spec 035 Step 4b) — ported behavior-for-behavior
  // from the legacy 2,400-line inline script in templates/session_detail.html.
  // The server-rendered shell keeps the page header (h1, session details, join
  // banner, flash messages) and the whole legacy <style> block; this component
  // emits the same class names, so the look is unchanged. Globals (TuneDetailModal,
  // TunebookStatus, AccentUtils, showMessage) come from base.html exactly as
  // before; the add-tune pane is bundled in as a child component.
  import { untrack } from 'svelte'
  import TunesTab from './TunesTab.svelte'
  import LogsTab from './LogsTab.svelte'
  import PeopleTab from './PeopleTab.svelte'
  import AddInstanceModal from './AddInstanceModal.svelte'
  import SessionTuneAddApp from '../mytunes/SessionTuneAddApp.svelte'
  import { basePathOf } from './logic.js'
  import { publishHeight } from './sticky.js'
  import {
    ExportBanner,
    ExportBar,
    isExportMode,
    leaveExportMode,
    onExportModeChange,
    runExport,
    tn,
  } from '../lib/index.js'

  // The tab strip is sticky under the fixed site header, and the active tab's
  // toolbar sticks under IT. Tabs renders the strip itself, so its height is
  // published from here by id rather than with an action on the element.
  $effect(() => {
    const strip = document.getElementById('session-tabs')
    if (!strip) return
    const handle = publishHeight(strip, '--session-tabs-h')
    return () => handle.destroy()
  })

  let { pageData, ctx = {} } = $props()

  const session = pageData.session
  const permissions = pageData.permissions
  const sessionPath = session.path
  const isFestival = session.session_type === 'festival'
  const defaultTab = pageData.default_tab
  // Spec 034: seeing the People tab requires the SESSION to have vouched for you
  // (is_admin OR confirmed), not merely that you joined it. Anyone with an account can
  // self-join any session, so gating on membership would hand a stranger the roster.
  const showPeopleTab = permissions.is_logged_in && permissions.can_view_people

  // Festival sessions label the logs tab "Sessions" and order it first.
  // Counts come from the payload, not from the tabs' own data: Logs and People load
  // lazily when you open them, so a count derived client-side could only appear after
  // you had already gone and looked (spec 052 §B8 Stage 2).
  const tabs = $derived.by(() => {
    const tunes = { id: 'tunes', label: t('Tunes'), count: pageData.total_tunes_count }
    const logs = {
      id: 'logs',
      label: isFestival ? t('Sessions') : t('Logs'),
      count: pageData.total_logs_count,
    }
    const list = isFestival ? [logs, tunes] : [tunes, logs]
    if (showPeopleTab) {
      // null when the viewer may not see the roster; Tabs renders nothing for null,
      // and 0 is a real count.
      list.push({ id: 'people', label: t('People'), count: pageData.total_people_count })
    }
    return list
  })

  // The tab comes from the path (/sessions/<path>/tunes); `?tab=` is accepted too, so a
  // link that cannot know the path shape (the export chooser) still lands on the tab.
  const TAB_IDS = ['tunes', 'logs', 'people']
  const tabParam = new URLSearchParams(window.location.search).get('tab')
  let activeTab = $state(ctx.activeTab || (TAB_IDS.includes(tabParam) ? tabParam : null) || defaultTab)

  // ---- export mode (the profile's "Export my data" → /sessions/<path>/<tab>?export=1) --
  // One mode for the whole page: the tab you are on is what gets exported. Each tab
  // that can export reports its visible ids (display order) and a summary of its
  // filters through `onVisible`; the bar below sends them. People has nothing to
  // export, so there the bar says so and is disabled.
  let exportMode = $state(isExportMode())
  $effect(() => onExportModeChange((on) => (exportMode = on)))
  let exportFormat = $state('json')
  let exportBusy = $state(false)
  let exportProgress = $state(null)
  let tunesExport = $state({ ids: [], filters: [] })
  let logsExport = $state({ ids: [], filters: [] })
  const exportTarget = $derived.by(() => {
    if (activeTab === 'tunes')
      return {
        url: `/api/export/sessions/${sessionPath}/tunes`,
        key: 'tune_ids',
        ...tunesExport,
        label: tn(tunesExport.ids.length, 'Download {n} tune', 'Download {n} tunes'),
        reason: t('No tunes match these filters.'),
        note:
          exportFormat === 'pdf'
            ? t('Title and notation for each tune, in the setting this session plays')
            : t('One row per tune, with the name and setting this session uses'),
        fallbackName: `${sessionPath.replace(/\//g, '-')}-tunes`,
      }
    if (activeTab === 'logs')
      return {
        url: `/api/export/sessions/${sessionPath}/logs`,
        key: 'instance_ids',
        ...logsExport,
        label: tn(logsExport.ids.length, 'Download {n} night', 'Download {n} nights'),
        reason: t('No nights match these filters.'),
        note:
          exportFormat === 'pdf'
            ? t('Nights as headings, sets under them, each tune with its notation')
            : t('One row per tune: night, set, position, name used that night, key, setting'),
        fallbackName: `${sessionPath.replace(/\//g, '-')}-logs`,
      }
    return {
      url: null,
      key: null,
      ids: [],
      filters: [],
      label: t('Download'),
      reason: t('Nothing to export on this tab. Switch to Tunes or Logs.'),
      note: '',
      fallbackName: 'ceol-export',
    }
  })
  async function downloadExport() {
    const target = exportTarget
    if (exportBusy || !target.url || !target.ids.length) return
    exportBusy = true
    exportProgress = null
    try {
      await runExport({
        url: target.url,
        format: exportFormat,
        body: { [target.key]: target.ids, filters: target.filters },
        onProgress: (p) => {
          exportProgress = p ? t('Preparing notation {done} of {total}', p) : null
        },
        fallbackName: target.fallbackName,
      })
    } catch (e) {
      console.error('Export failed:', e)
      toast(e?.message || t("Couldn't export. Check your connection and try again."), 'error')
    } finally {
      exportBusy = false
      exportProgress = null
    }
  }

  // Path-based tab URLs; the legacy switchTab dropped the query string here. The
  // export flag is the one param that survives: it is a mode on the page, and a
  // tab switch in the mode is how you choose what to export.
  function onTabChange(tabName) {
    const newPath = `${basePathOf(window.location.pathname)}/${tabName}${exportMode ? '?export=1' : ''}`
    window.history.pushState({}, '', newPath)
  }

  let addInstanceModal = $state(null)
  const openAddInstance = () => addInstanceModal && addInstanceModal.open()

  // Add-tune pane: the same component the standalone /static/mytunes bundle used
  // to mount, now bundled in as a child with callback props (no window global).
  let addPane = $state(null)

  import { toast, Tabs, t } from '../lib/index.js'

  $effect(() => {
    untrack(() => {
      // No tab in the URL: canonicalize to the default tab, keeping the query
      // string (?show/?added survive the rewrite).
      if (!ctx.activeTab && defaultTab) {
        const basePath = basePathOf(window.location.pathname)
        window.history.replaceState({}, '', `${basePath}/${defaultTab}${window.location.search}`)
      }

      // Copy-flow handoff toast (sessionStorage, set by the source page).
      const copyMessage = sessionStorage.getItem('copyTunesMessage')
      if (copyMessage) {
        sessionStorage.removeItem('copyTunesMessage')
        toast(copyMessage, 'success')
      }

      // Reveal any server-rendered flash messages.
      const existingMessage = document.querySelector('.message')
      if (existingMessage) {
        setTimeout(() => existingMessage.classList.add('show'), 10)
      }

    })
  })
</script>

<!-- Tabbed Interface: the kit Tabs engine with this page's legacy skin
     (.tab-buttons/.tab-button CSS + e2e select on these classes). Pane
     components stay mounted across switches so their state survives. This page
     never had the mobile <select>, and since spec 052 §B3 no page does. -->
{#if exportMode}
  <ExportBanner
    label={t('Exporting {name}', { name: session.name })}
    hint={t('The tab you are on is what gets exported. Tunes exports the repertoire, Logs exports the nights.')}
    onLeave={leaveExportMode} />
{/if}
<div class="tabs-container">
  <Tabs
    {tabs}
    bind:value={activeTab}
    onValueChange={onTabChange}
    styled={false}
    listId="session-tabs"
    listClass="tab-buttons"
    tabClass="tab-button">
    {#snippet children(active)}
  <TunesTab
    active={active === 'tunes'}
    {session}
    {permissions}
    addPane={() => addPane}
    tunes={pageData.tunes || []}
    totalTunesCount={pageData.total_tunes_count || 0}
    hasMoreTunes={!!pageData.has_more_tunes}
    deepLinkTuneId={ctx.tuneId || null}
    {exportMode}
    onVisible={(v) => (tunesExport = v)} />

  <LogsTab
    active={active === 'logs'}
    {session}
    isLoggedIn={permissions.is_logged_in}
    onAddInstance={openAddInstance}
    {exportMode}
    onVisible={(v) => (logsExport = v)} />

  {#if showPeopleTab}
    <PeopleTab
      active={active === 'people'}
      {sessionPath}
      sessionType={session.session_type}
      canonicalInstruments={ctx.canonicalInstruments || []}
      currentUserId={ctx.currentUserPersonId ?? null}
      initialPersonId={ctx.personId || null}
      isSessionAdmin={permissions.is_session_admin}
      trackAttendance={session.track_attendance !== false} />
  {/if}
    {/snippet}
  </Tabs>
</div>

<AddInstanceModal bind:this={addInstanceModal} {sessionPath} locationName={session.location_name} {isFestival} />

<!-- Add-to-session-tunes pane: same component as before, now a bundled-in child
     with callback props instead of the window.SessionTuneAddPane global. -->
<SessionTuneAddApp bind:this={addPane} />

{#if exportMode}
  <ExportBar
    bind:format={exportFormat}
    label={exportTarget.label}
    note={exportTarget.note}
    disabled={!exportTarget.url || !exportTarget.ids.length}
    reason={exportTarget.reason}
    busy={exportBusy}
    progress={exportProgress}
    onDownload={downloadExport}
    onDone={leaveExportMode} />
{/if}

<script>
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
  const tabs = (() => {
    const t = isFestival
      ? [
          { id: 'logs', label: 'Sessions' },
          { id: 'tunes', label: 'Tunes' },
        ]
      : [
          { id: 'tunes', label: 'Tunes' },
          { id: 'logs', label: 'Logs' },
        ]
    if (showPeopleTab) t.push({ id: 'people', label: 'People' })
    return t
  })()

  let activeTab = $state(ctx.activeTab || defaultTab)

  // Path-based tab URLs; the legacy switchTab dropped the query string here.
  function onTabChange(tabName) {
    const newPath = `${basePathOf(window.location.pathname)}/${tabName}`
    window.history.pushState({}, '', newPath)
  }

  let addInstanceModal = $state(null)
  const openAddInstance = () => addInstanceModal && addInstanceModal.open()

  // Add-tune pane: the same component the standalone /static/mytunes bundle used
  // to mount, now bundled in as a child with callback props (no window global).
  let addPane = $state(null)

  import { toast, Tabs } from '../lib/index.js'

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
     components stay mounted across switches so their state survives.
     mobileSelect stays 'auto': 2-3 tabs fit a phone, so this page keeps its
     pre-unification visual tabs on mobile (it never had the select). -->
<div class="tabs-container">
  <Tabs
    {tabs}
    bind:value={activeTab}
    onValueChange={onTabChange}
    styled={false}
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
    deepLinkTuneId={ctx.tuneId || null} />

  <LogsTab
    active={active === 'logs'}
    {session}
    isLoggedIn={permissions.is_logged_in}
    onAddInstance={openAddInstance} />

  {#if showPeopleTab}
    <PeopleTab
      active={active === 'people'}
      {sessionPath}
      sessionType={session.session_type}
      canonicalInstruments={ctx.canonicalInstruments || []}
      currentUserId={ctx.currentUserPersonId ?? null}
      initialPersonId={ctx.personId || null}
      isSessionAdmin={permissions.is_session_admin} />
  {/if}
    {/snippet}
  </Tabs>
</div>

<AddInstanceModal bind:this={addInstanceModal} {sessionPath} locationName={session.location_name} />

<!-- Add-to-session-tunes pane: same component as before, now a bundled-in child
     with callback props instead of the window.SessionTuneAddPane global. -->
<SessionTuneAddApp bind:this={addPane} />

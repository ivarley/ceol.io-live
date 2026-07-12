<script>
  // The session-admin page view (spec 035 Step 5b) — ported behavior-for-behavior
  // from the legacy 1,300-line inline script in templates/session_admin.html.
  // Tab switching stays URL-based (each tab is its own wrapper route rendering
  // this same shell), exactly like the legacy <a>-tabs / mobile-dropdown page.
  // showMessage is a global from base.html, as before; the session-instance
  // detail is the bundled InstanceSheet (LogsAdminTab) since the Sheet round.
  import { Tabs } from '../lib/index.js'
  import DetailsTab from './DetailsTab.svelte'
  import TunesAdminTab from './TunesAdminTab.svelte'
  import PeopleAdminTab from './PeopleAdminTab.svelte'
  import LogsAdminTab from './LogsAdminTab.svelte'
  import CacheTab from './CacheTab.svelte'

  let { pageData, ctx = {} } = $props()

  const session = pageData.session
  const sessionPath = ctx.sessionPath || session.path
  const activeTab = ctx.activeTab || 'details'
  const isSystemAdmin = !!ctx.isSystemAdmin

  const breadcrumbTab =
    activeTab === 'tunes' ? 'Tunes' : activeTab === 'people' ? 'Members' : activeTab === 'logs' ? 'Logs' : ''

  // Each tab is a server route: the kit Tabs navigate mode renders real links
  // on desktop and navigates from the mobile select.
  const adminTabs = [
    { id: 'details', label: 'Details', href: `/admin/sessions/${sessionPath}` },
    { id: 'tunes', label: 'Tunes', href: `/admin/sessions/${sessionPath}/tunes` },
    { id: 'people', label: 'Members', href: `/admin/sessions/${sessionPath}/people` },
    { id: 'logs', label: 'Logs', href: `/admin/sessions/${sessionPath}/logs` },
    { id: 'cache', label: 'Local Cache', href: `/admin/sessions/${sessionPath}/cache` },
  ]
</script>

<!-- Session Admin Breadcrumb Navigation -->
<nav class="admin-breadcrumb" aria-label="breadcrumb">
  {#if isSystemAdmin}
    <a href="/admin" class="breadcrumb-item">Admin</a>
    <span class="breadcrumb-separator">&gt;&gt;</span>
    <a href="/admin/sessions" class="breadcrumb-item">Sessions</a>
  {:else}
    <a href="/admin/sessions" class="breadcrumb-item">My Sessions</a>
  {/if}
  <span class="breadcrumb-separator">&gt;&gt;</span>
  {#if activeTab === 'details'}
    <span class="breadcrumb-current">{session.name}</span>
  {:else}
    <a href="/admin/sessions/{session.path}" class="breadcrumb-item">{session.name}</a>
    <span class="breadcrumb-separator">&gt;&gt;</span>
    <span class="breadcrumb-current">{breadcrumbTab}</span>
  {/if}
</nav>

<!-- Session Admin Tab Navigation: kit Tabs in navigate mode (tabs are routes;
     real links on desktop, the mobile select navigates). Legacy skin classes kept. -->
<nav class="session-admin-tabs-nav">
  <Tabs
    tabs={adminTabs}
    navigate={true}
    value={activeTab}
    styled={false}
    listId="session-admin-tabs"
    listClass="nav nav-tabs"
    tabClass="nav-link"
    selectId="session-admin-mobile-select"
    selectClass="form-select"
    selectLabel="Admin section" />
</nav>

<!-- Tab Content -->
<div class="tab-content" id="session-admin-tab-content">
  <!-- Details Tab -->
  <div class="tab-pane fade {activeTab === 'details' ? 'show active' : ''}" id="details" role="tabpanel">
    <DetailsTab {session} {sessionPath} timezoneOptions={pageData.timezone_options || []} />
  </div>

  <!-- Tunes Tab -->
  <div class="tab-pane fade {activeTab === 'tunes' ? 'show active' : ''}" id="tunes" role="tabpanel">
    <TunesAdminTab {sessionPath} load={activeTab === 'tunes'} />
  </div>

  <!-- People Tab -->
  <div class="tab-pane fade {activeTab === 'people' ? 'show active' : ''}" id="people" role="tabpanel">
    <PeopleAdminTab {sessionPath} load={activeTab === 'people'} />
  </div>

  <!-- Logs Tab -->
  <div class="tab-pane fade {activeTab === 'logs' ? 'show active' : ''}" id="logs" role="tabpanel">
    <LogsAdminTab {sessionPath} locationName={session.location_name} load={activeTab === 'logs'} />
  </div>

  <!-- Local Cache Tab -->
  <div class="tab-pane fade {activeTab === 'cache' ? 'show active' : ''}" id="cache" role="tabpanel">
    <CacheTab
      {sessionPath}
      sessionLimit={session.live_cache_session_limit}
      globalLimit={session.live_cache_global_limit}
      load={activeTab === 'cache'} />
  </div>
</div>

<script>
  // The session-admin page view (spec 035 Step 5b) — ported behavior-for-behavior
  // from the legacy 1,300-line inline script in templates/session_admin.html.
  // Tab switching stays URL-based (each tab is its own wrapper route rendering
  // this same shell), exactly like the legacy <a>-tabs / mobile-dropdown page.
  // showMessage and SessionInstanceModal are globals from base.html /
  // static/js/session_instance_modal.js, as before.
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

  function onMobileTabChange(e) {
    const value = e.currentTarget.value
    let url
    if (value === 'details') {
      url = `/admin/sessions/${sessionPath}`
    } else if (value === 'tunes') {
      url = `/admin/sessions/${sessionPath}/tunes`
    } else if (value === 'people') {
      url = `/admin/sessions/${sessionPath}/people`
    } else if (value === 'logs') {
      url = `/admin/sessions/${sessionPath}/logs`
    } else if (value === 'cache') {
      url = `/admin/sessions/${sessionPath}/cache`
    }
    if (url) {
      window.location.href = url
    }
  }
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

<!-- Session Admin Tab Navigation -->
<nav class="session-admin-tabs-nav">
  <!-- Desktop Tab Navigation -->
  <div class="nav nav-tabs" id="session-admin-tabs" role="tablist">
    <a class="nav-link {activeTab === 'details' ? 'active' : ''}" href="/admin/sessions/{session.path}">
      Details
    </a>
    <a class="nav-link {activeTab === 'tunes' ? 'active' : ''}" href="/admin/sessions/{session.path}/tunes">
      Tunes
    </a>
    <a class="nav-link {activeTab === 'people' ? 'active' : ''}" href="/admin/sessions/{session.path}/people">
      Members
    </a>
    <a class="nav-link {activeTab === 'logs' ? 'active' : ''}" href="/admin/sessions/{session.path}/logs">
      Logs
    </a>
    <a class="nav-link {activeTab === 'cache' ? 'active' : ''}" href="/admin/sessions/{session.path}/cache">
      Local Cache
    </a>
  </div>

  <!-- Mobile Dropdown Navigation -->
  <div class="session-admin-tabs-mobile">
    <select class="form-select" id="session-admin-mobile-select" value={activeTab} onchange={onMobileTabChange}>
      <option value="details">Details</option>
      <option value="tunes">Tunes</option>
      <option value="people">Members</option>
      <option value="logs">Logs</option>
      <option value="cache">Local Cache</option>
    </select>
  </div>
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

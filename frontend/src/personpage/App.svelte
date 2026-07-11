<script>
  // The person-details page view (spec 035 Step 5a) — ported behavior-for-behavior
  // from the legacy 1,350-line inline script in templates/person_details.html.
  // Serves both flavors: /me (user profile) and /admin/people/<id> (system admin).
  // The shell keeps the whole legacy <style> blocks; this component emits the same
  // class names/ids, so the look is unchanged. showMessage comes from base.html.
  import { untrack } from 'svelte'
  import ProfileTab from './ProfileTab.svelte'
  import SessionsTab from './SessionsTab.svelte'
  import AttendedTab from './AttendedTab.svelte'
  import TunesStatsTab from './TunesStatsTab.svelte'
  import LoginsTab from './LoginsTab.svelte'

  let { pageData, ctx = {} } = $props()

  const person = pageData.person
  const user = pageData.user
  const isUserProfile = pageData.is_user_profile
  const isSystemAdmin = pageData.is_system_admin
  const personId = person.id

  const toast = (msg, type) => window.showMessage && window.showMessage(msg, type)

  const validTabs = ['profile', 'sessions', 'attended', 'tunes', 'logins']

  // Initial tab from the URL (?tab=), exactly like the legacy DOMContentLoaded path
  // (activateTab(tabFromUrl, false) — no URL rewrite on load).
  const initialTab = (() => {
    const t = new URLSearchParams(window.location.search).get('tab')
    return t && validTabs.includes(t) ? t : 'profile'
  })()

  let activeTab = $state(initialTab)
  let attendedLoaded = $state(false)
  let tunesLoaded = $state(false)
  let loginsLoaded = $state(false)

  // Lazy-load bookkeeping for whichever tab is (or becomes) active.
  function noteActivated(tabId) {
    if (tabId === 'attended') attendedLoaded = true
    else if (tabId === 'tunes') tunesLoaded = true
    else if (tabId === 'logins') loginsLoaded = true
  }
  noteActivated(initialTab)

  function activateTab(targetId, updateUrl = true) {
    activeTab = targetId
    noteActivated(targetId)
    if (updateUrl) {
      const url = new URL(window.location)
      if (targetId === 'profile') {
        url.searchParams.delete('tab')
      } else {
        url.searchParams.set('tab', targetId)
      }
      window.history.replaceState({}, '', url)
    }
  }

  // Breadcrumb nesting (admin flavor): non-profile tabs demote the person name to
  // a link and append the tab name.
  const tabDisplayNames = {
    profile: null,
    sessions: 'Sessions',
    attended: 'Attended',
    tunes: 'Tunes',
    logins: 'Logins',
  }
  const breadcrumbTabName = $derived(tabDisplayNames[activeTab] || null)

  const sessionsTabLabel = isUserProfile ? 'My Sessions' : 'Sessions'
  const attendedTabLabel = isUserProfile ? "I've Attended" : 'Attended'

  $effect(() => {
    untrack(() => {
      // Saved flash messages (survive the save/add reloads) from sessionStorage.
      const savedMessage = sessionStorage.getItem('personSavedMessage')
      if (savedMessage) {
        toast(savedMessage, 'success')
        sessionStorage.removeItem('personSavedMessage')
      }
    })
  })
</script>

{#if isUserProfile}
  <header class="docs-header">
    <h1 class="docs-heading">Profile: {person.name}</h1>
  </header>
{:else}
  <!-- Admin Breadcrumb Navigation -->
  <nav class="admin-breadcrumb" aria-label="breadcrumb">
    <a href="/admin" class="breadcrumb-item">Admin</a>
    <span class="breadcrumb-separator">&gt;&gt;</span>
    <a href="/admin/people" class="breadcrumb-item">People</a>
    <span class="breadcrumb-separator">&gt;&gt;</span>
    {#if breadcrumbTabName}
      <span id="breadcrumb-person-name"><a
          href="#profile"
          class="breadcrumb-item"
          onclick={(e) => {
            e.preventDefault()
            activateTab('profile')
          }}>{person.name}</a></span>
      <span id="breadcrumb-tab-separator" class="breadcrumb-separator">&gt;&gt;</span>
      <span id="breadcrumb-tab-name" class="breadcrumb-current">{breadcrumbTabName}</span>
    {:else}
      <span id="breadcrumb-person-name" class="breadcrumb-current">{person.name}</span>
      <span id="breadcrumb-tab-separator" class="breadcrumb-separator" style="display: none;">&gt;&gt;</span>
      <span id="breadcrumb-tab-name" class="breadcrumb-current" style="display: none;"></span>
    {/if}
  </nav>
{/if}

<!-- Mobile Tab Navigation (dropdown) -->
<div class="profile-mobile-nav d-md-none mb-3">
  <select
    id="profile-tab-select"
    class="form-select"
    value={activeTab}
    onchange={(e) => activateTab(e.currentTarget.value)}>
    <option value="profile">Profile</option>
    <option value="sessions">{sessionsTabLabel}</option>
    <option value="attended">{attendedTabLabel}</option>
    <option value="tunes">Tunes</option>
    {#if user}
      <option value="logins">Logins</option>
    {/if}
  </select>
</div>

<!-- Desktop Tab Navigation -->
<ul class="nav nav-tabs d-none d-md-flex" id="profileTabs" role="tablist">
  <li class="nav-item" role="presentation">
    <button
      class="nav-link"
      class:active={activeTab === 'profile'}
      id="profile-tab"
      data-bs-toggle="tab"
      data-bs-target="#profile"
      type="button"
      role="tab"
      aria-controls="profile"
      aria-selected={activeTab === 'profile'}
      onclick={() => activateTab('profile')}>Profile</button>
  </li>
  <li class="nav-item" role="presentation">
    <button
      class="nav-link"
      class:active={activeTab === 'sessions'}
      id="sessions-tab"
      data-bs-toggle="tab"
      data-bs-target="#sessions"
      type="button"
      role="tab"
      aria-controls="sessions"
      aria-selected={activeTab === 'sessions'}
      onclick={() => activateTab('sessions')}>{sessionsTabLabel}</button>
  </li>
  <li class="nav-item" role="presentation">
    <button
      class="nav-link"
      class:active={activeTab === 'attended'}
      id="attended-tab"
      data-bs-toggle="tab"
      data-bs-target="#attended"
      type="button"
      role="tab"
      aria-controls="attended"
      aria-selected={activeTab === 'attended'}
      onclick={() => activateTab('attended')}>{attendedTabLabel}</button>
  </li>
  <li class="nav-item" role="presentation">
    <button
      class="nav-link"
      class:active={activeTab === 'tunes'}
      id="tunes-tab"
      data-bs-toggle="tab"
      data-bs-target="#tunes"
      type="button"
      role="tab"
      aria-controls="tunes"
      aria-selected={activeTab === 'tunes'}
      onclick={() => activateTab('tunes')}>Tunes</button>
  </li>
  {#if user}
    <li class="nav-item" role="presentation">
      <button
        class="nav-link"
        class:active={activeTab === 'logins'}
        id="logins-tab"
        data-bs-toggle="tab"
        data-bs-target="#logins"
        type="button"
        role="tab"
        aria-controls="logins"
        aria-selected={activeTab === 'logins'}
        onclick={() => activateTab('logins')}>Logins</button>
    </li>
  {/if}
</ul>

<!-- Tab Content -->
<div class="tab-content" id="profileTabContent">
  <!-- Profile Tab (Person & User Info Combined) -->
  <div
    class="tab-pane fade"
    class:show={activeTab === 'profile'}
    class:active={activeTab === 'profile'}
    id="profile"
    role="tabpanel"
    aria-labelledby="profile-tab">
    <ProfileTab
      {person}
      {user}
      {isUserProfile}
      {personId}
      timezoneOptions={pageData.timezone_options || []}
      canonicalInstruments={ctx.canonicalInstruments || []} />
  </div>

  <!-- Sessions Tab -->
  <div
    class="tab-pane fade"
    class:show={activeTab === 'sessions'}
    class:active={activeTab === 'sessions'}
    id="sessions"
    role="tabpanel"
    aria-labelledby="sessions-tab">
    <SessionsTab
      initialSessions={pageData.sessions || []}
      {person}
      {personId}
      {isUserProfile}
      {isSystemAdmin} />
  </div>

  <!-- Attended Tab -->
  <div
    class="tab-pane fade"
    class:show={activeTab === 'attended'}
    class:active={activeTab === 'attended'}
    id="attended"
    role="tabpanel"
    aria-labelledby="attended-tab">
    <AttendedTab {personId} load={attendedLoaded} />
  </div>

  <!-- Tunes Tab -->
  <div
    class="tab-pane fade"
    class:show={activeTab === 'tunes'}
    class:active={activeTab === 'tunes'}
    id="tunes"
    role="tabpanel"
    aria-labelledby="tunes-tab">
    <TunesStatsTab {personId} load={tunesLoaded} />
  </div>

  <!-- Logins Tab -->
  {#if user}
    <div
      class="tab-pane fade"
      class:show={activeTab === 'logins'}
      class:active={activeTab === 'logins'}
      id="logins"
      role="tabpanel"
      aria-labelledby="logins-tab">
      <LoginsTab {personId} load={loginsLoaded} />
    </div>
  {/if}
</div>

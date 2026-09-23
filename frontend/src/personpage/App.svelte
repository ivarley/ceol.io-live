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
  import LoggedTab from './LoggedTab.svelte'
  import LoginsTab from './LoginsTab.svelte'

  let { pageData, ctx = {} } = $props()

  const person = pageData.person
  const user = pageData.user
  const isUserProfile = pageData.is_user_profile
  const isSystemAdmin = pageData.is_system_admin
  const personId = person.id

  import { toast } from '../lib/index.js'
  import SectionList from './SectionList.svelte'
  import AccountSection from './AccountSection.svelte'

  const validTabs = ['profile', 'sessions', 'attended', 'tunes', 'logged', 'logins']

  // Initial tab from the URL (?tab=), exactly like the legacy DOMContentLoaded path
  // (activateTab(tabFromUrl, false) — no URL rewrite on load).
  const initialTab = (() => {
    const t = new URLSearchParams(window.location.search).get('tab')
    return t && validTabs.includes(t) ? t : 'profile'
  })()

  let activeTab = $state(initialTab)
  let attendedLoaded = $state(false)
  let tunesLoaded = $state(false)
  let loggedLoaded = $state(false)
  let loginsLoaded = $state(false)

  // Lazy-load bookkeeping for whichever tab is (or becomes) active.
  function noteActivated(tabId) {
    if (tabId === 'attended') attendedLoaded = true
    else if (tabId === 'tunes') tunesLoaded = true
    else if (tabId === 'logged') loggedLoaded = true
    else if (tabId === 'logins') loginsLoaded = true
  }
  noteActivated(initialTab)

  // The sections you can open from the profile. Profile itself is not in the list:
  // it is the page you are already on (spec 052 §B3). Logins only exists when the
  // person has a login account. domId keeps the legacy `#<name>-tab` hooks, which
  // CSS and the tests still name.
  const drilldowns = $derived.by(() => {
    const t = [
      { id: 'sessions', label: sessionsTabLabel, domId: 'sessions-tab',
        hint: 'Sessions they belong to' },
      { id: 'attended', label: attendedTabLabel, domId: 'attended-tab',
        hint: 'Nights they turned up' },
      { id: 'tunes', label: 'Tunebook', domId: 'tunes-tab',
        hint: 'What they know and are learning' },
      { id: 'logged', label: 'Logged', domId: 'logged-tab',
        hint: 'Tunes they put on a log' },
    ]
    if (user) t.push({ id: 'logins', label: 'Logins', domId: 'logins-tab',
                       hint: 'Recent sign-ins' })
    return isUserProfile
      ? t.map((x) => ({ ...x, hint: MY_HINTS[x.id] || x.hint }))
      : t
  })

  // On your own profile the same rows are about you, so they say so.
  const MY_HINTS = {
    sessions: 'Sessions you belong to',
    attended: 'Nights you turned up',
    tunes: 'What you know and are learning',
    logged: 'Tunes you put on a log',
    logins: 'Your recent sign-ins',
  }

  const drilldownLabel = $derived(
    drilldowns.find((d) => d.id === activeTab)?.label || ''
  )

  // Kit Tabs drives activeTab via bind:value; this handler adds the page's
  // ?tab= URL sync + lazy-load bookkeeping (also called by the breadcrumb).
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
    tunes: 'Tunebook',
    logged: 'Logged',
    logins: 'Logins',
  }
  const breadcrumbTabName = $derived(tabDisplayNames[activeTab] || null)

  const sessionsTabLabel = 'Sessions' // spec 034: was "My Sessions" on your own profile
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

<!-- One idiom, not two (spec 052 §B3).
     This page used to carry six tabs across the top AND a vertical Account list
     underneath, so the same screen offered two different kinds of menu. It is a
     vertical list now: your details, then the places you can go from here, then the
     account actions — all the same shape of row. That is also the only form iOS has
     for this screen, where a six-tab strip has no counterpart.

     The `?tab=` URLs are unchanged, so every existing link still lands where it did;
     what was a tab switch is now a drill-down, and each section renders in full on
     its own screen rather than being squeezed under a strip. -->
{#if activeTab === 'profile'}
  <SectionList
    sections={drilldowns}
    onOpen={(id) => activateTab(id)}
    heading={isUserProfile ? 'More about you' : 'More'} />

  {#if isUserProfile}
    <AccountSection isSystemAdmin={pageData.is_system_admin} personName={person.name} />
  {/if}
{:else}
  <!-- A drill-down: the way back, then the section's own title. -->
  <button type="button" class="section-back" id="section-back" onclick={() => activateTab('profile')}>
    <span aria-hidden="true">‹</span> {isUserProfile ? 'Profile' : person.name}
  </button>

  <h2 class="section-heading">{drilldownLabel}</h2>
{/if}

<!-- Every pane stays MOUNTED and is shown or hidden, exactly as it was under the
     tabs. Rendering only the open one inside an {#if} looked tidier and quietly
     undid the lazy-load contract: leaving a section destroyed its component, so
     coming back refetched. The panes keep their legacy ids and Bootstrap classes,
     which CSS and the tests still name. -->
<div class="tab-content" id="profileTabContent">
  <div
    class="tab-pane fade"
    class:show={activeTab === 'profile'}
    class:active={activeTab === 'profile'}
    id="profile"
    role="tabpanel">
    <ProfileTab
      {person}
      {user}
      {isUserProfile}
      {personId}
      timezoneOptions={pageData.timezone_options || []}
      canonicalInstruments={ctx.canonicalInstruments || []} />
  </div>

  <div
    class="tab-pane fade"
    class:show={activeTab === 'sessions'}
    class:active={activeTab === 'sessions'}
    id="sessions"
    role="tabpanel">
    <SessionsTab
      initialSessions={pageData.sessions || []}
      {person}
      {personId}
      {isUserProfile}
      {isSystemAdmin} />
  </div>

  <div
    class="tab-pane fade"
    class:show={activeTab === 'attended'}
    class:active={activeTab === 'attended'}
    id="attended"
    role="tabpanel">
    <AttendedTab {personId} load={attendedLoaded} />
  </div>

  <div
    class="tab-pane fade"
    class:show={activeTab === 'tunes'}
    class:active={activeTab === 'tunes'}
    id="tunes"
    role="tabpanel">
    <TunesStatsTab {personId} load={tunesLoaded} {isUserProfile} />
  </div>

  <div
    class="tab-pane fade"
    class:show={activeTab === 'logged'}
    class:active={activeTab === 'logged'}
    id="logged"
    role="tabpanel">
    <LoggedTab {personId} load={loggedLoaded} />
  </div>

  {#if user}
    <div
      class="tab-pane fade"
      class:show={activeTab === 'logins'}
      class:active={activeTab === 'logins'}
      id="logins"
      role="tabpanel">
      <LoginsTab {personId} load={loginsLoaded} />
    </div>
  {/if}
</div>

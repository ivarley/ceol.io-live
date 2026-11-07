<script>
  // i18n-converted
  // The person-details page view (spec 035 Step 5a) — ported behavior-for-behavior
  // from the legacy 1,350-line inline script in templates/person_details.html.
  // Serves both flavors: /me (user profile) and /admin/people/<id> (system admin).
  // The shell keeps the whole legacy <style> blocks; this component emits the same
  // class names/ids, so the look is unchanged. showMessage comes from base.html.
  import { untrack } from 'svelte'
  import ProfileTab from './ProfileTab.svelte'
  import SessionsTab from './SessionsTab.svelte'

  let { pageData, ctx = {} } = $props()

  const person = pageData.person
  const user = pageData.user
  const isUserProfile = pageData.is_user_profile
  const isSystemAdmin = pageData.is_system_admin
  const personId = person.id
  const sessions = pageData.sessions || []

  import { Tabs, toast, t, tc } from '../lib/index.js'
  import AccountSection from './AccountSection.svelte'

  // On /me the sections, and the tabs before them, are gone (spec 052 §B1). Four of
  // the five were the same data with a different frame around it, and the fifth was
  // not earning its place:
  //   Sessions  -> duplicated /sessions; its one unique control, leaving a session,
  //                moved to that session's own role sheet
  //   Attended  -> the Logs tab's "Attended" filter, on the session it is about
  //   Tunebook  -> My Tunes with an added-date filter, which is what it was
  //   Logged    -> deleted; nobody used it
  // What is left is your profile and the account actions, which is what a Me screen
  // is for.
  //
  // The ADMIN flavour is a different page: a system admin looking at somebody else
  // has no /sessions of theirs to go to, so it keeps a Sessions tab (read-only; the
  // role controls stay on each session's admin People tab). It is a web-only admin
  // page, like /admin/sessions/<path>, which is tabbed for the same reason.
  const VALID_TABS = ['profile', 'sessions']
  const initialTab = (() => {
    if (isUserProfile) return 'profile'
    const q = new URLSearchParams(window.location.search).get('tab')
    return q && VALID_TABS.includes(q) ? q : 'profile'
  })()
  let activeTab = $state(initialTab)

  const adminTabs = [
    { id: 'profile', label: t('Profile'), domId: 'profile-tab' },
    { id: 'sessions', label: t('Sessions'), count: sessions.length, domId: 'sessions-tab' },
  ]

  // Kit Tabs drives activeTab via bind:value; this keeps ?tab= in step so the
  // Sessions tab can be linked to and survives a reload.
  function onTabChange(id) {
    activeTab = id
    const url = new URL(window.location)
    if (id === 'profile') url.searchParams.delete('tab')
    else url.searchParams.set('tab', id)
    window.history.replaceState({}, '', url)
  }

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

<!-- No "Profile: Ian Varley" heading (spec 052 §B12). It spent 36px of a 664px
     screen telling you your own name, on the one page where you already know it,
     and the tab bar underneath already says Me. The identity header inside
     ProfileTab carries the name, and does it in the shape iOS uses at the top of
     Settings. The admin flavour keeps its breadcrumb, which is navigation rather
     than decoration. -->
{#if !isUserProfile}
  <!-- Admin Breadcrumb Navigation. On the Sessions tab the person's name becomes
       the way back and the tab's name ends the trail, as /admin/sessions does. -->
  <nav class="admin-breadcrumb" aria-label={t('breadcrumb')}>
    <a href="/admin" class="breadcrumb-item">{tc('area', 'Admin')}</a>
    <span class="breadcrumb-separator">{'>>'}</span>
    <a href="/admin/people" class="breadcrumb-item">{t('People')}</a>
    <span class="breadcrumb-separator">{'>>'}</span>
    {#if activeTab === 'sessions'}
      <span id="breadcrumb-person-name"><a
          href="?"
          class="breadcrumb-item"
          onclick={(e) => {
            e.preventDefault()
            onTabChange('profile')
          }}>{person.name}</a></span>
      <span id="breadcrumb-tab-separator" class="breadcrumb-separator">{'>>'}</span>
      <span id="breadcrumb-tab-name" class="breadcrumb-current">{t('Sessions')}</span>
    {:else}
      <span id="breadcrumb-person-name" class="breadcrumb-current">{person.name}</span>
      <span id="breadcrumb-tab-separator" class="breadcrumb-separator" style="display: none;">{'>>'}</span>
      <span id="breadcrumb-tab-name" class="breadcrumb-current" style="display: none;"></span>
    {/if}
  </nav>

  <nav class="person-admin-tabs-nav">
    <Tabs
      tabs={adminTabs}
      value={activeTab}
      onValueChange={onTabChange}
      styled={false}
      listId="person-admin-tabs"
      listClass="nav nav-tabs"
      tabClass="nav-link" />
  </nav>
{/if}

<!-- One idiom, not two (spec 052 §B3).
     /me used to carry six tabs across the top AND a vertical Account list
     underneath, so the same screen offered two different kinds of menu. It is a
     vertical list now: your details, then the places you can go from here, then the
     account actions — all the same shape of row. That is also the only form iOS has
     for this screen, where a six-tab strip has no counterpart.

     Both panes stay mounted and are shown or hidden, so the profile's edit state
     survives a look at the Sessions tab. -->
<div class="tab-content" id="profileTabContent">
  <div class="tab-pane fade {activeTab === 'profile' ? 'show active' : ''}" id="profile" role="tabpanel">
    <ProfileTab
      {person}
      {user}
      {isUserProfile}
      {personId}
      timezoneOptions={pageData.timezone_options || []}
      canonicalInstruments={ctx.canonicalInstruments || []} />
  </div>
  {#if !isUserProfile}
    <div class="tab-pane fade {activeTab === 'sessions' ? 'show active' : ''}" id="sessions" role="tabpanel">
      <SessionsTab {sessions} />
    </div>
  {/if}
</div>

{#if isUserProfile}
  <AccountSection isSystemAdmin={pageData.is_system_admin} personName={person.name} userEmail={user?.user_email || ''} />
{/if}

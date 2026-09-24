<script>
  // The person-details page view (spec 035 Step 5a) — ported behavior-for-behavior
  // from the legacy 1,350-line inline script in templates/person_details.html.
  // Serves both flavors: /me (user profile) and /admin/people/<id> (system admin).
  // The shell keeps the whole legacy <style> blocks; this component emits the same
  // class names/ids, so the look is unchanged. showMessage comes from base.html.
  import { untrack } from 'svelte'
  import ProfileTab from './ProfileTab.svelte'

  let { pageData, ctx = {} } = $props()

  const person = pageData.person
  const user = pageData.user
  const isUserProfile = pageData.is_user_profile
  const isSystemAdmin = pageData.is_system_admin
  const personId = person.id

  import { toast } from '../lib/index.js'
  import AccountSection from './AccountSection.svelte'

  // Sections, and the tabs before them, are gone (spec 052 §B1). Four of the five
  // were the same data with a different frame around it, and the fifth was not
  // earning its place:
  //   Sessions  -> duplicated /sessions; its one unique control, leaving a session,
  //                moved to that session's own role sheet
  //   Attended  -> the Logs tab's "Attended" filter, on the session it is about
  //   Tunebook  -> My Tunes with an added-date filter, which is what it was
  //   Logged    -> deleted; nobody used it
  // What is left is your profile and the account actions, which is what a Me screen
  // is for.

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
    <!-- The trailing " >> <tab name>" is gone with the tabs: the page has one level
         now, so the person's name is the end of the trail. The empty spans stay
         because admin CSS and selectors still name them. -->
    <span id="breadcrumb-person-name" class="breadcrumb-current">{person.name}</span>
    <span id="breadcrumb-tab-separator" class="breadcrumb-separator" style="display: none;">&gt;&gt;</span>
    <span id="breadcrumb-tab-name" class="breadcrumb-current" style="display: none;"></span>
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
<div class="tab-content" id="profileTabContent">
  <div class="tab-pane fade show active" id="profile" role="tabpanel">
    <ProfileTab
      {person}
      {user}
      {isUserProfile}
      {personId}
      timezoneOptions={pageData.timezone_options || []}
      canonicalInstruments={ctx.canonicalInstruments || []} />
  </div>
</div>

{#if isUserProfile}
  <AccountSection isSystemAdmin={pageData.is_system_admin} personName={person.name} />
{/if}

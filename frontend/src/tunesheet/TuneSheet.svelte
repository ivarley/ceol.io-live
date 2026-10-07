<script>
  // i18n-converted
  // The app-wide tune-detail drawer (spec 035 Step 3, derived-mode refactor).
  //
  // ONE payload feeds it — GET /api/tunes/<id>/detail (optionally ?session=
  // &instance=) — and the drawer DERIVES its own variant from that payload
  // instead of trusting call sites to hand-assemble configs:
  //
  //   fact                                  gates
  //   ------------------------------------  ------------------------------------
  //   viewer.logged_in                      status seg / Add, heard count,
  //                                         Generate Notation (login-gated API)
  //   person_tune_status.on_list            the full my-tunes variant (notes,
  //                                         name-alias config, My-sessions
  //                                         history scope, remove link)
  //   scope.session (+ scope.instance)      session/instance wording, session
  //                                         stats, session config fields
  //   scope.admin && viewer.is_admin        admin variant (name editing,
  //                                         repertoire stats)
  //   viewer.is_session_admin               "Remove From Session"
  //
  // The internal `mode` string (my_tunes / session / session_instance / admin /
  // global) is a compat detail derived from those facts — it picks field sets,
  // save endpoints, and wording; nothing outside this file passes it in.
  // show({ tuneId, scope?, ...callbacks }) is the new API; old-style configs
  // (context + apiEndpoint + additionalData, from the quarantined pill logger
  // template, admin_tunes.html and common_tunes.html) are mapped by
  // normalizeShowConfig and keep working.
  //
  // The DOM contract is unchanged — #tune-detail-modal / .modal-dialog /
  // #tune-detail-content and every legacy section class — because
  // static/css/tune_detail_modal.css, the live shell's dark scoping and the
  // e2e suite all select on it. For the same reason this component has NO
  // <style> block: Svelte scoping would detach it from the shared stylesheet.
  import { onMount, untrack } from 'svelte'
  import {
    Chevron,
    Chip,
    Dialog,
    LoadError,
    Seg,
    ServerError,
    SessionPicker,
    Tabs,
    TagInput,
    toast,
    toastFailure,
    t,
    tn,
    tuneTypeName,
    currentLang,
    instrumentName,
  } from '../lib/index.js'
  import {
    MUSICAL_KEYS,
    OTHER_SESSION,
    normalizeShowConfig,
    detailUrl,
    getDisplayName,
    getAkaName,
    historyScopeOptions,
    isEditableScope,
    historyUrl,
    instancePositions,
    initialSessionScope,
    playedWithScopeOptions,
    tuneHref,
    updateUrlWithTune,
    removeUrlTuneParam,
    getInstrumentData,
    getModalLearnStatus,
    setInstrumentOverrides,
    resolveInstStatus,
    rollupStatus,
    offlinePayload,
    personTunePayload,
    theSessionUrl,
    abcToolsUrl,
    notationInfo,
    notationDisplay,
    submitMyTunesOp,
    normalizeTag,
    normalizeTags,
    tagsEqual,
  } from './logic.js'
  import { STATUSES, STATUS_LABELS } from '../mylist.js'
  import SettingChooser from './SettingChooser.svelte'

  // The tune type as the server sent it in English (the pill's CSS sets its case), the
  // interface word in Irish.
  const typeLabel = (type) => (currentLang() === 'ga' ? tuneTypeName(type) : type)

  // ---- modal state -----------------------------------------------------------
  let visible = $state(false)
  let showCls = $state(false)
  let phase = $state('loading') // 'loading' | 'error' | 'ready'
  let errorMsg = $state('')
  // A failed load that another try might fix gets a Retry (re-runs the last show());
  // a definitive answer (a merged-away tunebook entry) doesn't.
  let errorRetry = $state(null)
  let adding = $state(false) // the not-on-list Add button, while its op is in flight
  let myVersionLoading = $state(false)
  let mySessionsState = $state('idle') // idle | loading — the "different session" list
  let overridesError = $state(false) // the instance form's overrides failed to load
  let config = $state(null) // normalized show() config {tuneId, ptid, scope, callbacks, hints}
  let viewer = $state(null) // payload viewer block {logged_in, is_admin, is_session_admin}
  // Per-tune permission to pull this tune's notation from thesession.org, minted by
  // the detail payload for signed-out viewers when nothing is cached (spec 052 §B21).
  // Null for everyone else: a signed-in viewer's session is their authority, and a
  // tune we already hold notation for has nothing to fetch.
  let notationToken = $state(null)
  let tune = $state(null) // payload session_tune block (mutated optimistically)
  let mergedFrom = $state(null) // healed merged-tune permalink (spec 030)
  // The live load failed and the drawer is showing the offline cache's copy:
  // say so, so a stale copy never passes for what the server holds.
  let savedCopy = $state(false)
  let modalShowTime = 0 // scrim-click guard (500ms)
  let hideTimer = null

  // Reset on every show(): the per-instrument roll-up must not stay expanded
  // when the drawer moves to another tune (or reopens).
  let piExpanded = $state(false)
  let isConfigVisible = $state(false)
  let activeTab = $state('details')
  let activeSess = $state(null) // window.activeSession snapshot at render time

  // ---- the two forms (spec 037) ---------------------------------------------------
  //
  // These used to be ONE polymorphic form: in a session scope it stopped showing your
  // alias/setting and showed the session's instead, so your own configuration of a
  // tune became unreachable exactly when you might want to compare it. They are now
  // independent, and BOTH can be open at once — different owner, different table,
  // different endpoint, different permissions. Hence a Save per form, never a
  // drawer-wide one: a single button committing both would be lying about what it does.

  // Personal: person_tune. Rendered on EVERY surface for a tune on my list.
  let pcFields = $state({ name_alias: '', key: '', notes: '', tags: [] })
  let pcOriginals = $state({})
  let pcSaveState = $state('idle') // idle | saving | saved | error (the Configure Save button)
  // Notes & tags now live in an always-visible panel that auto-saves on blur —
  // this drives the small "Saving…/Saved" flash for that (separate from Configure).
  let autoSaveState = $state('idle') // idle | saving | saved | error
  let pcFetchState = $state('idle') // idle | loading | ok | warn | err (Generate Notation)

  // Session: session_tune when the droplist is on 'general', else that instance's
  // session_instance_tune. One form; the droplist picks its target, so you never see
  // both layers editable at once. The form itself is collapsed until asked for — the
  // tab's job is mostly to TELL you things (how often, in which sets), and editing is
  // the rarer errand.
  // 'general' | String(session_instance_id) | 'member' | 'all'. The ONE scope control:
  // which plays of this tune am I looking at — and, when the answer is a session or one of
  // its instances, what am I editing.
  let scopeId = $state('all')
  // The last value the droplist was really ON. The "At a different session ..." row is an
  // errand, not a target: picking it opens the picker and the select must snap back, or a
  // cancelled pick strands it on a row that means nothing. Plain variable, not $state —
  // it exists only to be read inside the change handler.
  let lastRealScope = 'all'
  // "While I was there" is a FILTER, not a scope — it ANDs on top of whatever is selected,
  // so "nights at Mueller I was actually there for" is expressible. It wasn't when
  // attended was one of a set of mutually-exclusive Seg options.
  let attendedOnly = $state(false)
  // The transient "You attended" beside the filter, shown by tapping a row's ✓.
  let attendedHint = $state(false)
  let attendedHintTimer = null
  let sessFields = $state({ alias: '', key: '' })
  let sessOriginals = $state({})
  let sessSaveState = $state('idle')
  let sessFormOpen = $state(false)

  // Details: the same session_tune row the History form writes at 'general' scope, but
  // pinned to that layer regardless of where the droplist points. It needs its own state
  // rather than sharing sessFields, or selecting a date in History would silently repoint
  // the fields sitting on Details. Not collapsed behind a link either — the tab exists
  // BECAUSE that link was undiscoverable.
  let dcFields = $state({ alias: '', key: '' })
  let dcOriginals = $state({})
  let dcSaveState = $state('idle')

  // "At a different session ..." — re-scope the drawer to another session I'm a member
  // of, to see what THEY do with this tune.
  let sessionPickerOpen = $state(false)
  let mySessions = $state([])

  // Admin: the canonical tune name. Untouched by 037 — spec 036 reworks admin.
  let adminFields = $state({ name: '' })
  let adminOriginals = $state({})
  let adminSaveState = $state('idle')

  // The learn status auto-saves on tap (no form), but setTunebookStatus needs to know
  // what it was in order to no-op and to revert.
  let learnStatusOriginal = $state('')

  // Offline gates the personal form's three override fields (Notes stays live, since
  // set_notes is an offline op).
  let onlineNow = $state(typeof navigator === 'undefined' ? true : navigator.onLine !== false)
  onMount(() => {
    const sync = () => (onlineNow = navigator.onLine !== false)
    sync()
    window.addEventListener('online', sync)
    window.addEventListener('offline', sync)
    return () => {
      window.removeEventListener('online', sync)
      window.removeEventListener('offline', sync)
    }
  })

  let refreshState = $state('idle') // idle | loading | ok | err
  let statusSaving = $state(false)
  let pendingHeard = $state(0)

  // ABC notation display state machine
  let notationMode = $state('dots') // 'dots' | 'abc'
  let notationSize = $state('incipit') // 'incipit' | 'full'
  // The staff always draws what was actually PLAYED (instance -> session -> mine).
  // When that isn't my setting, a note under it offers to swap to my version; this
  // holds the fetched notation for that view. Purely a view toggle — saves nothing.
  let myNotation = $state(null) // {setting_id, abc, incipit_abc, image, incipit_image}
  let showingMyVersion = $state(false)

  // History / Played With: fetched lazily and asynchronously, cached for this modal open.
  // Value: {status: 'loading'|'ready'|'error'|'none'|'offline', data}. History is keyed by
  // (scope + attended filter) — flipping the filter asks a different question and must not
  // read the cached answer to the other one.
  let historyCache = $state({})
  let playedWithScope = $state(null)
  let playedWithCache = $state({})

  // ---- mode derivation ----------------------------------------------------------
  const scope = $derived(config?.scope || null)
  const loggedIn = $derived(!!viewer?.logged_in)
  const isAdminView = $derived(!!(scope?.admin && viewer?.is_admin))
  const pts = $derived(tune?.person_tune_status || null)
  const onList = $derived(!!pts?.on_list)
  const isSessionAdmin = $derived(!!viewer?.is_session_admin)

  // The internal variant, derived — never passed in by a call site.
  const mode = $derived.by(() => {
    if (isAdminView) return 'admin'
    if (scope?.instance != null && scope?.session) return 'session_instance'
    if (scope?.session) return 'session'
    if (loggedIn && onList) return 'my_tunes'
    return 'global'
  })

  // ---- derived view state ---------------------------------------------------------
  const displayName = $derived(tune ? getDisplayName(tune, mode) : '')
  // "aka Michael Creamer's" — the next name down the chain that is meaningfully a
  // DIFFERENT name, not just a different spelling. Usually null.
  const akaName = $derived(tune ? getAkaName(tune, mode) : null)
  const headerTuneType = $derived((tune && tune.tune_type) || config?.tuneType || '')

  // ---- the Session tab (spec 037) ---------------------------------------------------
  const sessionScope = $derived(tune?.session_scope || null)
  const inSession = $derived(!!sessionScope)
  const playedInstances = $derived(sessionScope?.played_instances || [])
  const scopeOptions = $derived(
    historyScopeOptions(playedInstances, sessionScope?.session_name, { inSession, loggedIn })
  )
  // Only a session's own row or one of its instances can be edited: "what we call it" is a
  // fact about a session or a performance, and means nothing across all of them.
  const editableScope = $derived(isEditableScope(scopeId))
  const editingInstance = $derived(editableScope && scopeId !== 'general')

  // "Set 3, tune 2" — where the tune came round that night, each linking into the logger
  // at that exact record. Usually one; a tune played twice that night has two.
  const positions = $derived(
    editingInstance && tune
      ? instancePositions(playedInstances, scopeId, sessionScope.path, tune.tune_id)
      : []
  )

  // Who may write which layer. The session's own alias/setting/key is the session
  // making a canonical statement about its repertoire (admins); a specific instance is
  // a record of what happened in a room the member was in (any member). Neither applies
  // to a wide lens, hence the editableScope gate.
  const canEditSessionLayer = $derived(
    !editableScope
      ? false
      : editingInstance
        ? !!sessionScope?.can_edit_instance
        : !!sessionScope?.can_edit_session
  )
  // Details edits the session's own row and only ever that, so its gate is the session
  // gate alone — no scope in it.
  const canEditSessionGeneral = $derived(inSession && !!sessionScope?.can_edit_session)
  // Un-enrolling only ever means "a tune that was never actually played here". With
  // plays present the link is simply absent — no explanation, it just isn't an option.
  const canRemoveFromSession = $derived(!!sessionScope?.can_remove_from_session)

  // The "while I was there" filter is meaningless in the context of a session that
  // doesn't track attendance (spec 039) — so it hides when the scope IS that session.
  // The wide lenses ('member'/'all') keep it: they still count attendance at OTHER
  // sessions that do track it. (The counts themselves exclude off-sessions app-wide.)
  const showAttendedFilter = $derived(scopeId !== 'general' || sessionScope?.track_attendance !== false)

  // A one-line count above the list. The payload's counts don't know about the "while I
  // was there" filter, so the line steps aside when the filter is on — the list is then
  // the honest answer.
  const summaryLine = $derived.by(() => {
    if (!tune || attendedOnly || editingInstance) return ''
    if (scopeId === 'general')
      return tn(tune.times_played || 0, 'Played {n} time at this session', 'Played {n} times at this session')
    if (scopeId === 'member') return tn(myPlayCount, 'Played {n} time at my sessions', 'Played {n} times at my sessions')
    if (scopeId === 'all')
      return tn(tune.global_play_count || 0, 'Played {n} time at all sessions', 'Played {n} times at all sessions')
    return ''
  })

  // The empty option in a key select isn't "blank", it's "inherit" — so it names what
  // it would fall back to. An instance falls back to the session's key; the session
  // falls back to the setting's own key.
  const inheritKeyLabel = $derived.by(() => {
    if (!tune) return t('(not specified)')
    if (editingInstance) {
      const fallback = tune.key || tune.setting_key
      return fallback ? t('(as usual — {key})', { key: fallback }) : t('(as usual)')
    }
    return settingKeyLabel
  })

  // Details is always the session's own layer, so its inherit option always names the
  // setting's key — never "as usual", which is an instance's fallback.
  const settingKeyLabel = $derived(
    tune?.setting_key ? t("(the setting's key — {key})", { key: tune.setting_key }) : t('(not specified)')
  )
  const dcInheritKeyLabel = $derived(settingKeyLabel)

  const rollup = $derived(tune ? rollupStatus(tune) : 'want to learn')
  const instruments = $derived(tune ? getInstrumentData(tune).instruments : [])
  const multiInstrument = $derived(instruments && instruments.length >= 2)

  const heardVisible = $derived.by(() => {
    if (!tune || mode === 'admin' || !loggedIn) return false
    if (!pts || !pts.person_tune_id) return false
    return !!pts.learn_status && pts.learn_status !== 'learned'
  })
  const heardCountView = $derived((pts && pts.heard_count) || 0)
  // Spec 033 lenses. The detail payload carries them on the tune block for any
  // logged-in viewer; on-list tunes also carry them on person_tune_status. The
  // session_play_count fallback covers stale offline snapshots (deprecated alias).
  const myPlayCount = $derived(
    tune?.member_play_count ?? pts?.member_play_count ?? pts?.session_play_count ?? 0
  )
  const myAttendedCount = $derived(tune?.attended_play_count ?? pts?.attended_play_count ?? 0)
  const hasMyCounts = $derived(
    loggedIn &&
      (tune?.member_play_count != null ||
        pts?.member_play_count != null ||
        pts?.session_play_count != null)
  )

  // The setting the staff is actually drawn from. Precedence is deliberately the
  // OPPOSITE of the name chain: a name is a label (most personal wins) but a setting
  // is a record of what got played, so the most specific factual layer wins.
  const playedSettingId = $derived(
    (tune && (tune.setting_override || tune.setting_id)) || null
  )
  const mySettingId = $derived((pts && pts.setting_id) || null)
  const settingMismatch = $derived(
    inSession && onList && !!mySettingId && !!playedSettingId && mySettingId !== playedSettingId
  )
  const sessionLabel = $derived(sessionScope?.session_name || t('this session'))

  // What the notation section renders from: the played setting, or — while the
  // mismatch note's toggle is on — the viewer's own setting.
  // (My version is mine alone: a night's own setting must not ride along with it.)
  const notationSource = $derived(
    showingMyVersion && myNotation ? { ...tune, ...myNotation, setting_override: null } : tune
  )
  const notation = $derived(notationSource ? notationInfo(notationSource) : null)
  const notationView = $derived(
    notationSource ? notationDisplay(notationSource, notationMode, notationSize) : null
  )
  const thesessionLink = $derived(notationSource ? theSessionUrl(notationSource) : '')
  const abctoolsLink = $derived(notationSource ? abcToolsUrl(notationSource) : '')

  const hasCachedNotation = $derived(
    !!(tune && (tune.abc || tune.incipit_abc || tune.image || tune.incipit_image))
  )
  // Generate Notation shows for a signed-in viewer, and for a signed-out one holding
  // a token for this tune (spec 052 §B21). Both are payload-derived, so a call site
  // can never forget the flag.
  const canGenerateNotation = $derived(!!tune && (loggedIn || !!notationToken))

  // The status segs (overall and per-instrument) speak the app's one status
  // vocabulary — see STATUS_LABELS in mylist.js.
  // STATUS_LABELS is English (mylist.js); each word goes through a literal t() here.
  const STATUS_WORDS = {
    'want to learn': () => t('To Learn'),
    learning: () => t('Learning'),
    learned: () => t('Learned'),
  }
  const STATUS_OPTIONS = STATUSES.map((id) => ({ id, label: STATUS_WORDS[id] ? STATUS_WORDS[id]() : STATUS_LABELS[id] }))

  // Offline, the three override fields go read-only and Notes stays live — a phone in
  // a pub basement is exactly where someone types a note about a tune, and set_notes
  // is already an offline op. So a Save while offline can only ever be committing
  // notes, and it goes through the queue instead of the PUT.
  // Tracked directly rather than via svelte/reactivity/window, whose barrel drags in
  // DevicePixelRatio -> matchMedia, which jsdom doesn't have.
  const isOffline = $derived(!onlineNow)

  // The Configure Save button covers ONLY the fields that still batch-save behind it
  // (name alias / key; the setting saves from its chooser). Notes and tags moved to the always-visible panel and
  // auto-save on blur, so they no longer make this dirty.
  const pcDirty = $derived.by(() => {
    if (!tune || !onList) return false
    return (
      pcFields.name_alias !== pcOriginals.name_alias ||
      pcFields.key !== pcOriginals.key
    )
  })
  const pcSaveDisabled = $derived(!pcDirty || pcSaveState !== 'idle')
  const autoSaveLabel = $derived(
    autoSaveState === 'saving' ? t('Saving…') : autoSaveState === 'saved' ? t('Saved ✓') : autoSaveState === 'error' ? t("Couldn't save") : ''
  )

  const sessDirty = $derived.by(() => {
    if (!tune || !inSession) return false
    return (
      sessFields.alias !== sessOriginals.alias ||
      sessFields.key !== sessOriginals.key
    )
  })
  const sessSaveDisabled = $derived(!sessDirty || sessSaveState !== 'idle')

  const dcDirty = $derived.by(() => {
    if (!tune || !inSession) return false
    return (
      dcFields.alias !== dcOriginals.alias ||
      dcFields.key !== dcOriginals.key
    )
  })
  const dcSaveDisabled = $derived(!dcDirty || dcSaveState !== 'idle')

  const adminDirty = $derived(!!tune && adminFields.name !== adminOriginals.name)
  const adminSaveDisabled = $derived(!adminDirty || adminSaveState !== 'idle')

  const saveLabelFor = (s) =>
    s === 'saving' ? t('Saving...') : s === 'saved' ? t('Saved!') : s === 'error' ? t('Error') : t('Save')
  const saveBgFor = (s) => (s === 'saved' ? '#28a745' : s === 'error' ? '#dc3545' : '')

  const playedWithOptions = $derived(playedWithScopeOptions(mode, scope, loggedIn))
  const playedWithScopeKey = $derived(playedWithScope ?? playedWithOptions[0].key)
  const playedWithState = $derived(playedWithCache[playedWithScopeKey] || { status: 'loading' })

  // History is cached per (scope + filter): flipping the filter is a different question,
  // so it must not read a cached answer to the other one.
  const historyKey = $derived(`${scopeId}|${attendedOnly ? 'att' : 'any'}`)
  const historyState = $derived(historyCache[historyKey] || { status: 'loading' })

  // Tabs. "My List" — the personal status / notes / tags / configure — is the leftmost
  // tab and the default whenever it applies (a logged-in, non-admin viewer, on any
  // surface). History absorbed the old Session tab (spec 037). Panes all stay mounted
  // (CSS shows the active one), so History still loads eagerly on open regardless.
  //
  // "Details" is the old Stats tab, renamed and moved up to sit beside My List: what this
  // tune IS at this session (its name, setting and key here) on top of the facts about the
  // tune itself. 037 accepted that History didn't advertise being where you edit those;
  // in practice nobody found it, so the session layer gets a tab that says so. No fifth
  // tab — four is already the mobile ceiling.
  const showMyList = $derived(mode !== 'admin' && loggedIn)
  const tabList = $derived([
    ...(showMyList ? [{ id: 'my-list', label: t('My List') }] : []),
    { id: 'details', label: t('Details') },
    { id: 'history', label: t('History') },
    { id: 'played-with', label: t('Played With') },
  ])
  const defaultTab = $derived(showMyList ? 'my-list' : 'history')

  // ---- form seeding -------------------------------------------------------------

  // Personal config: the SAME fields on every surface. A session never replaces them.
  function seedPersonalForm() {
    pcOriginals = {
      name_alias: (pts && pts.name_alias) || '',
      setting_id: (pts && pts.setting_id) || '',
      key: (pts && pts.key) || '',
      notes: (pts && pts.notes) || '',
      tags: (pts && pts.tags) || [],
    }
    pcFields = {
      name_alias: pcOriginals.name_alias,
      key: pcOriginals.key,
      notes: pcOriginals.notes,
      // Copy the array — TagInput reassigns pcFields.tags, and pcOriginals must
      // keep the pristine snapshot for the dirty-check.
      tags: [...pcOriginals.tags],
    }
    pcSaveState = 'idle'
    pcFetchState = 'idle'
  }

  // Session config: one form, whose TARGET is whatever the droplist points at.
  // 'general' reads session_tune; an instance reads that session_instance_tune.
  function seedSessionForm() {
    if (!inSession) return
    if (editingInstance) {
      // Instance rows only exist for the instance in scope, so the payload can only
      // describe THAT one. Selecting a different instance loads it (loadInstance).
      const isScoped = String(sessionScope.instance ?? '') === String(scopeId)
      sessOriginals = {
        alias: (isScoped && tune.name) || '',
        setting_id: (isScoped && tune.setting_override) || '',
        key: (isScoped && tune.key_override) || '',
      }
    } else {
      sessOriginals = {
        alias: tune.alias || '',
        setting_id: tune.setting_id || '',
        key: tune.key || '',
      }
    }
    sessFields = {
      alias: sessOriginals.alias,
      key: sessOriginals.key,
    }
    sessSaveState = 'idle'
  }

  // Details config: always the session's own row (session_tune), never an instance —
  // which is exactly what makes it safe to sit on a tab with no scope control.
  function seedDetailsForm() {
    if (!inSession) return
    dcOriginals = {
      alias: tune.alias || '',
      setting_id: tune.setting_id || '',
      key: tune.key || '',
    }
    dcFields = {
      alias: dcOriginals.alias,
      key: dcOriginals.key,
    }
    dcSaveState = 'idle'
  }

  function seedAdminForm() {
    adminOriginals = { name: tune.tune_name || '' }
    adminFields = { name: adminOriginals.name }
    adminSaveState = 'idle'
  }

  // ---- payload application --------------------------------------------------------

  // (Re)apply a full payload and reset the per-render section state (tabs back
  // to Stats unless asked to keep one, notation back to initial, configure
  // collapsed except admin, fields re-seeded).
  function applyPayload(data, opts = {}) {
    viewer = data.viewer || viewer || { logged_in: false, is_admin: false, is_session_admin: false }
    notationToken = data.notation_token || null
    tune = data.session_tune
    mergedFrom = null
    savedCopy = false

    learnStatusOriginal = (tune.person_tune_status && tune.person_tune_status.learn_status) || ''
    // Where the droplist lands: the instance the drawer was opened in (the live logger),
    // else ?siid= / ?date=, else the session in general — and with no session in scope at
    // all, the widest lens the viewer is entitled to.
    scopeId = tune.session_scope
      ? initialSessionScope(
          tune.session_scope.played_instances,
          tune.session_scope.instance,
          typeof window !== 'undefined' ? window.location.search : ''
        )
      : viewer.logged_in
        ? 'member'
        : 'all'
    lastRealScope = scopeId
    attendedOnly = false
    sessFormOpen = false
    seedPersonalForm()
    seedSessionForm()
    seedDetailsForm()
    seedAdminForm()

    refreshState = 'idle'
    statusSaving = false
    myNotation = null
    showingMyVersion = false
    // Personal config starts collapsed; admin's canonical-name editor is always open.
    isConfigVisible = mode === 'admin'
    // Default tab is My List when it applies (logged-in, non-admin), else History.
    activeTab = opts.keepTab || config.initialTab || defaultTab
    // History loads eagerly so its pane is ready the instant that tab is opened, even
    // though the drawer now usually lands on My List.
    loadHistory()
    if (activeTab === 'played-with') loadPlayedWith()
    // An explicit played-with scope choice survives a re-apply only if the (possibly
    // changed) mode still offers it. (History's scope is the droplist, reset above.)
    if (playedWithScope != null && !playedWithScopeOptions(mode, scope, loggedIn).some((o) => o.key === playedWithScope))
      playedWithScope = null
    const info = notationInfo(data.session_tune)
    notationMode = info.initialMode
    notationSize = 'incipit'
    activeSess = window.activeSession || null
    phase = 'ready'
    syncPtidUrl()
  }

  // On the my-tunes page the URL contract is ?ptid=<person_tune_id>. A drawer
  // that arrived at the my-tunes variant without one (chaining, add-upgrade)
  // learns it from the payload and fixes the URL.
  function syncPtidUrl() {
    if (mode !== 'my_tunes' || config.ptid || !pts?.person_tune_id) return
    if (!window.location.pathname.includes('/my-tunes')) return
    config.ptid = pts.person_tune_id
    updateUrlWithTune(config.ptid, 'my_tunes')
  }

  function showErr(message, retry = null) {
    errorMsg = message
    errorRetry = retry
    phase = 'error'
  }


  // Offline fallback: derive the payload from the locally-cached bundle +
  // not-yet-synced ops (offlinePayload synthesizes the viewer/on-list facts) so
  // the drawer works without a connection.
  function renderTuneFromOffline(cfg, errMsg) {
    const fail = () => showErr(errMsg || t("Couldn't load this tune."), () => show(cfg))
    if (!window.CeolOffline || !cfg.tuneId) {
      fail()
      return
    }
    const pending =
      window.MyTunesOffline && window.MyTunesOffline.pending
        ? window.MyTunesOffline.pending()
        : Promise.resolve([])
    Promise.all([window.CeolOffline.getTune(cfg.tuneId), pending])
      .then(([cached, ops]) => {
        if (!cached) {
          fail()
          return
        }
        applyPayload(offlinePayload(cached, ops, cfg.tuneId))
        savedCopy = true
      })
      .catch(fail)
  }

  // ---- public API (wired to window.TuneDetailModal by main.js) ------------------

  export function show(rawCfg) {
    const cfg = normalizeShowConfig(rawCfg)
    config = cfg
    chooserOpen = false
    errorRetry = null
    adding = false
    mySessionsState = 'idle'
    overridesError = false
    historyCache = {}
    playedWithCache = {}
    playedWithScope = null
    piExpanded = !!cfg.expandInstrumentStatus
    pendingHeard = 0
    mergedFrom = null

    // URL param: the my-tunes page deep-links by ptid; everything else by tune id
    // (session/admin pages get path-based URLs inside updateUrlWithTune).
    if (cfg.ptid && window.location.pathname.includes('/my-tunes')) {
      updateUrlWithTune(cfg.ptid, 'my_tunes')
    } else if (cfg.tuneId != null) {
      updateUrlWithTune(cfg.tuneId, 'global')
    }

    phase = 'loading'
    clearTimeout(hideTimer)
    visible = true
    setTimeout(() => {
      showCls = true
    }, 10)
    modalShowTime = Date.now()

    // ptid-only deep link (?ptid whose tune the host couldn't resolve): the
    // my-tunes endpoint is the only ptid-keyed lookup — its 404 is the
    // merged-away signal. The normal render path never calls it.
    if (cfg.tuneId == null && cfg.ptid != null) {
      resolveByPtid(cfg)
      return
    }

    fetch(detailUrl(cfg.tuneId, cfg.scope))
      .then((response) => {
        if (!response.ok) {
          const err = new Error(`HTTP error! status: ${response.status}`)
          err.status = response.status
          throw err
        }
        return response.json()
      })
      .then((data) => {
        if (data.success) {
          const td = data.session_tune
          if (data.redirected_from && td && td.tune_id) {
            // The tune was merged away (spec 030): the server followed the redirect
            // and returned the canonical tune. Heal the stale id in our config +
            // the URL bar, and tell the user what happened.
            const oldId = data.redirected_from
            config.tuneId = td.tune_id
            if (!window.location.pathname.includes('/my-tunes')) updateUrlWithTune(td.tune_id, 'global')
            applyPayload(data)
            mergedFrom = oldId
          } else {
            applyPayload(data)
          }
        } else {
          renderTuneFromOffline(cfg, data.error || data.message)
        }
      })
      .catch((error) => {
        console.error('Error loading tune details:', error)
        renderTuneFromOffline(cfg)
      })
  }

  function resolveByPtid(cfg) {
    fetch(`/api/my-tunes/${cfg.ptid}`)
      .then((response) => {
        if (!response.ok) {
          const err = new Error(`HTTP error! status: ${response.status}`)
          err.status = response.status
          throw err
        }
        return response.json()
      })
      .then((d) => {
        if (d.success && d.person_tune) {
          config.tuneId = d.person_tune.tune_id
          applyPayload(personTunePayload(d.person_tune))
        } else {
          showErr(t("Couldn't load this tune."), () => show(cfg))
        }
      })
      .catch((error) => {
        // A dead ptid deep-link (the row was conflict-deleted by a tune merge,
        // spec 030) degrades to a notice + a clean URL rather than a raw error.
        if (error.status === 404) {
          removeUrlTuneParam('my_tunes')
          showErr(
            t(
              'This tunebook entry no longer exists — it may have been merged into another tune. Check your tunebook list for the merged tune.'
            )
          )
          return
        }
        renderTuneFromOffline(cfg)
      })
  }

  export function close() {
    chooserOpen = false
    showCls = false
    pendingHeard = 0
    removeUrlTuneParam(mode)
    clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      visible = false
    }, 300)
  }

  // The "Configure" link in the status block's action row. Personal config only —
  // and only for a tune on my list, which is where the link lives.
  export function toggleConfigSection() {
    if (mode === 'admin') return // always visible on admin
    isConfigVisible = !isConfigVisible
  }

  export function logToActiveSession() {
    const active = window.activeSession
    if (!active || !active.session_instance_id) return
    const tuneId = (config && config.tuneId) || (tune && tune.tune_id)
    if (!tuneId) return
    // Clean the modal's tune param off the URL so the back button is sane.
    removeUrlTuneParam(mode)
    window.location.href = `/live/instances/${active.session_instance_id}?tune=${tuneId}`
  }

  // ---- overlay / keyboard ---------------------------------------------------------

  function onOverlayClick(event) {
    const timeSinceShown = Date.now() - modalShowTime
    if (timeSinceShown < 500) return
    if (event.target === event.currentTarget) close()
  }

  // Escape inside a sheet or dialog stacked on the drawer closes only that. This runs in
  // the capture phase, before Bits' own Escape handling closes the sheet, so the check
  // still sees it open.
  function onKeydown(event) {
    if (event.key !== 'Escape' || !visible) return
    if (chooserOpen || sessionPickerOpen || removeMyTunesOpen || removeSessionOpen) return
    close()
  }

  // ---- tunebook status control ------------------------------------------------------

  // Tell the host page a status was changed (statuses auto-save in place, without
  // the Save button / onSave), so it can update its own list immediately. Works
  // for ANY tune shown in the drawer, not just the one it opened with: on_list +
  // person_tune_id give a host that has no card for this tune (chained Played
  // With navigation) enough identity to fetch the row and add one.
  function notifyStatusChange() {
    if (!config || typeof config.onStatusChange !== 'function' || !tune) return
    const data = getInstrumentData(tune)
    config.onStatusChange({
      tune_id: tune.tune_id,
      learn_status: getModalLearnStatus(tune),
      instrument_status: { ...data.overrides },
      on_list: onList,
      person_tune_id: (pts && pts.person_tune_id) || null,
    })
  }

  export function toggleStatusExpand(event) {
    if (event) event.stopPropagation()
    piExpanded = !piExpanded
  }

  // Auto-save the learn status on tap through the offline op-queue. Setting the
  // tune's overall status realigns the AUTO instruments to it (clears their
  // overrides — snap-back); manual instruments are curated and left alone.
  export function setTunebookStatus(newStatus) {
    const tuneId = tune && tune.tune_id
    if (!tuneId || !pts) return
    const data = getInstrumentData(tune)
    const autoOverridden = (data.instruments || []).filter(
      (i) => i.is_auto && Object.prototype.hasOwnProperty.call(data.overrides, i.instrument)
    )
    if (newStatus === learnStatusOriginal && autoOverridden.length === 0) return // nothing to do

    const prevStatus = learnStatusOriginal
    const prevOverrides = { ...data.overrides }
    const nextOverrides = { ...data.overrides }
    autoOverridden.forEach((i) => delete nextOverrides[i.instrument])

    const applyUi = (status, overrides) => {
      learnStatusOriginal = status
      if (tune.person_tune_status) tune.person_tune_status.learn_status = status
      setInstrumentOverrides(tune, overrides)
      notifyStatusChange()
    }

    applyUi(newStatus, nextOverrides)
    statusSaving = true
    const ops = [submitMyTunesOp({ type: 'set_status', tune_id: tuneId, learn_status: newStatus })]
    autoOverridden.forEach((i) => {
      ops.push(
        submitMyTunesOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: i.instrument, status: null })
      )
    })
    Promise.all(ops)
      .then(() => {
        statusSaving = false // success OR queued offline
      })
      .catch((error) => {
        statusSaving = false
        applyUi(prevStatus, prevOverrides) // revert
        toastFailure(t('change the status'), error)
      })
  }

  // Set one instrument's status directly. Clicking the active status on a MANUAL
  // instrument toggles it off (untracked). An auto instrument always keeps a status,
  // and setting it to learn_status stores no override (snap-back).
  export function setInstrumentStatus(index, status) {
    const tuneId = tune && tune.tune_id
    if (!tuneId) return
    const data = getInstrumentData(tune)
    const inst = data.instruments[index]
    if (!inst) return
    const learnStatus = getModalLearnStatus(tune)
    const current = resolveInstStatus(tune, inst)
    let target = status
    if (status === current) {
      if (inst.is_auto) return // an auto instrument always has a status
      target = null // toggle a manual instrument off (untrack)
    }
    const shouldStore = target !== null && !(inst.is_auto && target === learnStatus)
    const prev = { ...data.overrides }
    const updated = { ...data.overrides }
    if (shouldStore) updated[inst.instrument] = target
    else delete updated[inst.instrument]
    setInstrumentOverrides(tune, updated)
    notifyStatusChange()
    submitMyTunesOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: inst.instrument, status: target }).catch(
      (error) => {
        setInstrumentOverrides(tune, prev)
        notifyStatusChange()
        toastFailure(t('change the status for {instrument}', { instrument: instrumentName(inst.instrument) }), error)
      }
    )
  }

  // Remove a tune from one (manual) instrument's list — deletes the override entirely.
  export function removeInstrumentTune(index) {
    const tuneId = tune && tune.tune_id
    if (!tuneId) return
    const data = getInstrumentData(tune)
    const inst = data.instruments[index]
    if (!inst || inst.is_auto) return
    const prev = { ...data.overrides }
    const updated = { ...data.overrides }
    delete updated[inst.instrument]
    setInstrumentOverrides(tune, updated)
    notifyStatusChange()
    submitMyTunesOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: inst.instrument, status: null }).catch(
      (error) => {
        setInstrumentOverrides(tune, prev)
        notifyStatusChange()
        toastFailure(t('remove the tune from your {instrument} list', { instrument: instrumentName(inst.instrument) }), error)
      }
    )
  }

  // Add the tune to the user's list as 'want to learn'. Online, the refetched
  // payload's on_list flips the derived mode, so a my-tunes-origin drawer
  // upgrades to the full variant naturally — no special re-show plumbing.
  export function addToTunebook() {
    if (adding) return
    const tuneId = tune.tune_id
    const keepTab = activeTab // survives the refetch's per-render tab reset
    adding = true
    // name/tune_type ride along so an offline add shows in the My Tunes list while queued.
    submitMyTunesOp({
      type: 'add',
      tune_id: tuneId,
      learn_status: 'want to learn',
      name: tune.tune_name || tune.name,
      tune_type: tune.tune_type,
    })
      .then((res) => {
        if (res && res.queued) {
          // Offline: no person_tune row exists yet to derive the full variant
          // from — send the user to their list (where the queued add shows as
          // pending) and acknowledge with a toast there, exactly as before.
          try {
            sessionStorage.setItem('myTunesToast', t('Added to your tunes. It will sync when you are back online.'))
          } catch (e) {}
          window.location.href = '/my-tunes'
          return
        }
        // Online: reload the payload; the new person_tune identity notifies the
        // host (chained adds live-update the underlying list) exactly once —
        // the derived-mode upgrade is just this re-apply, it never re-notifies.
        // The add has landed; if this reload fails, reload the whole drawer so it can't
        // go on claiming the tune is not on the list (its failure state has a Retry).
        return fetch(detailUrl(tuneId, scope))
          .then((response) => response.json())
          .then((data) => {
            if (!data.success) throw new Error(data.error || data.message || 'reload failed')
            applyPayload(data, { keepTab })
            notifyStatusChange()
          })
          .catch((error) => {
            console.error('Added, but reloading the tune failed:', error)
            toast(t('Added to your list.'), 'success')
            show({ ...config, initialTab: keepTab })
          })
      })
      .catch((error) => toastFailure(t('add the tune to your list'), error))
      .finally(() => {
        adding = false
      })
  }

  // ---- heard count -------------------------------------------------------------------

  function bumpHeard(delta) {
    if (mode === 'admin' || !pts) return
    const currentCount = heardCountView
    if (delta < 0 && currentCount === 0) return
    const newCount = Math.max(0, currentCount + delta)

    const setLocal = (n) => {
      if (tune.person_tune_status) tune.person_tune_status.heard_count = n
    }
    setLocal(newCount) // optimistic

    // Heard count is keyed by catalog tune_id and sent as an ABSOLUTE target so a
    // replayed offline op can never double-count. Requires the tune to be in the
    // user's collection (a person_tune row must exist for the set to land).
    const tuneId = tune.tune_id
    if (!tuneId || !onList) {
      console.error('Cannot set heard count: tune is not in your collection')
      setLocal(currentCount)
      return
    }
    pendingHeard++
    submitMyTunesOp({ type: 'set_heard', tune_id: tuneId, heard_count: newCount })
      .then(() => {
        pendingHeard = Math.max(0, pendingHeard - 1) // success OR queued offline: keep optimistic UI
      })
      .catch((error) => {
        setLocal(currentCount)
        pendingHeard = Math.max(0, pendingHeard - 1)
        toastFailure(t('update the heard count'), error)
      })
  }

  export function incrementHeardCount() {
    bumpHeard(1)
  }
  export function decrementHeardCount() {
    bumpHeard(-1)
  }

  // ---- configure section / save --------------------------------------------------------

  // ---- the setting-mismatch note ----------------------------------------------------

  // The staff draws what was PLAYED. When that isn't my setting, the note under it
  // swaps the staff to my version and back — view only, saves nothing, resets on close.
  // A warning you can't act on is just an irritant; being able to compare is the point.
  export function toggleMyVersion() {
    if (showingMyVersion) {
      showingMyVersion = false
      return
    }
    if (myNotation) {
      showingMyVersion = true
      return
    }
    if (myVersionLoading) return
    myVersionLoading = true
    // The unscoped detail payload resolves notation from MY setting.
    fetch(detailUrl(tune.tune_id, null))
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new Error('no payload')
        const st = data.session_tune
        myNotation = {
          setting_id: st.setting_id,
          setting_key: st.setting_key,
          abc: st.abc,
          incipit_abc: st.incipit_abc,
          image: st.image,
          incipit_image: st.incipit_image,
        }
        showingMyVersion = true
        const info = notationInfo(myNotation)
        notationMode = info.initialMode
        notationSize = 'incipit'
      })
      .catch((error) => toastFailure(t('load your version of this tune'), error))
      .finally(() => {
        myVersionLoading = false
      })
  }

  // The Session form's PUT target follows the droplist: 'general' writes the session's
  // own row, an instance writes that night's.
  function sessionEndpoint() {
    if (!inSession || !tune) return ''
    const path = sessionScope.path
    return editingInstance
      ? `/api/sessions/${path}/${scopeId}/tunes/${tune.tune_id}`
      : `/api/sessions/${path}/tunes/${tune.tune_id}`
  }

  const flashSaveState = (set, state) => {
    set(state)
    if (state === 'error') setTimeout(() => set('idle'), 2000)
  }

  // ---- personal config (person_tune) ------------------------------------------------

  // Configure Save: name alias / key. These are read-only offline, so this
  // is an online-only PUT. Notes & tags are NOT here — they auto-save (autoSavePersonal).
  export function savePersonal() {
    if (!tune || !config || pcSaveDisabled || isOffline) return
    const ptid = (pts && pts.person_tune_id) || config.ptid
    if (!ptid) return

    const updates = {}
    if (pcFields.name_alias !== pcOriginals.name_alias) updates.name_alias = pcFields.name_alias.trim() || null
    if (pcFields.key !== pcOriginals.key) updates.key = pcFields.key || null
    if (!Object.keys(updates).length) return

    pcSaveState = 'saving'
    fetch(`/api/my-tunes/${ptid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.error || data.message)
        pcSaveState = 'saved'
        if (tune.person_tune_status) Object.assign(tune.person_tune_status, updates)
        // Reseed ONLY the config originals — leaving notes/tags in pcFields untouched so
        // an in-progress (or just-autosaved) edit there isn't clobbered.
        pcOriginals.name_alias = pcFields.name_alias
        pcOriginals.key = pcFields.key
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (pcSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        toastFailure(t('save your changes'), error)
        flashSaveState((s) => (pcSaveState = s), 'error')
      })
  }

  // Cancel the Configure edits — reverts ONLY name/key, never the
  // separately-auto-saved notes & tags.
  export function cancelConfigure() {
    pcFields.name_alias = pcOriginals.name_alias
    pcFields.key = pcOriginals.key
    pcSaveState = 'idle'
    pcFetchState = 'idle'
  }

  // Auto-save one field of the always-visible notes/tags panel, fired on blur. Online:
  // a scoped PUT. Offline: the matching op (both survive the basement, like before).
  function autoSavePersonal(field) {
    if (!tune || !onList) return
    const ptid = (pts && pts.person_tune_id) || (config && config.ptid)
    if (!ptid) return

    let value
    if (field === 'notes') {
      if (pcFields.notes === pcOriginals.notes) return
      value = pcFields.notes.trim() || null
    } else {
      if (tagsEqual(pcFields.tags, pcOriginals.tags)) return
      value = normalizeTags(pcFields.tags)
    }

    autoSaveState = 'saving'
    const onDone = () => {
      if (tune.person_tune_status) tune.person_tune_status[field] = value
      if (field === 'notes') pcOriginals.notes = pcFields.notes
      else pcOriginals.tags = [...value]
      autoSaveState = 'saved'
      setTimeout(() => {
        if (autoSaveState === 'saved') autoSaveState = 'idle'
      }, 1200)
    }
    const onErr = (error) => {
      toastFailure(field === 'notes' ? t('save your notes') : t('save your tags'), error)
      flashSaveState((s) => (autoSaveState = s), 'error')
    }

    if (isOffline) {
      const op =
        field === 'notes'
          ? { type: 'set_notes', tune_id: tune.tune_id, notes: value }
          : { type: 'set_tags', tune_id: tune.tune_id, tags: value }
      submitMyTunesOp(op).then(onDone).catch(onErr)
      return
    }
    fetch(`/api/my-tunes/${ptid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [field]: value }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.error || data.message)
        onDone()
        // Deliberately NOT calling config.onSave here: notes & tags don't appear in
        // the list behind the drawer, so a full loadTunes() refresh on every blur is
        // pure cost — and it visibly flickers the page. The optimistic person_tune_status
        // update above is all the surrounding UI needs.
      })
      .catch(onErr)
  }

  // ---- session config (session_tune / session_instance_tune) --------------------------

  export function saveSession() {
    if (!tune || !config || sessSaveDisabled) return
    const endpoint = sessionEndpoint()
    if (!endpoint) return

    const updates = {}
    if (editingInstance) {
      if (sessFields.alias !== sessOriginals.alias) updates.name = sessFields.alias.trim() || null
      if (sessFields.key !== sessOriginals.key) updates.key_override = sessFields.key || null
    } else {
      if (sessFields.alias !== sessOriginals.alias) updates.alias = sessFields.alias.trim() || null
      if (sessFields.key !== sessOriginals.key) updates.key = sessFields.key || null
    }
    if (!Object.keys(updates).length) return

    sessSaveState = 'saving'
    fetch(endpoint, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.message || data.error)
        sessSaveState = 'saved'
        // Mirror onto the payload so the form's originals rebuild from what we wrote,
        // and the title/aka recompute against the new session alias.
        if (editingInstance) {
          if (String(sessionScope.instance ?? '') === String(scopeId)) Object.assign(tune, updates)
        } else {
          Object.assign(tune, updates)
          if (tune.session_scope) tune.session_scope.in_repertoire = true
        }
        seedSessionForm()
        // At 'general' scope this and the Details form wrote the same row, so the other
        // one has to be told; at instance scope it's a no-op re-seed.
        seedDetailsForm()
        sessSaveState = 'saved'
        // The instance response carries the saved records, so a live logger can patch
        // its rows now rather than wait for the change to come back round the feed.
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (sessSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        toastFailure(t('save your changes'), error)
        flashSaveState((s) => (sessSaveState = s), 'error')
      })
  }

  // ---- details config (session_tune, always) -----------------------------------------

  // The Details form's target never moves: the session's own row. That's the whole
  // difference from saveSession, whose endpoint follows the History droplist.
  export function saveDetails() {
    if (!tune || !config || dcSaveDisabled || !canEditSessionGeneral) return

    const updates = {}
    if (dcFields.alias !== dcOriginals.alias) updates.alias = dcFields.alias.trim() || null
    if (dcFields.key !== dcOriginals.key) updates.key = dcFields.key || null
    if (!Object.keys(updates).length) return

    dcSaveState = 'saving'
    fetch(`/api/sessions/${sessionScope.path}/tunes/${tune.tune_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.message || data.error)
        // Mirror onto the payload so both session forms rebuild from what we wrote, and
        // the title/aka recompute against the new session alias. Saving the session layer
        // for a tune with no session_tune row silently creates it (spec 037).
        Object.assign(tune, updates)
        if (tune.session_scope) tune.session_scope.in_repertoire = true
        seedDetailsForm()
        seedSessionForm()
        dcSaveState = 'saved'
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (dcSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        toastFailure(t('save your changes'), error)
        flashSaveState((s) => (dcSaveState = s), 'error')
      })
  }

  // ---- "At a different session ..." -------------------------------------------------

  // The picker only opens once the list is in hand: an empty picker would read as
  // "you have no other sessions". While it loads, the droplist row says so.
  function openSessionPicker() {
    if (mySessions.length) {
      sessionPickerOpen = true
      return
    }
    if (mySessionsState === 'loading') return
    mySessionsState = 'loading'
    fetch('/api/my-sessions?limit=100')
      .then((r) => r.json())
      .then((d) => {
        if (!d.success) throw new ServerError(d.error || d.message)
        mySessions = d.sessions || []
        mySessionsState = 'idle'
        sessionPickerOpen = true
      })
      .catch((error) => {
        mySessionsState = 'idle'
        toastFailure(t('load your sessions'), error)
      })
  }

  /**
   * Re-scope the whole drawer to another session. Everything downstream follows from the
   * refetched payload — the title chain (that session's alias may outrank the canonical
   * name), the aka line, the notation's setting, the droplist, the permissions.
   *
   * The URL is deliberately NOT rewritten: the page BEHIND the drawer is still the
   * session you came from, and a path claiming otherwise would be a lie.
   */
  function scopeToSession(session) {
    if (!session || !tune) return
    const cfg = { ...config, scope: { session: session.path }, initialTab: 'history' }
    config = cfg
    scopeId = 'general'
    lastRealScope = 'general'
    sessFormOpen = false
    phase = 'loading'
    fetch(detailUrl(tune.tune_id, cfg.scope))
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.message || data.error)
        applyPayload(data, { keepTab: 'history' })
      })
      .catch((error) => {
        console.error('Error re-scoping to session:', error)
        const msg = error instanceof ServerError && error.message ? error.message : ''
        showErr(
          msg ||
            (session.name
              ? t("Couldn't load this tune at {name}.", { name: session.name })
              : t("Couldn't load this tune at that session.")),
          () => scopeToSession(session)
        )
      })
  }

  /** "While I was there" — a filter over whatever scope is selected, not a scope of its own. */
  export function toggleAttendedOnly() {
    attendedOnly = !attendedOnly
    loadHistory()
  }

  // Tapping the ✓ says what it means, beside the filter, then fades. A `title` never shows
  // on touch, and a toast is too loud for a footnote on one row.
  export function showAttendedHint() {
    attendedHint = true
    clearTimeout(attendedHintTimer)
    attendedHintTimer = setTimeout(() => (attendedHint = false), 1600)
  }

  // THE scope control. It chooses what history we're looking at AND — when the answer is a
  // session or one of its instances — what the form below writes to.
  export function selectSessionScope(id) {
    // The "different session" row isn't a target, it's an errand: open the picker and snap
    // the select back, so a cancelled pick doesn't strand it on a row that means nothing.
    if (String(id) === OTHER_SESSION) {
      openSessionPicker()
      scopeId = lastRealScope
      return
    }

    scopeId = String(id)
    lastRealScope = scopeId
    sessFormOpen = false
    loadHistory()

    if (!editableScope) return
    if (!editingInstance || String(sessionScope?.instance ?? '') === String(scopeId)) {
      seedSessionForm()
      return
    }
    loadInstanceOverrides()
  }

  // An instance's own name/setting/key, for the form. Until they arrive the form must
  // not pass blanks off as "no overrides", so a failure hides it behind a Retry.
  function loadInstanceOverrides() {
    const requested = scopeId
    sessFields = { alias: '', key: '' }
    sessOriginals = { alias: '', setting_id: '', key: '' }
    overridesError = false
    fetch(detailUrl(tune.tune_id, { session: sessionScope.path, instance: requested }))
      .then((r) => r.json())
      .then((data) => {
        if (scopeId !== requested) return
        if (!data.success) throw new ServerError(data.message || data.error)
        const st = data.session_tune
        sessOriginals = {
          alias: st.name || '',
          setting_id: st.setting_override || '',
          key: st.key_override || '',
        }
        sessFields = {
          alias: sessOriginals.alias,
          key: sessOriginals.key,
        }
      })
      .catch((error) => {
        console.error('Error loading instance overrides:', error)
        if (scopeId === requested) overridesError = true
      })
  }

  // ---- admin (canonical tune name) — untouched by 037; see spec 036 ---------------------

  export function saveAdmin() {
    if (!tune || adminSaveDisabled) return
    const name = adminFields.name.trim()
    if (!name) {
      toast(t('Tune name cannot be empty'), 'error')
      return
    }
    adminSaveState = 'saving'
    fetch(`/api/admin/tunes/${tune.tune_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.error || data.message)
        adminSaveState = 'saved'
        tune.tune_name = name
        seedAdminForm()
        adminSaveState = 'saved'
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (adminSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        toastFailure(t('save the tune name'), error)
        flashSaveState((s) => (adminSaveState = s), 'error')
      })
  }

  // Put a setting's notation on the staff — the abc and whichever images it has. Any
  // "your version" view is dropped: the staff now shows what was just fetched or chosen.
  function showNotation(n) {
    showingMyVersion = false
    myNotation = null
    tune.abc = n.abc
    tune.incipit_abc = n.incipit_abc
    tune.image = n.image || null
    tune.incipit_image = n.incipit_image || null
    if (n.key !== undefined) tune.setting_key = n.key
    notationMode = notationInfo(tune).initialMode
    notationSize = 'incipit'
  }

  // Generate Notation: fetch and cache this tune's notation from TheSession.org, then
  // draw it. For a tune on my list that is my setting (or, if I have none, the tune's
  // first, which then becomes mine); otherwise it only caches the tune's first setting.
  // Resolves true when notation was fetched (even if saving the setting then warned).
  function fetchNotation() {
    if (!tune || pcFetchState === 'loading') return Promise.resolve(false)
    const tuneId = tune.tune_id
    const ptid = onList ? (pts && pts.person_tune_id) || config?.ptid : null
    const params = new URLSearchParams()
    if (ptid && pcOriginals.setting_id) params.set('setting_id', String(pcOriginals.setting_id))
    // A signed-out viewer's authority to make this one call. Harmless to send when
    // signed in; the server prefers the session.
    if (notationToken) params.set('token', notationToken)
    const query = params.toString()
    pcFetchState = 'loading'
    const feedback = (st) => {
      pcFetchState = st
      setTimeout(() => {
        if (pcFetchState === st) pcFetchState = 'idle'
      }, 2000)
    }

    return fetch(`/api/tunes/${tuneId}/settings/cache${query ? `?${query}` : ''}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          toastFailure(t('get the notation from thesession.org'), new ServerError(data.message || data.error))
          feedback('err')
          return false
        }
        showNotation(data.setting)
        const fetchedSettingId = data.setting.setting_id
        if (!ptid || fetchedSettingId === pcOriginals.setting_id) {
          feedback('ok')
          return true
        }
        return fetch(`/api/my-tunes/${ptid}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ setting_id: fetchedSettingId }),
        })
          .then((response) => response.json())
          .then((saveData) => {
            if (!saveData.success) throw new ServerError(saveData.error || saveData.message)
            if (pts) pts.setting_id = fetchedSettingId
            pcOriginals.setting_id = fetchedSettingId
            feedback('ok')
            return true
          })
          .catch((error) => {
            console.error('Error saving setting_id:', error)
            toast(t("Got the notation, but couldn't save the setting. Try again."), 'error')
            feedback('warn')
            return true
          })
      })
      .catch((error) => {
        toastFailure(t('get the notation from thesession.org'), error)
        feedback('err')
        return false
      })
  }

  // ---- the setting chooser ------------------------------------------------------------
  // Which written version a layer plays is picked by looking at them, not by typing a
  // setting number: the chooser pages every setting of the tune with its full notation.
  // It opens for one layer — mine, the session's, or one night's — and the pick saves
  // at once, on its own, like the learn status (not behind a form's Save).
  let chooserOpen = $state(false)
  let chooserLayer = $state(null) // {kind: 'personal' | 'session' | 'instance', instanceId?}

  // The link under the staff offers the layer the drawer is looking at: on my list, my
  // version; at a session, the session's; on one night, that night's.
  const viewLayer = $derived.by(() => {
    if (!tune || !loggedIn || isOffline) return null
    if (mode === 'session_instance') {
      const instanceId = sessionScope?.instance
      const playedThatNight = playedInstances.some((i) => String(i.session_instance_id) === String(instanceId))
      return playedThatNight && sessionScope?.can_edit_instance ? { kind: 'instance', instanceId } : null
    }
    if (mode === 'session') return sessionScope?.can_edit_session ? { kind: 'session' } : null
    if (mode === 'my_tunes') return { kind: 'personal' }
    return null
  })
  const viewLayerPrompt = $derived(
    !viewLayer
      ? ''
      : viewLayer.kind === 'personal'
        ? t('I play a different version')
        : viewLayer.kind === 'session'
          ? t('We play a different version')
          : t('We played a different version on this night')
  )

  const isScopedInstance = (instanceId) => String(instanceId) === String(sessionScope?.instance ?? '')

  // The setting a layer uses now — where the chooser opens, and the one it marks in use.
  // A night with no setting of its own played the session's.
  function layerSettingId(layer) {
    if (!tune || !layer) return null
    if (layer.kind === 'personal') return (pts && pts.setting_id) || (inSession ? null : tune.setting_id) || null
    if (layer.kind === 'session') return tune.setting_id || null
    const own = isScopedInstance(layer.instanceId)
      ? tune.setting_override
      : editingInstance && String(scopeId) === String(layer.instanceId)
        ? sessOriginals.setting_id
        : null
    return own || tune.setting_id || null
  }
  const chooserHeading = $derived(
    !chooserLayer
      ? ''
      : chooserLayer.kind === 'personal'
        ? t('Which version do you play?')
        : chooserLayer.kind === 'session'
          ? t('Which version does {name} play?', { name: sessionLabel })
          : t('Which version was played that night?')
  )

  export function openChooser(layer) {
    if (!tune || !layer || isOffline) return
    chooserLayer = layer
    chooserOpen = true
  }

  // Where a layer's setting is written. Mine goes through the tunebook op (as the iOS
  // app's does); the session's and a night's through their own rows.
  function settingWrite(layer, tuneId, settingId) {
    if (layer.kind === 'personal') {
      return {
        method: 'POST',
        endpoint: '/api/my-tunes/ops',
        body: { op_id: crypto.randomUUID(), type: 'set_setting', tune_id: tuneId, setting_id: settingId },
      }
    }
    const path = sessionScope.path
    if (layer.kind === 'session') {
      return { method: 'PUT', endpoint: `/api/sessions/${path}/tunes/${tuneId}`, body: { setting_id: settingId } }
    }
    return {
      method: 'PUT',
      endpoint: `/api/sessions/${path}/${layer.instanceId}/tunes/${tuneId}`,
      body: { setting_override: settingId },
    }
  }

  // The chooser's pick: write it to the layer, then mirror it here. A setting only
  // thesession.org has is imported by the server on the way (nothing may point at a
  // setting we don't hold); its opening bars then render on first view. Resolves true
  // when saved, which closes the chooser.
  async function chooseSetting(setting, fullImage) {
    const layer = chooserLayer
    if (!tune || !layer) return false
    const { method, endpoint, body } = settingWrite(layer, tune.tune_id, setting.setting_id)
    try {
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!data.success) throw new ServerError(data.message || data.error)
      applyChosenSetting(layer, setting.setting_id, {
        abc: setting.abc,
        incipit_abc: setting.incipit_abc,
        incipit_image: setting.incipit_image || null,
        image: fullImage || null,
        key: setting.key,
      })
      if (config?.onSave && typeof config.onSave === 'function') config.onSave(data)
      return true
    } catch (error) {
      toastFailure(t('change the setting'), error)
      return false
    }
  }

  // Mirror a saved pick onto the payload and the forms, and redraw the staff when it
  // draws from the layer that changed (instance -> session -> mine, most specific wins).
  function applyChosenSetting(layer, settingId, notation) {
    let drawn = false
    if (layer.kind === 'personal') {
      if (pts) pts.setting_id = settingId
      pcOriginals.setting_id = settingId
      if (!inSession) {
        tune.setting_id = settingId
        drawn = true
      }
    } else if (layer.kind === 'session') {
      tune.setting_id = settingId
      dcOriginals.setting_id = settingId
      if (!editingInstance) sessOriginals.setting_id = settingId
      if (tune.session_scope) tune.session_scope.in_repertoire = true
      drawn = !tune.setting_override
    } else {
      if (isScopedInstance(layer.instanceId)) {
        tune.setting_override = settingId
        drawn = true
      }
      if (editingInstance && String(scopeId) === String(layer.instanceId)) sessOriginals.setting_id = settingId
    }
    if (drawn) showNotation(notation)
  }

  // ---- lazy notation render ------------------------------------------------------
  // A tune imported from thesession.org arrives with ABC only — the PNGs are rendered
  // on demand (they go through the abc-renderer service, too slow to block an add on).
  // The live logger already redeems that promise via its incipit endpoint; the drawer
  // used to just show the abc text and wait for someone to press Generate Notation, so
  // every tune added through the My Tunes pane stayed dot-less. Render it on first view
  // instead: the setting-image endpoint draws from the ABC we already hold (no
  // thesession.org round trip) and caches the PNG, so this happens once per setting ever.
  const renderTried = new Set() // setting_ids this drawer has already asked about
  async function settingImagePng(settingId, kind) {
    const res = await fetch(`/api/tunes/settings/${settingId}/image?kind=${kind}`, {
      credentials: 'same-origin',
    })
    if (!res.ok) return null
    const data = await res.json().catch(() => ({}))
    return data.image || null
  }
  // Write a freshly rendered PNG back into whichever block the view is reading from.
  function patchNotationImage(settingId, field, value) {
    if (tune && (tune.setting_override || tune.setting_id) === settingId) tune[field] = value
    if (myNotation && myNotation.setting_id === settingId) myNotation = { ...myNotation, [field]: value }
  }
  async function renderMissingNotation(settingId) {
    try {
      // The incipit first — it's what the drawer opens on, so it's the visible win.
      const incipit = await settingImagePng(settingId, 'incipit')
      if (!incipit) return
      patchNotationImage(settingId, 'incipit_image', incipit)
      notationMode = 'dots' // the abc view was only ever the no-dots fallback
      // Then the full staff, so the incipit/full toggle isn't a dead control.
      const full = await settingImagePng(settingId, 'full')
      if (full) patchNotationImage(settingId, 'image', full)
    } catch {
      /* leave the abc text (and Generate Notation) exactly as they were */
    }
  }
  $effect(() => {
    if (!visible || !loggedIn || isOffline) return
    const src = notationSource
    // The setting drawn: a night's own, else the one under it.
    const settingId = src?.setting_override || src?.setting_id
    if (settingId == null) return
    // Only when there's something to render and nothing rendered yet.
    if (src.incipit_image || !(src.incipit_abc || src.abc)) return
    if (renderTried.has(settingId)) return
    renderTried.add(settingId)
    untrack(() => renderMissingNotation(settingId))
  })

  // "Generate Notation" (shown in the notation area when nothing is cached). It saves
  // the setting to my list when I have one, and otherwise just caches the notation.
  export function generateNotation() {
    // fetchNotation has already said what went wrong when it resolves false.
    fetchNotation().then((ok) => {
      if (!ok) return
      // If the fetch produced a rendered image, show the dots the user asked
      // for instead of leaving them on the abc text view.
      if (tune?.incipit_image || tune?.image) notationMode = 'dots'
    })
  }

  // ---- removals ---------------------------------------------------------------------

  // Removals are decisions -> kit Dialogs with explicit verbs (spec 035), not
  // native confirms.
  let removeMyTunesOpen = $state(false)
  let removeSessionOpen = $state(false)

  export function removeFromMyTunes() {
    removeMyTunesOpen = true
  }

  function doRemoveFromMyTunes() {
    const personTuneId = (pts && pts.person_tune_id) || config?.ptid
    if (!personTuneId) {
      toast(t('Unable to remove tune'), 'error')
      return
    }
    // Returned so the Dialog stays open, its confirm busy, until the server answers.
    return fetch(`/api/my-tunes/${personTuneId}`, { method: 'DELETE' })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.error || data.message)
        removeUrlTuneParam(mode)
        if (config.onSave && typeof config.onSave === 'function') config.onSave()
        close()
      })
      .catch((error) => {
        toastFailure(t('remove the tune from your list'), error)
        return false
      })
  }

  export function removeFromSession() {
    removeSessionOpen = true
  }

  function doRemoveFromSession() {
    const sessionPath = scope?.session
    const tuneId = tune?.tune_id
    if (!sessionPath || !tuneId) {
      toast(t('Unable to remove tune from session'), 'error')
      return
    }
    return fetch(`/api/sessions/${sessionPath}/tunes/${tuneId}`, { method: 'DELETE' })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) throw new ServerError(data.message || data.error)
        removeUrlTuneParam(mode)
        if (config.onSave && typeof config.onSave === 'function') config.onSave()
        close()
      })
      .catch((error) => {
        toastFailure(t('remove the tune from the session'), error)
        return false
      })
  }

  // ---- stats / tabs -------------------------------------------------------------------

  export function refreshTunebookCount() {
    if (!tune || refreshState !== 'idle') return
    const tuneId = tune.tune_id
    refreshState = 'loading'
    // Session variants refresh through their session; everything else uses the
    // admin-path endpoint (as the my-tunes variant always has).
    const apiEndpoint =
      mode === 'session' || mode === 'session_instance'
        ? `/api/sessions/${scope.session}/tunes/${tuneId}/refresh_tunebook_count`
        : `/api/admin/tunes/${tuneId}/refresh_tunebook_count`
    fetch(apiEndpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          const newCount = data.new_count || data.tunebook_count
          tune.tunebook_count = newCount
          tune.tunebook_count_cached = newCount
          refreshState = 'ok'
        } else {
          refreshState = 'err'
          toastFailure(t('refresh the count'), new ServerError(data.error || data.message))
        }
      })
      .catch((error) => {
        refreshState = 'err'
        toastFailure(t('refresh the count'), error)
      })
      .finally(() => {
        setTimeout(() => {
          refreshState = 'idle'
        }, 2000)
      })
  }

  export function switchTab(tabName) {
    activeTab = tabName
    // History and Played With are fetched lazily, only when the tab is actually viewed
    if (tabName === 'history') loadHistory()
    if (tabName === 'played-with') loadPlayedWith()
  }

  export function setPlayedWithScope(scopeKey) {
    playedWithScope = scopeKey
    loadPlayedWith()
  }

  // History is fetched lazily and asynchronously — the drawer never waits on it, which is
  // why it can be the default tab without costing anything at open.
  //
  // An instance scope needs NO request: the payload already carries that night's Set/tune
  // coordinates, so selecting a date answers instantly.
  function loadHistory() {
    if (!config) return
    const key = historyKey
    const requested = scopeId
    const tuneId = config.tuneId || (tune && tune.tune_id)
    if (!tuneId || requested === OTHER_SESSION) return
    if (editingInstance) return // answered from the payload
    if (historyCache[key]?.status === 'ready') return

    // Offline, the history simply isn't there — it's a live query, not part of the offline
    // bundle. Say so rather than showing a failed-request error.
    if (isOffline) {
      historyCache[key] = { status: 'offline' }
      return
    }

    historyCache[key] = { status: 'loading' }
    fetch(historyUrl(tuneId, requested, sessionScope?.path, attendedOnly))
      .then((r) => r.json())
      .then((data) => {
        if (key !== historyKey) return // scope/filter changed while loading
        historyCache[key] = data.success ? { status: 'ready', data } : { status: 'error' }
      })
      .catch(() => {
        if (key === historyKey) historyCache[key] = { status: isOffline ? 'offline' : 'error' }
      })
  }

  function loadPlayedWith() {
    if (!config) return
    const scopeKey = playedWithScopeKey
    const tuneId = config.tuneId || (tune && tune.tune_id)
    if (!tuneId) {
      playedWithCache[scopeKey] = { status: 'none' }
      return
    }
    if (playedWithCache[scopeKey]?.status === 'ready') return
    playedWithCache[scopeKey] = { status: 'loading' }
    let url = `/api/tunes/${tuneId}/played-with`
    if (scopeKey === 'session') {
      url += `?session_path=${encodeURIComponent(scope.session)}`
    } else if (scopeKey === 'member' || scopeKey === 'attended') {
      url += `?scope=${scopeKey}`
    }
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (scopeKey !== playedWithScopeKey) return
        if (!data.success) {
          playedWithCache[scopeKey] = { status: 'error' }
          return
        }
        playedWithCache[scopeKey] = { status: 'ready', data }
      })
      .catch(() => {
        if (scopeKey === playedWithScopeKey) playedWithCache[scopeKey] = { status: 'error' }
      })
  }

  // Open a companion tune's detail modal in place of the current one. Chaining
  // is just show() with the SAME scope and callbacks — the payload derives the
  // variant, so an on-list companion opens as the full my-tunes variant, a
  // session-scoped drawer keeps its session, and a not-on-list companion shows
  // the Add view — however deep the chain goes.
  function openPlayedWithTune(pwTune) {
    if (!pwTune || !pwTune.tune_id) return
    show({
      tuneId: pwTune.tune_id,
      scope: config?.scope || null,
      onSave: config?.onSave,
      onStatusChange: config?.onStatusChange,
      tuneName: pwTune.name,
    })
  }

  // ---- ABC notation section -----------------------------------------------------------

  // Switch between notation modes (dots vs abc), keeping the size state shared
  // across modes with the legacy fallback (requested size, else incipit, else full).
  export function switchNotationMode(newMode) {
    if (!tune || notationMode === newMode) return
    if (newMode === 'dots') {
      if (notationSize === 'incipit' && tune.incipit_image) {
        // keep size
      } else if (notationSize === 'full' && tune.image) {
        // keep size
      } else if (tune.incipit_image) {
        notationSize = 'incipit'
      } else if (tune.image) {
        notationSize = 'full'
      }
    } else {
      if (notationSize === 'incipit' && tune.incipit_abc) {
        // keep size
      } else if (notationSize === 'full' && tune.abc) {
        // keep size
      } else if (tune.incipit_abc) {
        notationSize = 'incipit'
      } else if (tune.abc) {
        notationSize = 'full'
      }
    }
    notationMode = newMode
  }

  // Toggle between incipit and full notation (no-op when the target isn't cached).
  export function toggleNotationSize() {
    if (!tune) return
    const newSize = notationSize === 'incipit' ? 'full' : 'incipit'
    if (notationMode === 'dots') {
      if (!(newSize === 'incipit' ? tune.incipit_image : tune.image)) return
    } else {
      if (!(newSize === 'incipit' ? tune.incipit_abc : tune.abc)) return
    }
    notationSize = newSize
  }

  function onNotationClick() {
    if (notation?.canToggleSize) toggleNotationSize()
  }

  const tunebookCountView = $derived(tune ? tune.tunebook_count || tune.tunebook_count_cached || 0 : 0)

  // A sentence whose number (or link) sits in its own element: t()/tn() fill the
  // placeholder with MARK, and the sentence is split around it, so the element lands
  // wherever the language puts it. tn() still picks the plural form by the real count.
  const MARK = '\u0000'
  function around(text) {
    const i = text.indexOf(MARK)
    return i < 0 ? [text, ''] : [text.slice(0, i), text.slice(i + MARK.length)]
  }
  const heardLine = $derived(
    around(tn(heardCountView, "You've heard this {n} time", "You've heard this {n} times", { n: MARK }))
  )
  const listCountLine = $derived(
    around(tn(tune?.person_list_count || 0, 'Saved in {n} tune list on Ceol.io', 'Saved in {n} tune lists on Ceol.io', { n: MARK }))
  )
  const tunebookLine = $derived(
    around(tn(tunebookCountView, 'Saved in {n} tunebook on TheSession.org', 'Saved in {n} tunebooks on TheSession.org', { n: MARK }))
  )
  const loggedHereLine = $derived(
    around(tn(tune?.times_played || 0, 'Logged {n} time at this session', 'Logged {n} times at this session', { n: MARK }))
  )
  const loggedMineLine = $derived(
    around(tn(myPlayCount, 'Logged {n} time at my sessions', 'Logged {n} times at my sessions', { n: MARK }))
  )
  const loggedThereLine = $derived(
    around(tn(myAttendedCount, 'Logged {n} time while I was there', 'Logged {n} times while I was there', { n: MARK }))
  )
  const loggedAllLine = $derived(
    around(tn(tune?.global_play_count || 0, 'Logged {n} time at all sessions', 'Logged {n} times at all sessions', { n: MARK }))
  )
  const repertoireLine = $derived(
    around(tn(tune?.session_count || 0, 'In the repertoire of {n} session', 'In the repertoire of {n} sessions', { n: MARK }))
  )
  const mergedLine = $derived(
    around(t("Tune #{old} was merged into {link} (#{id}) — you're viewing the merged tune.", { old: mergedFrom, link: MARK, id: tune?.tune_id }))
  )
  const mismatchMine = $derived(around(t('{name} plays a different one.', { name: MARK })))
  const mismatchTheirs = $derived(around(t('{link} differs.', { link: MARK })))
</script>

<svelte:window onkeydowncapture={onKeydown} />

<!-- Inline display:none is a safety default (matches the legacy container partial):
     a page with its own `.modal-overlay { display: … }` rule can't reveal it. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div
  id="tune-detail-modal"
  class="modal-overlay{showCls ? ' show' : ''}"
  style="display: {visible ? 'flex' : 'none'};"
  onclick={onOverlayClick}
>
  <div class="modal-dialog">
    <div id="tune-detail-content">
      {#if phase === 'loading'}
        <table class="modal-header-section">
          <tbody>
            <tr>
              {#if config?.tuneType}
                <td class="modal-header-pill-cell"><Chip label={typeLabel(config.tuneType)} styled={false} chipClass="tune-type-pill" /></td>
              {/if}
              <td class="modal-header-title-cell">
                <h2 class="modal-tune-title">{config?.tuneName || t('Loading...')}</h2>
              </td>
              <td class="modal-header-spacer-cell"></td>
              <td class="modal-header-close-cell">
                <button class="modal-close-btn" onclick={close} title={t('Close')}>×</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="modal-loading">
          <div class="loading-spinner"></div>
          <p>{t('Loading tune details...')}</p>
        </div>
      {:else if phase === 'error'}
        <table class="modal-header-section">
          <tbody>
            <tr>
              <td class="modal-header-title-cell">
                <h2 class="modal-tune-title">{t('Error')}</h2>
              </td>
              <td class="modal-header-spacer-cell"></td>
              <td class="modal-header-close-cell">
                <button class="modal-close-btn" onclick={close} title={t('Close')}>×</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="modal-error">
          {#if errorRetry}
            <LoadError message={errorMsg} onRetry={errorRetry} />
          {:else}
            <p>{errorMsg}</p>
          {/if}
        </div>
      {:else if phase === 'ready' && tune}
        {#if savedCopy}
          <LoadError
            class="tune-saved-copy"
            inline
            message={isOffline ? t("You're offline, so this is your saved copy of the tune.") : t("Couldn't load the latest for this tune, so this is your saved copy.")}
            onRetry={isOffline ? null : () => show(config)} />
        {/if}
        {#if mergedFrom != null}
          <!-- Banner for a healed merged-tune permalink (spec 030) -->
          <div
            class="tune-merged-notice"
            style="background: var(--input-bg, #f8f9fa); border: 1px solid var(--border-color, #dee2e6); border-radius: 6px; padding: 0.5rem 0.75rem; margin-bottom: 0.75rem; font-size: 0.85rem; color: var(--secondary-text, #6c757d);"
          >
            {mergedLine[0]}<a
              href={tuneHref(tune.tune_id, 'global')}
              onclick={(e) => {
                e.preventDefault()
                openPlayedWithTune({ tune_id: tune.tune_id, name: tune.tune_name || tune.name })
              }}>"{tune.tune_name || tune.name || `#${tune.tune_id}`}"</a
            >{mergedLine[1]}
          </div>
        {/if}

        <!-- Header -->
        <table class="modal-header-section">
          <tbody>
            <tr>
              {#if headerTuneType}
                <td class="modal-header-pill-cell"><Chip label={typeLabel(headerTuneType)} styled={false} chipClass="tune-type-pill" /></td>
              {/if}
              <td class="modal-header-title-cell">
                <!-- The title is NOT clickable any more: expanding a config panel by
                     clicking a heading was quirky and undiscoverable. Configure lives
                     in the status block's action row. -->
                <h2 class="modal-tune-title">{displayName}</h2>
                {#if akaName}
                  <div class="modal-tune-aka">{t('aka {name}', { name: akaName })}</div>
                {/if}
              </td>
              <td class="modal-header-spacer-cell"></td>
              <td class="modal-header-close-cell">
                <button class="modal-close-btn" onclick={close} title={t('Close')}>×</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- "Log to current session" — only when a session is in progress (spec 024) -->
        {#if activeSess && activeSess.session_instance_id && (config.tuneId || tune.tune_id)}
          <div class="active-session-log-section">
            <button class="active-session-log-btn" onclick={logToActiveSession}>
              <span class="active-session-log-dot"></span>
              {activeSess.session_name ? t('Log to {name}', { name: activeSess.session_name }) : t('Log to the current session')}
            </button>
          </div>
        {/if}

        <!-- ABC notation — the FIRST content block (spec 037). It is what you opened
             the drawer for; it used to sit below the status block and the heard count.
             The staff draws what was PLAYED (instance -> session -> mine): a name is a
             label, so the most personal wins, but a setting is a record of what
             happened, so the most specific factual layer wins. -->
        {#if notation && notation.hasAny}
          <div class="abc-notation-section">
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
            <div
              class="abc-notation-display{notation.canToggleSize ? ' abc-notation-clickable' : ''}"
              data-current-mode={notationMode}
              data-current-size={notationSize}
              title={notation.canToggleSize ? t('Click to toggle between incipit and full notation') : undefined}
              onclick={onNotationClick}
            >
              {#if notationView}
                {#if notationView.kind === 'img'}
                  <img
                    src="data:image/png;base64,{notationView.src}"
                    alt={notationView.size === 'incipit' ? t('Incipit notation') : t('Full notation')}
                    class="abc-notation-image abc-notation-{notationView.size}"
                  />
                {:else}
                  <pre class="abc-notation-text abc-notation-{notationView.size}">{notationView.text}</pre>
                {/if}
              {/if}
            </div>
            <div class="notation-controls-row">
              <div class="notation-mode-tabs">
                {#if notation.hasDots && notation.hasAbc}
                  <button
                    class="notation-mode-tab {notationMode === 'dots' ? 'active' : ''}"
                    data-mode="dots"
                    onclick={(e) => {
                      e.stopPropagation()
                      switchNotationMode('dots')
                    }}
                  >
                    {t('notes')}
                  </button>
                  <button
                    class="notation-mode-tab {notationMode === 'abc' ? 'active' : ''}"
                    data-mode="abc"
                    onclick={(e) => {
                      e.stopPropagation()
                      switchNotationMode('abc')
                    }}
                  >
                    {t('abc')}
                  </button>
                {:else if notation.hasAbc && !notation.hasDots && canGenerateNotation}
                  <!-- abc text is cached but no rendered staff image: offer to
                       generate the dots where the notes/abc toggle would sit. -->
                  <button
                    type="button"
                    class="generate-notation-link"
                    onclick={(e) => {
                      e.stopPropagation()
                      generateNotation()
                    }}
                    disabled={pcFetchState === 'loading'}
                  >
                    {pcFetchState === 'loading' ? t('Generating notation…') : t('Generate Notation')}
                  </button>
                {/if}
              </div>
              <div class="notation-external-links">
                {#if thesessionLink}<a
                    href={thesessionLink}
                    target="_blank"
                    class="notation-external-link"
                    title={t('View on TheSession.org')}
                    onclick={(e) => e.stopPropagation()}>{'thesession'}</a
                  >{/if}{#if abctoolsLink}<a
                    href={abctoolsLink}
                    target="_blank"
                    class="notation-external-link"
                    title={t('View in ABC Tools')}
                    onclick={(e) => e.stopPropagation()}>{'abc-tools'}</a
                  >{/if}
              </div>
            </div>
            <!-- You're looking at the session's version, not yours. A warning you can't
                 act on is just an irritant, so the link swaps the staff to your setting
                 and back. View only — it saves nothing and resets when the drawer closes. -->
            {#if settingMismatch}
              <div class="notation-mismatch">
                {#if showingMyVersion}
                  {t('Showing your version.')}
                  {mismatchMine[0]}<button type="button" class="notation-mismatch-link" onclick={toggleMyVersion}
                    >{sessionLabel}</button
                  >{mismatchMine[1]}
                {:else}
                  {t('This is the version {name} plays.', { name: sessionLabel })}
                  {mismatchTheirs[0]}<button type="button" class="notation-mismatch-link" onclick={toggleMyVersion} disabled={myVersionLoading}
                    >{myVersionLoading ? t('Loading your version…') : t('Your personal version')}</button
                  >{mismatchTheirs[1]}
                {/if}
              </div>
            {/if}
          </div>
        {:else if canGenerateNotation}
          <!-- No cached notation for this tune: offer to generate it in place. -->
          <div class="abc-notation-section abc-notation-empty">
            <button
              type="button"
              class="generate-notation-link"
              onclick={generateNotation}
              disabled={pcFetchState === 'loading'}
            >
              {pcFetchState === 'loading' ? t('Generating notation…') : t('Generate Notation')}
            </button>
          </div>
        {/if}
        {#if viewLayer}
          <div class="notation-change-setting">
            {viewLayerPrompt}
            <button type="button" class="change-setting-btn" onclick={() => openChooser(viewLayer)}
              >{t('Change Setting')}</button
            >
          </div>
        {/if}

        <!-- The "My List" tab body: my relationship to this tune (status), plus notes,
             tags, and the Configure form. Defined as a snippet here and rendered inside
             the tabbed area below as the leftmost, default tab. -->
        {#snippet myListPane()}
          {#if !onList}
            <div class="tunebook-status-section tunebook-status-not-on-list">
              <div class="tunebook-status-seg tsc-notlist-seg" role="group" aria-label={t('Status')}>
                <span class="tunebook-status-opt tsc-notlist-label">{t('This tune is not on your list')}</span>
                <button type="button" class="tunebook-status-opt tsc-notlist-add" onclick={addToTunebook} disabled={adding}
                  >{adding ? t('Adding…') : t('Add')}</button
                >
              </div>
            </div>
          {:else}
            <div class="tunebook-status-section tunebook-status-{rollup.replace(/ /g, '-')}">
              <div class="tsc-block tsc-main-block">
                <div class="tsc-label-line">
                  <span class="tsc-name tunebook-status-label">{t('This tune is on your list as')}</span>
                </div>
                <Seg
                  options={STATUS_OPTIONS}
                  value={rollup}
                  idAttr="data-status"
                  styled={false}
                  segClass="tunebook-status-seg{statusSaving ? ' saving' : ''}"
                  optClass="tunebook-status-opt"
                  role="group"
                  aria-label={t('Status')}
                  onSelect={setTunebookStatus} />
              </div>
              <!-- Per-instrument toggle, centered right under the roll-up so the status
                   box stays compact. Configure/Remove moved to the notes & tags panel. -->
              {#if multiInstrument}
                <button type="button" class="tsc-expand-link tsc-expand-center" onclick={toggleStatusExpand}>
                  {piExpanded ? t('Hide Instruments') : t('View By Instrument')}
                </button>
              {/if}
              {#if multiInstrument && piExpanded}
                <div class="tsc-instruments">
                  {#each instruments as inst, i}
                    {@const st = resolveInstStatus(tune, inst)}
                    <div class="tsc-block tsc-inst-block">
                      <div class="tsc-label-line">
                        <span class="tsc-name"
                          >{instrumentName(inst.instrument)}{#if !inst.is_auto}
                            <Chip label={t('manual')} styled={false} chipClass="tsc-manual" />{/if}</span
                        >
                        {#if !inst.is_auto && st !== null}
                          <button type="button" class="tsc-remove" onclick={() => removeInstrumentTune(i)}
                            >× {t('remove')}</button
                          >
                        {/if}
                      </div>
                      {#if st === null}
                        <div class="tunebook-status-seg tsc-notlist-seg" role="group" aria-label={t('Status')}>
                          <span class="tunebook-status-opt tsc-notlist-label">{t('This tune is not on your list')}</span>
                          <button
                            type="button"
                            class="tunebook-status-opt tsc-notlist-add"
                            onclick={() => setInstrumentStatus(i, 'want to learn')}>{t('Add')}</button
                          >
                        </div>
                      {:else}
                        <Seg
                          options={STATUS_OPTIONS}
                          value={st}
                          idAttr="data-status"
                          styled={false}
                          segClass="tunebook-status-seg"
                          optClass="tunebook-status-opt"
                          role="group"
                          aria-label={t('Status')}
                          onSelect={(val) => setInstrumentStatus(i, val)} />
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}

            </div>

            <!-- Notes & tags: always visible for a tune on my list, auto-saved on blur
                 (no Save button). The Configure and Remove links live here now, below
                 them — Configure expands the extra fields (name / setting / key). -->
            <div class="tsc-personal-panel">
              {#if autoSaveState !== 'idle'}
                <span class="tsc-autosave tsc-autosave-{autoSaveState}" aria-live="polite">{autoSaveLabel}</span>
              {/if}
              <!-- Heard count (hidden for 'learned'; requires a person_tune row). Its own
                   bar above the notes now, out of the tinted status box. -->
              {#if heardVisible}
                <div class="heard-count-section">
                  <div class="heard-count-label">
                    {heardLine[0]}<span id="heard-count-value">{heardCountView}</span>{heardLine[1]}
                  </div>
                  <div class="heard-count-controls">
                    <span class="heard-count-spinner" style="display: {pendingHeard > 0 ? 'inline-block' : 'none'};">
                      <svg class="spinner-icon" viewBox="0 0 50 50">
                        <circle class="spinner-path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
                      </svg>
                    </span>
                    <button
                      class="heard-count-btn heard-count-btn-minus"
                      onclick={decrementHeardCount}
                      disabled={heardCountView === 0}>−</button
                    >
                    <button class="heard-count-btn heard-count-btn-plus" onclick={incrementHeardCount}>+</button>
                  </div>
                </div>
              {/if}
              <div class="configure-field-group">
                <textarea
                  id="notes-textarea"
                  class="notes-textarea"
                  aria-label={t('My notes')}
                  placeholder={t('Enter notes here')}
                  bind:value={pcFields.notes}
                  onblur={() => autoSavePersonal('notes')}
                ></textarea>
              </div>
              <div class="configure-field-group">
                <TagInput
                  inputId="tags-input"
                  bind:tags={pcFields.tags}
                  normalize={normalizeTag}
                  onblur={() => autoSavePersonal('tags')}
                  placeholder={t('Add tags — space or enter…')}
                />
              </div>

              <div class="tsc-action-row">
                <span class="tsc-action-left">
                  <button
                    type="button"
                    class="tsc-action-link"
                    aria-expanded={isConfigVisible}
                    onclick={toggleConfigSection}
                  >
                    <Chevron class="tsc-caret" dir={isConfigVisible ? "down" : "right"} size={14} />{t('Configure')}
                  </button>
                </span>
                <button type="button" class="tsc-action-link tsc-action-danger" onclick={removeFromMyTunes}>
                  {t('Remove From My Tunes')}
                </button>
              </div>

              <!-- Configure: the extra personal fields (name alias / setting / key),
                   the SAME on every surface (037). Still an explicit Save/Cancel. -->
              {#if isConfigVisible}
                <div id="configure-section" class="configure-section tsc-config-body">
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="name-alias-input">{t('I call this:')}</label>
                    <input
                      type="text"
                      id="name-alias-input"
                      class="configure-input"
                      autocomplete="off"
                      autocorrect="off"
                      autocapitalize="off"
                      spellcheck="false"
                      placeholder={tune.tune_name || t('Enter your name for this tune')}
                      disabled={isOffline}
                      bind:value={pcFields.name_alias}
                    />
                  </div>
                  <div class="configure-field-group-inline">
                    <div class="configure-label">{t('I play setting:')}</div>
                    <div class="configure-value setting-value" id="setting-value">
                      {pcOriginals.setting_id ? `#${pcOriginals.setting_id}` : '—'}
                      <button
                        type="button"
                        class="change-setting-btn"
                        disabled={isOffline}
                        onclick={() => openChooser({ kind: 'personal' })}>{t('Change')}</button
                      >
                    </div>
                  </div>
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="my-key-select">{t('I play this in:')}</label>
                    <select
                      id="my-key-select"
                      class="configure-select"
                      disabled={isOffline}
                      bind:value={pcFields.key}
                    >
                      {#each MUSICAL_KEYS as key}
                        <option value={key}
                          >{key || settingKeyLabel}</option
                        >
                      {/each}
                    </select>
                  </div>
                  <div class="modal-action-buttons">
                    {#if isOffline}
                      <span class="tsc-offline-hint">{t("Offline — these can't be edited (notes & tags still can)")}</span>
                    {/if}
                    <button class="btn-secondary" onclick={cancelConfigure} disabled={!pcDirty}>{t('Cancel')}</button>
                    <button
                      id="save-btn"
                      class="btn-primary"
                      onclick={savePersonal}
                      disabled={pcSaveDisabled}
                      style:background-color={saveBgFor(pcSaveState)}
                    >
                      {saveLabelFor(pcSaveState)}
                    </button>
                  </div>
                </div>
              {/if}
            </div>
          {/if}
        {/snippet}

        <!-- Admin: the canonical tune name. 037 does not touch admin mode — it is the
             one remaining place where the drawer's shape depends on which page opened
             it. Spec 036 asks the prior question of what /admin/tunes is even for. -->
        {#if mode === 'admin'}
          <div id="configure-section" class="configure-section">
            <div class="configure-field-group">
              <label class="configure-label" for="tune-name-input">{t('Tune Name:')}</label>
              <input
                type="text"
                id="tune-name-input"
                class="configure-input"
                autocomplete="off"
                autocorrect="off"
                autocapitalize="off"
                spellcheck="false"
                placeholder={t('Enter tune name')}
                bind:value={adminFields.name}
              />
            </div>
            <div class="modal-action-buttons">
              <button class="btn-secondary" onclick={() => seedAdminForm()} disabled={!adminDirty}>{t('Cancel')}</button>
              <button
                class="btn-primary"
                onclick={saveAdmin}
                disabled={adminSaveDisabled}
                style:background-color={saveBgFor(adminSaveState)}
              >
                {saveLabelFor(adminSaveState)}
              </button>
            </div>
          </div>
        {/if}

        <!-- Tabs: My List / Details / History / Played With. Which one the drawer lands
             on is a function of the viewer, never of the page that opened it: My List
             where it applies, History otherwise. (037 phrased that as "the leftmost tab";
             moving Details up made the phrasing wrong without changing the behaviour.) -->
        <div class="modal-tabs-section">
          <Tabs
            tabs={tabList}
            bind:value={activeTab}
            onValueChange={switchTab}
            styled={false}
            listClass="modal-tabs-header"
            tabClass="modal-tab" />
          <div class="modal-tabs-content">
            <!-- MY LIST — the personal status / notes / tags / configure, the drawer's
                 default tab (rendered from the snippet defined above). -->
            {#if showMyList}
              <div id="my-list-tab" class="modal-tab-pane{activeTab === 'my-list' ? ' active' : ''}">
                {@render myListPane()}
              </div>
            {/if}
            <!-- DETAILS — what this tune is AT THIS SESSION (its name, setting and key
                 here), on top of the facts about the tune itself. The session block is
                 always the session's own row: an instance's overrides are a fact of one
                 night, so they stay in History with the droplist that selects one. -->
            <div id="details-tab" class="modal-tab-pane{activeTab === 'details' ? ' active' : ''}">
              {#if inSession}
                <div class="details-sess-block">
                  <div class="details-sess-heading">{t('At {name}', { name: sessionLabel })}</div>
                  {#if canEditSessionGeneral}
                    <div class="configure-section sess-form">
                      <div class="configure-field-group-inline">
                        <label class="configure-label" for="dc-alias-input">{t('We call this:')}</label>
                        <input
                          type="text"
                          id="dc-alias-input"
                          class="configure-input"
                          autocomplete="off"
                          autocorrect="off"
                          autocapitalize="off"
                          spellcheck="false"
                          placeholder={tune.tune_name || ''}
                          bind:value={dcFields.alias}
                        />
                      </div>
                      <div class="configure-field-group-inline">
                        <div class="configure-label">{t('Our setting:')}</div>
                        <div class="configure-value setting-value" id="dc-setting-value">
                          {dcOriginals.setting_id ? `#${dcOriginals.setting_id}` : '—'}
                          <button
                            type="button"
                            class="change-setting-btn"
                            disabled={isOffline}
                            onclick={() => openChooser({ kind: 'session' })}>{t('Change')}</button
                          >
                        </div>
                      </div>
                      <div class="configure-field-group-inline">
                        <label class="configure-label" for="dc-key-select">{t('We play this in:')}</label>
                        <select id="dc-key-select" class="configure-select" bind:value={dcFields.key}>
                          {#each MUSICAL_KEYS as key}
                            <option value={key}>{key || dcInheritKeyLabel}</option>
                          {/each}
                        </select>
                      </div>
                      <div class="modal-action-buttons">
                        <button class="btn-secondary" onclick={seedDetailsForm} disabled={!dcDirty}>{t('Cancel')}</button>
                        <button
                          class="btn-primary"
                          onclick={saveDetails}
                          disabled={dcSaveDisabled}
                          style:background-color={saveBgFor(dcSaveState)}
                        >
                          {saveLabelFor(dcSaveState)}
                        </button>
                      </div>
                    </div>
                  {:else}
                    <!-- Anyone can see what a session calls a tune, including logged-out
                         visitors; only a session admin can change it. -->
                    <div class="configure-section sess-form sess-form-readonly">
                      <div class="configure-field-group-inline">
                        <div class="configure-label">{t('We call this:')}</div>
                        <div class="configure-value">{dcOriginals.alias || '—'}</div>
                      </div>
                      <div class="configure-field-group-inline">
                        <div class="configure-label">{t('Our setting:')}</div>
                        <div class="configure-value">{dcOriginals.setting_id || '—'}</div>
                      </div>
                      <div class="configure-field-group-inline">
                        <div class="configure-label">{t('We play this in:')}</div>
                        <div class="configure-value">{dcOriginals.key || '—'}</div>
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
              {#if tune.person_list_count != null}
                <div class="stat-card">
                  <div class="stat-line">
                    {listCountLine[0]}<span class="stat-number">{tune.person_list_count}</span>{listCountLine[1]}
                  </div>
                </div>
              {/if}
              <div class="stat-card">
                <div class="stat-line">
                  {tunebookLine[0]}<span class="stat-number" id="tunebook-count">{tunebookCountView}</span>{tunebookLine[1]}
                  <button
                    class="refresh-btn"
                    onclick={refreshTunebookCount}
                    disabled={refreshState === 'loading'}
                    style:background-color={refreshState === 'ok' ? '#28a745' : refreshState === 'err' ? '#dc3545' : ''}
                    style:color={refreshState === 'ok' || refreshState === 'err' ? 'white' : ''}
                    title={t('Refresh')}
                  >
                    {refreshState === 'loading' ? '⟳' : refreshState === 'ok' ? '✓' : refreshState === 'err' ? '✗' : '↻'}
                  </button>
                  {#if tune.tunebook_count_cached_date}<span class="stat-note"
                      >{t('Last Updated {date}', { date: tune.tunebook_count_cached_date })}</span
                    >{/if}
                </div>
              </div>
              <!-- Logged-count cards, in scope order: this session -> my sessions
                   (spec 033 R3) -> while I was there (R4) -> all sessions. The
                   personal pair shows for any logged-in viewer whose payload
                   carries the lens fields (stale offline snapshots may not). -->
              {#if mode === 'session' || mode === 'session_instance'}
                <div class="stat-card">
                  <div class="stat-line">
                    {loggedHereLine[0]}<span class="stat-number">{tune.times_played || 0}</span>{loggedHereLine[1]}
                  </div>
                </div>
              {/if}
              {#if mode !== 'admin' && hasMyCounts}
                <div class="stat-card">
                  <div class="stat-line">
                    {loggedMineLine[0]}<span class="stat-number">{myPlayCount}</span>{loggedMineLine[1]}
                  </div>
                </div>
                <div class="stat-card">
                  <div class="stat-line">
                    {loggedThereLine[0]}<span class="stat-number">{myAttendedCount}</span>{loggedThereLine[1]}
                  </div>
                </div>
              {/if}
              <div class="stat-card">
                <div class="stat-line">
                  {loggedAllLine[0]}<span class="stat-number">{tune.global_play_count || 0}</span>{loggedAllLine[1]}
                </div>
              </div>
              {#if mode === 'admin'}
                <div class="stat-card">
                  <div class="stat-line">
                    {repertoireLine[0]}<span class="stat-number">{tune.session_count || 0}</span>{repertoireLine[1]}
                  </div>
                </div>
              {/if}
              <!-- The canonical name and id. They used to sit at the top of the Configure
                   section, above everything you actually came to look at; they're facts
                   about the tune, so they belong with the other facts. -->
              <div class="stat-canonical">
                {t('Canonical name: {name} (#{id})', { name: tune.tune_name || t('Unknown'), id: tune.tune_id })}
              </div>

              <!-- Un-enrolling a tune from the repertoire. Only ever available for a tune
                   with NO plays here: every tune played at an instance belongs to the
                   session, and this endpoint used to break that by deleting the
                   session_tune row and orphaning the plays. With plays present the link is
                   simply absent — no explanation, it just isn't an option. -->
              {#if inSession && canRemoveFromSession}
                <div class="sess-danger-foot">
                  <button type="button" class="tsc-action-link tsc-action-danger" onclick={removeFromSession}>
                    {t('Remove From Session')}
                  </button>
                </div>
              {/if}
            </div>
            <!-- HISTORY — which plays of this tune am I looking at, and (when the answer
                 is a session or one of its instances) what am I editing. The old Session
                 tab and the old History tab were asking the same question, so they became
                 one droplist. Loads async: the drawer never waits on it. -->
            <div id="history-tab" class="modal-tab-pane{activeTab === 'history' ? ' active' : ''}">
              <!-- The droplist IS the heading. It names the scope ("At The Cobblestone")
                   and the list continues the sentence downward ("… on Tue 8 Jul"). -->
              <div class="sess-scope-row">
                <!-- Two-way bound on purpose: picking the "different session" row must be
                     able to snap the select BACK, and a one-way `value=` only writes the
                     DOM when the state actually changes. -->
                <select
                  id="sess-scope-select"
                  class="configure-select"
                  aria-label={t('Which plays of this tune')}
                  bind:value={scopeId}
                  onchange={(e) => selectSessionScope(e.currentTarget.value)}
                >
                  {#each scopeOptions as opt}
                    <option value={opt.id}>{opt.label}</option>
                  {/each}
                </select>
                {#if mySessionsState === 'loading'}
                  <span class="history-loading" aria-live="polite">{t('Loading your sessions…')}</span>
                {/if}
              </div>

              <!-- Editing lives here because an instance's name/key/setting IS a fact of
                   that performance, and a session's is a fact about that session. Neither
                   means anything across a wide lens, so both vanish for one. -->
              {#if canEditSessionLayer && !sessFormOpen}
                <button type="button" class="sess-edit-link" onclick={() => (sessFormOpen = true)}>
                  {editingInstance
                    ? t('Update name, setting or key for this tune on this date')
                    : t('Update name, setting or key for this tune at this session')}
                </button>
              {/if}

              {#if canEditSessionLayer && sessFormOpen && overridesError}
                <LoadError what={t("this date's name, setting and key")} inline onRetry={loadInstanceOverrides} />
              {:else if canEditSessionLayer && sessFormOpen}
                <div class="configure-section sess-form">
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="sess-alias-input">
                      {editingInstance ? t('We called it:') : t('We call this:')}
                    </label>
                    <input
                      type="text"
                      id="sess-alias-input"
                      class="configure-input"
                      autocomplete="off"
                      autocorrect="off"
                      autocapitalize="off"
                      spellcheck="false"
                      placeholder={editingInstance ? tune.alias || tune.tune_name || '' : tune.tune_name || ''}
                      bind:value={sessFields.alias}
                    />
                  </div>
                  <div class="configure-field-group-inline">
                    <div class="configure-label">
                      {editingInstance ? t('We played setting:') : t('Our setting:')}
                    </div>
                    <div class="configure-value setting-value" id="sess-setting-value">
                      {sessOriginals.setting_id ? `#${sessOriginals.setting_id}` : '—'}
                      <button
                        type="button"
                        class="change-setting-btn"
                        disabled={isOffline}
                        onclick={() =>
                          openChooser(editingInstance ? { kind: 'instance', instanceId: scopeId } : { kind: 'session' })}
                        >{t('Change')}</button
                      >
                    </div>
                  </div>
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="sess-key-select">
                      {editingInstance ? t('We played it in:') : t('We play this in:')}
                    </label>
                    <select id="sess-key-select" class="configure-select" bind:value={sessFields.key}>
                      {#each MUSICAL_KEYS as key}
                        <option value={key}>{key || inheritKeyLabel}</option>
                      {/each}
                    </select>
                  </div>
                  <div class="modal-action-buttons">
                    <button
                      class="btn-secondary"
                      onclick={() => {
                        seedSessionForm()
                        sessFormOpen = false
                      }}
                    >
                      {t('Cancel')}
                    </button>
                    <button
                      class="btn-primary"
                      onclick={saveSession}
                      disabled={sessSaveDisabled}
                      style:background-color={saveBgFor(sessSaveState)}
                    >
                      {saveLabelFor(sessSaveState)}
                    </button>
                  </div>
                </div>
              {:else if editableScope && inSession && !canEditSessionLayer}
                <!-- Read-only: anyone can see what a session plays, including logged-out
                     visitors. Editing the session's own row is admin-only; an instance is
                     open to any member. -->
                <div class="configure-section sess-form sess-form-readonly">
                  <div class="configure-field-group-inline">
                    <div class="configure-label">{editingInstance ? t('We called it:') : t('We call this:')}</div>
                    <div class="configure-value">{sessOriginals.alias || '—'}</div>
                  </div>
                  <div class="configure-field-group-inline">
                    <div class="configure-label">{editingInstance ? t('We played setting:') : t('Our setting:')}</div>
                    <div class="configure-value">{sessOriginals.setting_id || '—'}</div>
                  </div>
                  <div class="configure-field-group-inline">
                    <div class="configure-label">{editingInstance ? t('We played it in:') : t('We play this in:')}</div>
                    <div class="configure-value">{sessOriginals.key || '—'}</div>
                  </div>
                </div>
              {/if}

              <!-- ...and under it, the plays themselves. -->
              <div class="hist-controls">
                {#if summaryLine}<span class="hist-summary">{summaryLine}</span>{/if}
                <!-- The hint and the filter travel together as a right-anchored pair, so the
                     checkbox holds its place whether or not either neighbour is there. (It
                     can't go to the RIGHT of the checkbox: that's the drawer's edge, so it
                     would overflow — or shove the control, which is the jump we just fixed.) -->
                <span class="hist-right">
                  {#if attendedHint}
                    <span class="hist-attended-hint" aria-live="polite">{t('You attended')}</span>
                  {/if}
                  {#if loggedIn && !editingInstance && showAttendedFilter}
                    <label class="hist-filter">
                      <input type="checkbox" checked={attendedOnly} onchange={toggleAttendedOnly} />
                      {t('Only when I was there')}
                    </label>
                  {/if}
                </span>
              </div>

              {#if editingInstance}
                <!-- One night: the history IS where it came round. No request needed — the
                     payload already carries the coordinates. -->
                <div id="history-list-container">
                  {#if positions.length}
                    <div class="history-list">
                      {#each positions as p}
                        <div class="history-item">
                          <div class="history-instance-name"><a href={p.href}>{p.label}</a></div>
                        </div>
                      {/each}
                    </div>
                  {:else}
                    <div class="no-history">{t('Not played that night.')}</div>
                  {/if}
                </div>
              {:else}
                <div id="history-list-container">
                  {#if historyState.status === 'ready'}
                    {@const playInstances = historyState.data.play_instances || []}
                    {#if playInstances.length === 0}
                      <div class="no-history">
                        {attendedOnly
                          ? t("You weren't there for any of this tune's plays here.")
                          : t('No play history recorded yet.')}
                      </div>
                    {:else}
                      <div class="history-list">
                        {#each playInstances as instance}
                          <div class="history-item">
                            <div class="history-instance-name">
                              <!-- Scoped to one session the name is redundant, so the row is
                                   instance_label ("2026-06-06 - Advanced Session @ Jim Bowie");
                                   across sessions it's full_name, which prefixes the session.
                                   Both carry the place at a festival, where the date names
                                   several different rooms (spec 006). -->
                              <a href={instance.link}>
                                {scopeId === 'general'
                                  ? instance.instance_label || instance.date || t('Unknown')
                                  : instance.full_name || instance.date || t('Unknown')}
                              </a>
                              {#if instance.attended}
                                <!-- A quiet mark, not a label: it's a footnote on the row, not
                                     the point of it. `title` covers hover; tapping shows the
                                     words beside the filter and fades them out, since a title
                                     never appears on touch. -->
                                <button
                                  type="button"
                                  class="history-attended-mark"
                                  title={t('You were there')}
                                  aria-label={t('You were there')}
                                  onclick={(e) => {
                                    e.preventDefault()
                                    showAttendedHint()
                                  }}>✓</button
                                >
                              {/if}
                            </div>
                            {#if instance.set_number && instance.position_in_set}
                              <div class="history-position">
                                {t('Set {set}, Tune {position}', { set: instance.set_number, position: instance.position_in_set })}
                              </div>
                            {/if}
                            {#if instance.setting_id_override}
                              <div class="history-setting">{t('Setting: #{id}', { id: instance.setting_id_override })}</div>
                            {/if}
                          </div>
                        {/each}
                      </div>
                      {#if historyState.data.truncated}
                        <div class="history-truncated">{t('Showing the 100 most recent sessions.')}</div>
                      {/if}
                    {/if}
                  {:else if historyState.status === 'offline'}
                    <div class="no-history">{t("Play history isn't available offline.")}</div>
                  {:else if historyState.status === 'error'}
                    <LoadError what={t('play history')} onRetry={loadHistory} />
                  {:else if historyState.status === 'none'}
                    <div class="no-history">{t('No play history recorded yet.')}</div>
                  {:else}
                    <div class="history-loading">{t('Loading play history…')}</div>
                  {/if}
                </div>
              {/if}
            </div>
            <div id="played-with-tab" class="modal-tab-pane{activeTab === 'played-with' ? ' active' : ''}">
              {#if playedWithOptions.length > 1}
                <Seg
                  options={playedWithOptions.map((o) => ({ id: o.key, label: o.label }))}
                  value={playedWithScopeKey}
                  idAttr="data-scope"
                  styled={false}
                  segClass="history-scope-toggle"
                  optClass="played-with-scope-btn history-scope-btn"
                  onSelect={setPlayedWithScope} />
              {/if}
              <div id="played-with-container">
                {#if playedWithState.status === 'ready'}
                  {@const pwTunes = playedWithState.data.tunes || []}
                  {#if pwTunes.length === 0}
                    <div class="no-history">
                      {playedWithScopeKey === 'session'
                        ? t('This tune has not been played in a set with any other tune at this session yet.')
                        : t('This tune has not been played in a set with any other tune yet.')}
                    </div>
                  {:else}
                    <div class="played-with-list">
                      {#each pwTunes as pw}
                        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                        <div class="played-with-item" data-tune-id={pw.tune_id} onclick={() => openPlayedWithTune(pw)}>
                          <span class="played-with-name">{pw.name}</span>
                          <span class="played-with-count">{pw.count}</span>
                        </div>
                      {/each}
                    </div>
                  {/if}
                {:else if playedWithState.status === 'error'}
                  <LoadError what={t('played-with tunes')} onRetry={loadPlayedWith} />
                {:else if playedWithState.status === 'none'}
                  <div class="no-history">{t('No set history recorded yet.')}</div>
                {:else}
                  <div class="history-loading">{t('Loading tunes…')}</div>
                {/if}
              </div>
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<Dialog
  bind:open={removeMyTunesOpen}
  title={t('Remove this tune from your list?')}
  confirmLabel={t('Remove tune')}
  busyLabel={t('Removing…')}
  destructive={true}
  onConfirm={doRemoveFromMyTunes} />

<Dialog
  bind:open={removeSessionOpen}
  title={t('Remove this tune from the session tune list?')}
  confirmLabel={t('Remove tune')}
  busyLabel={t('Removing…')}
  destructive={true}
  onConfirm={doRemoveFromSession} />

<!-- "At a different session ..." — re-scopes the whole drawer to another session I'm a
     member of, so I can see what THEY do with this tune. Visitor sessions are excluded:
     a session you dropped into once isn't one whose repertoire you have a view on. -->
<!-- The setting chooser: every setting of the tune, full notation, for one layer. -->
{#if tune}
  <SettingChooser
    bind:open={chooserOpen}
    tuneId={tune.tune_id}
    tuneName={displayName}
    tuneType={tune.tune_type || ''}
    currentSettingId={layerSettingId(chooserLayer)}
    heading={chooserHeading}
    onChoose={chooseSetting} />
{/if}

<SessionPicker
  bind:open={sessionPickerOpen}
  sessions={mySessions}
  currentPath={sessionScope?.path ?? null}
  onSelect={scopeToSession} />

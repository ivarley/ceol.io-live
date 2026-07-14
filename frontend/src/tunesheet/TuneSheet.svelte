<script>
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
  import { onMount } from 'svelte'
  import { Chip, Dialog, Seg, SessionPicker, Tabs, toast } from '../lib/index.js'
  import {
    MUSICAL_KEYS,
    OTHER_SESSION,
    normalizeShowConfig,
    detailUrl,
    getDisplayName,
    getAkaName,
    sessionScopeOptions,
    instancePositions,
    initialSessionScope,
    extractSettingId,
    validateSettingInput,
    historyScopeOptions,
    playedWithScopeOptions,
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
  } from './logic.js'

  // ---- modal state -----------------------------------------------------------
  let visible = $state(false)
  let showCls = $state(false)
  let phase = $state('loading') // 'loading' | 'error' | 'ready'
  let errorMsg = $state('')
  let config = $state(null) // normalized show() config {tuneId, ptid, scope, callbacks, hints}
  let viewer = $state(null) // payload viewer block {logged_in, is_admin, is_session_admin}
  let tune = $state(null) // payload session_tune block (mutated optimistically)
  let mergedFrom = $state(null) // healed merged-tune permalink (spec 030)
  let modalShowTime = 0 // scrim-click guard (500ms)
  let hideTimer = null

  // Reset on every show(): the per-instrument roll-up must not stay expanded
  // when the drawer moves to another tune (or reopens).
  let piExpanded = $state(false)
  let isConfigVisible = $state(false)
  let activeTab = $state('stats')
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
  let pcFields = $state({ name_alias: '', setting: '', key: '', notes: '' })
  let pcOriginals = $state({})
  let pcSettingError = $state('')
  let pcSaveState = $state('idle') // idle | saving | saved | error
  let pcFetchState = $state('idle') // idle | loading | ok | warn | err

  // Session: session_tune when the droplist is on 'general', else that instance's
  // session_instance_tune. One form; the droplist picks its target, so you never see
  // both layers editable at once. The form itself is collapsed until asked for — the
  // tab's job is mostly to TELL you things (how often, in which sets), and editing is
  // the rarer errand.
  let sessScopeId = $state('general') // 'general' | String(session_instance_id)
  // The last value the droplist was really ON. The "At a different session ..." row is an
  // errand, not a target: picking it opens the picker and the select must snap back, or a
  // cancelled pick strands it on a row that means nothing. Plain variable, not $state —
  // it exists only to be read inside the change handler.
  let lastRealScope = 'general'
  let sessFields = $state({ alias: '', setting: '', key: '' })
  let sessOriginals = $state({})
  let sessSettingError = $state('')
  let sessSaveState = $state('idle')
  let sessFetchState = $state('idle')
  let sessFormOpen = $state(false)

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

  // History / Played With tabs: fetched lazily on first view, cached per scope
  // for this modal open. Value: {status: 'loading'|'ready'|'error'|'none', data}
  // A null scope key means "the mode's default" (mode is only known post-fetch).
  let historyScope = $state(null)
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
  const sessOptions = $derived(sessionScopeOptions(playedInstances, sessionScope?.session_name))
  const editingInstance = $derived(sessScopeId !== 'general' && sessScopeId !== OTHER_SESSION)

  // "Set 3, tune 2" — where the tune came round that night, each linking into the logger
  // at that exact record. Usually one; a tune played twice that night has two.
  const positions = $derived(
    editingInstance && tune
      ? instancePositions(playedInstances, sessScopeId, sessionScope.path, tune.tune_id)
      : []
  )

  // Who may write which layer. The session's own alias/setting/key is the session
  // making a canonical statement about its repertoire (admins); a specific instance is
  // a record of what happened in a room the member was in (any member).
  const canEditSessionLayer = $derived(
    editingInstance ? !!sessionScope?.can_edit_instance : !!sessionScope?.can_edit_session
  )
  // Un-enrolling only ever means "a tune that was never actually played here". With
  // plays present the link is simply absent — no explanation, it just isn't an option.
  const canRemoveFromSession = $derived(!!sessionScope?.can_remove_from_session)

  // The empty option in a key select isn't "blank", it's "inherit" — so it names what
  // it would fall back to. An instance falls back to the session's key; the session
  // falls back to the setting's own key.
  const inheritKeyLabel = $derived.by(() => {
    if (!tune) return '(not specified)'
    if (editingInstance) {
      const fallback = tune.key || tune.setting_key
      return fallback ? `(as usual — ${fallback})` : '(as usual)'
    }
    return tune.setting_key ? `(the setting's key — ${tune.setting_key})` : '(not specified)'
  })

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
  const sessionLabel = $derived(sessionScope?.session_name || 'this session')

  // What the notation section renders from: the played setting, or — while the
  // mismatch note's toggle is on — the viewer's own setting.
  const notationSource = $derived(showingMyVersion && myNotation ? { ...tune, ...myNotation } : tune)
  const notation = $derived(notationSource ? notationInfo(notationSource) : null)
  const notationView = $derived(
    notationSource ? notationDisplay(notationSource, notationMode, notationSize) : null
  )
  const thesessionLink = $derived(notationSource ? theSessionUrl(notationSource) : '')
  const abctoolsLink = $derived(notationSource ? abcToolsUrl(notationSource) : '')

  const hasCachedNotation = $derived(
    !!(tune && (tune.abc || tune.incipit_abc || tune.image || tune.incipit_image))
  )
  // The settings/cache endpoint is login-required, so the Generate Notation
  // affordance only shows for logged-in viewers (payload-derived, so a call
  // site can never forget the flag again).
  const canGenerateNotation = $derived(!!tune && loggedIn)

  // Offline, the three override fields go read-only and Notes stays live — a phone in
  // a pub basement is exactly where someone types a note about a tune, and set_notes
  // is already an offline op. So a Save while offline can only ever be committing
  // notes, and it goes through the queue instead of the PUT.
  // Tracked directly rather than via svelte/reactivity/window, whose barrel drags in
  // DevicePixelRatio -> matchMedia, which jsdom doesn't have.
  const isOffline = $derived(!onlineNow)

  const settingLabelFor = (value, originalId) => {
    const v = (value || '').trim()
    const same = (!v && !originalId) || extractSettingId(v) === originalId
    return hasCachedNotation && same ? 'Refresh' : 'Fetch'
  }
  const pcFetchLabel = $derived(settingLabelFor(pcFields.setting, pcOriginals.setting_id || null))
  const sessFetchLabel = $derived(settingLabelFor(sessFields.setting, sessOriginals.setting_id || null))

  const pcDirty = $derived.by(() => {
    if (!tune || !onList) return false
    return (
      pcFields.name_alias !== pcOriginals.name_alias ||
      extractSettingId(pcFields.setting) !== (pcOriginals.setting_id || null) ||
      pcFields.key !== pcOriginals.key ||
      pcFields.notes !== pcOriginals.notes
    )
  })
  const pcSaveDisabled = $derived(!pcDirty || pcSaveState !== 'idle' || !!pcSettingError)

  const sessDirty = $derived.by(() => {
    if (!tune || !inSession) return false
    return (
      sessFields.alias !== sessOriginals.alias ||
      extractSettingId(sessFields.setting) !== (sessOriginals.setting_id || null) ||
      sessFields.key !== sessOriginals.key
    )
  })
  const sessSaveDisabled = $derived(!sessDirty || sessSaveState !== 'idle' || !!sessSettingError)

  const adminDirty = $derived(!!tune && adminFields.name !== adminOriginals.name)
  const adminSaveDisabled = $derived(!adminDirty || adminSaveState !== 'idle')

  const saveLabelFor = (s) =>
    s === 'saving' ? 'Saving...' : s === 'saved' ? 'Saved!' : s === 'error' ? 'Error' : 'Save'
  const saveBgFor = (s) => (s === 'saved' ? '#28a745' : s === 'error' ? '#dc3545' : '')

  const historyOptions = $derived(historyScopeOptions(mode, scope, loggedIn))
  const playedWithOptions = $derived(playedWithScopeOptions(mode, scope, loggedIn))
  // null = "the mode's default scope" (mode is only known once the payload lands)
  const historyScopeKey = $derived(historyScope ?? historyOptions[0].key)
  const playedWithScopeKey = $derived(playedWithScope ?? playedWithOptions[0].key)
  const historyState = $derived(historyCache[historyScopeKey] || { status: 'loading' })
  const playedWithState = $derived(playedWithCache[playedWithScopeKey] || { status: 'loading' })

  // Tabs. Session is LEFTMOST when a session is in scope, and the drawer always opens
  // on its leftmost tab — which is the whole reason the old "which tab do we land on"
  // fork disappears: Session when scoped, Stats when not. One rule, no per-surface
  // special case. Labelled just "Session" so four tabs still fit a phone.
  const tabList = $derived([
    ...(inSession ? [{ id: 'session', label: 'Session' }] : []),
    { id: 'stats', label: 'Stats' },
    { id: 'history', label: 'History' },
    { id: 'played-with', label: 'Played With' },
  ])
  const defaultTab = $derived(tabList[0].id)

  // ---- form seeding -------------------------------------------------------------

  // Personal config: the SAME fields on every surface. A session never replaces them.
  function seedPersonalForm() {
    pcOriginals = {
      name_alias: (pts && pts.name_alias) || '',
      setting_id: (pts && pts.setting_id) || '',
      key: (pts && pts.key) || '',
      notes: (pts && pts.notes) || '',
    }
    pcFields = {
      name_alias: pcOriginals.name_alias,
      setting: String(pcOriginals.setting_id || ''),
      key: pcOriginals.key,
      notes: pcOriginals.notes,
    }
    pcSettingError = ''
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
      const isScoped = String(sessionScope.instance ?? '') === String(sessScopeId)
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
      setting: String(sessOriginals.setting_id || ''),
      key: sessOriginals.key,
    }
    sessSettingError = ''
    sessSaveState = 'idle'
    sessFetchState = 'idle'
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
    tune = data.session_tune
    mergedFrom = null

    learnStatusOriginal = (tune.person_tune_status && tune.person_tune_status.learn_status) || ''
    // The Session form points at the instance the drawer was opened in (the live
    // logger), else ?siid= / ?date=, else the session in general.
    sessScopeId = tune.session_scope
      ? initialSessionScope(
          tune.session_scope.played_instances,
          tune.session_scope.instance,
          typeof window !== 'undefined' ? window.location.search : ''
        )
      : 'general'
    lastRealScope = sessScopeId
    sessFormOpen = false
    seedPersonalForm()
    seedSessionForm()
    seedAdminForm()

    refreshState = 'idle'
    statusSaving = false
    myNotation = null
    showingMyVersion = false
    // Personal config starts collapsed; admin's canonical-name editor is always open.
    isConfigVisible = mode === 'admin'
    // The drawer opens on its LEFTMOST tab — Session when a session is in scope, Stats
    // otherwise. A re-apply can ask to keep the tab the user was on (the in-place
    // add -> my_tunes upgrade).
    activeTab = opts.keepTab || config.initialTab || defaultTab
    if (activeTab === 'history') loadHistory()
    else if (activeTab === 'played-with') loadPlayedWith()
    // An explicit history/played-with scope choice survives a re-apply only if
    // the (possibly changed) mode still offers it.
    if (historyScope != null && !historyScopeOptions(mode, scope, loggedIn).some((o) => o.key === historyScope))
      historyScope = null
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

  function showErr(message) {
    errorMsg = message
    phase = 'error'
  }

  // Offline fallback: derive the payload from the locally-cached bundle +
  // not-yet-synced ops (offlinePayload synthesizes the viewer/on-list facts) so
  // the drawer works without a connection.
  function renderTuneFromOffline(cfg, errMsg) {
    if (!window.CeolOffline || !cfg.tuneId) {
      showErr(errMsg || 'Failed to load tune details')
      return
    }
    const pending =
      window.MyTunesOffline && window.MyTunesOffline.pending
        ? window.MyTunesOffline.pending()
        : Promise.resolve([])
    Promise.all([window.CeolOffline.getTune(cfg.tuneId), pending])
      .then(([cached, ops]) => {
        if (!cached) {
          showErr(errMsg || 'Failed to load tune details')
          return
        }
        applyPayload(offlinePayload(cached, ops, cfg.tuneId))
      })
      .catch(() => showErr(errMsg || 'Failed to load tune details'))
  }

  // ---- public API (wired to window.TuneDetailModal by main.js) ------------------

  export function show(rawCfg) {
    const cfg = normalizeShowConfig(rawCfg)
    config = cfg
    historyCache = {}
    playedWithCache = {}
    historyScope = null
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
        renderTuneFromOffline(cfg, 'Failed to load tune details')
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
          showErr('Failed to load tune details')
        }
      })
      .catch((error) => {
        // A dead ptid deep-link (the row was conflict-deleted by a tune merge,
        // spec 030) degrades to a notice + a clean URL rather than a raw error.
        if (error.status === 404) {
          removeUrlTuneParam('my_tunes')
          showErr(
            'This tunebook entry no longer exists — it may have been merged into another tune. Check your tunebook list for the merged tune.'
          )
          return
        }
        renderTuneFromOffline(cfg, 'Failed to load tune details')
      })
  }

  export function close() {
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

  function onKeydown(event) {
    if (event.key === 'Escape' && visible) close()
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
      .catch(() => {
        statusSaving = false
        applyUi(prevStatus, prevOverrides) // revert
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
      () => {
        setInstrumentOverrides(tune, prev)
        notifyStatusChange()
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
      () => {
        setInstrumentOverrides(tune, prev)
        notifyStatusChange()
      }
    )
  }

  // Add the tune to the user's list as 'want to learn'. Online, the refetched
  // payload's on_list flips the derived mode, so a my-tunes-origin drawer
  // upgrades to the full variant naturally — no special re-show plumbing.
  export function addToTunebook() {
    const tuneId = tune.tune_id
    const keepTab = activeTab // survives the refetch's per-render tab reset
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
            sessionStorage.setItem('myTunesToast', 'Added to your tunes. It will sync when you are back online.')
          } catch (e) {}
          window.location.href = '/my-tunes'
          return
        }
        // Online: reload the payload; the new person_tune identity notifies the
        // host (chained adds live-update the underlying list) exactly once —
        // the derived-mode upgrade is just this re-apply, it never re-notifies.
        fetch(detailUrl(tuneId, scope))
          .then((response) => response.json())
          .then((data) => {
            if (data.success) {
              applyPayload(data, { keepTab })
              notifyStatusChange()
            }
          })
      })
      .catch((error) => {
        console.error('Error adding to tunebook:', error)
        toast('Failed to add tune to your list', 'error')
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
        console.error('Error setting heard count:', error)
        setLocal(currentCount)
        pendingHeard = Math.max(0, pendingHeard - 1)
      })
  }

  export function incrementHeardCount() {
    bumpHeard(1)
  }
  export function decrementHeardCount() {
    bumpHeard(-1)
  }

  // ---- configure section / save --------------------------------------------------------

  // Both forms have a setting input; each validates its own.
  function validateSettingField(which) {
    const form = which === 'session' ? sessFields : pcFields
    const setError = (msg) => {
      if (which === 'session') sessSettingError = msg
      else pcSettingError = msg
    }
    const value = (form.setting || '').trim()
    if (!value) {
      setError('')
      return
    }
    const validation = validateSettingInput(value, tune.tune_id)
    if (!validation.valid) {
      setError(validation.error)
      return
    }
    setError('')
    // A pasted thesession.org URL collapses to just the setting number.
    if (validation.settingId !== null && value !== validation.settingId.toString()) {
      form.setting = validation.settingId.toString()
    }
  }

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
      .catch(() => toast('Could not load your version of this tune', 'error'))
  }

  // The Session form's PUT target follows the droplist: 'general' writes the session's
  // own row, an instance writes that night's.
  function sessionEndpoint() {
    if (!inSession || !tune) return ''
    const path = sessionScope.path
    return editingInstance
      ? `/api/sessions/${path}/${sessScopeId}/tunes/${tune.tune_id}`
      : `/api/sessions/${path}/tunes/${tune.tune_id}`
  }

  const flashSaveState = (set, state) => {
    set(state)
    if (state === 'error') setTimeout(() => set('idle'), 2000)
  }

  // ---- personal config (person_tune) ------------------------------------------------

  export function savePersonal() {
    if (!tune || !config || pcSaveDisabled) return
    const ptid = (pts && pts.person_tune_id) || config.ptid
    if (!ptid) return

    // Offline, only notes can be dirty (the other three are read-only), so the save is
    // necessarily a notes change — and that has an op, so it survives the basement.
    if (isOffline) {
      const notes = pcFields.notes.trim() || null
      pcSaveState = 'saving'
      submitMyTunesOp({ type: 'set_notes', tune_id: tune.tune_id, notes })
        .then(() => {
          if (tune.person_tune_status) tune.person_tune_status.notes = notes
          pcSaveState = 'saved'
          seedPersonalForm()
          setTimeout(() => (pcSaveState = 'idle'), 1200)
        })
        .catch(() => flashSaveState((s) => (pcSaveState = s), 'error'))
      return
    }

    const updates = {}
    if (pcFields.name_alias !== pcOriginals.name_alias) updates.name_alias = pcFields.name_alias.trim() || null
    const newSettingId = extractSettingId(pcFields.setting)
    if (newSettingId !== (pcOriginals.setting_id || null)) updates.setting_id = newSettingId
    if (pcFields.key !== pcOriginals.key) updates.key = pcFields.key || null
    if (pcFields.notes !== pcOriginals.notes) updates.notes = pcFields.notes.trim() || null
    if (!Object.keys(updates).length) return

    pcSaveState = 'saving'
    fetch(`/api/my-tunes/${ptid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new Error(data.error || data.message)
        pcSaveState = 'saved'
        if (tune.person_tune_status) Object.assign(tune.person_tune_status, updates)
        seedPersonalForm()
        pcSaveState = 'saved'
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (pcSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        console.error('Error saving personal config:', error)
        flashSaveState((s) => (pcSaveState = s), 'error')
      })
  }

  // ---- session config (session_tune / session_instance_tune) --------------------------

  export function saveSession() {
    if (!tune || !config || sessSaveDisabled) return
    const endpoint = sessionEndpoint()
    if (!endpoint) return

    const updates = {}
    const newSettingId = extractSettingId(sessFields.setting)
    if (editingInstance) {
      if (sessFields.alias !== sessOriginals.alias) updates.name = sessFields.alias.trim() || null
      if (newSettingId !== (sessOriginals.setting_id || null)) updates.setting_override = newSettingId
      if (sessFields.key !== sessOriginals.key) updates.key_override = sessFields.key || null
    } else {
      if (sessFields.alias !== sessOriginals.alias) updates.alias = sessFields.alias.trim() || null
      if (newSettingId !== (sessOriginals.setting_id || null)) updates.setting_id = newSettingId
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
        if (!data.success) throw new Error(data.message || data.error)
        sessSaveState = 'saved'
        // Mirror onto the payload so the form's originals rebuild from what we wrote,
        // and the title/aka recompute against the new session alias.
        if (editingInstance) {
          if (String(sessionScope.instance ?? '') === String(sessScopeId)) Object.assign(tune, updates)
        } else {
          Object.assign(tune, updates)
          if (tune.session_scope) tune.session_scope.in_repertoire = true
        }
        seedSessionForm()
        sessSaveState = 'saved'
        // The instance response carries the saved records, so a live logger can patch
        // its rows now rather than wait for the change to come back round the feed.
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (sessSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        console.error('Error saving session config:', error)
        toast(String(error.message || 'Could not save'), 'error')
        flashSaveState((s) => (sessSaveState = s), 'error')
      })
  }

  // ---- "At a different session ..." -------------------------------------------------

  function openSessionPicker() {
    sessionPickerOpen = true
    if (mySessions.length) return
    fetch('/api/my-sessions?limit=100')
      .then((r) => r.json())
      .then((d) => {
        if (d.success) mySessions = d.sessions || []
      })
      .catch(() => toast('Could not load your sessions', 'error'))
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
    const cfg = { ...config, scope: { session: session.path }, initialTab: 'session' }
    config = cfg
    sessScopeId = 'general'
    lastRealScope = 'general'
    sessFormOpen = false
    phase = 'loading'
    fetch(detailUrl(tune.tune_id, cfg.scope))
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) throw new Error(data.message || 'Could not load that session')
        applyPayload(data, { keepTab: 'session' })
      })
      .catch((error) => {
        console.error('Error re-scoping to session:', error)
        showErr(String(error.message || 'Could not load that session'))
      })
  }

  /** The context line's link: over to History, already filtered to this session. */
  export function showSessionHistory() {
    switchTab('history')
    setHistoryScope('session')
  }

  // Point the Session form at a different target. 'general' is already in the payload;
  // a specific instance has to be fetched, since the payload only ever describes the
  // instance the drawer was opened in.
  export function selectSessionScope(id) {
    // The last row isn't a target, it's an errand: open the picker and snap the select
    // back, so a cancelled pick doesn't strand it on a row that means nothing.
    if (String(id) === OTHER_SESSION) {
      openSessionPicker()
      sessScopeId = lastRealScope
      return
    }

    sessScopeId = String(id)
    lastRealScope = sessScopeId
    sessFormOpen = false
    if (!editingInstance || String(sessionScope?.instance ?? '') === String(sessScopeId)) {
      seedSessionForm()
      return
    }
    sessFields = { alias: '', setting: '', key: '' }
    sessOriginals = { alias: '', setting_id: '', key: '' }
    fetch(detailUrl(tune.tune_id, { session: sessionScope.path, instance: sessScopeId }))
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) return
        const st = data.session_tune
        sessOriginals = {
          alias: st.name || '',
          setting_id: st.setting_override || '',
          key: st.key_override || '',
        }
        sessFields = {
          alias: sessOriginals.alias,
          setting: String(sessOriginals.setting_id || ''),
          key: sessOriginals.key,
        }
      })
      .catch((error) => console.error('Error loading instance overrides:', error))
  }

  // ---- admin (canonical tune name) — untouched by 037; see spec 036 ---------------------

  export function saveAdmin() {
    if (!tune || adminSaveDisabled) return
    const name = adminFields.name.trim()
    if (!name) {
      toast('Tune name cannot be empty', 'error')
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
        if (!data.success) throw new Error(data.error || data.message)
        adminSaveState = 'saved'
        tune.tune_name = name
        seedAdminForm()
        adminSaveState = 'saved'
        if (config.onSave && typeof config.onSave === 'function') config.onSave(data)
        setTimeout(() => (adminSaveState = 'idle'), 1200)
      })
      .catch((error) => {
        console.error('Error saving tune name:', error)
        flashSaveState((s) => (adminSaveState = s), 'error')
      })
  }

  // Fetch and cache a setting from TheSession.org, persist the setting id to whichever
  // form asked, then re-render with the fetched notation. Resolves true when notation
  // was fetched (even if the setting-id save then warned), so generateNotation can
  // surface failures its own way.
  //
  // `which` is 'personal' | 'session' | 'none' — 'none' just caches the notation
  // (Generate Notation for a viewer with no form to save into).
  export function fetchSetting(which = 'personal') {
    if (!tune) return Promise.resolve(false)
    const usingSession = which === 'session'
    const state = () => (usingSession ? sessFetchState : pcFetchState)
    const setState = (v) => (usingSession ? (sessFetchState = v) : (pcFetchState = v))
    if (state() === 'loading') return Promise.resolve(false)

    const tuneId = tune.tune_id
    const form = usingSession ? sessFields : pcFields
    const settingIdValue = which === 'none' ? '' : (form.setting || '').trim()
    setState('loading')

    const feedback = (s) => {
      setState(s)
      setTimeout(() => {
        if (state() === s) setState('idle')
      }, 2000)
    }

    let apiUrl = `/api/tunes/${tuneId}/settings/cache`
    if (settingIdValue) {
      const validation = validateSettingInput(settingIdValue, tuneId)
      apiUrl += `?setting_id=${validation.settingId || settingIdValue}`
    }

    // Where the chosen setting id gets persisted. Personal writes person_tune; session
    // writes whichever layer the droplist points at; 'none' writes nowhere.
    const target = () => {
      if (which === 'none') return null
      if (usingSession) {
        const endpoint = sessionEndpoint()
        if (!endpoint || !canEditSessionLayer) return null
        return { endpoint, body: (id) => (editingInstance ? { setting_override: id } : { setting_id: id }) }
      }
      const ptid = (pts && pts.person_tune_id) || config?.ptid
      if (!ptid) return null
      return { endpoint: `/api/my-tunes/${ptid}`, body: (id) => ({ setting_id: id }) }
    }

    return fetch(apiUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          console.error('Error fetching setting:', data.message)
          feedback('err')
          return false
        }
        const fetchedSettingId = data.setting.setting_id
        // The staff always shows what was just fetched, so drop any "my version" view.
        showingMyVersion = false
        myNotation = null
        tune.abc = data.setting.abc
        tune.incipit_abc = data.setting.incipit_abc
        tune.image = data.setting.image
        tune.incipit_image = data.setting.incipit_image
        const info = notationInfo(tune)
        notationMode = info.initialMode
        notationSize = 'incipit'

        const t = target()
        if (!t) {
          feedback('ok')
          return true
        }
        const body = t.body(fetchedSettingId)
        return fetch(t.endpoint, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
          .then((response) => response.json())
          .then((saveData) => {
            if (saveData.success) {
              if (usingSession) {
                Object.assign(tune, body)
                seedSessionForm()
              } else {
                if (tune.person_tune_status) Object.assign(tune.person_tune_status, body)
                seedPersonalForm()
              }
              feedback('ok')
            } else {
              console.error('Error saving setting_id:', saveData.error || saveData.message)
              feedback('warn')
            }
            return true
          })
          .catch((error) => {
            console.error('Error saving setting_id:', error)
            feedback('warn')
            return true
          })
      })
      .catch((error) => {
        console.error('Error:', error)
        feedback('err')
        return false
      })
  }

  // "Generate Notation" (shown in the notation area when nothing is cached): the SAME
  // action as a form's Fetch/Refresh button. It saves the setting to my list when I
  // have one, and otherwise just caches the notation.
  export function generateNotation() {
    fetchSetting(onList ? 'personal' : 'none').then((ok) => {
      if (!ok) {
        toast('Could not fetch notation for this tune', 'error')
        return
      }
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
      toast('Unable to remove tune', 'error')
      return
    }
    fetch(`/api/my-tunes/${personTuneId}`, { method: 'DELETE' })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          removeUrlTuneParam(mode)
          if (config.onSave && typeof config.onSave === 'function') config.onSave()
          close()
        } else {
          console.error('Error removing tune:', data.error)
          toast('Failed to remove tune from your list', 'error')
        }
      })
      .catch((error) => {
        console.error('Error:', error)
        toast('Failed to remove tune from your list', 'error')
      })
  }

  export function removeFromSession() {
    removeSessionOpen = true
  }

  function doRemoveFromSession() {
    const sessionPath = scope?.session
    const tuneId = tune?.tune_id
    if (!sessionPath || !tuneId) {
      toast('Unable to remove tune from session', 'error')
      return
    }
    fetch(`/api/sessions/${sessionPath}/tunes/${tuneId}`, { method: 'DELETE' })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          removeUrlTuneParam(mode)
          if (config.onSave && typeof config.onSave === 'function') config.onSave()
          close()
        } else {
          console.error('Error removing tune from session:', data.message)
          toast(data.message || 'Failed to remove tune from session', 'error')
        }
      })
      .catch((error) => {
        console.error('Error:', error)
        toast('Failed to remove tune from session', 'error')
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
          console.error('Error refreshing tunebook count:', data.error)
        }
      })
      .catch((error) => {
        console.error('Error:', error)
        refreshState = 'err'
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

  export function setHistoryScope(scopeKey) {
    historyScope = scopeKey
    loadHistory()
  }

  export function setPlayedWithScope(scopeKey) {
    playedWithScope = scopeKey
    loadPlayedWith()
  }

  function loadHistory() {
    if (!config) return
    const scopeKey = historyScopeKey
    const tuneId = config.tuneId || (tune && tune.tune_id)
    if (!tuneId) {
      historyCache[scopeKey] = { status: 'none' }
      return
    }
    if (historyCache[scopeKey]?.status === 'ready') return
    historyCache[scopeKey] = { status: 'loading' }
    let url = `/api/tunes/${tuneId}/history`
    if (scopeKey === 'session') {
      url += `?session_path=${encodeURIComponent(scope.session)}`
    } else if (scopeKey === 'member' || scopeKey === 'attended') {
      url += `?scope=${scopeKey}`
    }
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (scopeKey !== historyScopeKey) return // user toggled scope while loading
        if (!data.success) {
          historyCache[scopeKey] = { status: 'error' }
          return
        }
        historyCache[scopeKey] = { status: 'ready', data }
      })
      .catch(() => {
        if (scopeKey === historyScopeKey) historyCache[scopeKey] = { status: 'error' }
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

  const plural = (n, word) => (n === 1 ? word : word + 's')
  const tunebookCountView = $derived(tune ? tune.tunebook_count || tune.tunebook_count_cached || 0 : 0)
</script>

<svelte:window onkeydown={onKeydown} />

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
                <td class="modal-header-pill-cell"><Chip label={config.tuneType} styled={false} chipClass="tune-type-pill" /></td>
              {/if}
              <td class="modal-header-title-cell">
                <h2 class="modal-tune-title">{config?.tuneName || 'Loading...'}</h2>
              </td>
              <td class="modal-header-spacer-cell"></td>
              <td class="modal-header-close-cell">
                <button class="modal-close-btn" onclick={close} title="Close">&times;</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="modal-loading">
          <div class="loading-spinner"></div>
          <p>Loading tune details...</p>
        </div>
      {:else if phase === 'error'}
        <table class="modal-header-section">
          <tbody>
            <tr>
              <td class="modal-header-title-cell">
                <h2 class="modal-tune-title">Error</h2>
              </td>
              <td class="modal-header-spacer-cell"></td>
              <td class="modal-header-close-cell">
                <button class="modal-close-btn" onclick={close} title="Close">&times;</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="modal-error">
          <p>{errorMsg}</p>
        </div>
      {:else if phase === 'ready' && tune}
        {#if mergedFrom != null}
          <!-- Banner for a healed merged-tune permalink (spec 030) -->
          <div
            class="tune-merged-notice"
            style="background: var(--input-bg, #f8f9fa); border: 1px solid var(--border-color, #dee2e6); border-radius: 6px; padding: 0.5rem 0.75rem; margin-bottom: 0.75rem; font-size: 0.85rem; color: var(--secondary-text, #6c757d);"
          >
            Tune #{mergedFrom} was merged into "{tune.tune_name || tune.name || `#${tune.tune_id}`}" (#{tune.tune_id})
            — you're viewing the merged tune.
          </div>
        {/if}

        <!-- Header -->
        <table class="modal-header-section">
          <tbody>
            <tr>
              {#if headerTuneType}
                <td class="modal-header-pill-cell"><Chip label={headerTuneType} styled={false} chipClass="tune-type-pill" /></td>
              {/if}
              <td class="modal-header-title-cell">
                <!-- The title is NOT clickable any more: expanding a config panel by
                     clicking a heading was quirky and undiscoverable. Configure lives
                     in the status block's action row. -->
                <h2 class="modal-tune-title">{displayName}</h2>
                {#if akaName}
                  <div class="modal-tune-aka">aka {akaName}</div>
                {/if}
              </td>
              <td class="modal-header-spacer-cell"></td>
              <td class="modal-header-close-cell">
                <button class="modal-close-btn" onclick={close} title="Close">&times;</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- "Log to current session" — only when a session is in progress (spec 024) -->
        {#if activeSess && activeSess.session_instance_id && (config.tuneId || tune.tune_id)}
          <div class="active-session-log-section">
            <button class="active-session-log-btn" onclick={logToActiveSession}>
              <span class="active-session-log-dot"></span>
              Log to {activeSess.session_name || 'the current session'}
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
              title={notation.canToggleSize ? 'Click to toggle between incipit and full notation' : undefined}
              onclick={onNotationClick}
            >
              {#if notationView}
                {#if notationView.kind === 'img'}
                  <img
                    src="data:image/png;base64,{notationView.src}"
                    alt="{notationView.size === 'incipit' ? 'Incipit' : 'Full'} notation"
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
                    notes
                  </button>
                  <button
                    class="notation-mode-tab {notationMode === 'abc' ? 'active' : ''}"
                    data-mode="abc"
                    onclick={(e) => {
                      e.stopPropagation()
                      switchNotationMode('abc')
                    }}
                  >
                    abc
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
                    {pcFetchState === 'loading' ? 'Generating notation…' : 'Generate Notation'}
                  </button>
                {/if}
              </div>
              <div class="notation-external-links">
                {#if thesessionLink}<a
                    href={thesessionLink}
                    target="_blank"
                    class="notation-external-link"
                    title="View on TheSession.org"
                    onclick={(e) => e.stopPropagation()}>thesession</a
                  >{/if}{#if abctoolsLink}<a
                    href={abctoolsLink}
                    target="_blank"
                    class="notation-external-link"
                    title="View in ABC Tools"
                    onclick={(e) => e.stopPropagation()}>abc-tools</a
                  >{/if}
              </div>
            </div>
            <!-- You're looking at the session's version, not yours. A warning you can't
                 act on is just an irritant, so the link swaps the staff to your setting
                 and back. View only — it saves nothing and resets when the drawer closes. -->
            {#if settingMismatch}
              <div class="notation-mismatch">
                {#if showingMyVersion}
                  Showing your version.
                  <button type="button" class="notation-mismatch-link" onclick={toggleMyVersion}
                    >{sessionLabel}</button
                  > plays a different one.
                {:else}
                  This is the version {sessionLabel} plays.
                  <button type="button" class="notation-mismatch-link" onclick={toggleMyVersion}
                    >Your personal version</button
                  > differs.
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
              {pcFetchState === 'loading' ? 'Generating notation…' : 'Generate Notation'}
            </button>
          </div>
        {/if}

        <!-- Tunebook status: my relationship to this tune. Now also carries the heard
             count, the action row, and the personal Configure form — so everything that
             is MINE about this tune lives in one block, on every surface. -->
        {#if mode !== 'admin' && loggedIn}
          {#if !onList}
            <div class="tunebook-status-section tunebook-status-not-on-list">
              <div class="tunebook-status-seg tsc-notlist-seg" role="group" aria-label="Status">
                <span class="tunebook-status-opt tsc-notlist-label">This tune is not on your list</span>
                <button type="button" class="tunebook-status-opt tsc-notlist-add" onclick={addToTunebook}>Add</button>
              </div>
            </div>
          {:else}
            <div class="tunebook-status-section tunebook-status-{rollup.replace(/ /g, '-')}">
              <div class="tsc-block tsc-main-block">
                <div class="tsc-label-line">
                  <span class="tsc-name tunebook-status-label">This tune is on your list as</span>
                </div>
                <Seg
                  options={[
                    { id: 'want to learn', label: 'Want To Learn' },
                    { id: 'learning', label: 'Learning' },
                    { id: 'learned', label: 'Learned' },
                  ]}
                  value={rollup}
                  idAttr="data-status"
                  styled={false}
                  segClass="tunebook-status-seg{statusSaving ? ' saving' : ''}"
                  optClass="tunebook-status-opt"
                  role="group"
                  aria-label="Status"
                  onSelect={setTunebookStatus} />
              </div>
              {#if multiInstrument && piExpanded}
                <div class="tsc-instruments">
                  {#each instruments as inst, i}
                    {@const st = resolveInstStatus(tune, inst)}
                    <div class="tsc-block tsc-inst-block">
                      <div class="tsc-label-line">
                        <span class="tsc-name"
                          >{inst.instrument}{#if !inst.is_auto}
                            <Chip label="manual" styled={false} chipClass="tsc-manual" />{/if}</span
                        >
                        {#if !inst.is_auto && st !== null}
                          <button type="button" class="tsc-remove" onclick={() => removeInstrumentTune(i)}
                            >× remove</button
                          >
                        {/if}
                      </div>
                      {#if st === null}
                        <div class="tunebook-status-seg tsc-notlist-seg" role="group" aria-label="Status">
                          <span class="tunebook-status-opt tsc-notlist-label">This tune is not on your list</span>
                          <button
                            type="button"
                            class="tunebook-status-opt tsc-notlist-add"
                            onclick={() => setInstrumentStatus(i, 'want to learn')}>Add</button
                          >
                        </div>
                      {:else}
                        <Seg
                          options={[
                            { id: 'want to learn', label: 'Want To Learn' },
                            { id: 'learning', label: 'Learning' },
                            { id: 'learned', label: 'Learned' },
                          ]}
                          value={st}
                          idAttr="data-status"
                          styled={false}
                          segClass="tunebook-status-seg"
                          optClass="tunebook-status-opt"
                          role="group"
                          aria-label="Status"
                          onSelect={(val) => setInstrumentStatus(i, val)} />
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}

              <!-- Heard count (hidden for 'learned'; requires a person_tune row) -->
              {#if heardVisible}
                <div class="heard-count-section">
                  <div class="heard-count-label">
                    You've heard this <span id="heard-count-value">{heardCountView}</span> time{heardCountView !== 1
                      ? 's'
                      : ''}
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

              <!-- The action row. Configure and View By Instrument cluster left and wrap
                   together (both expand more UI); Remove stays right and TOP-aligned, so
                   it holds the first line even when the left cluster wraps on a phone. -->
              <div class="tsc-action-row">
                <span class="tsc-action-left">
                  <button
                    type="button"
                    class="tsc-action-link"
                    aria-expanded={isConfigVisible}
                    onclick={toggleConfigSection}
                  >
                    <span class="tsc-caret">{isConfigVisible ? '▾' : '▸'}</span>Configure
                  </button>
                  {#if multiInstrument}
                    <button type="button" class="tsc-action-link tsc-expand-link" onclick={toggleStatusExpand}>
                      {piExpanded ? 'Hide Instruments' : 'View By Instrument'}
                    </button>
                  {/if}
                </span>
                <button type="button" class="tsc-action-link tsc-action-danger" onclick={removeFromMyTunes}>
                  Remove From My Tunes
                </button>
              </div>

              <!-- Personal config: the SAME fields on every surface. A session never
                   replaces them — that was the whole point of 037. -->
              {#if isConfigVisible}
                <div id="configure-section" class="configure-section tsc-config-body">
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="name-alias-input">I call this:</label>
                    <input
                      type="text"
                      id="name-alias-input"
                      class="configure-input"
                      autocomplete="off"
                      autocorrect="off"
                      autocapitalize="off"
                      spellcheck="false"
                      placeholder={tune.tune_name || 'Enter your name for this tune'}
                      disabled={isOffline}
                      bind:value={pcFields.name_alias}
                    />
                  </div>
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="setting-input">I play setting:</label>
                    <div class="input-with-button">
                      <input
                        type="text"
                        id="setting-input"
                        class="configure-input"
                        autocomplete="off"
                        autocorrect="off"
                        autocapitalize="off"
                        spellcheck="false"
                        placeholder="e.g., 123 or paste URL"
                        style:border-color={pcSettingError ? '#dc3545' : ''}
                        disabled={isOffline}
                        bind:value={pcFields.setting}
                        oninput={() => validateSettingField('personal')}
                      />
                      <button
                        type="button"
                        class="fetch-setting-btn{pcFetchState === 'loading' ? ' fetch-setting-btn-loading' : ''}"
                        onclick={() => fetchSetting('personal')}
                        disabled={pcFetchState !== 'idle' || isOffline}
                        style:background-color={pcFetchState === 'ok' ? '#28a745' : pcFetchState === 'warn' ? '#f0ad4e' : pcFetchState === 'err' ? '#dc3545' : ''}
                        style:color={pcFetchState === 'ok' || pcFetchState === 'warn' || pcFetchState === 'err' ? 'white' : ''}
                        title="Fetch setting from TheSession.org"
                      >
                        {#if pcFetchState === 'loading'}<span class="fetch-setting-spinner"></span>
                        {:else if pcFetchState === 'ok'}✓
                        {:else if pcFetchState === 'warn'}⚠
                        {:else if pcFetchState === 'err'}✗
                        {:else}{pcFetchLabel}{/if}
                      </button>
                    </div>
                  </div>
                  <div id="setting-error" class="field-error" style="display: {pcSettingError ? 'block' : 'none'};">
                    {pcSettingError}
                  </div>
                  <div class="configure-field-group-inline">
                    <label class="configure-label" for="my-key-select">I play this in:</label>
                    <select
                      id="my-key-select"
                      class="configure-select"
                      disabled={isOffline}
                      bind:value={pcFields.key}
                    >
                      {#each MUSICAL_KEYS as key}
                        <option value={key}
                          >{key || (tune.setting_key ? `(the setting's key — ${tune.setting_key})` : '(not specified)')}</option
                        >
                      {/each}
                    </select>
                  </div>
                  <div class="configure-field-group">
                    <label class="configure-label" for="notes-textarea">My notes:</label>
                    <textarea
                      id="notes-textarea"
                      class="notes-textarea"
                      placeholder="Anything you want to remember about this tune…"
                      bind:value={pcFields.notes}
                    ></textarea>
                  </div>
                  <div class="modal-action-buttons">
                    {#if isOffline}
                      <span class="tsc-offline-hint">Offline — only notes can be edited</span>
                    {/if}
                    <button class="btn-secondary" onclick={() => seedPersonalForm()} disabled={!pcDirty}>Cancel</button>
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
        {/if}

        <!-- Admin: the canonical tune name. 037 does not touch admin mode — it is the
             one remaining place where the drawer's shape depends on which page opened
             it. Spec 036 asks the prior question of what /admin/tunes is even for. -->
        {#if mode === 'admin'}
          <div id="configure-section" class="configure-section">
            <div class="configure-field-group">
              <label class="configure-label" for="tune-name-input">Tune Name:</label>
              <input
                type="text"
                id="tune-name-input"
                class="configure-input"
                autocomplete="off"
                autocorrect="off"
                autocapitalize="off"
                spellcheck="false"
                placeholder="Enter tune name"
                bind:value={adminFields.name}
              />
            </div>
            <div class="modal-action-buttons">
              <button class="btn-secondary" onclick={() => seedAdminForm()} disabled={!adminDirty}>Cancel</button>
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

        <!-- Tabs: Session (when a session is in scope, and leftmost) / Stats / History /
             Played With. The drawer opens on its leftmost tab, which is the single rule
             that replaced "which tab do we land on, given which page opened us". -->
        <div class="modal-tabs-section">
          <Tabs
            tabs={tabList}
            bind:value={activeTab}
            onValueChange={switchTab}
            styled={false}
            listClass="modal-tabs-header"
            tabClass="modal-tab"
            selectLabel="Tune info section" />
          <div class="modal-tabs-content">
            {#if inSession}
              <div id="session-tab" class="modal-tab-pane{activeTab === 'session' ? ' active' : ''}">
                <!-- The droplist IS the heading: it names the session ("At The
                     Cobblestone") and the list continues the sentence downward ("… on Tue
                     8 Jul"). It also picks what the form below writes to — the session's
                     own row, or one night's — so you never see both layers editable at
                     once, which was the confusing part. -->
                <div class="sess-scope-row">
                  <!-- Two-way bound on purpose: picking the "different session" row must be
                       able to snap the select BACK, and a one-way `value=` only writes the
                       DOM when the state actually changes. -->
                  <select
                    id="sess-scope-select"
                    class="configure-select"
                    aria-label="Which session, or which night"
                    bind:value={sessScopeId}
                    onchange={(e) => selectSessionScope(e.currentTarget.value)}
                  >
                    {#each sessOptions as opt}
                      <option value={opt.id}>{opt.label}</option>
                    {/each}
                  </select>
                </div>

                <!-- What the tab is mostly FOR: telling you where this tune has been. -->
                <div class="sess-context">
                  {#if editingInstance}
                    {#if positions.length}
                      {#each positions as p, i}
                        <a class="sess-position" href={p.href}>{p.label}</a>{#if i < positions.length - 1}<span
                            class="sess-position-sep">;</span
                          >{/if}
                      {/each}
                    {:else}
                      <span class="sess-context-empty">Not played that night.</span>
                    {/if}
                  {:else if tune.times_played}
                    This tune has been played
                    <button type="button" class="sess-context-link" onclick={showSessionHistory}>
                      {tune.times_played} {plural(tune.times_played, 'time')} at this session
                    </button>
                  {:else}
                    <span class="sess-context-empty">This tune has never been played at this session.</span>
                  {/if}
                </div>

                {#if canEditSessionLayer && !sessFormOpen}
                  <button type="button" class="sess-edit-link" onclick={() => (sessFormOpen = true)}>
                    Update name, setting or key for this tune {editingInstance
                      ? 'on this date'
                      : 'at this session'}
                  </button>
                {/if}

                {#if canEditSessionLayer && sessFormOpen}
                  <div class="configure-section sess-form">
                    <div class="configure-field-group-inline">
                      <label class="configure-label" for="sess-alias-input">
                        {editingInstance ? 'We called it:' : 'We call this:'}
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
                      <label class="configure-label" for="sess-setting-input">
                        {editingInstance ? 'We played setting:' : 'Our setting:'}
                      </label>
                      <div class="input-with-button">
                        <input
                          type="text"
                          id="sess-setting-input"
                          class="configure-input"
                          autocomplete="off"
                          autocorrect="off"
                          autocapitalize="off"
                          spellcheck="false"
                          placeholder="e.g., 123 or paste URL"
                          style:border-color={sessSettingError ? '#dc3545' : ''}
                          bind:value={sessFields.setting}
                          oninput={() => validateSettingField('session')}
                        />
                        <button
                          type="button"
                          class="fetch-setting-btn{sessFetchState === 'loading' ? ' fetch-setting-btn-loading' : ''}"
                          onclick={() => fetchSetting('session')}
                          disabled={sessFetchState !== 'idle'}
                          style:background-color={sessFetchState === 'ok' ? '#28a745' : sessFetchState === 'warn' ? '#f0ad4e' : sessFetchState === 'err' ? '#dc3545' : ''}
                          style:color={sessFetchState === 'ok' || sessFetchState === 'warn' || sessFetchState === 'err' ? 'white' : ''}
                          title="Fetch setting from TheSession.org"
                        >
                          {#if sessFetchState === 'loading'}<span class="fetch-setting-spinner"></span>
                          {:else if sessFetchState === 'ok'}✓
                          {:else if sessFetchState === 'warn'}⚠
                          {:else if sessFetchState === 'err'}✗
                          {:else}{sessFetchLabel}{/if}
                        </button>
                      </div>
                    </div>
                    <div class="field-error" style="display: {sessSettingError ? 'block' : 'none'};">
                      {sessSettingError}
                    </div>
                    <div class="configure-field-group-inline">
                      <label class="configure-label" for="sess-key-select">
                        {editingInstance ? 'We played it in:' : 'We play this in:'}
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
                        Cancel
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
                {:else if !canEditSessionLayer}
                  <!-- Read-only: anyone can see what a session plays, including logged-out
                       visitors. Editing 'In General' is admin-only; an instance is open to
                       any member. Someone who CAN edit sees nothing here until they ask —
                       the values live inside the form they're about to open. -->
                  <div class="configure-section sess-form sess-form-readonly">
                    <div class="configure-field-group-inline">
                      <div class="configure-label">{editingInstance ? 'We called it:' : 'We call this:'}</div>
                      <div class="configure-value">{sessOriginals.alias || '—'}</div>
                    </div>
                    <div class="configure-field-group-inline">
                      <div class="configure-label">{editingInstance ? 'We played setting:' : 'Our setting:'}</div>
                      <div class="configure-value">{sessOriginals.setting_id || '—'}</div>
                    </div>
                    <div class="configure-field-group-inline">
                      <div class="configure-label">{editingInstance ? 'We played it in:' : 'We play this in:'}</div>
                      <div class="configure-value">{sessOriginals.key || '—'}</div>
                    </div>
                  </div>
                {/if}

                <!-- Un-enrolling a tune from the repertoire. Only ever available for a
                     tune with NO plays here: every tune played at an instance belongs to
                     the session, and this endpoint used to break that by deleting the
                     session_tune row and orphaning the plays. With plays present the link
                     is simply absent — no explanation, it just isn't an option. -->
                {#if canRemoveFromSession}
                  <div class="sess-danger-foot">
                    <button type="button" class="tsc-action-link tsc-action-danger" onclick={removeFromSession}>
                      Remove From Session
                    </button>
                  </div>
                {/if}
              </div>
            {/if}
            <div id="stats-tab" class="modal-tab-pane{activeTab === 'stats' ? ' active' : ''}">
              {#if tune.person_list_count != null}
                <div class="stat-card">
                  <div class="stat-line">
                    Saved in <span class="stat-number">{tune.person_list_count}</span> tune {plural(
                      tune.person_list_count,
                      'list'
                    )} on Ceol.io
                  </div>
                </div>
              {/if}
              <div class="stat-card">
                <div class="stat-line">
                  Saved in <span class="stat-number" id="tunebook-count">{tunebookCountView}</span>
                  {plural(tunebookCountView, 'tunebook')} on TheSession.org
                  <button
                    class="refresh-btn"
                    onclick={refreshTunebookCount}
                    disabled={refreshState === 'loading'}
                    style:background-color={refreshState === 'ok' ? '#28a745' : refreshState === 'err' ? '#dc3545' : ''}
                    style:color={refreshState === 'ok' || refreshState === 'err' ? 'white' : ''}
                    title="Refresh"
                  >
                    {refreshState === 'loading' ? '⟳' : refreshState === 'ok' ? '✓' : refreshState === 'err' ? '✗' : '↻'}
                  </button>
                  {#if tune.tunebook_count_cached_date}<span class="stat-note"
                      >Last Updated {tune.tunebook_count_cached_date}</span
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
                    Logged <span class="stat-number">{tune.times_played || 0}</span>
                    {plural(tune.times_played || 0, 'time')} at this session
                  </div>
                </div>
              {/if}
              {#if mode !== 'admin' && hasMyCounts}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{myPlayCount}</span>
                    {plural(myPlayCount, 'time')} at my sessions
                  </div>
                </div>
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{myAttendedCount}</span>
                    {plural(myAttendedCount, 'time')} while I was there
                  </div>
                </div>
              {/if}
              <div class="stat-card">
                <div class="stat-line">
                  Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                  {plural(tune.global_play_count || 0, 'time')} at all sessions
                </div>
              </div>
              {#if mode === 'admin'}
                <div class="stat-card">
                  <div class="stat-line">
                    In the repertoire of <span class="stat-number">{tune.session_count || 0}</span> sessions
                  </div>
                </div>
              {/if}
              <!-- The canonical name and id. They used to sit at the top of the Configure
                   section, above everything you actually came to look at; they're facts
                   about the tune, so they belong with the other facts. -->
              <div class="stat-canonical">
                Canonical name: {tune.tune_name || 'Unknown'} (#{tune.tune_id})
              </div>
            </div>
            <div id="history-tab" class="modal-tab-pane{activeTab === 'history' ? ' active' : ''}">
              {#if historyOptions.length > 1}
                <Seg
                  options={historyOptions.map((o) => ({ id: o.key, label: o.label }))}
                  value={historyScopeKey}
                  idAttr="data-scope"
                  styled={false}
                  segClass="history-scope-toggle"
                  optClass="history-scope-btn"
                  onSelect={setHistoryScope} />
              {/if}
              <div id="history-list-container">
                {#if historyState.status === 'ready'}
                  {@const playInstances = historyState.data.play_instances || []}
                  {#if playInstances.length === 0}
                    <div class="no-history">No play history recorded yet.</div>
                  {:else}
                    <div class="history-list">
                      {#each playInstances as instance}
                        <div class="history-item">
                          <div class="history-instance-name">
                            <a href={instance.link}>
                              {historyScopeKey !== 'session'
                                ? instance.full_name || instance.date || 'Unknown'
                                : instance.date || 'Unknown'}
                            </a>
                          </div>
                          {#if instance.set_number && instance.position_in_set}
                            <div class="history-position">
                              Set {instance.set_number}, Tune {instance.position_in_set}
                            </div>
                          {/if}
                          {#if instance.setting_id_override}
                            <div class="history-setting">Setting: #{instance.setting_id_override}</div>
                          {/if}
                        </div>
                      {/each}
                    </div>
                    {#if historyState.data.truncated}
                      <div class="history-truncated">Showing the 100 most recent sessions.</div>
                    {/if}
                  {/if}
                {:else if historyState.status === 'error'}
                  <div class="no-history">Could not load play history.</div>
                {:else if historyState.status === 'none'}
                  <div class="no-history">No play history recorded yet.</div>
                {:else}
                  <div class="history-loading">Loading play history…</div>
                {/if}
              </div>
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
                      This tune has not been played in a set with any other tune{playedWithScopeKey === 'session'
                        ? ' at this session'
                        : ''} yet.
                    </div>
                  {:else}
                    <div class="played-with-list">
                      {#each pwTunes as t}
                        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                        <div class="played-with-item" data-tune-id={t.tune_id} onclick={() => openPlayedWithTune(t)}>
                          <span class="played-with-name">{t.name}</span>
                          <span class="played-with-count">{t.count}</span>
                        </div>
                      {/each}
                    </div>
                  {/if}
                {:else if playedWithState.status === 'error'}
                  <div class="no-history">Could not load played-with tunes.</div>
                {:else if playedWithState.status === 'none'}
                  <div class="no-history">No set history recorded yet.</div>
                {:else}
                  <div class="history-loading">Loading tunes…</div>
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
  title="Remove this tune from your list?"
  confirmLabel="Remove tune"
  destructive={true}
  onConfirm={doRemoveFromMyTunes} />

<Dialog
  bind:open={removeSessionOpen}
  title="Remove this tune from the session tune list?"
  confirmLabel="Remove tune"
  destructive={true}
  onConfirm={doRemoveFromSession} />

<!-- "At a different session ..." — re-scopes the whole drawer to another session I'm a
     member of, so I can see what THEY do with this tune. Visitor sessions are excluded:
     a session you dropped into once isn't one whose repertoire you have a view on. -->
<SessionPicker
  bind:open={sessionPickerOpen}
  sessions={mySessions}
  currentPath={sessionScope?.path ?? null}
  onSelect={scopeToSession} />

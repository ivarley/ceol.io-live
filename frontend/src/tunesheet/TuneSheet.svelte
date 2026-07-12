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
  import { Chip, Dialog, Seg, Tabs, toast } from '../lib/index.js'
  import {
    MUSICAL_KEYS,
    normalizeShowConfig,
    detailUrl,
    getDisplayName,
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

  // Form fields + originals for dirty checking
  let fields = $state({})
  let originals = $state({})
  let settingError = $state('')
  let saveState = $state('idle') // idle | saving | saved | error
  let fetchBtnState = $state('idle') // idle | loading | ok | warn | err
  let refreshState = $state('idle') // idle | loading | ok | err
  let statusSaving = $state(false)
  let pendingHeard = $state(0)

  // ABC notation display state machine
  let notationMode = $state('dots') // 'dots' | 'abc'
  let notationSize = $state('incipit') // 'incipit' | 'full'

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
  const headerTuneType = $derived((tune && tune.tune_type) || config?.tuneType || '')
  const isTitleClickable = $derived(mode !== 'admin' && mode !== 'global')

  const rollup = $derived(tune ? rollupStatus(tune) : 'want to learn')
  const instruments = $derived(tune ? getInstrumentData(tune).instruments : [])
  const multiInstrument = $derived(instruments && instruments.length >= 2)

  const heardVisible = $derived.by(() => {
    if (!tune || mode === 'admin' || !loggedIn) return false
    if (!pts || !pts.person_tune_id) return false
    return !!pts.learn_status && pts.learn_status !== 'learned'
  })
  const heardCountView = $derived((pts && pts.heard_count) || 0)
  const myPlayCount = $derived((pts && pts.session_play_count) || 0)

  const notation = $derived(tune ? notationInfo(tune) : null)
  const notationView = $derived(tune ? notationDisplay(tune, notationMode, notationSize) : null)
  const thesessionLink = $derived(tune ? theSessionUrl(tune) : '')
  const abctoolsLink = $derived(tune ? abcToolsUrl(tune) : '')

  const hasCachedNotation = $derived(
    !!(tune && (tune.abc || tune.incipit_abc || tune.image || tune.incipit_image))
  )
  // The settings/cache endpoint is login-required, so the Generate Notation
  // affordance only shows for logged-in viewers (payload-derived, so a call
  // site can never forget the flag again).
  const canGenerateNotation = $derived(!!tune && loggedIn)

  const fetchBtnLabel = $derived.by(() => {
    if (!tune) return 'Fetch'
    const value = (fields.setting || '').trim()
    const originalSettingId =
      (mode === 'session_instance' ? originals.setting_override : originals.setting_id) || null
    const settingIdsMatch = (!value && !originalSettingId) || extractSettingId(value) === originalSettingId
    return hasCachedNotation && settingIdsMatch ? 'Refresh' : 'Fetch'
  })

  const isDirty = $derived.by(() => {
    if (!tune || !config) return false
    switch (mode) {
      case 'my_tunes':
        return (
          fields.name_alias !== originals.name_alias ||
          extractSettingId(fields.setting) !== (originals.setting_id || null) ||
          fields.notes !== originals.notes
        )
      case 'session':
        return (
          fields.alias !== originals.alias ||
          extractSettingId(fields.setting) !== (originals.setting_id || null) ||
          fields.key !== originals.key
        )
      case 'session_instance':
        return (
          fields.alias !== originals.name ||
          extractSettingId(fields.setting) !== (originals.setting_override || null) ||
          fields.key !== originals.key_override
        )
      case 'admin':
        return fields.name !== originals.name
      default:
        return false
    }
  })
  const saveDisabled = $derived(!isDirty || saveState !== 'idle' || !!settingError)
  const saveLabel = $derived(
    saveState === 'saving' ? 'Saving...' : saveState === 'saved' ? 'Saved!' : saveState === 'error' ? 'Error' : 'Save'
  )
  const saveBtnBg = $derived(saveState === 'saved' ? '#28a745' : saveState === 'error' ? '#dc3545' : '')

  const historyOptions = $derived(historyScopeOptions(mode, scope))
  const playedWithOptions = $derived(playedWithScopeOptions(mode, scope))
  // null = "the mode's default scope" (mode is only known once the payload lands)
  const historyScopeKey = $derived(historyScope ?? historyOptions[0].key)
  const playedWithScopeKey = $derived(playedWithScope ?? playedWithOptions[0].key)
  const historyState = $derived(historyCache[historyScopeKey] || { status: 'loading' })
  const playedWithState = $derived(playedWithCache[playedWithScopeKey] || { status: 'loading' })

  const hasAdditionalLinks = $derived(mode === 'my_tunes' || mode === 'session' || mode === 'session_instance')

  // ---- fields / originals per mode ---------------------------------------------

  function buildOriginals() {
    const o = { learn_status: (pts && pts.learn_status) || '' }
    switch (mode) {
      case 'my_tunes':
        o.name_alias = (pts && pts.name_alias) || ''
        o.setting_id = (pts && pts.setting_id) || ''
        o.notes = (pts && pts.notes) || ''
        break
      case 'session':
        o.alias = tune.alias || ''
        o.setting_id = tune.setting_id || ''
        o.key = tune.key || ''
        break
      case 'session_instance':
        o.name = tune.name || ''
        o.setting_override = tune.setting_override || ''
        o.key_override = tune.key_override || ''
        break
      case 'admin':
        o.name = tune.tune_name || ''
        break
    }
    return o
  }

  function initFields() {
    switch (mode) {
      case 'my_tunes':
        return {
          name_alias: (pts && pts.name_alias) || '',
          setting: String((pts && pts.setting_id) || ''),
          notes: (pts && pts.notes) || '',
        }
      case 'session':
        return {
          alias: tune.alias || '',
          setting: String(tune.setting_id || ''),
          key: tune.key || '',
        }
      case 'session_instance':
        return {
          alias: tune.name || '',
          setting: String(tune.setting_override || ''),
          key: tune.key_override || '',
        }
      case 'admin':
        return { name: tune.tune_name || '' }
      default:
        return {}
    }
  }

  // ---- payload application --------------------------------------------------------

  // (Re)apply a full payload and reset the per-render section state (tabs back
  // to Stats unless asked to keep one, notation back to initial, configure
  // collapsed except admin, fields re-seeded).
  function applyPayload(data, opts = {}) {
    viewer = data.viewer || viewer || { logged_in: false, is_admin: false, is_session_admin: false }
    tune = data.session_tune
    mergedFrom = null
    originals = buildOriginals()
    fields = initFields()
    settingError = ''
    saveState = 'idle'
    fetchBtnState = 'idle'
    refreshState = 'idle'
    statusSaving = false
    isConfigVisible = mode === 'admin'
    // Tabs reset to Stats — except a show()/re-apply that asked to keep a tab
    // (the in-place add -> my_tunes upgrade preserves the user's tab).
    activeTab = opts.keepTab || config.initialTab || 'stats'
    if (activeTab === 'history') loadHistory()
    else if (activeTab === 'played-with') loadPlayedWith()
    // An explicit history/played-with scope choice survives a re-apply only if
    // the (possibly changed) mode still offers it.
    if (historyScope != null && !historyScopeOptions(mode, scope).some((o) => o.key === historyScope)) historyScope = null
    if (playedWithScope != null && !playedWithScopeOptions(mode, scope).some((o) => o.key === playedWithScope))
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
    if (newStatus === originals.learn_status && autoOverridden.length === 0) return // nothing to do

    const prevStatus = originals.learn_status
    const prevOverrides = { ...data.overrides }
    const nextOverrides = { ...data.overrides }
    autoOverridden.forEach((i) => delete nextOverrides[i.instrument])

    const applyUi = (status, overrides) => {
      originals.learn_status = status
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

  function onSettingInputHandler() {
    const value = (fields.setting || '').trim()
    if (!value) {
      settingError = ''
      return
    }
    const validation = validateSettingInput(value, tune.tune_id)
    if (!validation.valid) {
      settingError = validation.error
    } else {
      settingError = ''
      // If we extracted a setting ID from a URL, replace with just the number
      if (validation.settingId !== null && value !== validation.settingId.toString()) {
        fields.setting = validation.settingId.toString()
      }
    }
  }

  // The PUT target for the current variant's editable fields ('' = read-only).
  function saveEndpointFor() {
    switch (mode) {
      case 'my_tunes':
        return pts && pts.person_tune_id ? `/api/my-tunes/${pts.person_tune_id}` : ''
      case 'session':
        return `/api/sessions/${scope.session}/tunes/${tune.tune_id}`
      case 'session_instance':
        return `/api/sessions/${scope.session}/${scope.instance}/tunes/${tune.tune_id}`
      case 'admin':
        return `/api/admin/tunes/${tune.tune_id}`
      default:
        return ''
    }
  }

  // Mirror a successful save's updates onto the local payload so originals
  // rebuild from the truth we just wrote.
  function applySavedUpdates(updates) {
    if (mode === 'my_tunes' && tune.person_tune_status) {
      Object.assign(tune.person_tune_status, updates)
    } else if (mode === 'admin') {
      if (updates.name !== undefined) tune.tune_name = updates.name
    } else {
      Object.assign(tune, updates)
    }
  }

  export function save() {
    if (!tune || !config || saveDisabled) return

    const updates = {}
    switch (mode) {
      case 'my_tunes': {
        if (fields.name_alias !== originals.name_alias) updates.name_alias = fields.name_alias.trim() || null
        const newSettingId = extractSettingId(fields.setting)
        if (newSettingId !== (originals.setting_id || null)) updates.setting_id = newSettingId
        if (fields.notes !== originals.notes) updates.notes = fields.notes.trim() || null
        break
      }
      case 'session': {
        if (fields.alias !== originals.alias) updates.alias = fields.alias.trim() || null
        const newSettingId = extractSettingId(fields.setting)
        if (newSettingId !== (originals.setting_id || null)) updates.setting_id = newSettingId
        if (fields.key !== originals.key) updates.key = fields.key || null
        break
      }
      case 'session_instance': {
        if (fields.alias !== originals.name) updates.name = fields.alias.trim() || null
        const newSettingId = extractSettingId(fields.setting)
        if (newSettingId !== (originals.setting_override || null)) updates.setting_override = newSettingId
        if (fields.key !== originals.key_override) updates.key_override = fields.key || null
        break
      }
      case 'admin': {
        updates.name = fields.name.trim()
        if (!updates.name) {
          toast('Tune name cannot be empty', 'error')
          return
        }
        break
      }
      default:
        return
    }
    const apiEndpoint = saveEndpointFor()
    if (!apiEndpoint) return

    saveState = 'saving'
    const hasMainUpdates = Object.keys(updates).length > 0
    const savePromise = hasMainUpdates
      ? fetch(apiEndpoint, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        }).then((response) => response.json())
      : Promise.resolve({ success: true, message: 'No changes to save' })

    savePromise
      .then((data) => {
        if (data.success) {
          saveState = 'saved'
          // Update original values to reflect saved state
          applySavedUpdates(updates)
          originals = buildOriginals()
          // Remove tune parameter from URL first (before onSave which might reload)
          removeUrlTuneParam(mode)
          if (config.onSave && typeof config.onSave === 'function') config.onSave()
          setTimeout(() => close(), 1000)
        } else {
          saveState = 'error'
          console.error('Error saving:', data.error || data.message)
          setTimeout(() => {
            if (saveState === 'error') saveState = 'idle'
          }, 2000)
        }
      })
      .catch((error) => {
        console.error('Error:', error)
        saveState = 'error'
        setTimeout(() => {
          if (saveState === 'error') saveState = 'idle'
        }, 2000)
      })
  }

  // Fetch and cache setting from TheSession.org, save the setting id per mode,
  // then re-render with the fetched notation. Resolves true when notation was
  // fetched (even if the per-mode setting-id save then warned), so callers
  // like generateNotation can surface failures their own way.
  export function fetchSetting() {
    if (!tune || fetchBtnState === 'loading') return Promise.resolve(false)
    const tuneId = tune.tune_id
    const settingIdValue = (fields.setting || '').trim()
    fetchBtnState = 'loading'

    const feedback = (state) => {
      fetchBtnState = state
      setTimeout(() => {
        if (fetchBtnState === state) fetchBtnState = 'idle'
      }, 2000)
    }

    let apiUrl = `/api/tunes/${tuneId}/settings/cache`
    if (settingIdValue) {
      const validation = validateSettingInput(settingIdValue, tuneId)
      const settingId = validation.settingId || settingIdValue
      apiUrl += `?setting_id=${settingId}`
    }

    // Re-render with the freshly cached notation, keeping the current tab.
    const reapply = () => applyPayload({ viewer, session_tune: tune }, { keepTab: activeTab })

    return fetch(apiUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          console.error('Error fetching setting:', data.message)
          feedback('err')
          return false
        }
        const fetchedSettingId = data.setting.setting_id
        tune.abc = data.setting.abc
        tune.incipit_abc = data.setting.incipit_abc
        tune.image = data.setting.image
        tune.incipit_image = data.setting.incipit_image

        // Save the setting id per the current variant (none in the global view)
        const saveEndpoint = mode === 'admin' ? '' : saveEndpointFor()
        const savePayload =
          mode === 'session_instance' ? { setting_override: fetchedSettingId } : { setting_id: fetchedSettingId }

        if (saveEndpoint) {
          return fetch(saveEndpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(savePayload),
          })
            .then((response) => response.json())
            .then((saveData) => {
              if (saveData.success) {
                applySavedUpdates(savePayload)
                if (mode === 'my_tunes') tune.setting_id = fetchedSettingId
                reapply() // legacy re-renders the modal here
                feedback('ok')
              } else {
                console.error('Error saving setting_id:', saveData.error)
                reapply() // still re-render with the fetched data
                feedback('warn')
              }
              return true
            })
            .catch((error) => {
              console.error('Error saving setting_id:', error)
              reapply() // still re-render with the fetched data
              return true
            })
        }
        reapply()
        feedback('ok')
        return true
      })
      .catch((error) => {
        console.error('Error:', error)
        feedback('err')
        return false
      })
  }

  // "Generate Notation" (shown in the notation area when nothing is cached):
  // the SAME action as the configure section's Fetch/Refresh button; a failure
  // surfaces through the drawer's toast pattern.
  export function generateNotation() {
    fetchSetting().then((ok) => {
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
    } else if (scopeKey === 'mine') {
      url += '?person=me'
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
                {#if isTitleClickable}
                  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
                  <h2
                    class="modal-tune-title modal-tune-title-clickable"
                    onclick={toggleConfigSection}
                    title="Click to configure"
                  >
                    {displayName}
                  </h2>
                {:else}
                  <h2 class="modal-tune-title">{displayName}</h2>
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

        <!-- Configure section (collapsible except on admin; not in the read-only/Add
             view, and never for anonymous viewers — saves would just 401) -->
        {#if mode !== 'global' && loggedIn}
          <div id="configure-section" class="configure-section" style="display: {isConfigVisible ? 'block' : 'none'};">
            <div class="configure-field-group-inline">
              <div class="configure-label">Official Name:</div>
              <div class="configure-value">{tune.tune_name || tune.name || 'Unknown'}</div>
            </div>
            <div class="configure-field-group-inline">
              <div class="configure-label">Tune ID:</div>
              <div class="configure-value">{tune.tune_id || 'Unknown'}</div>
            </div>
            {#if mode === 'my_tunes'}
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
                  placeholder="Enter your name for this tune"
                  bind:value={fields.name_alias}
                />
              </div>
              <div class="configure-field-group-inline">
                <label class="configure-label" for="setting-input">My setting:</label>
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
                    style:border-color={settingError ? '#dc3545' : ''}
                    bind:value={fields.setting}
                    oninput={onSettingInputHandler}
                  />
                  <button
                    type="button"
                    class="fetch-setting-btn{fetchBtnState === 'loading' ? ' fetch-setting-btn-loading' : ''}"
                    onclick={fetchSetting}
                    disabled={fetchBtnState !== 'idle'}
                    style:background-color={fetchBtnState === 'ok' ? '#28a745' : fetchBtnState === 'warn' ? '#f0ad4e' : fetchBtnState === 'err' ? '#dc3545' : ''}
                    style:color={fetchBtnState === 'ok' || fetchBtnState === 'warn' || fetchBtnState === 'err' ? 'white' : ''}
                    title="Fetch setting from TheSession.org"
                  >
                    {#if fetchBtnState === 'loading'}<span class="fetch-setting-spinner"></span>
                    {:else if fetchBtnState === 'ok'}✓
                    {:else if fetchBtnState === 'warn'}⚠
                    {:else if fetchBtnState === 'err'}✗
                    {:else}{fetchBtnLabel}{/if}
                  </button>
                </div>
              </div>
              <div id="setting-error" class="field-error" style="display: {settingError ? 'block' : 'none'};">
                {settingError}
              </div>
            {:else if mode === 'session' || mode === 'session_instance'}
              <div class="configure-field-group-inline">
                <label class="configure-label" for="alias-input">
                  {mode === 'session' ? 'We call this:' : 'In this case, we called it:'}
                </label>
                <input
                  type="text"
                  id="alias-input"
                  class="configure-input"
                  autocomplete="off"
                  autocorrect="off"
                  autocapitalize="off"
                  spellcheck="false"
                  placeholder={mode === 'session' ? 'Enter session name for this tune' : 'Enter name for this instance'}
                  bind:value={fields.alias}
                />
              </div>
              <div class="configure-field-group-inline">
                <label class="configure-label" for="setting-input">
                  {mode === 'session' ? 'Our setting:' : 'This time, we played setting:'}
                </label>
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
                    style:border-color={settingError ? '#dc3545' : ''}
                    bind:value={fields.setting}
                    oninput={onSettingInputHandler}
                  />
                  <button
                    type="button"
                    class="fetch-setting-btn{fetchBtnState === 'loading' ? ' fetch-setting-btn-loading' : ''}"
                    onclick={fetchSetting}
                    disabled={fetchBtnState !== 'idle'}
                    style:background-color={fetchBtnState === 'ok' ? '#28a745' : fetchBtnState === 'warn' ? '#f0ad4e' : fetchBtnState === 'err' ? '#dc3545' : ''}
                    style:color={fetchBtnState === 'ok' || fetchBtnState === 'warn' || fetchBtnState === 'err' ? 'white' : ''}
                    title="Fetch setting from TheSession.org"
                  >
                    {#if fetchBtnState === 'loading'}<span class="fetch-setting-spinner"></span>
                    {:else if fetchBtnState === 'ok'}✓
                    {:else if fetchBtnState === 'warn'}⚠
                    {:else if fetchBtnState === 'err'}✗
                    {:else}{fetchBtnLabel}{/if}
                  </button>
                </div>
              </div>
              <div id="setting-error" class="field-error" style="display: {settingError ? 'block' : 'none'};">
                {settingError}
              </div>
              <div class="configure-field-group-inline">
                <label class="configure-label" for="key-select">
                  {mode === 'session' ? 'We play this in:' : 'This time, we played in:'}
                </label>
                <select id="key-select" class="configure-select" bind:value={fields.key}>
                  {#each MUSICAL_KEYS as key}
                    <option value={key}>{key || '(not specified)'}</option>
                  {/each}
                </select>
              </div>
            {:else if mode === 'admin'}
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
                  bind:value={fields.name}
                />
              </div>
            {/if}
          </div>
        {/if}

        <!-- Tunebook status section (not on admin; only when the viewer is logged in) -->
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
              {#if multiInstrument}
                {#if piExpanded}
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
                <button type="button" class="tsc-expand-link" onclick={toggleStatusExpand}>
                  {piExpanded ? 'Hide Instruments' : 'View By Instrument'}
                </button>
              {/if}
            </div>
          {/if}
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

        <!-- ABC notation -->
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
                    disabled={fetchBtnState === 'loading'}
                  >
                    {fetchBtnState === 'loading' ? 'Generating notation…' : 'Generate Notation'}
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
          </div>
        {:else if canGenerateNotation}
          <!-- No cached notation for this tune: offer to generate it in place
               (same action as the configure section's Fetch/Refresh). -->
          <div class="abc-notation-section abc-notation-empty">
            <button
              type="button"
              class="generate-notation-link"
              onclick={generateNotation}
              disabled={fetchBtnState === 'loading'}
            >
              {fetchBtnState === 'loading' ? 'Generating notation…' : 'Generate Notation'}
            </button>
          </div>
        {/if}

        <!-- Notes (the my-tunes variant only) -->
        {#if mode === 'my_tunes'}
          <div class="notes-section">
            <textarea
              id="notes-textarea"
              class="notes-textarea"
              placeholder="Add notes about this tune..."
              bind:value={fields.notes}
            ></textarea>
          </div>
        {/if}

        <!-- Action buttons (none in the read-only/Add view) -->
        {#if mode !== 'global'}
          <div class="modal-action-buttons">
            <button id="cancel-btn" class="btn-secondary" onclick={close}>Cancel</button>
            <button
              id="save-btn"
              class="btn-primary"
              onclick={save}
              disabled={saveDisabled}
              style:background-color={saveBtnBg}
            >
              {saveLabel}
            </button>
          </div>
        {/if}

        <!-- Additional links -->
        {#if hasAdditionalLinks}
          <div class="modal-additional-links">
            {#if mode === 'my_tunes'}<a
                href="#"
                class="remove-link"
                onclick={(e) => {
                  e.preventDefault()
                  removeFromMyTunes()
                }}>Remove From My Tunes</a
              >{/if}{#if loggedIn}<a
                href="#"
                onclick={(e) => {
                  e.preventDefault()
                  toggleConfigSection()
                }}>Configure This Tune</a
              >{/if}{#if mode === 'session' && isSessionAdmin}<a
                href="#"
                class="remove-link"
                onclick={(e) => {
                  e.preventDefault()
                  removeFromSession()
                }}>Remove From Session</a
              >{/if}
          </div>
        {/if}

        <!-- Tabs (Stats / History / Played With) -->
        <div class="modal-tabs-section">
          <!-- Kit Tabs engine with the drawer's legacy skin; switchTab (the
               onValueChange handler) keeps the lazy History/Played-With loads.
               mobileSelect stays 'auto': 3 tabs fit a phone, so the drawer keeps
               visual tabs at mobile width (it never had the select). -->
          <Tabs
            tabs={[
              { id: 'stats', label: 'Stats' },
              { id: 'history', label: 'History' },
              { id: 'played-with', label: 'Played With' },
            ]}
            bind:value={activeTab}
            onValueChange={switchTab}
            styled={false}
            listClass="modal-tabs-header"
            tabClass="modal-tab"
            selectLabel="Tune info section" />
          <div class="modal-tabs-content">
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
              {#if mode === 'my_tunes'}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{myPlayCount}</span>
                    {plural(myPlayCount, 'time')} at my sessions
                  </div>
                </div>
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                    {plural(tune.global_play_count || 0, 'time')} at all sessions
                  </div>
                </div>
              {:else if mode === 'session' || mode === 'session_instance'}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.times_played || 0}</span>
                    {plural(tune.times_played || 0, 'time')} at this session
                  </div>
                </div>
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                    {plural(tune.global_play_count || 0, 'time')} at all sessions
                  </div>
                </div>
              {:else if mode === 'admin'}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                    {plural(tune.global_play_count || 0, 'time')} at all sessions
                  </div>
                </div>
                <div class="stat-card">
                  <div class="stat-line">
                    In the repertoire of <span class="stat-number">{tune.session_count || 0}</span> sessions
                  </div>
                </div>
              {:else}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                    {plural(tune.global_play_count || 0, 'time')} at all sessions
                  </div>
                </div>
              {/if}
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

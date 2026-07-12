<script>
  // Svelte 5 port of the unified tune-detail modal (spec 035 Step 3).
  //
  // A behavior-for-behavior port of the legacy vanilla tune-detail modal behind the same
  // window.TuneDetailModal contract (installed by main.js). The DOM contract is
  // unchanged — #tune-detail-modal / .modal-dialog / #tune-detail-content and every
  // legacy section class — because static/css/tune_detail_modal.css, the live
  // shell's dark scoping (frontend/src/app.css targets #tune-detail-modal) and the
  // e2e suite all select on it. For the same reason this component has NO <style>
  // block: Svelte scoping would detach it from the shared stylesheet.
  //
  // Contexts: my_tunes / session / session_instance / admin, plus the read-only
  // global lookup view (additionalData.global).
  import { Chip, Dialog, Seg, Tabs, toast } from '../lib/index.js'
  import {
    MUSICAL_KEYS,
    extractTuneData,
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
    overlayOfflineOps,
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
  let config = $state(null) // current show() config
  let tune = $state(null) // currentTuneData
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
  let historyScope = $state('all')
  let historyCache = $state({})
  let playedWithScope = $state('all')
  let playedWithCache = $state({})

  // ---- derived ----------------------------------------------------------------
  const ctx = $derived(config?.context)
  const addl = $derived(config?.additionalData || {})
  const isGlobal = $derived(!!addl.global)
  const isTitleClickable = $derived(ctx !== 'admin' && !isGlobal)

  const displayName = $derived(tune ? getDisplayName(tune, ctx) : '')
  const headerTuneType = $derived((tune && tune.tune_type) || addl.tuneType || '')

  const onList = $derived.by(() => {
    if (!tune) return false
    if (ctx === 'my_tunes') return true
    return tune.person_tune_status?.on_list || false
  })
  const rollup = $derived(tune ? rollupStatus(tune, ctx) : 'want to learn')
  const instruments = $derived(tune ? getInstrumentData(tune, ctx).instruments : [])
  const multiInstrument = $derived(instruments && instruments.length >= 2)

  const heardVisible = $derived.by(() => {
    if (!tune || ctx === 'admin') return false
    const status = tune.person_tune_status?.learn_status || tune.learn_status
    if (!status || status === 'learned') return false
    return ctx === 'my_tunes'
      ? !!(tune.person_tune_id || addl.personTuneId)
      : !!tune.person_tune_status?.person_tune_id
  })
  const heardCountView = $derived.by(() => {
    if (!tune) return 0
    return ctx === 'my_tunes' ? tune.heard_count || 0 : tune.person_tune_status?.heard_count || 0
  })

  const notation = $derived(tune ? notationInfo(tune) : null)
  const notationView = $derived(tune ? notationDisplay(tune, notationMode, notationSize) : null)
  const thesessionLink = $derived(tune ? theSessionUrl(tune) : '')
  const abctoolsLink = $derived(tune ? abcToolsUrl(tune) : '')

  const hasCachedNotation = $derived(
    !!(tune && (tune.abc || tune.incipit_abc || tune.image || tune.incipit_image))
  )
  // The settings/cache endpoint is login-required, so the Generate Notation
  // affordance only shows for logged-in viewers (admin context implies one).
  const canGenerateNotation = $derived(!!tune && (ctx === 'admin' || !!addl.isUserLoggedIn))
  const fetchBtnLabel = $derived.by(() => {
    if (!tune) return 'Fetch'
    const value = (fields.setting || '').trim()
    const originalSettingId =
      (ctx === 'session_instance' ? originals.setting_override : originals.setting_id) || null
    const settingIdsMatch = (!value && !originalSettingId) || extractSettingId(value) === originalSettingId
    return hasCachedNotation && settingIdsMatch ? 'Refresh' : 'Fetch'
  })

  const isDirty = $derived.by(() => {
    if (!tune || !config) return false
    switch (ctx) {
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

  const historyOptions = $derived(config ? historyScopeOptions(config) : [])
  const playedWithOptions = $derived(config ? playedWithScopeOptions(config) : [])
  const historyState = $derived(historyCache[historyScope] || { status: 'loading' })
  const playedWithState = $derived(playedWithCache[playedWithScope] || { status: 'loading' })

  const hasAdditionalLinks = $derived(
    ctx === 'my_tunes' || (ctx !== 'admin' && !isGlobal) || (ctx === 'session' && !!addl.isSessionAdmin)
  )

  // ---- data application --------------------------------------------------------

  function buildOriginals(tuneData, cfg) {
    const o = { context: cfg.context }
    switch (cfg.context) {
      case 'my_tunes':
        o.name_alias = tuneData.name_alias || ''
        o.setting_id = tuneData.setting_id || ''
        o.notes = tuneData.notes || ''
        o.learn_status = tuneData.learn_status || 'want to learn'
        break
      case 'session':
        o.alias = tuneData.alias || ''
        o.setting_id = tuneData.setting_id || ''
        o.key = tuneData.key || ''
        o.learn_status = tuneData.person_tune_status?.learn_status || ''
        break
      case 'session_instance':
        o.name = tuneData.name || ''
        o.setting_override = tuneData.setting_override || ''
        o.key_override = tuneData.key_override || ''
        o.learn_status = tuneData.person_tune_status?.learn_status || ''
        break
      case 'admin':
        o.name = tuneData.name || ''
        break
    }
    return o
  }

  function initFields(tuneData, cfg) {
    switch (cfg.context) {
      case 'my_tunes':
        return {
          name_alias: tuneData.name_alias || '',
          setting: String(tuneData.setting_id || ''),
          notes: tuneData.notes || '',
        }
      case 'session':
        return {
          alias: tuneData.alias || '',
          setting: String(tuneData.setting_id || ''),
          key: tuneData.key || '',
        }
      case 'session_instance':
        return {
          alias: tuneData.name || '',
          setting: String(tuneData.setting_override || ''),
          key: tuneData.key_override || '',
        }
      case 'admin':
        return { name: tuneData.name || '' }
      default:
        return {}
    }
  }

  // Equivalent of the legacy renderModalContent: (re)apply tune data and reset
  // all per-render section state (tabs back to Stats, notation back to initial,
  // configure collapsed except admin, fields re-seeded).
  function applyTuneData(data) {
    tune = data
    mergedFrom = null
    originals = buildOriginals(data, config)
    fields = initFields(data, config)
    settingError = ''
    saveState = 'idle'
    fetchBtnState = 'idle'
    refreshState = 'idle'
    statusSaving = false
    isConfigVisible = config.context === 'admin'
    // Tabs reset to Stats — except a show() that asked to keep a tab (the
    // in-place add -> my_tunes variant upgrade preserves the user's tab).
    activeTab = config.initialTab || 'stats'
    if (activeTab === 'history') loadHistory()
    else if (activeTab === 'played-with') loadPlayedWith()
    const info = notationInfo(data)
    notationMode = info.initialMode
    notationSize = 'incipit'
    activeSess = window.activeSession || null
    phase = 'ready'
  }

  function showErr(message) {
    errorMsg = message
    phase = 'error'
  }

  // Offline fallback: render the tune from the locally-cached bundle (incipit
  // notation) + not-yet-synced ops so the drawer works without a connection.
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
        const t = overlayOfflineOps(cached, ops, cfg.tuneId)
        // extractTuneData just picks a sub-key, so provide the tune under each.
        applyTuneData(extractTuneData({ success: true, person_tune: t, session_tune: t, tune: t }, cfg.context))
      })
      .catch(() => showErr(errMsg || 'Failed to load tune details'))
  }

  // ---- public API (wired to window.TuneDetailModal by main.js) ------------------

  export function show(cfg) {
    config = cfg
    historyCache = {}
    playedWithCache = {}
    historyScope = historyScopeOptions(cfg)[0].key
    playedWithScope = playedWithScopeOptions(cfg)[0].key
    piExpanded = !!cfg.expandInstrumentStatus
    pendingHeard = 0
    mergedFrom = null

    // For my_tunes, the URL param is the person_tune_id; otherwise the tune_id.
    const urlParam =
      cfg.context === 'my_tunes' && cfg.additionalData?.personTuneId
        ? cfg.additionalData.personTuneId
        : cfg.tuneId
    updateUrlWithTune(urlParam, cfg.context)

    phase = 'loading'
    clearTimeout(hideTimer)
    visible = true
    setTimeout(() => {
      showCls = true
    }, 10)
    modalShowTime = Date.now()

    fetch(cfg.apiEndpoint)
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
          const td = extractTuneData(data, cfg.context)
          if (data.redirected_from && td.tune_id) {
            // The tune was merged away (spec 030): the server followed the redirect
            // and returned the canonical tune. Heal the stale id in our config +
            // the URL bar, and tell the user what happened.
            const oldId = data.redirected_from
            const newId = td.tune_id
            config.tuneId = newId
            config.apiEndpoint = config.apiEndpoint.replace(`/tunes/${oldId}`, `/tunes/${newId}`)
            if (cfg.context !== 'my_tunes') updateUrlWithTune(newId, cfg.context)
            applyTuneData(td)
            mergedFrom = oldId
          } else {
            applyTuneData(td)
          }
        } else {
          renderTuneFromOffline(cfg, data.error)
        }
      })
      .catch((error) => {
        console.error('Error loading tune details:', error)
        // A dead ptid deep-link (the row was conflict-deleted by a tune merge,
        // spec 030) degrades to a notice + a clean URL rather than a raw error.
        if (error.status === 404 && cfg.context === 'my_tunes') {
          removeUrlTuneParam(cfg.context)
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
    removeUrlTuneParam(ctx)
    clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      visible = false
    }, 300)
  }

  export function toggleConfigSection() {
    if (ctx === 'admin') return // always visible on admin
    isConfigVisible = !isConfigVisible
  }

  export function logToActiveSession() {
    const active = window.activeSession
    if (!active || !active.session_instance_id) return
    const tuneId = (config && config.tuneId) || (tune && tune.tune_id)
    if (!tuneId) return
    // Clean the modal's tune param off the URL so the back button is sane.
    removeUrlTuneParam(ctx)
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
    const data = getInstrumentData(tune, ctx)
    config.onStatusChange({
      tune_id: tune.tune_id,
      learn_status: getModalLearnStatus(tune, ctx),
      instrument_status: { ...data.overrides },
      on_list: onList,
      person_tune_id:
        (ctx === 'my_tunes'
          ? tune.person_tune_id || addl.personTuneId
          : tune.person_tune_status && tune.person_tune_status.person_tune_id) || null,
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
    if (!tuneId) return
    const data = getInstrumentData(tune, ctx)
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
      tune.learn_status = status
      if (tune.person_tune_status) tune.person_tune_status.learn_status = status
      setInstrumentOverrides(tune, ctx, overrides)
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
    const data = getInstrumentData(tune, ctx)
    const inst = data.instruments[index]
    if (!inst) return
    const learnStatus = getModalLearnStatus(tune, ctx)
    const current = resolveInstStatus(tune, ctx, inst)
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
    setInstrumentOverrides(tune, ctx, updated)
    notifyStatusChange()
    submitMyTunesOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: inst.instrument, status: target }).catch(
      () => {
        setInstrumentOverrides(tune, ctx, prev)
        notifyStatusChange()
      }
    )
  }

  // Remove a tune from one (manual) instrument's list — deletes the override entirely.
  export function removeInstrumentTune(index) {
    const tuneId = tune && tune.tune_id
    if (!tuneId) return
    const data = getInstrumentData(tune, ctx)
    const inst = data.instruments[index]
    if (!inst || inst.is_auto) return
    const prev = { ...data.overrides }
    const updated = { ...data.overrides }
    delete updated[inst.instrument]
    setInstrumentOverrides(tune, ctx, updated)
    notifyStatusChange()
    submitMyTunesOp({ type: 'set_instrument_status', tune_id: tuneId, instrument: inst.instrument, status: null }).catch(
      () => {
        setInstrumentOverrides(tune, ctx, prev)
        notifyStatusChange()
      }
    )
  }

  // Add the tune to the user's list as 'want to learn'.
  export function addToTunebook() {
    const tuneId = tune.tune_id
    const keepTab = activeTab // survives the refetch's per-render tab reset
    // name/tune_type ride along so an offline add shows in the My Tunes list while queued.
    submitMyTunesOp({
      type: 'add',
      tune_id: tuneId,
      learn_status: 'want to learn',
      name: tune.name || tune.tune_name,
      tune_type: tune.tune_type,
    })
      .then((res) => {
        if (res && res.queued) {
          // Offline: send the user to their list (where the queued add shows as
          // pending) and acknowledge with a toast there — not a blocking alert.
          try {
            sessionStorage.setItem('myTunesToast', 'Added to your tunes. It will sync when you are back online.')
          } catch (e) {}
          window.location.href = '/my-tunes'
          return
        }
        // Online: reload the modal to show the updated (in-collection) state.
        if (config && config.apiEndpoint) {
          fetch(config.apiEndpoint)
            .then((response) => response.json())
            .then((data) => {
              if (data.success) {
                applyTuneData(extractTuneData(data, ctx))
                // The refetched payload carries the new person_tune identity, so
                // the host can add a card for a tune it has none for (chained adds
                // must live-update the underlying My Tunes list). Fires exactly
                // once — the variant upgrade below never re-notifies.
                notifyStatusChange()
                maybeUpgradeToMyTunesVariant(keepTab)
              }
            })
        }
      })
      .catch((error) => {
        console.error('Error adding to tunebook:', error)
        toast('Failed to add tune to your list', 'error')
      })
  }

  // ---- heard count -------------------------------------------------------------------

  function bumpHeard(delta) {
    if (ctx === 'admin') return
    const currentCount = heardCountView
    if (delta < 0 && currentCount === 0) return
    const newCount = Math.max(0, currentCount + delta)

    const setLocal = (n) => {
      if (ctx === 'my_tunes') tune.heard_count = n
      else if (tune.person_tune_status) tune.person_tune_status.heard_count = n
    }
    setLocal(newCount) // optimistic

    // Heard count is keyed by catalog tune_id and sent as an ABSOLUTE target so a
    // replayed offline op can never double-count. Requires the tune to be in the
    // user's collection (a person_tune row must exist for the set to land).
    const tuneId = tune.tune_id
    const inCollection = ctx === 'my_tunes' || !!tune.person_tune_status
    if (!tuneId || !inCollection) {
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

  export function save() {
    if (!tune || !config || saveDisabled) return

    const updates = {}
    let apiEndpoint = ''

    switch (ctx) {
      case 'my_tunes': {
        if (fields.name_alias !== originals.name_alias) updates.name_alias = fields.name_alias.trim() || null
        const newSettingId = extractSettingId(fields.setting)
        if (newSettingId !== (originals.setting_id || null)) updates.setting_id = newSettingId
        if (fields.notes !== originals.notes) updates.notes = fields.notes.trim() || null
        apiEndpoint = `/api/my-tunes/${config.additionalData.personTuneId}`
        break
      }
      case 'session': {
        if (fields.alias !== originals.alias) updates.alias = fields.alias.trim() || null
        const newSettingId = extractSettingId(fields.setting)
        if (newSettingId !== (originals.setting_id || null)) updates.setting_id = newSettingId
        if (fields.key !== originals.key) updates.key = fields.key || null
        apiEndpoint = `/api/sessions/${config.additionalData.sessionPath}/tunes/${tune.tune_id}`
        break
      }
      case 'session_instance': {
        if (fields.alias !== originals.name) updates.name = fields.alias.trim() || null
        const newSettingId = extractSettingId(fields.setting)
        if (newSettingId !== (originals.setting_override || null)) updates.setting_override = newSettingId
        if (fields.key !== originals.key_override) updates.key_override = fields.key || null
        apiEndpoint = `/api/sessions/${config.additionalData.sessionPath}/${config.additionalData.dateOrId}/tunes/${tune.tune_id}`
        break
      }
      case 'admin': {
        updates.name = fields.name.trim()
        if (!updates.name) {
          toast('Tune name cannot be empty', 'error')
          return
        }
        apiEndpoint = `/api/admin/tunes/${tune.tune_id}`
        break
      }
    }

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
          originals = buildOriginals({ ...tune, ...updates }, config)
          // Remove tune parameter from URL first (before onSave which might reload)
          removeUrlTuneParam(ctx)
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

  // Fetch and cache setting from TheSession.org, save the setting id per context,
  // then re-render with the fetched notation. Resolves true when notation was
  // fetched (even if the per-context setting-id save then warned), so callers
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

        // Save the setting id to the database based on context (none on admin/global)
        let saveEndpoint = ''
        let savePayload = {}
        if (ctx === 'my_tunes') {
          saveEndpoint = `/api/my-tunes/${config.additionalData.personTuneId}`
          savePayload = { setting_id: fetchedSettingId }
        } else if (ctx === 'session') {
          saveEndpoint = `/api/sessions/${config.additionalData.sessionPath}/tunes/${tune.tune_id}`
          savePayload = { setting_id: fetchedSettingId }
        } else if (ctx === 'session_instance') {
          saveEndpoint = `/api/sessions/${config.additionalData.sessionPath}/${config.additionalData.dateOrId}/tunes/${tune.tune_id}`
          savePayload = { setting_override: fetchedSettingId }
        }

        if (saveEndpoint) {
          return fetch(saveEndpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(savePayload),
          })
            .then((response) => response.json())
            .then((saveData) => {
              if (saveData.success) {
                if (ctx === 'session_instance') tune.setting_override = fetchedSettingId
                else tune.setting_id = fetchedSettingId
                applyTuneData(tune) // legacy re-renders the modal here
                feedback('ok')
              } else {
                console.error('Error saving setting_id:', saveData.error)
                applyTuneData(tune) // still re-render with the fetched data
                feedback('warn')
              }
              return true
            })
            .catch((error) => {
              console.error('Error saving setting_id:', error)
              applyTuneData(tune) // still re-render with the fetched data
              return true
            })
        }
        applyTuneData(tune)
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
    const personTuneId = config.additionalData?.personTuneId
    if (!personTuneId) {
      toast('Unable to remove tune', 'error')
      return
    }
    fetch(`/api/my-tunes/${personTuneId}`, { method: 'DELETE' })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          removeUrlTuneParam(ctx)
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
    const sessionPath = config.additionalData?.sessionPath
    const tuneId = tune?.tune_id
    if (!sessionPath || !tuneId) {
      toast('Unable to remove tune from session', 'error')
      return
    }
    fetch(`/api/sessions/${sessionPath}/tunes/${tuneId}`, { method: 'DELETE' })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          removeUrlTuneParam(ctx)
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
    let apiEndpoint
    if (ctx === 'admin') {
      apiEndpoint = `/api/admin/tunes/${tuneId}/refresh_tunebook_count`
    } else if (ctx === 'session' || ctx === 'session_instance') {
      apiEndpoint = `/api/sessions/${config.additionalData.sessionPath}/tunes/${tuneId}/refresh_tunebook_count`
    } else {
      // my_tunes uses the admin endpoint (same as the legacy modal)
      apiEndpoint = `/api/admin/tunes/${tuneId}/refresh_tunebook_count`
    }
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

  export function setHistoryScope(scope) {
    historyScope = scope
    loadHistory()
  }

  export function setPlayedWithScope(scope) {
    playedWithScope = scope
    loadPlayedWith()
  }

  function loadHistory() {
    if (!config) return
    const scope = historyScope
    const tuneId = config.tuneId || (tune && tune.tune_id)
    if (!tuneId) {
      historyCache[scope] = { status: 'none' }
      return
    }
    if (historyCache[scope]?.status === 'ready') return
    historyCache[scope] = { status: 'loading' }
    let url = `/api/tunes/${tuneId}/history`
    if (scope === 'session') {
      url += `?session_path=${encodeURIComponent(config.additionalData.sessionPath)}`
    } else if (scope === 'mine') {
      url += '?person=me'
    }
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (scope !== historyScope) return // user toggled scope while loading
        if (!data.success) {
          historyCache[scope] = { status: 'error' }
          return
        }
        historyCache[scope] = { status: 'ready', data }
      })
      .catch(() => {
        if (scope === historyScope) historyCache[scope] = { status: 'error' }
      })
  }

  function loadPlayedWith() {
    if (!config) return
    const scope = playedWithScope
    const tuneId = config.tuneId || (tune && tune.tune_id)
    if (!tuneId) {
      playedWithCache[scope] = { status: 'none' }
      return
    }
    if (playedWithCache[scope]?.status === 'ready') return
    playedWithCache[scope] = { status: 'loading' }
    let url = `/api/tunes/${tuneId}/played-with`
    if (scope === 'session') {
      url += `?session_path=${encodeURIComponent(config.additionalData.sessionPath)}`
    }
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (scope !== playedWithScope) return
        if (!data.success) {
          playedWithCache[scope] = { status: 'error' }
          return
        }
        playedWithCache[scope] = { status: 'ready', data }
      })
      .catch(() => {
        if (scope === playedWithScope) playedWithCache[scope] = { status: 'error' }
      })
  }

  // Open a companion tune's detail modal in place of the current one, KEEPING
  // the drawer's current "version": in-drawer navigation inherits the context
  // (and the host callbacks — onSave/onStatusChange) so the user stays in the
  // same variant however deep they chain.
  //  * session-scoped drawers carry the session along (as a 'session' view —
  //    the tune may not be in this particular instance's log) so the At This
  //    Session / Globally toggles stay available.
  //  * my_tunes drawers resolve the companion's person_tune row first: on-list
  //    tunes reopen as the full my_tunes variant (notes/config/My-Sessions
  //    history); not-on-list tunes degrade to the logged-in global view (with
  //    the Add control), remembering the my_tunes chain (chainCtx) so a later
  //    hop still resolves against the my_tunes variant.
  //  * admin drawers chain as admin; the global lookup stays global.
  function openPlayedWithTune(tuneId) {
    if (!tuneId) return
    const prev = config?.additionalData || {}
    const loggedIn = prev.isUserLoggedIn ?? (ctx === 'my_tunes' || !!tune?.person_tune_status)
    const inherited = { onSave: config?.onSave, onStatusChange: config?.onStatusChange }
    const baseCtx = prev.chainCtx || ctx
    const sessionPath = !prev.global && (ctx === 'session' || ctx === 'session_instance') ? prev.sessionPath : null
    if (sessionPath) {
      show({
        context: 'session',
        tuneId: tuneId,
        apiEndpoint: `/api/sessions/${sessionPath}/tunes/${tuneId}`,
        ...inherited,
        additionalData: {
          sessionPath: sessionPath,
          isUserLoggedIn: loggedIn,
          isSessionAdmin: !!prev.isSessionAdmin,
        },
      })
    } else if (baseCtx === 'my_tunes' && loggedIn) {
      openMyTunesChained(tuneId, inherited)
    } else if (baseCtx === 'admin') {
      show({
        context: 'admin',
        tuneId: tuneId,
        apiEndpoint: `/api/admin/tunes/${tuneId}`,
        ...inherited,
        additionalData: { isUserLoggedIn: loggedIn },
      })
    } else {
      show({
        context: 'session_instance',
        tuneId: tuneId,
        apiEndpoint: `/api/tunes/${tuneId}/detail`,
        ...inherited,
        additionalData: { isUserLoggedIn: loggedIn, global: true },
      })
    }
  }

  // my_tunes chaining: the global detail payload carries person_tune_status
  // (incl. person_tune_id), which tells us whether the companion tune can open
  // as the full my_tunes variant or must fall back to the global view.
  function openMyTunesChained(tuneId, inherited) {
    phase = 'loading'
    const fallback = (st) =>
      show({
        context: 'session_instance',
        tuneId: tuneId,
        apiEndpoint: `/api/tunes/${tuneId}/detail`,
        ...inherited,
        additionalData: {
          isUserLoggedIn: true,
          global: true,
          chainCtx: 'my_tunes',
          tuneName: st && st.tune_name,
          tuneType: st && st.tune_type,
        },
      })
    fetch(`/api/tunes/${tuneId}/detail`)
      .then((r) => r.json())
      .then((data) => {
        const st = (data && data.session_tune) || null
        const ptid = st && st.person_tune_status && st.person_tune_status.person_tune_id
        if (data && data.success && ptid) {
          show({
            context: 'my_tunes',
            tuneId: st.tune_id || tuneId,
            apiEndpoint: `/api/my-tunes/${ptid}`,
            ...inherited,
            additionalData: {
              personTuneId: ptid,
              tuneName: st.tune_name,
              tuneType: st.tune_type,
              isUserLoggedIn: true,
            },
          })
        } else {
          fallback(st)
        }
      })
      .catch(() => fallback(null))
  }

  // A tune just added from an Add view whose ORIGIN is the my_tunes variant
  // (Played With chaining carries chainCtx; the "Find a tune" global view opened
  // on the /my-tunes page itself shares this path) upgrades the drawer IN PLACE
  // to the full my_tunes variant it would have opened as had the tune already
  // been on the list — keeping the tab the user was on. Called after the add's
  // refetch + host notification; never re-notifies. Offline adds never get here
  // (no person_tune_id exists yet — the queued-add flow redirects to /my-tunes).
  function maybeUpgradeToMyTunesVariant(keepTab) {
    if (ctx === 'my_tunes') return // already the full variant
    const fromMyTunes = addl.chainCtx === 'my_tunes' || window.location.pathname.includes('/my-tunes')
    const ptid = tune && tune.person_tune_status && tune.person_tune_status.person_tune_id
    if (!fromMyTunes || !ptid) return
    show({
      context: 'my_tunes',
      tuneId: tune.tune_id,
      apiEndpoint: `/api/my-tunes/${ptid}`,
      onSave: config?.onSave,
      onStatusChange: config?.onStatusChange,
      initialTab: keepTab,
      additionalData: {
        personTuneId: ptid,
        tuneName: tune.tune_name || tune.name,
        tuneType: tune.tune_type,
        isUserLoggedIn: true,
      },
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
              {#if addl.tuneType}
                <td class="modal-header-pill-cell"><Chip label={addl.tuneType} styled={false} chipClass="tune-type-pill" /></td>
              {/if}
              <td class="modal-header-title-cell">
                <h2 class="modal-tune-title">{addl.tuneName || 'Loading...'}</h2>
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

        <!-- Configure section (collapsible except on admin; not in the global lookup view) -->
        {#if !isGlobal}
          <div id="configure-section" class="configure-section" style="display: {isConfigVisible ? 'block' : 'none'};">
            <div class="configure-field-group-inline">
              <div class="configure-label">Official Name:</div>
              <div class="configure-value">{tune.tune_name || tune.name || 'Unknown'}</div>
            </div>
            <div class="configure-field-group-inline">
              <div class="configure-label">Tune ID:</div>
              <div class="configure-value">{tune.tune_id || 'Unknown'}</div>
            </div>
            {#if ctx === 'my_tunes'}
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
            {:else if ctx === 'session' || ctx === 'session_instance'}
              <div class="configure-field-group-inline">
                <label class="configure-label" for="alias-input">
                  {ctx === 'session' ? 'We call this:' : 'In this case, we called it:'}
                </label>
                <input
                  type="text"
                  id="alias-input"
                  class="configure-input"
                  autocomplete="off"
                  autocorrect="off"
                  autocapitalize="off"
                  spellcheck="false"
                  placeholder={ctx === 'session' ? 'Enter session name for this tune' : 'Enter name for this instance'}
                  bind:value={fields.alias}
                />
              </div>
              <div class="configure-field-group-inline">
                <label class="configure-label" for="setting-input">
                  {ctx === 'session' ? 'Our setting:' : 'This time, we played setting:'}
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
                  {ctx === 'session' ? 'We play this in:' : 'This time, we played in:'}
                </label>
                <select id="key-select" class="configure-select" bind:value={fields.key}>
                  {#each MUSICAL_KEYS as key}
                    <option value={key}>{key || '(not specified)'}</option>
                  {/each}
                </select>
              </div>
            {:else if ctx === 'admin'}
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

        <!-- Tunebook status section (not on admin; only when logged in) -->
        {#if ctx !== 'admin' && addl.isUserLoggedIn}
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
                      {@const st = resolveInstStatus(tune, ctx, inst)}
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

        <!-- Notes (my_tunes only) -->
        {#if ctx === 'my_tunes'}
          <div class="notes-section">
            <textarea
              id="notes-textarea"
              class="notes-textarea"
              placeholder="Add notes about this tune..."
              bind:value={fields.notes}
            ></textarea>
          </div>
        {/if}

        <!-- Action buttons (none in the read-only global lookup view) -->
        {#if !isGlobal}
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
            {#if ctx === 'my_tunes'}<a
                href="#"
                class="remove-link"
                onclick={(e) => {
                  e.preventDefault()
                  removeFromMyTunes()
                }}>Remove From My Tunes</a
              >{/if}{#if ctx !== 'admin' && !isGlobal}<a
                href="#"
                onclick={(e) => {
                  e.preventDefault()
                  toggleConfigSection()
                }}>Configure This Tune</a
              >{/if}{#if ctx === 'session' && addl.isSessionAdmin}<a
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
              {#if ctx === 'my_tunes'}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.session_play_count || 0}</span>
                    {plural(tune.session_play_count || 0, 'time')} at my sessions
                  </div>
                </div>
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                    {plural(tune.global_play_count || 0, 'time')} at all sessions
                  </div>
                </div>
              {:else if ctx === 'session' || ctx === 'session_instance'}
                {#if !isGlobal}
                  <div class="stat-card">
                    <div class="stat-line">
                      Logged <span class="stat-number">{tune.times_played || 0}</span>
                      {plural(tune.times_played || 0, 'time')} at this session
                    </div>
                  </div>
                {/if}
                <div class="stat-card">
                  <div class="stat-line">
                    Logged <span class="stat-number">{tune.global_play_count || 0}</span>
                    {plural(tune.global_play_count || 0, 'time')} at all sessions
                  </div>
                </div>
              {:else if ctx === 'admin'}
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
              {/if}
            </div>
            <div id="history-tab" class="modal-tab-pane{activeTab === 'history' ? ' active' : ''}">
              {#if historyOptions.length > 1}
                <Seg
                  options={historyOptions.map((o) => ({ id: o.key, label: o.label }))}
                  value={historyScope}
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
                              {historyScope !== 'session'
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
                  value={playedWithScope}
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
                      This tune has not been played in a set with any other tune{playedWithScope === 'session'
                        ? ' at this session'
                        : ''} yet.
                    </div>
                  {:else}
                    <div class="played-with-list">
                      {#each pwTunes as t}
                        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                        <div class="played-with-item" data-tune-id={t.tune_id} onclick={() => openPlayedWithTune(t.tune_id)}>
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

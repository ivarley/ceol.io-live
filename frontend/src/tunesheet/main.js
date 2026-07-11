// Entry for the app-wide tune-detail sheet (spec 035 Step 3) — the Svelte port of
// the legacy vanilla tune-detail modal. Mounts the host component (which always renders
// the #tune-detail-modal container, hidden) and installs the window.TuneDetailModal
// shim so every legacy caller (my-tunes page, session pages, admin tunes, the live
// logger, the hamburger "Find a tune") keeps working unchanged.
import { mount } from 'svelte'
import TuneSheet from './TuneSheet.svelte'
import FindTune from './FindTune.svelte'
import { getTuneIdFromUrl } from './logic.js'

// Idempotent, like the legacy file: base.html loads this on every page and the
// hamburger's ensureTuneModal() can inject it again — registering twice would
// mount a second modal container.
if (!window.TuneDetailModal) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const sheet = mount(TuneSheet, { target: host })

  window.TuneDetailModal = {
    // The Svelte component wires its own listeners; kept for legacy callers.
    init() {},
    show: (config) => sheet.show(config),
    close: () => sheet.close(),
    getTuneIdFromUrl,
    logToActiveSession: () => sheet.logToActiveSession(),
    toggleConfigSection: () => sheet.toggleConfigSection(),
    switchNotationMode: (mode) => sheet.switchNotationMode(mode),
    toggleNotationSize: () => sheet.toggleNotationSize(),
    switchTab: (tab) => sheet.switchTab(tab),
    setHistoryScope: (scope) => sheet.setHistoryScope(scope),
    setPlayedWithScope: (scope) => sheet.setPlayedWithScope(scope),
    save: () => sheet.save(),
    incrementHeardCount: () => sheet.incrementHeardCount(),
    decrementHeardCount: () => sheet.decrementHeardCount(),
    addToTunebook: () => sheet.addToTunebook(),
    setTunebookStatus: (status) => sheet.setTunebookStatus(status),
    setInstrumentStatus: (index, status) => sheet.setInstrumentStatus(index, status),
    removeInstrumentTune: (index) => sheet.removeInstrumentTune(index),
    toggleStatusExpand: (event) => sheet.toggleStatusExpand(event),
    removeFromMyTunes: () => sheet.removeFromMyTunes(),
    removeFromSession: () => sheet.removeFromSession(),
    refreshTunebookCount: () => sheet.refreshTunebookCount(),
    fetchSetting: () => sheet.fetchSetting(),
    // Dirty-checking is reactive in the Svelte port; kept as no-ops for legacy callers.
    onFieldChange() {},
    onSettingInput() {},
  }

  // The app-wide "Find a tune" overlay (spec 035 Step 3c) rides in the same
  // bundle; hamburger_menu.js's findTune() delegates here outside the live editor.
  const findHost = document.createElement('div')
  document.body.appendChild(findHost)
  const findTune = mount(FindTune, { target: findHost })
  window.FindTuneOverlay = { open: () => findTune.show() }
}

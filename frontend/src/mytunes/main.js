// Add-tune pane bundle: a thin shell around the live logger's TuneSearch plus a
// context-specific configure phase. One bundle serves both flavors — the mount
// target decides which app a page gets:
//   #mytunes-add-root      -> window.MyTunesAddPane      (/my-tunes)
//   #session-tune-add-root -> window.SessionTuneAddPane  (/sessions/<path> tunes tab)
import { mount } from 'svelte'
import './mytunes-add.css'
import AddTuneApp from './AddTuneApp.svelte'
import SessionTuneAddApp from './SessionTuneAddApp.svelte'

const myRoot = document.getElementById('mytunes-add-root')
if (myRoot) {
  window.MyTunesAddPane = mount(AddTuneApp, { target: myRoot })
}

const sessionRoot = document.getElementById('session-tune-add-root')
if (sessionRoot) {
  window.SessionTuneAddPane = mount(SessionTuneAddApp, { target: sessionRoot })
}

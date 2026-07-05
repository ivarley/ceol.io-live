// Add-to-My-Tunes pane bundle (spec: my-tunes add redesign). Mounted standalone on
// /my-tunes — a thin shell around the live logger's TuneSearch plus the configure
// phase. The page drives it through window.MyTunesAddPane.open()/close().
import { mount } from 'svelte'
import './mytunes-add.css'
import AddTuneApp from './AddTuneApp.svelte'

const target = document.getElementById('mytunes-add-root')
if (target) {
  window.MyTunesAddPane = mount(AddTuneApp, { target })
}

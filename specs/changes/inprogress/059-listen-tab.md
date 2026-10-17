# 059: Listen, with a home of its own

**Date:** 2026-10-11
**Status:** BUILT in the iOS app (this change). Not on the web, which has no listener.

## Why

The certainty meter (spec 053, "Listening on the phone") names the tune that is playing.
Until now it could only be reached from a night's page, as a recorder: you were recording
a night for the listener, and the meter was a panel over that. But the plainest use of
the thing is "what tune is this?", with no night in mind: at a session you don't log, in
a kitchen, from a recording. This gives the meter a tab of its own and lets it be used
without logging anything.

## Decisions

Made by the product owner, 2026-10-11.

- **A fifth tab, Listen**, with an ear icon, between Sessions and Tunes. It is the
  meter's home. The system tab bar on the web stays four tabs: the web has no listener.
- **Two modes**, named here and not in the app:
  - **Log mode**: the meter logs the tunes it is sure of to a night, as before. It is
    the mode you arrive in from a night's page (its Listen button). The screen says
    "Logging tunes to {night}" at the top, with **Stop logging**, which asks "Stop
    logging these tunes to {night} and just show them instead?" and then moves to
    Ad-hoc mode without stopping the listening.
    Several phones can log the same night at once. Before logging a tune, the meter
    checks the night's latest set (the last one with tunes, open or just ended); if
    that tune is already its last or second-to-last tune, someone else has logged it,
    and the meter treats it as logged without adding a row (and "Wrong tune" leaves
    that row alone). The server still merges two adds of the same tune into the open
    set when they cross on the way (spec 024 §H30).
  - **Ad-hoc mode**: the meter only says what is playing. It is the mode you arrive in
    from the tab, from Home ("What tune am I hearing right now?") and from the three
    "Add a tune" searches (your tunebook, a session's list, a night's log), each of
    which has **Listen To What's Playing Now** under its empty search box. If the meter
    is already logging a night, that button opens it as it is, still logging.
- **When the meter is sure of a tune** in Ad-hoc mode:
  - the tune's relationship to your tunebook, as on any tune sheet: add it (with your
    own name and key, as elsewhere) or change its status, and the heard count;
  - from a session's "Add a tune": **Add To This Session's Tune List**;
  - from a night's "Add a tune", when the meter isn't logging that night: **Log This Tune**;
  - the notation, full screen, to sight-read it.
- **Recent Tunes Heard**, at the bottom of the screen in Ad-hoc mode: the last tunes
  the meter was sure of, each opening the tune's sheet (your tunebook only: there is no
  session to add to or log to from there). Kept on the phone, fifty at most.
- **Recording is off by default in Ad-hoc mode** and can be turned on; in Log mode it is
  on, as before. Turned off part-way, the file so far is discarded. A recording made
  with no night can't be uploaded (the server files recordings under a night), so the
  recordings list keeps it on the phone and offers no Upload.
- **"Log automatically at 100%"** is off and disabled when nothing is being logged. The
  meter still goes to its "sure" state at 100% in either mode: the switch is about
  logging, not about saying so.
- The listening service admits system admins only (listen/service.py). Everyone else
  listens on the phone, where the decider's data ships in the app; the "Listening on"
  choice is shown to system admins only.

## What changed

- `NightRecorder` (`ios/Ceol/Ceol/NightRecorder.swift`): the night is optional
  (`logsTo`, `startLogging`, `stopLogging`: the stream starts again with the night as
  its hint, as a change of where to listen does); the recording file is optional and
  can start or be discarded mid-listen (`AudioCapture.startFile` / `discardFile`; the
  meter log is held in memory until there is a file to sit beside); `selfConfirm` marks
  the tune sure at 100% always and logs only in Log mode with the switch on;
  `RecentTunes` keeps the tunes it was sure of.
- `AppModel`: `startListening(logging:)`, `stopListening()`, `openListen(logging:)`
  (the Listen tab, with a night to log to or none); `pendingLog` for the start screen.
- `ListenScreen.swift`: the tab's screen, also presented full-screen over a search
  sheet (`ListenContext`: where it was opened from and what it offers a sure tune).
- `TunebookPanel` (`TunesViews.swift`): the tune sheet's "your list" box, shared with
  the listen screen.
- `DeepSearchSheet`: the Listen button under the empty field, and the full-screen
  listen cover with the search's own pick as the sure tune's action.
- `HomeView`: "What tune am I hearing right now?".
- `RecordingStore`: `instanceID` optional; no upload without one.

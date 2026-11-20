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
    from the tab, from Home ("What tune is this?") and from the three
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
  recordings list keeps it on the phone and offers "Attach to a night" instead of
  Upload (2026-10-24): pick the session, then one of its nights, the ones on the day
  it was recorded first, or add a night on that day; Upload follows. The list also
  plays any recording on the phone (▶, a slider), and an uploaded one has "Open in
  the segmenter" (the web, signed in): uploading it took the same right the segmenter
  asks, a system admin's or a session admin's with recordings.
- **Provisional tunes** (2026-11-19, web and iPhone). A tune the meter logs by itself
  is logged, but no person has approved it. The row says so with what it already
  carries: `source='listen'` and `confidence=99` (under 100, which is a person's word;
  no new column). In the log it is marked "not checked" and offers Confirm. A second
  phone's meter logging the same tune merges into the row without approving it; a
  person logging it by hand does approve it.
- **Three buttons under the sure tune** (2026-11-19), in either mode, also when the
  meter has logged the tune by itself. They replace the tap on the tune that asked
  "Wrong tune" or "Tune changed":
  - **thumbs down**, left: wrong tune. As before: its row comes back out of the night
    (only the row this meter added), the listener rules it out, and the meter won't be
    sure of it by itself again;
  - **thumbs up**, middle: right tune, a person's check. The row is confirmed
    (`set_confidence` to 100): this meter's own, or whoever's row in the latest set has
    the tune. A sure tune not logged yet (the switch off, or logged lately) is logged
    as the person's own. The listener is told, as for a tapped name. Tapping a name
    while it is figuring counts as the same check. With nothing being logged it only
    tells the listener and the meter log;
  - **next**, right: the tune has ended and another is playing; the listener lets go
    of it and listens afresh. The row stays as it is, checked or not.

  Tapping the tune's name opens the tune (its sheet). Under the buttons, a logged tune
  says "Logged to the night", or "Logged to the night, not checked yet".
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
- `HomeView`: "What tune is this?" ("Cén fonn é seo?": short enough to stay on one line beside the ear).
- `RecordingStore`: `instanceID` optional; no upload without one.

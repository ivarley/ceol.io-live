# 061: Listen on the web

**Date:** 2026-10-29
**Status:** Stage 1 BUILT (the right to listen on the server); stage 2 BUILT, its
field test on an Android phone at a session still to do; stage 3 BUILT (the meter,
Ad-hoc mode); stage 4 BUILT (Log mode), its two-phone test still to do; stage 5 BUILT
(recording on the server), its test with real storage still to do; stage 6 PLANNED.
The decisions below were made by the product owner on 2026-10-29.

## Why

Listen (spec 053, spec 059) is the thing Ceol does that nothing else does: it names the
tune that is playing. Today it exists only in the iPhone app. The website, which is also
the Android app (a PWA on the home screen, spec 052 §B and `/help/phone`), has no
listener at all, and the help page says so.

Android players are a large part of any session. Until the web can listen, they can log
a night by hand but never by ear, and "what tune is this?" is an iPhone-only answer.
This spec brings both of Listen's modes to the web: **Log mode** (the meter logs a
night's tunes) and **Ad-hoc mode** (it only says what is playing), so that a phone of
either kind at the same table can do the same job.

## Where the listening happens

The iPhone can listen on the phone itself, with no connection, from the decider's data
(spec 053, "Listening on the phone"). The web can't, yet: the decider is Swift. So the
web listens **on the server**: the browser streams what it hears to the listening
service (`listen/`) and shows what the service decides.

That changes who can listen. The service admits system admins only. For the web to be
of any use, that becomes a right a person can be given, and later a right everyone has
once the service can carry the load. Listening on the server is also the only kind the
web will have until a browser-side decider exists, which is a later spec, not this one.

## Decisions

Made by the product owner, 2026-10-29.

- **Server-side first.** The web listens through the listening service. A listener that
  runs in the browser is out of scope.
- **Who may listen: a right given to named people.** A system admin turns it on for a
  person. For now that is the whole answer; whether it later becomes everyone's is a
  question for stage 6, after the cost per stream is known.
- **The same two modes as iOS**, with the same names in this spec and none in the
  product: Log mode from a night's page, Ad-hoc mode from the Listen tab and from the
  "Add a tune" searches.
- **A fifth tab, Listen, for people with the right.** It matches the iPhone's tab, with
  the ear icon, between Sessions and Tunes. Everyone else keeps the four-tab bar, and
  the entry points in stage 3 (Home, the "Add a tune" searches, a night's page) show
  only to people with the right.
- **Recording happens on the server, as an option, never in the browser.** The browser
  keeps no audio. When recording is on, the listening service keeps what it is sent and
  files it under the night when the night ends, where the segmenter and the background
  "find the tunes" can use it. The browser's recording constraints (a recording that
  lives only as long as the tab) never arise.
- **Phones only, or desktops too.** Desktops can listen the same way. Nothing in this
  spec is phone-only, but the layout is designed for a phone at the table first.

## Plan

Each stage is usable on its own, and each is a change of its own with tests, Irish and
help. The order puts the small, certain pieces first and the long tail last.

### 1. A right to listen on the server

A person can be allowed to listen on the server without being a system admin. A system
admin gives the right from the person's admin page; the account's own page shows it.
The listening service checks the right rather than admin status. The iPhone app follows
it too: a person with the right sees the "Listening on" choice that admins see today.

*Done when:* a named non-admin can open the iPhone's Listen with the server chosen, and
anyone without the right is still refused.

*Built (2026-10-31):* `user_account.can_listen_on_server` (migration 067, in the
account's history). `User.listens_on_server()` is true for system admins and for
anyone with the flag; `/api/me` (and every login response) carries it as
`can_listen_on_server`, an additive field in the native surface. A system admin ticks
"Can listen on Ceol's server" on `/admin/people/<id>`, which saves at once through
`PUT /api/admin/user/<user_id>/listen-on-server` `{"allowed": bool}`; the box is ticked
and fixed for a system admin. `/me` shows "Listen on Ceol's server: Allowed" only to
those who have it. The listening service admits a token when `/api/me` says
`can_listen_on_server` (falling back to `is_system_admin` from a web app that predates
it). A night's known tunes (`/api/session-instances/<id>/known-tunes`), which the
service asks for with the listener's token, are open to anyone with the right, not only
those who manage the session's recordings. The iPhone shows the "Listening on" choice,
and listens on the server, when `User.listensOnServer` is true. Help: a "Listening on
Ceol's Server" section in `/help/listen`, both languages. Tests:
`tests/integration/test_listen_on_server_061.py`.

### 2. The web can hear

The browser captures the microphone and streams it to the listening service, with the
sign-in it already has. This stage has no interface beyond a plain page that shows the
service's answers as they arrive. It settles the things that could sink the whole plan:
capture and resampling in the browser, keeping the stream alive while the phone's screen
is on, reconnecting after a dropped connection without losing the night's clock, and
what Chrome on Android does when the tab is hidden.

*Done when:* a phone at a session, screen on, sees the right tunes named for an hour
without a restart.

*Built (2026-10-31):* `/listen/test` (`templates/listen_test.html`,
`frontend/src/listentest/`), for those with the right; others are sent home.

- **Sign-in.** `GET /api/listen/connection` gives the service's address
  (`LISTEN_SERVICE_URL`) and a token: the web session's own `user_session` row
  (`session["db_session_id"]`, made if the session has none), so signing out ends
  it and a second visit gets the same one. A browser can set no header on a
  WebSocket, and a token in the URL would be in the service's logs, so the
  service now also takes `"token"` in the "start" message; a socket that arrives
  with none is accepted and closed (4401) unless its start carries a good one
  within 15 s. The service worker leaves `/api/listen/*` alone (no cached token).
- **Capture** (`capture.js`): an AudioContext at the device's rate, an
  AudioWorklet tap, and a windowed-sinc resampler to 22050 Hz (`resample.js`)
  that keeps everything above the new Nyquist from folding back as a false
  pitch. Microphone processing (echo cancellation, noise suppression, gain) is
  off. A recording file can stand in for the microphone, through the same path.
- **The night's clock** is the wall clock from the start, not the count of
  samples: when audio stops arriving for more than 2 s (the page asleep), the
  next chunk goes where the wall clock says, and the link sends a "skip" for
  the gap.
- **The link** (`link.js`) keeps every chunk until the service acknowledges it
  (ten minutes at most; a skip covers anything older), reconnects with backoff
  (1, 2, 4, 8, 15 s, and at once when the browser comes back online) on the same
  stream_id, and resends from the "ready" message's `have`, even when that is
  less than before (the service forgets a stream idle for five minutes).
- **Staying awake**: the screen wake lock, taken again when the page is shown.
  The page logs every page hide and show, freeze and resume, audio context
  change, microphone mute, wake lock loss, gap and reconnect, with a Copy button,
  so a night's log can be brought back from the table.
- **Checked** with the service running locally and a non-admin with the right:
  three minutes of night 137 named The Roaring Barmaid at 100%, answered 0.5 s
  behind the audio; a socket cut at 0:20 reconnected in a second and the service
  resumed at 19.9 s with nothing resent twice. Tests:
  `tests/integration/test_web_listen_061.py`, `frontend/tests/listentest.test.js`.
- **Still to find out, at a session:** whether Chrome on Android keeps the
  microphone with the screen on for an hour; what happens when the screen does
  go off (the log will say); how a phone's own microphone does against the
  iPhone's.

### 3. The meter: Ad-hoc mode

The certainty meter as the iPhone shows it, on the web: what is playing, how sure, the
"Wrong tune" and "Not a tune" taps, and when the meter is sure, the tune's sheet with
its place in your tunebook. Recent Tunes Heard at the bottom, kept in the browser. The
page is the Listen tab, and is also reached from Home ("What tune is this?"); both
show only to people with the right. "Listen To What's Playing Now" under the empty search box of the three
"Add a tune" searches, with the same offers as iOS: add to your tunebook, add to this
session's list, log this tune.

*Done when:* a player with the right can answer "what tune is this?" on an Android
phone, and put the answer where they want it.

*Built (2026-11-01):* `/listen` (`templates/listen.html`, `frontend/src/listenpage/`,
`serializers.build_listen_payload`), for those with the right; others are sent home.
It streams through stage 2's capture and link (`frontend/src/listentest/`).

- **The meter** (`meter.js`) has the iPhone's rules (`NightRecorder.swift`): waiting,
  "No tune playing" (`none` over 0.5), "Figuring out the tune…" with the candidates
  (every one at 5% or more, at most two under it, faded) and a ten-cell bar, or sure.
  It is sure by itself when the tune shown reaches 99.5% and the listener isn't
  watching for a change, and sure when a candidate is tapped (`tap this`). After at
  least one step it lets go when the listener shows another tune, hears no tune, may
  have changed, or holds it under 80%. "None of these" rules out every candidate;
  "Wrong tune" rules out the sure one, which is then never sure by itself again that
  run; "Tune changed" lets go of it and says "The tune may have changed (was …)" until
  another is shown. The taps are the iPhone's messages, `why` included. "Not a tune"
  is a state, not a tap, on the iPhone too.
- **When sure:** the tune's place in your list (`TunebookBox.svelte`): add it as To
  Learn, Learning or Learned (`POST /api/my-tunes` with the tune as a thesession.org
  id, so a tune Ceol doesn't hold is imported), or, if it is on your list, change its
  status and, while To Learn, its heard count (My Tunes ops). "Open the tune" opens
  the app-wide tune sheet, or thesession.org for a tune Ceol doesn't hold yet: the
  listener knows every thesession.org tune, and Ceol imports one only when someone
  adds it. Wrong tune and Tune changed are buttons under the sure tune, not behind a
  tap on it.
- **Recent Tunes Heard**, at the bottom: the last 50 tunes it was sure of, the same
  tune again within ten minutes counting once, kept in the browser (`localStorage`).
  A row opens the tune.
- **Ways in:** a fifth tab, Listen, with the ear, between Sessions and Tunes, and the
  same link in the desktop header; Home's "What tune is this?" (`viewer.
  can_listen_on_server` in the Home payload); "Listen To What's Playing Now" under the
  empty box of the three "Add a tune" searches (`TuneSearch` `offerListen`, shown when
  `window.CEOL_LISTENS`). From a search it goes to `/listen?session=` or `?instance=`,
  with `back=` the page it came from (only ever a path on this site), and the sure
  tune gets that search's one offer: "Add To This Session's Tune List" (`POST
  /api/sessions/<path>/tunes`; already there counts as done) or "Log This Tune" (an
  `add_tune` live op, at the end of the night). With a night, the listener prefers
  that session's tunes, and a candidate new to it says so.
- **Unlike the iPhone:** a page of its own rather than a sheet over the search, with
  a link back; no "Listening on" choice (the web has only the server) and no
  recording option (stage 5).
- **Checked** with the service running locally: from a night's search, the clip of
  night 137 named The Roaring Barmaid at 0:24; it was added to the list as Learning
  and logged to the night; "Wrong tune" ruled it out and the listener moved on; Stop
  left the service no streams; five tabs fit a 390 px screen. Tests:
  `tests/integration/test_listen_page_061.py`, `frontend/tests/listenpage.test.js`,
  `frontend/tests/tunesearch.test.js`.

### 4. Log mode

From a night's page, Listen logs the tunes it is sure of to that night, through the
same live-logging ops as the hand logger, so several phones of either kind can log the
same night at once and the night's log is one log. "Stop logging" moves to Ad-hoc mode
without stopping the listening. "Log automatically at 100%" as on iOS. The night's page
shows that Listen is logging it, as it does for the iPhone.

*Done when:* an Android phone and an iPhone at the same table log one night together
and every tune appears once.

*Built (2026-11-02):* on the night's logger itself (`frontend/src/App.svelte`), not on
`/listen`: the log stays in view while the meter fills it, and the tunes go through the
logger's own ops, offline queue and live updates.

- **The way in:** "Listen and log", under the last set, for those with the right while
  the log isn't marked complete. While it listens, a strip across the bottom of the log
  (in the dock) shows what the meter hears, the clock, and "End set" when it can end
  one; a tap opens the meter in a sheet. The "Add a tune" searches on the logger (the
  modal and the desktop pane) now listen there too (`TuneSearch` `onListen`), instead
  of going to `/listen?instance=`, and open the meter as it is when it is already
  listening; in either case the meter starts in Log mode. Leaving the page asks first,
  since it would stop the microphone.
- **The rules** are the iPhone's (`meter.js`, `NightListen.svelte`): a tune sure at 100%
  is logged by itself when "Log automatically at 100%" is on (kept in the browser, on
  by default), and otherwise by "Log This Tune" or by tapping a candidate; the tune
  logged last, sure again, says "Logged to the night" and isn't logged twice; no tune
  is logged by itself twice within ten minutes. Before logging, the night's latest set
  is checked (`latestSetEndsWith`), and also the logger's own merge rule for the open
  set (`openSetMergeTarget`): a tune already there is treated as logged, with no row.
  "Wrong tune" takes back the row this page added (cancelled if still queued). Three
  states of no tune with the log ending in a tune offer "End the set", and end it by
  themselves with the switch on.
- **The rows** are `add_tune` ops at the very end of the log whatever the cursor
  (`after_record_id: null`), by thesession.org id, so the server links a tune Ceol has
  and imports one it hasn't. The end of a set is the logger's own `set_break`.
- **Stop logging** asks, then goes on listening in Ad-hoc mode: the sure tune's place in
  your list and "Open the tune"; "Log to this night" starts logging again. Marking the
  log complete stops the logging too.
- **Shared with `/listen`:** the run (`listening.svelte.js`, the microphone, the link
  and the meter) and the meter's view (`MeterView.svelte`).
- **Checked** with the service running locally, on night 120 from a phone-width
  browser fed the night 137 clip: The Roaring Barmaid was logged by itself to the end
  of the open set; "Wrong tune" removed it; The Rose in the Heather was logged next.
  Tests: `frontend/tests/nightlisten.test.js`, `frontend/tests/tunesearch.test.js`.
- **Still to do:** the two-phone test (an Android phone and an iPhone logging one
  night), at a session.

### 5. Recording on the server

A "Record this night" option in Log mode, off in Ad-hoc mode as on iOS. When it is on,
the listening service keeps the audio it is streamed and, when the night ends, files it
as the night's recording, the same place an iPhone's upload goes, so the segmenter and
the background "find the tunes" have it. A dropped connection must not lose what was
already sent, and a stream that never ends cleanly (the tab closed) still becomes a
recording. The browser holds nothing.

*Done when:* a night listened to from an Android phone with recording on appears in the
segmenter like one uploaded from an iPhone.

*Built (2026-11-02):* the service files the audio it already writes for every stream
(`audio.flac`) as the night's recording (`listen/recording.py`), through the web app's
own endpoints and as the person listening (the token they listen with), so the
permission is the iPhone upload's: a system admin, or a session admin with the
recordings bit (`can_manage_recordings`).

- **The choice:** for those who may manage the night's recordings, "Listen and log"
  first shows the start with **Record this night** (on, as on the iPhone; not kept).
  Everyone else starts at once, as in stage 4. It is offered only in Log mode, and
  carries on through "Stop logging", since it is the night's. While it records, the
  sheet says "Recording this night on Ceol's server" and the strip "Recording"; if the
  service won't record the night, the sheet says so and the listening goes on.
- **The protocol:** the start message carries `record`, `started_at` (when the
  microphone began, sample 0) and `title`; at the start the service asks the web app
  (`GET /api/session-instances/<id>/recordings`) and its "ready" says `recording`
  true, or false with `recording_error`.
- **Filing** is `POST /api/recordings/upload-url`, a PUT of the FLAC to the bucket,
  `POST /api/recordings` (label "{night} (Ceol website)", `started_at`, `duration_ms`),
  then `PUT /api/recordings/<id>/listen-log` with the meter log in the iPhone's shape
  (`{"at_ms", "dir", "msg"}`: states in, taps out). From there the web app's ingest
  makes it a recording like any other, for the segmenter and "find the tunes". The
  stream's folder is then deleted. A failure is tried again five times over about
  fifteen minutes; a refusal (4xx) is not. Under ten seconds is not filed.
- **When:** on stop; when the page goes (`pagehide` says stop, so a closed tab is
  filed at once); when a stream nobody is sending to is swept, which for a recording
  is after 30 minutes (`RECORD_IDLE_S`) rather than 5, so a phone that loses its
  connection for a while comes back to the same recording; and when the service shuts
  down (a deploy: uvicorn closes the sockets, then the lifespan files every open
  recording, waiting up to 25 s, `SHUTDOWN_FILE_S`).
- **Limits.** A deploy during a night splits it in two: the browser reconnects to the
  new instance, which has none of the stream, and its recording starts there
  (`started_at` moved on by the skip; audio before the first real sample is not kept).
  The second recording is not the night's clock anchor and sits at offset 0, since
  spec 050 has no way yet to place a second recording. A crash of the service (not a
  shutdown) loses that night's recording. Render's shutdown delay must allow the 25 s.
- **Checked** locally with the real service and the real web app, the bucket stood in
  by a folder and the ingest stubbed: 150 s of night 137 streamed with `record` to
  night 120 became recording 2 (FLAC, 150.0 s, the clock anchor, labelled
  "… (Ceol website)", `started_at` the stream's), with its meter log (37 lines) beside
  it, and the stream's folder gone; a stream open when the service got SIGTERM was
  filed during the shutdown as recording 3. Tests:
  `tests/unit/test_listen_recording_061.py` (a fake web app and bucket),
  `frontend/tests/nightlisten.test.js`, `frontend/tests/listentest.test.js`.
- **Still to do:** the spec's test, with real storage: a night recorded from an
  Android phone, then opened in the segmenter. The browser's side has been run only
  in tests, not in a browser.

### 6. Opening it up

Measure what a live stream costs the service, decide how many it can carry, and decide
whether the right stays a given one or widens: everyone signed in, or everyone. Size
the service for that. The help page says who may use Listen on the website (stage 3);
it changes again with the answer.

## What this does not do

- A listener that runs in the browser with no connection. That needs the decider in
  JavaScript or WebAssembly, and is a spec of its own.
- Background listening on a locked phone. Browsers stop the microphone when the page
  is hidden; the web Listen asks for the screen to stay on and says so.
- Changing how the listening service decides. It gets a second kind of client, not a
  new detector.

## Risks

- **The browser.** Microphone capture on Android Chrome is reliable with the screen on
  and unreliable otherwise. Stage 2 exists to find out exactly where the line is before
  anything is built on it.
- **Cost.** Each stream runs the pitch trackers on the service, and with stage 5 holds
  its audio too. Opening Listen beyond named people is a hosting decision as much as a
  product one, which is why stage 6 is last and separate.
- **Two logs.** Log mode on two kinds of phone at one night depends on the live-logging
  merge rules (spec 024 §H30, spec 059) holding for a second client. Stage 4's test is
  the two phones together, not one.

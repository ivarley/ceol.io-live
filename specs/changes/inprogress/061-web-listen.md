# 061: Listen on the web

**Date:** 2026-10-29
**Status:** Stage 1 BUILT (the right to listen on the server); stages 2-6 PLANNED.
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

### 4. Log mode

From a night's page, Listen logs the tunes it is sure of to that night, through the
same live-logging ops as the hand logger, so several phones of either kind can log the
same night at once and the night's log is one log. "Stop logging" moves to Ad-hoc mode
without stopping the listening. "Log automatically at 100%" as on iOS. The night's page
shows that Listen is logging it, as it does for the iPhone.

*Done when:* an Android phone and an iPhone at the same table log one night together
and every tune appears once.

### 5. Recording on the server

A "Record this night" option in Log mode, off in Ad-hoc mode as on iOS. When it is on,
the listening service keeps the audio it is streamed and, when the night ends, files it
as the night's recording, the same place an iPhone's upload goes, so the segmenter and
the background "find the tunes" have it. A dropped connection must not lose what was
already sent, and a stream that never ends cleanly (the tab closed) still becomes a
recording. The browser holds nothing.

*Done when:* a night listened to from an Android phone with recording on appears in the
segmenter like one uploaded from an iPhone.

### 6. Opening it up

Measure what a live stream costs the service, decide how many it can carry, and decide
whether the right stays a given one or widens: everyone signed in, or everyone. Size
the service for that. The help page's "the website does not have Listen" changes when
stage 3 ships, and says who may use it.

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

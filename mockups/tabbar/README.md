# Tab-bar IA — Prototype (Feature 052 §B)

A **clickable, mobile-first prototype** of the navigation reshaping proposed in
`specs/changes/inprogress/052-native-ios-readiness.md` §B: the hamburger menu
becomes a five-tab bar, Home becomes a real first screen, the person page becomes
sections with drill-downs, and success toasts (almost) disappear. Pure HTML/CSS/JS
with dummy data mirroring the seeded local DB; no backend.

## Where it runs
- **In the app:** `/mockups/tabbar/` (served by the existing mockups route in `app.py`).
- **Locally:** open `index.html`, or `python3 -m http.server` in this folder.
- **On a phone:** open it in mobile Safari and *Add to Home Screen* to see it full-screen
  with the tab bar over the safe area.

## What it shows
- **Home · Sessions · Tunes · Me** in a bottom tab bar (Home is the C from the wordmark; the wordmark sits top-left on Home). Add A Session is the
  `+` in Sessions; Help, Admin, Share and Log Out live in Me.
- **Home** is session-centric: today's session up top (only when one is on; the whole card opens the log, "18 tunes logged so far"; a festival day becomes a swipeable row with dots — tap the Prototype tag to cycle none / one / festival),
  this week, learning counts and the suggested tune, then "pick up where you left off"
  (unfinished log, half-placed recording).
- **Sessions** → Mine / All (All has a search); a session **pushes in from the right**
  and pops back out on Back. Its page has three tabs with faint counts (Tunes / Logs /
  People), each with a search + filter line; Tunes also has `+` to add a tune. The
  **filter expands downward from its own button** (with a notch pointing back at it)
  rather than rising as a bottom sheet — it refines the list right below it, so that
  is where it belongs. Sort, on the Tunes tab, is an anchored pull-down from the bar
  button for the same reason. Learn
  status sits at the right edge of each tune row. Logs keep the date block; the row text
  carries what the block doesn't (tune count, complete, who logged).
- **Tunes** with the status Seg and one search field. Typing on **All** keeps your
  matches in place and adds a "Not on your list" section below for catalogue matches;
  on Know / Learning / Want it just filters that list. Name or ABC (`EBBA B2`).
- **Tune sheet** rises almost to the top and mirrors today's drawer: type pill · title
  · ×, "Log to Mueller Session" when live, notation first, then My List / Details /
  History / Played With. Status changes update the list behind it quietly.
- **Me**: profile + three stat tiles, My sessions, Attended, Logged by me (See all
  drill-downs), Settings (timezone, password, emails, login activity), Help, Admin, Share,
  Log out — instead of six tabs behind a `<select>`.

Taps that would leave the prototype (the live logger, the segmenter, admin, help) open a
small "In the real app" sheet saying what happens.

## Not shown
The live logger itself (spec 021's prototype covers it), the add-tune configure step,
desktop layouts (this is the phone IA — the two-pane desktop is unaffected).

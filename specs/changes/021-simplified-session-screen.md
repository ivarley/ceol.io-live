# 021 Simplified Session Screen

I'm going to design an entirely new tune entry screen for use during live session transcriptions. The goals of this redesign are:

- A mobile-first design: simple direct interactions; if you use a desktop browser that's fine too, but everything has to work natively given mobile phone viewport and interaction limits. And it has to be easy to see, which means not crowding too much onto a small screen at once.
- A tighter interface purpose that focusses on supporting the *core* activities you do while you're logging a session: moving to the right point in the session where you want to add or remove a tune, and finding the tune to add. (The "view a session" will use a different, much simpler UI that's essentially just a bullet list of sets with tunes.)
- A more modal design that lets users do more complex activities to figure out and find the next tune to log (searches by name, ABC notation, etc, plus disambiguating between options
- Working well with multiple users logging tunes at the same time from different devices (as well as a new process that'll automatically log tunes based on audio identification), including showing "another user is typing" sorts of animations.
- Working offline (with a cache of common tunes to match against) and sensible reconnect behavior that accepts that other users may have also been editing

The core interface still has the same basic metaphor: you're inside a single session instance, with contextual info (session / date) at the top in a fixed position; in the middle area of the screen is the list, and the sets scroll vertically, and tunes within a set are grouped as a unit, showing the tune name. However, the first major change is that the "manipulable" interface (adding tunes, etc) happens in a pinned area at the bottom that's always present, either right against the bottom of the viewport, or just above the keyboard if it's showing during data entry. This will likely have a button or two in standard spots, an a place you can click to start typing the next tune at your current position. There's some visual indication of "where" you are current pointed in the set (which will often, but not always, be at the end of the list so far, because you're adding the tune currently being played). Some 

We're going to mock this up as pure HTML/Javascript/CSS with dummy data at first until we get the interactions right, then we'll build a "real" version of it that uses the system's APIs (and potentially adds new ones).

---

# Prototype

- **Location**: `mockups/logging/` — self-contained `index.html` + `styles.css` + `app.js`, dummy data, no backend. Dark theme, mobile-first.
- **Run**: `python3 mockups/logging/serve.py` (no-cache static server, port 8021) or open `index.html` directly. Installable as a **PWA** (manifest + apple meta tags) so the *real* on-device keyboard/standalone behavior can be tested and shared.
- **Simulate menu** (🧪, next to the hamburger): prototype-only triggers for multi-user / audio / offline conditions (Sarah logs / starts / ends a set, audio log, typing holds, player join/leave, toggle offline, clear session). Not part of the real product.

# Detailed Requirements & Decisions

## A. Anatomy & modes
1. Fixed **app bar** (ceol logo + hamburger) → **session header** (name/date) → vertically scrolling **list** of sets → pinned **bottom bar**. All chrome is non-scrolling; only the list scrolls.
2. Two **modes**, toggled on the same screen:
   - **Edit (logging)** — full affordances; the default.
   - **View (read-only)** — compact, *no* seams / type-next-tune bar / action menus / yellow lines / per-row info icons / attribution colors. Tapping a tune still opens its details. A single **"✎ Edit log"** footer button returns to edit.
3. **Mode toggle**: in edit mode, when no set is in progress the bottom-right slot shows a subtle grey **"Done"** → View. (When a set *is* in progress that slot is the yellow **"End set"** instead.) "Done" is hidden while seam-editing (so it isn't confused with the yellow "✓ Done").

## B. Position model (the heart of it)
4. **Append-at-end by default**: the insertion point lives at the end of the open set; logging a tune appends there. Optimizes the 95% live case (zero navigation).
5. **Rows vs seams**: a **tune row** acts on that tune (Info / Before / After / Edit / Remove); a **seam** (gap between two rows, or between two sets) is a *position* — tap it to place the insertion point. Same gesture, two targets.
6. **Yellow line** = the active insertion point. In append mode it sits at the open set's trailing seam; relocating moves it. The seam's "＋" hides while it's the active (yellow) seam.
7. Tapping a tune **selects** it (turns yellow, shows its action row) and steals focus from any armed seam. Yellow consistently means "this is where I'm working."
8. **Positions are relational keys** (fractional-index / CRDT style — the schema already uses `order_position`), *not* array indices. This is what makes concurrent edits and re-anchoring work.

## C. Sets
9. A **set** is built in place; the open ("…in progress") set is the one at the bottom. **End set** is a dumb divider button (no tune) that closes the open set; it only appears when a set is in progress and glows yellow.
10. **Split / Join on a seam**: when a seam is armed (yellow), a small action sits on its right edge — **Split** on an intra-set seam (splits into two sets), **Join** on a between-sets seam (merges the two). Both leave edit mode. The "Done" for a between-sets insert sits *below* the seam.
11. `normalizeSets()` invariant (runs before every render): only the last set (or the one being edited) may stay open; empty set containers are dropped; a dangling cursor returns to the end.

## D. Bottom bar & tune entry
12. Resting bar = `[ Type next tune… ][ 🎤 ]` (placeholder is **"Type first tune…"** in the empty state). **End set** / **Done** appear contextually on the right.
13. **Stay-hot burst entry**: tapping the field opens a results sheet above the bar; picking a tune lands it and re-arms the field for the next (matches "log a whole set after it's played"). Dismissing or End-set exits.
14. **Search is progressive**: lightweight ranked results inline; escalate to a full-screen **"Search deeper"** modal (pinned search/tabs, scrolling result cards with name + type + notation) only for real disambiguation. "Log as-is" (unlinked) lives in the deep modal.
15. **Ranking**: tunes **played at *this* session** rank first, then popularity. Empty field is quiet (no guesses). Whether to show a "here N×" badge is an open visual knob.
16. **Already / just-logged nudge**: while typing, a result already in the current set is flagged inline — **"✓ just logged by Sarah"** (with a one-tap **Discard**) for the most recent, or muted "already in this set" for earlier ones. Committing a duplicate **merges** rather than adding a copy.

## E. Tune rows & details
17. **One tune per row** (vertical stack), grouped in a set card; tune **type shows once at the set level** (the card label), not per tune. Larger text. Row *styling* is an open knob.
18. Each row has a right-edge **ⓘ** → full-screen **details drawer**: rendered **dots** at top (with notes/abc toggle + thesession / abc-tools links), "on your list as" status, stats (popularity, played-here, played-globally), and history. Unlinked tunes show a "find & link" path instead.
19. **Started-by** pop-in (tap the type label): opens above the first tune. Shows **"Logged by <name> · <time of latest tune, local tz>"**; in edit mode it's an info→edit flow with a type-ahead attendee list and **"＋ Add people…"**; in view mode it's read-only. The chosen starter shows as a grey right-aligned pill mirroring the type label.

## F. Header expand, attendance, notes
20. Tapping the header expands it: **"N tunes in M sets"**, **notes** (if any), **"In attendance: K people"**, and a verbose **"Currently logging"** list (avatar + full name + tag). Stat font matches the date. Chips (Notes / Edit) are big tap targets. In **view mode** the header is collapsed by default but its collapsed line carries the summary inline ("N tunes in M sets — <notes>").
21. **Attendance editor** (full-screen): type-ahead add from the roster; people **already attending sink to the bottom, disabled + italic**; remove with ✕. **Escape hatch** — "＋ Add a new person '<typed>'" opens a form (First/Last, optional Email, instruments checkbox grid + Other, Add Person/Cancel) that adds to attendance and the roster.
22. **Notes**: simple editor (stub); the note shows in the expanded/collapsed header.

## G. Audio (the mic)
23. The mic is a **persistent recorder** on the logged-in user's device (it logs *as them*, in their color — the 🎤 is only an attribution label, never its own identity/color).
24. First tap → starts (stays on, red pulse ~2.2s, auto-logs ~every 9s). Tap again → a control panel above the bar: **elapsed time, N tunes logged, Pause/Resume, Stop**.
25. The mic can also **end a set** when it "hears a pause."
26. **Confidence**: audio entries carry a confidence the recognizer can revise upward. Show **"(N%)"** as an amber pill **by the name** only when **≤ 70%**, and lighten the pill. A human **Confirm** or **Edit** clears it. Low-confidence selection shows a dedicated **Confirm / Edit** row above the normal actions (Edit moves up there).

## H. Multi-user (real-time)
27. **Presence**: each logger has a two-initial dot + color. A tune logged by someone else carries **their color** on the row (dot + border) — **edit mode only** (who's logging matters while logging, not while reading).
28. **Typing indicator = a position reservation**, not a notification: a slim, color-coded bar (deliberately thinner than a tune row, big "•••") held at a slot. When a tune is inserted at/before it, the hold **re-anchors (slides down)** rather than vanishing. Multiple simultaneous holds stack. A hold clears on the person's commit, or after **10s of inactivity** (resets on activity).
29. **Append ordering**: concurrent "next tune" logs order by claimed timestamp + per-device tiebreak; holds shift, never vanish. Hand-entry knows only *relative* position — the system never guesses logical intent; it relies on **live visibility** + cheap fixes.
30. **Corroboration / merge**: same tune at the same slot → collapse to one, **earliest logger credited**, confidence ticks up (the merge animation). Different tune at the same slot → surface both as candidates (don't silently pick); a wrong name is a separate entry until someone deletes it.
31. **Conflict rule**: last-write-wins with a quiet "Sarah also changed this" notice; **removal beats a concurrent edit** ("Sarah removed the tune you were editing"). *(Notice UX not yet built.)*
32. **Time model**: a tune is an *assertion about a performance slot* carrying — (a) played-start, (b) played-end [audio only], (c) when asserted, (d) other assertions, (e) when received. **Order/merge by claimed position+time (a/c), never by receipt time (e).** Receipt time only drives when the UI updates.

## I. Offline / reconnect
33. **Pinned offline banner** under the header while disconnected (shows queued/server-update counts, with Reconnect). Your presence dot greys; **others' presence and all holds drop immediately** (you can't observe them).
34. Offline changes are **visible as queued**: inserts/edits show **"⏳ queued"** (dashed); deletes show **"⏳ removing"** (struck-through, still present) with a **Restore** action replacing Remove.
35. Remote events that happen while you're offline are **deferred to a server queue** (invisible to you), counted in the banner.
36. **Reconnect** applies queued deletes, clears insert/edit pending flags (settle flash), replays server changes, and shows a **"Reconnected — X of yours synced, Y added while you were away"** summary. Presence returns.
37. **Merge unit is the set** (not individual tunes): never interleave tunes into someone else's set. New sets insert by time; partial-overlap sets align on shared tunes into a superset; messier cases insert best-effort for manual cleanup. *(Partial-overlap alignment intentionally **not** prototyped — naive append + manual cleanup is an acceptable real default.)*

## J. Cross-cutting
38. **"Go to end"**: a grey pill appears only when you've scrolled away from the live end (suppressed while a tune is selected or while editing). Following the live end auto-scrolls on new arrivals / when the keyboard or recorder panel opens, so you don't get stranded behind a pill.
39. **Settle animation**: your own inserted tune flares bright (~2.6×) and eases down over ~1.6s.
40. **Undo** (4s toast) on the destructive/structural single actions: **Remove, Split, Join, Confirm**. (Not on additive ones like Add Person.)
41. **Keyboard handling (iOS) — PROVEN LIMITATION**: the app sizes to `visualViewport` and snaps a compensating `translateY(offsetTop)` so the header lands in the right place and the bar rides above the keyboard. The header still visibly *jumps-and-settles during the keyboard animation*, and a minimal isolation test (`mockups/logging/kbtest.html`) proved this is **not fixable in pure web**: even polling `visualViewport.offsetTop` every animation frame, the header's `getBoundingClientRect().top` stays exactly `0` the whole time, yet it still moves on screen — because iOS *animates the visual viewport's own on-screen position*, and web content has no screen-absolute coordinate space (fixed/sticky/visualViewport are all relative to that moving viewport). The **only** true fix is a native wrapper (a `WKWebView` that resizes the *layout* viewport for the keyboard). Transform-follow is the accepted floor for the web prototype; `position:fixed` alone is worse (header flies off-screen). (This was proven with a now-removed minimal isolation page + trace overlay; even per-frame polling of `offsetTop` kept the header at `top:0` yet it still moved, because `getBoundingClientRect`/`visualViewport` are relative to the animating viewport.)

## K. Out of scope for the prototype (real-implementation)
- Real APIs / persistence / auth; genuine CRDT/fractional-index backend; real audio recognition; partial-overlap set-merge alignment; deep-search "By ABC" and filter panels; the conflict-notice UX; light mode; accessibility pass.

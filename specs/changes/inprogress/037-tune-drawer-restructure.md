# 037 — Tune Drawer Restructure

**Status:** BUILT (2026-07-14). Design agreed by interview 2026-07-13/14; implemented and
verified end-to-end in Chrome. 861 backend + 427 frontend tests green. Uncommitted.

## Why

`TuneSheet.svelte` is the one tune-detail surface in the app — a drawer mounted on every page,
opened from `/my-tunes`, the session tunes page, the live logger, `/admin/tunes`, and the
hamburger's "Find a tune". It derives a five-way **mode** (`admin | session_instance | session
| my_tunes | global`) and rearranges itself accordingly. Three problems follow from that:

- **A session replaces you.** In `session` / `session_instance` mode the Configure section
  stops showing *your* alias and setting and shows the *session's* instead. Your personal
  configuration of a tune becomes unreachable the moment you look at that tune through a
  session — which is precisely when you might want to compare them.
- **The important thing is buried.** Notation — the thing you actually opened the drawer for —
  sits below the status block, the heard count, and the Configure section.
- **The shape depends on where you came from, not on what's true.** Same tune, same person,
  different page, different drawer.

This spec makes the drawer's shape a function of two things only:

> **scope** — is a session in context? an instance? — and **relationship** — is this tune on my list?

Never of which page opened it.

## Block order (top to bottom)

1. **Header** — type chip, title, `aka` line, close.
2. **Merged-tune banner** (spec 030), when the tune id was redirected.
3. **"Log This Tune to \<session\>"**, when `window.activeSession` is set. Styled to match the
   `＋ Log This Tune` primary action in `TunePreview.svelte`.
4. **Notation** — incipit/full, notation/abc, thesession + abc-tools links, and the new
   setting-mismatch note.
5. **My-list status** — the status Seg, per-instrument roll-up, heard count, and the action row
   (Configure / View By Instrument / Remove From My Tunes) with the personal Configure form
   beneath it.
6. **Tabs** — `History` · `Stats` · `Played With`.

**The drawer always opens on History**, which loads asynchronously so nothing waits on it.

## Names vs. settings — two different precedences, on purpose

A **name** is a label, so the most *personal* one wins.
A **setting** is a record of what was actually played, so the most *specific factual* one wins.

| | precedence |
|---|---|
| **Title** | `person_tune.name_alias` → `session_instance_tune.name` → `session_tune.alias` → `tune.name` |
| **Notation** | `session_instance_tune.setting_override` → `session_tune.setting_id` → `person_tune.setting_id` → tune's first setting |

The notation precedence is **unchanged** from today (`serializers.py:1442`). Only the title
chain changes — `getDisplayName` (`logic.js:83`) currently ignores your alias entirely in
session scope and never consults the instance name at all.

### The `aka` line

Under the title, one dim line naming **the next layer down the chain that meaningfully
differs** — `aka Michael Creamer's`. Exactly one; walk down and stop at the first meaningful
difference. Nothing renders when nothing below the title meaningfully differs, which is the
common case. Not a link (it's the same tune).

The canonical name is *not* the fallback for this line — it's a normal link in the chain, and
it also always appears in Stats.

### The setting-mismatch note

When the notation being drawn comes from a setting other than yours, a dim line under the
staff: *"This is the version The Cobblestone plays. **Your personal version** differs."* The
bold part is a button that re-renders the staff from your setting and flips the line to
*"Showing your version. **The Cobblestone** plays a different one."* Purely a view toggle —
saves nothing, resets on close.

Deliberately **not** covered: instance-vs-session setting differences (the Session tab shows
those) and key differences (the key doesn't change what's drawn). Spec-later: an upcoming
change goes deeper on settings and will revisit this.

## The name matcher

"Meaningfully differs" is a display-only heuristic. Pure function in
`frontend/src/tunesheet/logic.js`, no backend involvement. It must never print
*The Silver Spear / aka Silver Spear*.

**Stage 1 — normalize.** Lowercase; collapse whitespace; strip all punctuation, including
both `'` and the smart quote (`’` — always `\u`-escaped in source, never written
literally; see the `normalize_apostrophes` breakage); strip a leading `the` and a trailing
`, the`; strip a trailing possessive `s` from *every* token (so `swallow's tail` ≡
`swallow tail` ≡ `swallows tail`); strip a trailing `favourite`/`favorite`; strip a trailing
tune-type word (`reel`, `jig`, `slip jig`, `polka`, `hornpipe`, `slide`, `waltz`, `march`,
`barndance`, `mazurka`, `strathspey`); then **remove spaces entirely**, which also collapses
compound splits (`connacht man` ≡ `connachtman`).

**Stage 2 — spelling substitutions.** A deliberately *minimal* table, e.g.
`connaught|connaght|connachtmann → connacht`, `-our- → -or-`. Entries are only ever added to
fix a real failing fixture pair — never speculatively.

**Stage 3 — compare.** Same if one string is a **prefix** of the other, or if character-bigram
(Dice) similarity ≥ **0.8**.

**Two hard guards**, both marking a DELIBERATE distinction, so both outrank every rule above
— including prefix, which would otherwise read the undecorated name as "a short form of" the
decorated one:

- **Digits.** `Paddy Fahey's` vs `Paddy Fahey's No. 3` (a prefix), and `No. 2` vs `No. 3`
  (Dice 0.90). Both must stay distinct.
- **Parentheticals.** `The Silver Spear (Kevin's)` vs `The Silver Spear`. A bracketed aside
  is a disambiguation someone added on purpose.

### What the real data taught us (things a design can't predict)

Built against 34,035 within-tune name pairs from the top-200 tunes' alias sets. Four rules
came out of the data rather than the design, and each fixes a real failure:

- **Two normalized forms, not one.** Sorting tokens (so `Maggie Drowsy` ≡ `Drowsy Maggie`)
  lets a short shared token float to the front, where the prefix rule then swallows it:
  `Collins'` "prefixed" `Daniel Michael Collins's Father's`. So the prefix test runs on the
  **word-order-preserving** form and the similarity test on the **sorted** form.
- **Fold diacritics, don't strip them.** A naive `[^a-z0-9]` strip *deletes* `É`, so every
  accented Irish title diverged from its unaccented spelling. NFD + strip combining marks.
- **Token-final `-y` / `-ie` / `-ey` → `i`.** Drowsy / Drowsie / Drowsey, Maggie / Maggy.
- **The 0.8 threshold sits on a real cliff.** `A Shetland Fiddler's Welcome To The Cape Breton
  Symphony` vs `Cape Breton Fiddler's Welcome To The Shetland Isles` — mirror-image titles,
  genuinely different tunes — scores **0.7987**. Do not lower it.

Note also: ~92% of within-tune alias pairs are genuinely DIFFERENT names (`The Kesh` / `The
Castle` / `Na Ceis` / `Kincora`), so showing the `aka` is the common, correct outcome. The
matcher exists only to suppress the noisy minority.

### Calibration harness

The matcher's thresholds are tuned once against real data and the fixtures are checked in.

- A dev script under `scripts/` takes the **top 200 tunes by `tune.tunebook_count_cached`**
  (which *is* thesession.org's popularity metric — no scraping needed) and pulls their alias
  sets from `csv/aliases.csv` in the weekly data dump. The fetch/parse code already exists in
  `services/tune_merge_scan_service.py` (spec 031).
- Every within-tune name pair is emitted and **hand-labelled**: `variant` (same name, different
  spelling → suppress the aka) vs `distinct` (genuinely a different name → show the aka).
  **The alias data cannot produce this labelling** — an alias group freely mixes both kinds.
- A **negative set** of hand-picked genuinely-different name pairs guards against a degenerate
  "always say same" matcher.
  - Do **not** build it by sampling cross-tune pairs. The same name legitimately belongs to
    several different tunes (`O'Keefe's`), so a cross-tune identical pair is *not* a matcher
    failure — "same name" is the correct answer there.
  - In the product this never arises anyway: the drawer only ever compares names belonging to
    a single `tune_id`.
- Labelled pairs are checked in as a JSON fixture and run under Vitest with **asymmetric bars**:
  **zero** tolerance for collapsing a genuinely-distinct pair, **≥95%** for suppressing true
  variants. Showing a spurious `aka` is a papercut; silently hiding that a tune is also known
  as something else defeats the feature.

**Refreshing:** re-run the script against a newer dump, label only the *new* pairs, re-tune
the threshold, and extend the substitution table only where a real pair fails.

## Personal configuration

Shown on **every** surface for any tune on your list — a session never replaces it.

The action row sits at the foot of the status block. `Configure` and `View By Instrument`
cluster left and wrap together; `Remove From My Tunes` stays right-aligned and *top*-aligned,
so it holds the first line even when the left cluster wraps. All three exist only for a tune on
your list. Dim, small, all the same font.

`Configure` expands a form with four fields:

| field | column |
|---|---|
| I call this | `person_tune.name_alias` |
| I play setting | `person_tune.setting_id` |
| **I play this in** | **`person_tune.key` — new** |
| My notes | `person_tune.notes` (now always rendered, not sometimes) |

### `person_tune.key`

`VARCHAR(20)` nullable, mirroring `session_tune.key`. Vocabulary is the existing
`MUSICAL_KEYS` (`logic.js:10`). Null means "no opinion — whatever the setting says."

It is a **label only**: it does not transpose the notation, and it does not surface anywhere
outside the drawer. (Contrast `session_instance_tune.key_override`, which already renders in
parentheses on the instance's tune label.)

Requires: migration; `key` added to `PERSON_TUNE_COLS` (`serializers.py:924`),
`person_tune_to_dict`, and the `update_person_tune` allowlist
(`api_person_tune_routes.py:534`).

### Offline

The three override fields (alias, setting, key) go **read-only** when offline, with a dim
"offline — only notes can be edited" hint. **Notes stays editable** and still queues through
the existing `set_notes` op in `POST /api/my-tunes/ops` — a phone in a pub basement is exactly
where someone types a note about a tune.

So: Save while offline can only ever be committing notes → enqueue `set_notes`. Save while
online → the single `PUT /api/my-tunes/<ptid>` with every dirty field.

## The History tab (which absorbed the Session tab)

Tabs are `History · Stats · Played With`, and **the drawer always opens on History**. It loads
asynchronously, so the drawer paints immediately either way; offline it doesn't even try (see
below).

The Session tab and the History tab were asking the same question — *which plays of this tune am
I looking at?* — so they became one, with one scope control. The tab is called **History** rather
than "At This Session" because the droplist can select scopes that aren't a session at all. The
cost, accepted deliberately: "History" doesn't advertise that it's where you edit a session's
alias/key/setting. That's tolerable because the session-level setting flow is likely to move to a
carousel chooser (as in search) before long, and the key would blend into that.

### The droplist IS the heading, and the ONE scope control

There is no separate title. It names the scope and the list continues the sentence downward:

```
At The Cobblestone            → editable: writes session_tune
… on Tue 8 Jul 2026           → editable: writes that instance's session_instance_tune
… on Sat 14 Feb 2026 · Gus O'Connor's
At a different session …      → not a target; an errand (see below)
All My Sessions               → read-only lens
All Sessions
```

Session rows appear only when a session is in scope; the wide lenses always do (`All My Sessions`
needs a login). **Only the session rows are editable** — "what we call it" is a fact about a
session or a performance, and means nothing across all of them, so the form and the read-only
values both vanish for a wide lens.

The instance rows are only the ones **this tune was actually played at** (the write endpoint 404s
otherwise). Labels are the date, plus `location_override` when set — that's how festivals
distinguish same-date instances (`LogsTab.svelte:132`); `start_time` is appended only to break a
remaining tie. Never called a "night" — not every session is at night.

**The "different session" row is an errand, not a target.** It opens a `SessionPicker` (kit,
composed like `PersonPicker`) listing my other **member** sessions — visitor sessions are
excluded, since a session you dropped into once on holiday isn't a repertoire you have a view on.
Choosing one **re-scopes the whole drawer**: the payload refetches, and the title chain, the aka
line, the notation's setting, the droplist and the permissions all recompute for that session.
The select must **snap back** when the picker opens, or cancelling it strands the select on a row
that means nothing — hence `bind:value`, since a one-way `value=` only writes the DOM when the
state actually changes.

The URL is deliberately **not** rewritten on a re-scope: the page behind the drawer is still the
session you came from, and a path claiming otherwise would be a lie.

### "While I was there" is a FILTER, not a scope

A checkbox that ANDs on top of *whatever* is selected. This is the point: **"nights at Mueller I
was actually there for" was not expressible before**, because `attended` was one of a set of
mutually-exclusive Seg options and you had to choose between "this session" and "the ones I
attended".

Server-side it's a new `?attended=1` param rather than overloading `?scope=`, precisely because
`scope=member` and `scope=attended` can't be ANDed. (`?scope=attended` is still accepted and means
the filter with no other person restriction.)

And it **marks** rather than only hides: every row carries an `attended` boolean — the same
predicate, selected instead of filtered — so you can see at a glance which plays you were present
for without hiding the ones you weren't. The mark is a small green check in a circle, with "You
were there" on hover (`title`) and on tap (a toast — a `title` never appears on touch). It's a
footnote on the row, not a label competing with it.

A note on the layout: the filter holds the right edge with `margin-left: auto`, **not**
`justify-content: space-between`. With space-between it slid left into the gap the moment the
filter was switched on and the count line stepped aside — a control that moves because of what it
just did.

### The list

- **A wide lens or the session** → the plays, each linking into the logger at that exact record.
- **One instance** → where it came round that night: *Set 3, tune 2* (and *Set 17, tune 1* if it
  came round twice). The same thing at finer granularity — which is what makes the merge more than
  a consolidation. **No request is needed**: the payload already carries that night's coordinates
  (`played_instances[].positions`), so selecting a date answers instantly.

The set/tune coordinates use the same window trick as `GET /api/tunes/<id>/history`: a running
`SUM` over break records numbers the sets (spec 023), and the breaks are dropped **after** the
window is computed so they never take a tune number.

Links go through the legacy `/sessions/<path>/<instance>?highlight=<session_instance_tune_id>`
URL, which redirects beta users to the live screen and **drops `?tune=`** — on the live screen
that param means "append this tune", which is not what a history link should do.

A count line sits above the list (*Played 4 times at this session*). It steps aside when the
attended filter is on, because the payload's counts don't know about the filter and the list is
then the honest answer.

### Offline

History is a live query, not part of the offline bundle. Offline the drawer still paints
normally and the list says **"Play history isn't available offline"** — it doesn't attempt the
request and fail.

### The form

Hidden until you click **"Update name, setting or key for this tune {at this session | on this
date}"**, since the tab's main job is to tell you things and editing is the rarer errand.

- **The session's own row** → present tense: *We call this / Our setting / We play this in.*
- **An instance** → past tense: *We called it / We played setting / We played it in.* Each field's
  inherit option names its fallback — `(as usual — Dmajor)`. Instance overrides belong here
  outright: what you called it and how you played it *is* a fact of that performance.

Someone who can't edit sees the values read-only instead (no link) — nobody loses information.

**URL:** `?siid=<session_instance_id>` selects an instance. `?date=YYYY-MM-DD` is accepted inbound
and resolves to the earliest instance that day. The id is always what's used internally — at a
festival there can be several instances on one date.

**Opening from the live logger** pre-selects the instance in scope. **Opening from the session
tunes page** selects the session row. With no session in scope at all, it lands on the widest lens
the viewer is entitled to.

### Played With keeps its own Seg

Untouched. Coupling it to the History droplist would be over-fitting: it asks a different question.

### Permissions

| | who |
|---|---|
| Read the tab | **anyone**, including logged out — rendered as plain text, no form, no Save |
| Edit `In General` | **session admins + system admins** |
| Edit an instance (all three fields) | **any session member** |
| Remove From Session | **session admins + system admins**, and only when the tune has zero plays here |

The `In General` gate **closes a live hole**: `update_session_tune_details`
(`api_routes.py:1671`) is currently only `@api_login_required`, so *any logged-in user can
rewrite any session's tune alias, setting, and key* — for a session they have never attended.

The instance rule is a deliberate **loosening**: today `update_session_instance_tune_details`
(`api_routes.py:10538`) lets a non-admin member set only `setting_override`. Members were in
the room; they know what got played.

### Soft-deleted plays (a latent bug, fixed here)

`session_instance_tune.deleted` was filtered **nowhere**. A soft-deleted play therefore still
inflated "played here N times" *and* blocked un-enrolling the tune from the repertoire. Every
play-counting path in 037 now filters `deleted = FALSE`: `times_played`, the droplist's
`played_instances`, and the `DELETE` gate. (Break records were never a problem — they carry a
NULL `tune_id`, so a tune-id filter already excluded them.)

### Remove From Session

Today `DELETE /api/sessions/<path>/tunes/<id>` (`api_routes.py:1844`) deletes the `session_tune`
row and its aliases and **leaves the plays orphaned** — actively producing the state we don't
want. The invariant is: *every tune played at an instance is in that session's repertoire.*

So: the link renders **only when the tune has no `session_instance_tune` rows at this session**,
and only for session/system admins. When there are plays it is simply **absent** — no
explanatory line. Enforced server-side too (409 if plays exist), since the endpoint is reachable
directly.

This makes Remove From Session mean one narrow thing: un-enrolling a tune that was added to the
repertoire and never actually played. It will be rare, and that's correct — "in the repertoire"
is becoming a fact derived from history rather than a thing you curate.

**Prerequisite, already satisfied:** spec 025 shipped (commit `8a48b66`) —
`live_logging_routes.py:343` `_enroll_session_tune` upserts into `session_tune` from both
`_handle_add_tune` and `_handle_change_tune`, and the historical backfill was run against
production. So a tune with plays but no `session_tune` row should no longer occur.

**Belt and braces:** saving `In General` for a tune with no `session_tune` row **silently
creates it**. A human stating "we play this in Ador here" about a tune demonstrably played
there is the strongest possible evidence it belongs in the repertoire; asking would be a silly
question.

## Saves

**Per-form Save / Cancel, disabled until dirty.** The drawer-wide Save is deleted. The two
forms have different owners, different permissions, and different endpoints — one button
committing both would be lying about what it does.

Unchanged: the status Seg, the per-instrument Segs, and the heard-count ± all still commit
immediately on click.

## Stats tab

Gains one line at its foot, replacing the "Official Name" and "Tune ID" rows that currently
live at the top of the Configure section:

> **Canonical name:** Michael Creamer's Favourite (#1073)

## Deletions

- **The title is no longer clickable.** `isTitleClickable` / `toggleConfigSection` on the `<h2>`
  (`TuneSheet.svelte:121`, `:1224`) go away — expanding a config panel by clicking a heading was
  quirky and undiscoverable.
- **The "Additional links" footer** disappears: `Remove From My Tunes` moved into the status
  block, `Configure This Tune` is now the `Configure` link, `Remove From Session` moved to the
  Session tab.

## Out of scope

- **Admin mode.** `admin` remains the one violation of the scope+relationship rule — it forces
  the Configure section open with a canonical-name editor and suppresses the status block
  entirely. Rather than half-fix it, `/admin/tunes` keeps its always-open canonical-name editor
  for now (the Official Name / Tune ID *display* still moves to Stats, for every mode). The
  rework is [036 — Admin Audit](036-admin-audit.md), which asks the prior question of what
  `/admin/tunes` is even *for*.
- **`session_tune_alias`** (a session's *extra* aliases). Has its own endpoints, isn't edited in
  the drawer today, and isn't edited in the drawer after this.
- **Transposition** and any deeper setting-switching UI — an upcoming settings spec.

## Where it lives

| | |
|---|---|
| Matcher + fixtures | `frontend/src/tunesheet/namematch.js`, `namematch.fixtures.json`, `frontend/tests/namematch.test.js` |
| Session picker | `frontend/src/lib/SessionPicker.svelte` (kit); `GET /api/my-sessions` now returns `relationship` |
| Fixture generator | `scripts/build_name_fixtures.py` (reuses the spec-031 dump fetch) |
| Name chain, aka, droplist labels, `?siid=`/`?date=` | `frontend/src/tunesheet/logic.js` |
| The drawer | `frontend/src/tunesheet/TuneSheet.svelte` |
| Styles | `static/css/tune_detail_modal.css` (spec 037 section at the foot) |
| Payload (`session_scope`, `can_edit_*`, `played_instances`, personal `key`) | `serializers.py` |
| Auth + delete gate | `api_routes.py` (`is_session_member_for`, `update_session_tune_details`, `update_session_instance_tune_details`, `delete_session_tune`) |
| Personal `key` write path | `api_person_tune_routes.py`, `services/person_tune_service.py`, `models/person_tune.py` |
| Migration | `schema/037_person_tune_key.sql` |
| Tests | `tests/integration/test_tune_drawer_037.py`, `frontend/tests/tunesheet.test.js` |

## Known pre-existing wrinkle

`session_instance_tune` writes are keyed by `(session_instance_id, tune_id)`, not by
`session_instance_tune_id` (`api_routes.py:10606`). A tune played *twice* on one night has two
rows, so editing that instance's override writes to **both**, and the read side
(`serializers.py:1338`) `fetchone()`s an arbitrary one. Not introduced here and not fixed here,
but the Session tab's droplist lists such an instance once, and that is the honest thing it can
do without addressing the key.

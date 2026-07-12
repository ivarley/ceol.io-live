# 034 — Session ↔ Person Relationships

**Status:** Design agreed (interview-driven, 2026-07-12). Implementation in progress.

## Why

A person's relationship to a session is two booleans on `session_person`: `is_regular` and
`is_admin`. That model can't say the things the app needs to say, and what it does say, it
says badly.

- **No way to say "I visited once."** A session you hit on holiday in Doolin is
  indistinguishable from your Tuesday local. Spec [033](033-person-tune-relationships.md) is
  blocked on this: its R2/R3 lenses ("my sessions' repertoire", "played at my sessions") join
  `session_person`, so with no visitor concept, one night's visit drags a stranger's entire
  back catalogue into your stats.
- **`is_regular` is a status ranking of humans** — assigned by someone else, visible to them,
  and it rots (someone who stopped coming in 2019 is still "Regular"). It gates nothing
  meaningful; its only real jobs are sort order and a filter. It's also incoherent for
  festivals, which force everyone to `is_regular = true` just to make tune stats work.
- **No roster hygiene.** People who moved away years ago clutter every list forever.
- **Anyone with an account can self-join any session and immediately read its full roster** —
  names, cities, instruments. `POST /api/sessions/<path>/join` creates a `session_person` row
  with no approval from anyone, and any such row unlocks the People tab.
- **The permission gates contradict each other.** `auth.py` grants attendance-view to any
  member (`is_session_regular` actually checks only that a row exists); `api_routes.py`
  requires `is_regular OR is_admin`. Both can't be right.
- **Adding a person is three different UIs.** The session People tab posts an `is_regular`
  boolean; the person page posts `role: 'regular'|'attendee'`; the live logger has its own
  drawer. Attributing a set to a player who isn't checked in yet means leaving the picker,
  opening a separate drawer, and coming back.

## The model

`session_person` becomes four orthogonal fields, each doing exactly one job. `is_regular` is
**dropped**, with no replacement flag.

| Field | The question it answers | Who sets it |
|---|---|---|
| `relationship` — `'member'` \| `'visitor'` | **Whose session is this?** | The person **or** a session admin |
| `confirmed` BOOLEAN | **Does the session vouch for this person?** Gates all people-visibility. | Session/system admins only |
| `archived` BOOLEAN | **Are they still around?** Roster display only. | Session/system admins only |
| `is_admin` BOOLEAN | Session admin. Unchanged. | System admins |

### `relationship` — whose session is this

`visitor` means "I came here, but this isn't one of my sessions." It is load-bearing:

- **033's R2/R3** (`repertoire`, `member_plays`) join `session_person` with
  `relationship = 'member'`. R4 (`attended_plays`, via `session_instance_person`) is untouched:
  a visitor still gets credit for the nights she was actually there.
- The session tunes grid's community tune-stats count members, not visitors
  (`relationship = 'member' AND archived = FALSE`). This *widens* those counts versus the old
  regulars-only CTE — the intended correction — and lets festivals drop their special case.
- Copy distinguishes "Sessions I attend" from "Sessions I've visited".

It grants **no access at all**. A visitor and a member see exactly the same things.

### `confirmed` — does the session vouch for this person

The **sole** gate on people-visibility: the People tab, person detail sheets, attendance
lists. The predicate is `is_admin OR confirmed`, and it applies to members and visitors alike —
a confirmed visitor is a known friend of the session who happens to live elsewhere, and she can
see the roster; an unconfirmed member cannot.

This is what closes the self-join hole. **Joining a session no longer hands you its roster.**
People-visibility is granted *by the session*, never claimed by the joiner.

| Path | `confirmed` |
|---|---|
| Admin adds someone from the People tab | TRUE |
| Admin flips Confirm on the person sheet | TRUE |
| **Check-in — by anyone, including an admin, including the live logger** | **unchanged** |
| Self-join, self-check-in | FALSE |
| Rows existing at migration time | TRUE (grandfathered — they have this access today) |

**Check-in must never confirm.** Checking someone in is a *logging* act, performed in a pub,
mid-tune, about whoever is in the room. If it granted roster access, an admin logging a
stranger's attendance would thereby hand him everyone's names — which is precisely the failure
this field exists to prevent.

The Confirm control must state its effect at the point of click — *"Confirm Sarah Murphy —
she'll be able to see this session's people list and attendance records"* — never a bare
toggle labelled "Confirmed".

### `archived` — an admin's display preference about their own roster

Archived people are hidden from **default** lists (the People tab; the pre-populated dimmed
tier of the check-in picker) but **remain findable by typing** — shown dimmed and marked
*(archived)*. Never unfindable: otherwise a member back for one night is invisible in the
picker and whoever's logging creates a duplicate person for her.

Check-in does **not** un-archive, and does not touch `relationship`. A visit means "she's here
tonight", not "she's back" — different facts, and only an admin states the second. Archiving is
set and cleared by admins, never inferred.

Archiving is **one-sided**: an archived session still appears in that person's own Sessions tab
and still counts in their 033 lenses until *they* leave it. A session and a person are allowed
to disagree about whether someone's still around.

### "Regular-ness" is computed, never stored

Ordering that used to key off `is_regular` now keys off actual attendance: distinct
`session_instance_person` rows with `attendance = 'yes'` in a trailing 6-month window, then
lifetime count, then alphabetical.

It is **advisory only** — default sort order and quick-pick shortlists. It gates nothing, is
never rendered as a badge, and is never a filter. If it's wrong, the cost is two more
keystrokes. This is why it can safely be a guess rather than a stored fact.

### No global person search, anywhere

You can never discover people from other sessions. Both scopes of the picker search only the
session's own roster; anyone else must be typed in fresh. If the email you enter matches an
existing person, that person is silently attached rather than duplicated — email is the only
cross-session identity key.

The cost is accepted: a fiddler who plays in three cities gets three `person` rows unless
someone types her email. `merge_person_ids` exists for cleanup.

## Changes

### 1 — Join (session page)

The "Do you attend this session? *Yes, Add Me*" link opens a Dialog: **"Are you a local, or
just visiting?"** → `member` / `visitor`. One question. The row lands `confirmed = FALSE`.

### 2 — Role badge (session page)

The badge reads `Member` / `Visitor` / `Admin`. Clicking it opens a Sheet with a Member/Visitor
`Seg` and Save. `Admin` is never self-assignable; an admin sees the Admin badge but still sets
their own underlying relationship.

### 3 — Sessions tab (person page)

Retitled from "My Sessions" to **Sessions**. The All/Regular `<select>` becomes filter
**chips** — `[Member] [Visitor] [Admin]` — single-select, click again to clear, starts
unfiltered. "Add another session I've been to" becomes the standard **`+`** button, top-right.
The add sheet is **search-first** (no prefetched list, no results until you type) with a
Member/Visitor `Seg`.

### 4 — PersonPicker: one flow for finding and adding people

One kit component (`Sheet desktop="dock"` — full-screen under 768px, right-docked pane above),
replacing the session People tab's stacked search/create sheets, the logger's starter picker,
and the logger's bespoke attendance drawer.

| | Tier 1 | Tier 2 (dimmed) | Empty state |
|---|---|---|---|
| **Session scope** | this session's roster (archived hidden until typed) | — | "Add *James Quinn*" → create person (email-dedupe) |
| **Instance scope** | checked in tonight | this session's roster, not yet checked in — ordered by computed regular-ness | same, then check in + `session_person(visitor, unconfirmed)` |

Two entry points, one component:

- **From a set** (the "Started by" control) → selecting a person checks them in *if needed*,
  attributes the set, and closes. Plus a "— Clear —" row.
- **From "Manage attendance"** → selecting a person toggles check-in and the pane **stays
  open**; checked-in rows get a ✕ to check out.

This collapses the "leave the picker, open the drawer, come back" hop that motivates the whole
change: *I notice Sarah's at the session, I log the tune, I tap "Started by", type "Sar", and
tap her — she's checked in and credited with the set, in one gesture.*

## Out of scope

- Spec 033 itself. This defines its predicates; it doesn't build them.
- The legacy pill logger and `src/ts/attendance.ts` — deleted by 035 step 6, not ported.
- Auto-archive suggestions and "N archived people have attended recently" nudges.
- Any clamp on non-people session data: tunes, logs and history stay visible to everyone,
  member or visitor, confirmed or not.

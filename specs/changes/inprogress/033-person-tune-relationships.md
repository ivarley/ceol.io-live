# 033 — Canonical Person ↔ Session ↔ Tune Relationships

**Status:** Built (all three phases, 2026-07-13) — awaiting user verification.
Predicates live in `services/person_scope.py`; API adds `?scope=member|attended` on
/history and /played-with, `member_play_count`/`attended_play_count` fields
(`session_play_count` kept as deprecated alias = member), `user_relationship` in
the sessions directory, and per-tune `attended_play_count` on the session-detail
payload. `person=me` is a deprecated alias of `scope=member`.

**R2 dropped as a user-facing lens (decision 2026-07-13):** plays auto-enroll tunes
into `session_tune`, so R2 only differs from R3 for on-list-but-never-played tunes
— not a useful question. R2 remains a definition here but has no filter, field, or
predicate helper; the surfaced lenses are R1 (the My Tunes page itself), R3
("Played at my sessions"), and R4 ("While I was there").
**Motivating bug:** Piper's Picnic (tune 5042) shows 2 plays at BD Riley's (Mueller), but the
My Tunes History tab's "My sessions" scope shows 0 — because that scope filters by per-night
check-ins (`session_instance_person`), not session membership (`session_person`), and the
user wasn't checked in on those nights.

## 1. Definitions

### Person ↔ Session (two distinct relationships, never to be conflated)

| Name | Table | Meaning |
|---|---|---|
| **Membership** ("My Sessions") | `session_person` **with `relationship = 'member'`** | This is one of *my* sessions. Dynamic — joined/left at will. A `session_person` row with `relationship = 'visitor'` is **not** membership: it records that I turned up, not that the session is mine (spec [034](034-session-person-changes.md)). |
| **Attendance** ("Sessions I Attended") | `session_instance_person` | I was at this specific instance. Membership NOT required — a visitor still gets credit for the nights she was there. Only rows with `attendance = 'yes'` count as attended; `'maybe'`/`'no'` never count toward any tune relationship. |

### Person ↔ Tune (four relationships)

| Key | Canonical name | Definition (SQL shape) |
|---|---|---|
| **R1** | `tunebook` — "In my tunebook" | `person_tune` row exists |
| **R2** | `repertoire` — "In my sessions' repertoire" | `session_tune st JOIN session_person sp ON st.session_id = sp.session_id AND sp.person_id = :me AND sp.relationship = 'member'` |
| **R3** | `member_plays` — "Played at my sessions" | `session_instance_tune sit JOIN session_instance si JOIN session_person sp ON si.session_id = sp.session_id AND sp.person_id = :me AND sp.relationship = 'member'` |
| **R4** | `attended_plays` — "Played while I was there" | `session_instance_tune sit JOIN session_instance_person sip ON sip.session_instance_id = sit.session_instance_id AND sip.person_id = :me AND sip.attendance = 'yes'` |

R3/R4 counts always exclude `deleted = TRUE` rows and `record_type = 'break'` rows (spec 023),
and count `DISTINCT session_instance_id` when the unit is "times played" (consistent with
existing `session_play_count` behavior).

### Semantic ground rules

1. **Membership is a current-state lens, deliberately retroactive.** Joining a session makes
   its entire history "played at my sessions"; leaving removes it. R2/R3 are views, not logs.
2. **Attendance requires `attendance = 'yes'`.** Today several queries count mere row
   existence, so an explicit "no" RSVP counts as attended. That is a bug everywhere it occurs.
3. **R3 and R4 differ in both directions** (member session on a night I missed; visited
   session I'm not a member of) and must have distinct names in code, API params, and UI copy.
4. **Where UI copy says "at my sessions", it means R3 (membership).** R4 surfaces must say
   "attended" / "while I was there".
5. **Goal:** anywhere tune history or counts appear (including sortable/filterable tune
   lists), the user can identify, filter, and sort by any of R1–R4 that is meaningful there.

### Known interactions / dependencies

- **Check-in auto-creates a `session_person` row** (`database.py:check_in_person`). **Resolved
  by spec [034](034-session-person-changes.md):** the auto-created row is a `visitor`, which is
  excluded from R2/R3 by definition. So check-in no longer implies membership, and R3 ⊉ R4 —
  exactly the property this section worried about. 033 must still not assume R4 ⊆ R3.
- **Spec 025 (session_tune enrollment backfill)** — the live logger doesn't enroll logged
  tunes into `session_tune`, so R2 undercounts until 025 lands. 025 is a data dependency for
  R2-based filters being trustworthy.

## 2. Current-state inventory (from full-app sweep, 2026-07-10)

### 2a. Sites with WRONG or ambiguous semantics (must change)

| Site | What it powers | Today | Target |
|---|---|---|---|
| `api_routes.py` `get_tune_history` `?person=me` (~L214) | Modal History tab "My sessions" scope (my_tunes context) | R4-ish: attendance row exists, **no value check** | R3 default; R4 available as separate scope |
| `api_person_tune_routes.py` `get_person_tune_detail` `session_play_count` (~L336) | My Tunes modal "Logged N times at my sessions" | R4-ish, no value check | R3; also return R4 as `attended_play_count` |
| `services/person_tune_service.py` `PLAYS_SORT_EXPR` (L22-31) + batched `session_play_count` (L658-671) | My Tunes list `plays` sort + per-card play count | R4-ish, no value check | R3; add R4 sort |
| `web_routes.py` `admin_people` `session_instance_count` (~L2671) | Admin People "instances attended" column | Attendance rows, no value check | `attendance='yes'`, label "checked in" |
| `api_routes.py` `get_person_attendance_ajax` (~L5517) | Person attendance history | Returns all rows incl. 'no' | OK to return all, but display must show the value (verify UI) |
| `web_routes.py` `home` suggested tune (~L69-86) | Home "most played at your sessions" suggestion | **R3 (membership)** — correct per new defs, but inconsistent with my-tunes' attendance basis | Keep R3; consistency arrives by fixing the others |

### 2b. Sites already consistent with the definitions (no semantic change)

- Check-in / active-session machinery (`active_session_manager.py` throughout; `live_logging_routes.py` `live_people`, `live_people_search`): attendance with `attendance='yes'` ✓
- Session-admin players/instances grids, `get_session_players`, `get_session_person_detail`: membership for lists, `attendance='yes'` for counts ✓
- `can_view_attendance`: membership OR attendance in ('yes','maybe') — acceptable (authorization, not counting) ✓
- Sessions page "My Sessions" filter (`get_sessions_with_today_status.user_is_member`): membership ✓
- Person profile tabs ("My Sessions" = membership, "I've Attended" = attendance): ✓ (verify 'no' rows are labeled)
- All pure R1 surfaces (my-tunes CRUD, tunebook status, heard counts, profile tune stats) ✓
- Session-scoped and global play counts (session tunes page/grid, live logger `played_here`, magic, common_tunes, modal `times_played`/`global_play_count`): not person-scoped, out of scope ✓

### 2c. Availability gaps (relationships not offered where they should be)

| Surface | Gap |
|---|---|
| Modal Stats tab (my_tunes context) | Shows only one "my" count; should show R3 and R4 as separate cards |
| Modal Stats tab (session/session_instance context) | No "my" aggregate at all (only this-session + global); add R3/R4 cards for logged-in users |
| Modal History tab | Scopes: session ctx = [This session, All]; my_tunes = [My sessions, All]. Target: offer This session (when in session ctx), My sessions (R3), Sessions I attended (R4), All — for any logged-in user |
| Modal Played With tab | Scopes: [At This Session, Globally] only. Add "At My Sessions" (R3) and "While I Was There" (R4) for logged-in users |
| My Tunes filter/sort panel | `plays` sort only (ambiguous). Target: sort by plays-at-my-sessions (R3) and plays-attended (R4); filter chips "played at my sessions" / "played while I was there" (~~R2 repertoire chip~~ — dropped, see status note) |
| Session detail page | `mystatus` filter covers R1 ✓; add filter "played on nights I attended" (R4) and expose R2 trivially (the page IS R2 for members). Play-count badge swaps meaning with sort — label it |
| My Tunes card badge | Badge silently swaps meaning with active sort (plays/popularity/heard) — label it |
| `my_tunes.html` legacy in-page modal (~L2084-2141) | Duplicate "Play count at your sessions" copy — confirm dead and delete, or align |

## 3. Implementation plan

### Phase 1 — Canonical predicates + correctness (fixes the reported bug)

1. **Shared SQL helpers** — new `services/person_scope.py` exposing composable SQL fragments
   (or well-named functions returning `(sql, params)`) for R1–R4, so every endpoint uses
   identical predicates. Include `attendance='yes'`, `deleted=FALSE`, break-row exclusion.
2. **`get_tune_history`**: replace `?person=me` with `?scope=member|attended` (keep
   `person=me` as a deprecated alias for `member`). Modal "My sessions" scope → `member`.
3. **`person_tune_service`**: `session_play_count` and `PLAYS_SORT_EXPR` become R3; add
   `attended_play_count` (R4) to the same batched query; API returns both.
4. **`get_person_tune_detail`**: same — return `member_play_count` (alias
   `session_play_count` for compatibility) + `attended_play_count`.
5. **`admin_people`**: filter instance count by `attendance='yes'`.
6. Tests: unit tests per predicate (member-not-attended, attended-not-member,
   attendance='no'/'maybe', deleted rows, break rows), plus regression test reproducing the
   Piper's Picnic case.

### Phase 2 — Truthful copy

1. Modal stats cards (my_tunes ctx): "Logged N times at my sessions" (R3) + "Logged N times
   while I was there" (R4) as separate cards.
2. History scope labels: "My sessions" (R3), "Sessions I attended" (R4), "All sessions".
3. My Tunes sort buttons: "Plays (my sessions)" etc.; badge gets a per-sort label/tooltip.
4. Delete or align the legacy my_tunes in-page modal copy.

### Phase 3 — Full availability (the "anywhere" requirement)

1. Modal History + Played With tabs: unified scope set — This session (session ctx only),
   My sessions (R3), Attended (R4), All/Globally — shown to logged-in users in every context.
   Backend: `?scope=` param on `/api/tunes/<id>/history` and `/api/tunes/<id>/played-with`.
2. Modal Stats (session/session_instance ctx): add R3/R4 cards for logged-in users
   (requires the detail endpoints or a small separate fetch to supply the counts).
3. My Tunes list: R3/R4 sorts; relationship filter chips (R3/R4; R1 is the page itself; R2 dropped — see status note).
4. Session detail page: R4 filter ("played on nights I attended"); labeled count badges.
5. Live logger: no semantic change (badges are R1/R2/this-session and correctly labeled);
   optionally add R4 dot later — out of scope for 033.

### Out of scope / follow-ups

- The "visiting" model — **now spec [034](034-session-person-changes.md)**, which is a
  prerequisite: R2/R3 depend on `session_person.relationship` existing.
- Spec 025 backfill (R2 data completeness) — prerequisite for prominent R2 filters.
- ~~`is_regular` behavior differences~~ — `is_regular` is deleted by 034. "Regular-ness" is a
  computed, advisory sort signal with no semantics.

## 4. Open decisions

1. ~~**Check-in auto-membership**~~ — **RESOLVED by spec 034.** Check-in still auto-creates a
   `session_person` row, but as a `visitor`, which R2/R3 exclude. Membership is now an explicit
   claim (`relationship = 'member'`), so R3 is no longer a superset of R4.
2. **`attendance='maybe'`** — proposed: never counts as attended for tune relationships;
   only authorization (`can_view_attendance`) keeps its yes/maybe rule. *(Confirm.)*
3. **API naming** — proposed params/fields: `scope=member|attended|session|all`,
   `member_play_count`, `attended_play_count` (with `session_play_count` kept as a
   deprecated alias during transition). *(Confirm.)*
4. **Default "my" scope** where only one fits: membership (R3). *(Confirmed by bug report.)*

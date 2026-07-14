# 036 — Admin Audit

**Status:** Placeholder. Opened 2026-07-13 while designing spec 037 (tune drawer restructure),
which surfaced the first item below and deliberately deferred it here.

## Why

The admin surfaces have accreted rather than been designed. They tend to be the *same* view
everyone else gets with a few extra fields bolted on, which serves neither audience: the
admin view is cluttered with things an admin doesn't need, and it's missing the things an
admin actually came for (provenance, audit trail, merge history, data quality, bulk fixes).

The intent of this spec is to look at every admin view as its own thing, with its own job,
rather than as a privileged variant of the member view.

## Items

### 1. The tune drawer's `admin` mode should not exist as a variant

Found while designing [037](037-tune-drawer-restructure.md).

`TuneSheet.svelte` derives a five-way mode (`admin | session_instance | session | my_tunes |
global`). The `admin` mode fires only on `/admin/tunes`, and it makes the drawer behave in two
ways that are hard to defend:

- The Configure section is force-open and holds an editable canonical **Tune Name**
  (`PUT /api/admin/tunes/<id>`), which is unreachable from anywhere else.
- The my-list status block is **suppressed entirely**, so an admin looking at a tune on
  `/admin/tunes` cannot see or change their own relationship to it — while the same admin
  opening the same tune from `/my-tunes` gets the normal drawer. Two shapes, one person, one
  tune.

Spec 037 restructures the drawer so its shape is determined purely by **scope** (is a session
in context? an instance?) and **relationship** (is it on my list?) — never by which page you
came from. `admin` mode is the one remaining violation of that, and 037 leaves it alone rather
than half-fix it.

The narrow fix considered and rejected for 037: delete the mode, move the canonical-name edit
to an inline affordance on the new `Canonical name: {name} (#{id})` line at the foot of the
Stats tab, and move the tunebook-count refresh next to the Tunebooks stat card — both lit up
for system admins on *every* surface. That's probably right, but it's a band-aid on a page
(`/admin/tunes`) that likely wants to be something quite different: a data-quality view, not a
tune-browsing view with edit rights.

Decide here what `/admin/tunes` is *for*, then decide whether the drawer needs any admin
affordances at all.

### 2. (to be filled in)

Audit the remaining admin views — `/admin/sessions/<path>`, `/admin/people/<id>`, the merge-sync
record UI (031) — against the same question.

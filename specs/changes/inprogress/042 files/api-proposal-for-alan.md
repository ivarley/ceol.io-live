# A Playlist API for irishtune.info ↔ ceol.io Sync

Hi Alan — here's the API proposal we discussed, in two parts. The first part
explains what we're trying to accomplish and how ceol.io would use the API, for
you to evaluate and push back on. The second part is a precise implementation
spec, written so you can hand it directly to an AI coding assistant.

## Part 1: Purpose and how we'll use it

### The goal

Let a musician who uses both sites keep their repertoire in sync, whichever
site is their "tune home." Someone who lives in irishtune.info gets their
playlists reflected into ceol.io (so session logging and my-tunes features know
what they play); someone who lives in ceol.io gets their tune list pushed into
irishtune.info playlists (so they can use the Practice Machine and your stats).
Sync is two-way: each side's edits propagate to the other.

### What ceol.io will do with the API

- A member connects their irishtune.info account to ceol.io once (by pasting an
  API token), and maps each of their playlists to an instrument on our side.
- On each sync (manual "Sync now" button, at most ~daily polling per connected
  member), ceol.io fetches full playlist snapshots, diffs them against the
  state from the previous sync, merges with local changes, and writes back any
  differences in a single batch per playlist.
- All merge logic lives on our side. The API can be completely stateless: no
  webhooks, no change feeds, no timestamps required (there's a nice-to-have
  noted below if you happen to have row timestamps).

### Tune identity is our problem, not yours

ceol.io's tune ids derive from thesession.org, and we know your tune universe
and thesession's don't line up 1:1 (your careful listening merges what they
split, and occasionally vice versa). We maintain a mapping table on our side —
seeded from a hand-built list of ~1,000 correspondences — modeled as attributed
assertions rather than identities, with room for "same," "variant," and
"covers both" relationships, and per-member overrides where universes genuinely
disagree. Your API only ever speaks irishtune.info tune ids. When we encounter
a playlist entry we can't map yet, it parks in a queue on our side until a
human resolves it — nothing is dropped, and nothing about that touches you.

To make that mapping work well, the one thing we'd love beyond playlist
access is bulk tune metadata (titles, alias titles, rhythm, mode, incipit) —
ideally as a periodically regenerated static dump file, in the same spirit as
thesession.org's data dumps. Cheaper for you than an endpoint, better for us.

### What we will never touch

- **Practice data.** Playing a tune at a session is not practicing it, and
  ceol.io doesn't represent practice at all. We will never write
  `last_practiced`; if it appears in read responses we ignore it. Your
  Practice Machine's data stays entirely yours.
- **Public notes.** We'll sync each member's private note ("note to myself
  only") to our per-tune personal notes. We won't write the friends-visible
  note — text someone wrote on ceol.io assuming it was private must not end up
  published to their friends on your site.
- **Anything site-level.** Tokens should only ever grant access to that
  member's own playlist data — never tune definitions, discography, etc.

### Questions for you

1. Do your playlist rows have modified timestamps? Not required, but if they
   exist, an optional `updated_at` + `modified_since` filter would let us poll
   more cheaply.
2. Is a weekly static tune-index dump acceptable (vs. a batch metadata
   endpoint)? Either works; the dump seems easier on your server.
3. Any preference on the token scheme? We assumed generate/revoke on your
   Preferences page; happy to adapt.
4. We believe notes and tags are stored per tune × member (shared across a
   member's playlists) — is that right, and are you comfortable exposing them
   through the API?
5. Does removing a tune from a playlist delete its learned/practiced history on
   your side? If so, we'll prefer setting `current=false` for retirements and
   reserve removal for explicit deletes.
6. What are your tag format rules (allowed characters, case, spaces)? We
   normalize tags to lowercase-hyphenated on our side; we'll compare in
   normalized form either way, but knowing your constraints means we won't
   push tags your side would reject.

Scale expectations, for sizing: a handful of connected members initially,
playlists up to ~1,000 tunes, one read + at most one write per playlist per
sync. This should be negligible load.

---

## Part 2: Implementation specification

This section specifies the API surface in implementation-ready detail. It is
written for the irishtune.info codebase; "the server" below means
irishtune.info, "the client" means ceol.io's sync engine.

### Conventions

- Base path: `https://www.irishtune.info/api/v1/`, JSON request/response
  bodies, UTF-8.
- Dates are ISO `YYYY-MM-DD` strings (matching the site's existing UI format).
  No times or timezones needed anywhere.
- Gzip response compression strongly encouraged (a 1,000-entry playlist
  snapshot is ~100–200 KB uncompressed).
- Errors: appropriate HTTP status plus body `{"error": "human-readable message"}`.
  401 for bad/missing token, 404 for unknown playlist id or a playlist not
  owned by the token's member, 400 for malformed requests.

### Authentication

- Each member can generate (and revoke) a personal API token on their
  Preferences page. One active token per member is sufficient.
- Every request sends `Authorization: Bearer <token>`.
- A token grants read/write access to that member's own playlist data only —
  playlists, entries, and the member's per-tune notes/tags. It must not allow
  any access to site-level tune data, other members, or account settings.

### Endpoint 1: `GET /api/v1/me`

Identifies the token's member and enumerates their playlists.

```json
{
  "username": "ianvarley",
  "playlists": [
    {"playlist_id": 2617, "name": "Piano Accordion", "tune_count": 942, "published": true},
    {"playlist_id": 5791, "name": "Concertina", "tune_count": 41, "published": true},
    {"playlist_id": 6090, "name": "Banjoo", "tune_count": 3, "published": false}
  ]
}
```

`published` reflects the member's existing choice to publish the list at
`/public/playlist/<username>/`. (The API itself ignores this flag — token auth
already proves the member's identity — but the client displays it.)

### Endpoint 2: `GET /api/v1/playlists/{playlist_id}`

Returns the complete entry list for one playlist — a full snapshot every time.
No pagination (playlists are at most a few thousand entries).

```json
{
  "playlist_id": 2617,
  "name": "Piano Accordion",
  "entries": [
    {
      "tune_id": 1768,
      "current": true,
      "learned_on": "2015-05-16",
      "note_public": "",
      "note_private": "Learned from the Chieftains recording",
      "tags": ["waltz-set", "slow"]
    }
  ]
}
```

Field notes:
- `tune_id` is the irishtune.info tune id.
- `current` is the entry's "I currently play this tune" flag.
- `learned_on` is the entry's learned date, `null` if unset.
- `note_public`, `note_private`, and `tags` are stored per tune × member
  (shared across the member's playlists); they are denormalized into every
  entry here for the client's convenience. Empty string / empty array if unset.
- `last_practiced` MAY be included; the client ignores it.
- Optional nice-to-have, only if the underlying rows already have (or can
  trivially gain) modification timestamps: an `updated_at` per entry and a
  `?modified_since=` query filter. Do not build change-tracking infrastructure
  for this — the full-snapshot contract is the design.

### Endpoint 3: `POST /api/v1/playlists/{playlist_id}/entries`

Batch write: upserts and removals in one request. This is the only write
endpoint.

Request:
```json
{
  "upsert": [
    {"tune_id": 1768, "current": true, "learned_on": "2015-05-16",
     "note_private": "Learned from the Chieftains recording",
     "tags": ["waltz-set", "slow"]}
  ],
  "remove": [4321]
}
```

Semantics:
- **Upsert**: if the tune is not in the playlist, add it; then set each field
  *included* in the object. Omitted fields are left untouched. Explicit `null`
  clears a clearable field (`learned_on`). This makes requests idempotent:
  re-sending the same batch is a no-op.
- `note_public`, `note_private`, `tags` write the member's per-tune values
  (visible across all their playlists), exactly as if edited on the Tune Info
  page.
- The client never sends `last_practiced`; if sent, reject or ignore it.
- **Remove**: delete the entry from this playlist (the existing "from
  playlist" action). Removing a tune not in the playlist is a no-op, not an
  error.
- **Per-item errors**: an unknown `tune_id` (or otherwise unprocessable item)
  fails that item only; the rest of the batch proceeds. Response:

```json
{
  "results": [
    {"tune_id": 1768, "ok": true},
    {"tune_id": 99999, "ok": false, "error": "unknown tune id"}
  ]
}
```

- Batch sizes: the client sends at most a few hundred items per request and
  can chunk to any limit you declare; a limit of 500 items is plenty.

### Endpoint 4: tune index for mapping

Either or both of:

**(a) Static dump (preferred).** A periodically regenerated (e.g. weekly) flat
file — JSON or CSV, one row per tune, publicly fetchable at a stable URL:

```json
{"tune_id": 1768, "title": "Sí Bheag, Sí Mhór",
 "aliases": ["Sí Beag, Sí Mór", "Sheebeg and Sheemore", "…"],
 "rhythm": "Air", "mode": "D Major", "structure": "AABB",
 "incipit_abc": "|f2 fe d2|d2 de d2|"}
```

**(b) Batch endpoint.** `GET /api/v1/tunes?ids=1768,538` (≤100 ids per
request), returning `{"tunes": [ …same shape as above… ]}`.

The dump serves offline fuzzy matching (title aliases + melodic incipit
comparison) in ceol.io's admin mapping tool; the batch endpoint would only be
used for on-demand lookups. If choosing one, choose the dump.

### Explicit non-requirements

- No OAuth, no webhooks, no pagination, no rate-limiting infrastructure, no
  change feeds, no deletion tombstones.
- No thesession.org awareness of any kind — all cross-site id mapping happens
  on the ceol.io side.
- The client identifies itself with a `User-Agent` header
  (`ceol.io-sync/<version>` plus a contact address) and polls each connected
  member's playlists at most ~daily, plus user-initiated manual syncs.

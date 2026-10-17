# 060: The app without signing in

**Date:** 2026-10-17
**Status:** BUILT (not yet released). Server, app, Irish, help and tests are done.

## Why

On the web you can read everything Ceol holds about sessions without an account: the
sessions directory, a session's tunes and logs, a night's log (live, while it is on), and
any tune. You need an account to change something or to keep something of your own.

The iOS app asks you to sign in before it shows anything. Someone who is sent a session
link, or who finds the app in the App Store, meets a sign-in screen first. App Review
also expects an app not to ask for an account before showing things that aren't tied to
one (guideline 5.1.1).

The rule this spec gives the app is the web's rule: **reading is open, and changing
things or keeping things of your own needs an account.**

## What the server already allows signed out

Most of what the Sessions tab reads is already `@public_api`, because the web's pages
read the same endpoints:

- the sessions list (`/api/sessions/with-today-status`), a session's detail, its
  remaining tunes, its logs, and the logged-tunes filter;
- festivals (`/api/resolve`);
- a night's bootstrap (`/api/live/instances/<id>/bootstrap`, with `can_edit` false and
  the people removed), and the streaming sidecar's events while the night is active
  (served anonymously, people removed);
- a tune's detail (`/api/tunes/<id>/detail`). This includes the notation images of
  its main setting, and for a tune with no cached notation it includes a notation
  token (spec 052 §B21);
- the public top tunes (`/api/tunes/top`) and the thesession.org search
  (`/api/tunes/thesession-search`, rate-limited).

## Decisions

Agreed with the product owner; see the end.

### Starting the app

- **With no sign-in stored, the app opens on Home as a guest**, not on the sign-in
  screen. `AppModel.phase` gains `.guest`. Launch goes to `.guest` where it now goes to
  `.signedOut`.
- **Signing in is a sheet** that can be opened from anywhere. It is today's
  `SignInView`, unchanged inside. When sign-in succeeds, the sheet closes and you are
  where you were. Each screen reloads, so its personal parts appear (your status on a
  tune, Join on a session, and so on). If the account still needs its profile filled in,
  the profile screen follows before you return.
- **An emailed sign-in link** opened while a guest signs you in, as it does now.
- **A sign-in that has run out** (`signInExpired`) puts you back in guest mode with
  today's notice ("Your sign-in ran out…"), instead of putting you in front of a
  sign-in screen. **Signing out** and **deleting your account** also put you in guest
  mode.
- **Request handling for guests:** the app sends no token. `UnauthorizedMiddleware`
  already ignores a 401 on a request that carried no token. The app's own URLSession
  path (`AppModel.authorized`, `LiveNight.swift`) must do the same, and treat a 401 as
  a run-out sign-in only when a token was sent.

### The tabs as a guest

- **Home.** `/api/home` is personal (your sessions, your recent nights, your tunes to
  learn), so a guest doesn't call it. A guest's Home is a short welcome, whose links open
  the screens they name:

  > Welcome to Ceol, an app for traditional Irish music. You can use the **Listen**
  > feature to figure out what tune you're hearing, and browse **tunes** and **session
  > logs**. To track your own tunes or edit session logs, **sign in** or **create a free
  > account**.

  - **Listen** opens the Listen tab; **tunes** the Tunes tab; **session logs** the
    Sessions tab.
  - **sign in** and **create a free account** both open the sign-in sheet, which is one
    email-first form for both.
- **Sessions.** These all read as they do signed in:
  - the list. A guest belongs to no session, and the app doesn't know where they are,
    so the list shows every active session, as it already does for a member of none.
    The filter sheet drops "Mine" and "Visited";
  - a session's Tunes and Logs;
  - festivals and their years;
  - a night's log, read-only, and live while the night is on;
  - tune sheets.

  The parts that need an account show a sign-in prompt where their control would be:
  - **People tab:** hidden. The server gives a guest no people.
  - **Join this session, Add a tune, Add a person, Add a night:** each opens the
    sign-in sheet.
  - **A night:** no entry box, as on the web. In its place is "Sign in to log tunes",
    which opens the sheet. Recordings and "Find the tunes automatically" don't appear.
  - **Add a session:** opens the sign-in sheet.
- **Tunes.** Signed in, this tab is your tunebook. As a guest it shows the most common
  tunes in tunebooks (`/api/tunes/top`, the web's public Tunes page), with **Sign in to
  keep your own tunebook** at the top. Search uses the catalogue's public name search
  (`/api/tunes/search`), because the deep search needs a login.
  On a tune sheet, the tunebook buttons (add, status, heard count) are replaced by
  **Sign in to add this to your tunes**.
- **Listen.** Ad-hoc mode works for a guest: the meter says what is playing, and the
  notation can be shown full screen. Recent Tunes Heard is kept on the phone, as now, and
  stays there after signing in. Only Ad-hoc mode is open to guests:
  - Log mode can't be reached, because it starts from a night's page, and a guest has
    no Listen button there.
  - Recording stays off and can't be turned on, because a guest's recording could not
    be uploaded.
  - When a tune is recognised, the offer to add it to your tunebook says **Sign in to
    add this to your tunes**.
- **Me.** A guest sees **Sign in or create an account**. Below it are the parts of Me that
  aren't about an account: Language, Help, Contact & Support, and the Privacy Policy.
  - **Opening the web pages:** signed in, those pages open through a one-time web
    sign-in link (`/api/auth/web-session`). For a guest they open as plain web pages.
  - **Language:** signed in, it is saved on your profile. For a guest it is kept on the
    phone. When you sign in, your profile's language takes over.

### Server changes

These open what a guest reads, and nothing that changes data:

- **`GET /api/listen/decider-data` becomes `@public_api`.** It is built from
  thesession.org's public data dump, and the phone needs it to hear tunes at all.
- **Notation images become public:**
  - `GET /api/tunes/settings/<id>/image` and `GET /api/tunes/<id>/incipit-image`. They
    render from ABC already in our database through our own ABC renderer, and make no
    outbound fetch, so they can't be used as an open proxy. Signed-out calls get the
    a rate limit of 60 a minute per address. That is twice the search's, because a pub's worth of guests can share one address.
  - The tune sheet's setting chooser and the search preview for a local tune also read
    `GET /api/tunes/<id>/preview`, so it opens the same way.
- **What stays behind a login:**
  - `GET /api/tunes/thesession/<id>/preview` and `POST /api/tunes/render-abc`. The
    first fetches from thesession.org, and the second renders any ABC it is sent. A
    guest's search preview of a tune we don't hold shows its ABC as text, with no
    rendered notation.
  - The catalogue's deep search, every write, `/api/home`, `/api/my-tunes*`,
    `/api/me*`, the session people endpoints, the night's vocabulary and people, and
    recordings.
- **The native surface** gains `/api/tunes/top`. The four endpoints that become public
  are marked public there. `tests/contract/test_native_surface.py` checks each of them
  signed out.

### Not in this change

- **Opening session and night links in the app.** The app claims those links (the AASA
  file lists `/sessions/*` and `/live/instances/*`), but `AppModel.open` only handles
  sign-in links, signed in or not. Routing a link to its page is its own change and
  helps signed-in people just as much.
- **The web.** It already works this way.

## Steps

1. **Server:**
   - Make `decider-data`, the two image endpoints and the local tune preview public.
   - Add the signed-out rate limit.
   - Update the native surface and the contract test.
   - Add tests: each endpoint answers a signed-out caller, and a guest is refused on
     the writes next to them.
2. **CeolKit:**
   - Add the guest phase to the app model's rules.
   - Make the raw-request path ignore a 401 when no token was sent.
   - Write tests for both.
3. **App, the shell:**
   - `.guest` at launch and after a sign-out, run-out sign-in or account deletion.
   - The sign-in sheet, with the return to where you were.
   - The prefetcher and the tune queue stay off for a guest. The decider data refresh
     runs.
4. **App, the tabs:**
   - Home's guest version.
   - The guest prompts in Sessions and on the night.
   - Tunes as the top tunes.
   - The tune sheet's sign-in button.
   - Listen's guest limits.
   - Me's guest version.
5. **Irish** for every new string (spec 057). **Help:** a short section on using the app
   without an account, in `help.html` and its Irish twin, and a line in the release notes.
6. **Tests:**
   - XCUITests: launch with no account, open a session's logs, open a night, open a
     tune; tap Join and get the sign-in sheet; sign in from the sheet and land back on
     the session with Join available.
   - The App Store screenshot test still signs in, so it is unchanged.

## Decided by the product owner (2026-10-17)

1. **First launch:** straight to Home as a guest, with no welcome screen before it. The
   guest Home is itself the welcome.
2. **The People tab for a guest:** hidden.
3. **Guest Home:** the welcome text above, not "happening now and today". The Sessions
   tab shows every session.

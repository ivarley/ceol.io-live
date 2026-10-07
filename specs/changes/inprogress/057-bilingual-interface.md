# 057: Bilingual interface (English and Irish)

**Date:** 2026-10-06
**Status:** STAGES 1-5 BUILT (2026-10-07): the machinery, the setting and switch, the
tests, the CLAUDE.md rule, the agreed glossary, every Svelte bundle and Jinja page, the
iOS app, the messages the server sends, and the emails. Next: help. The
decisions are the product owner's, from a short Q&A on 2026-10-06.

## Why

All of Ceol's text should be available in Irish as well as English, chosen per person.
And from here on, any interface work has to work in both languages.

## Decisions

- **Scope: everything a person reads.** The web pages (Svelte bundles and Jinja pages),
  the iOS app, the sentences the API returns (errors, confirmations), emails, and the
  help pages.
- **Not translated: data.** Names of tunes, sessions, places and people stay as entered.
  Interface vocabulary that describes data *is* translated: tune types ("Reel", "Jig"),
  session types, filter labels.
- **Who writes it.** Claude drafts the Irish in An Caighdeán Oifigiúil. The product owner
  reviews it. Every drafted string is marked as needing review until it is approved.
- **Glossary.** The repo holds a glossary of music terms, owned by the product owner and
  agreed before the bulk of the translation. The obvious word is often wrong ("port" is
  a jig, not any tune), and terms have to read the same everywhere.
- **Choosing the language.**
  - A profile setting: a language column on the account, editable on the profile and
    returned by `/api/me`.
  - Signed out: English, with a visible English/Gaeilge switch remembered in a cookie.
  - Signed in: the profile setting, on the web and in iOS. The iOS app does not follow
    the phone's language.
  - Server messages and emails go out in the recipient's language.
- **Dates and plurals follow Irish rules.** "Dé hAoine 23 Deireadh Fómhair", and Irish
  plural forms, which have more cases than English.
- **The invariant.** Every user-facing string exists in both languages. Tests in pytest,
  Vitest and the iOS suite fail when a string has no Irish entry. A drafted, unreviewed
  string still counts, and the review marking tracks it. CLAUDE.md states the rule in the
  same change that adds the machinery and these tests, so the rule never sits there
  unenforced.

## Machinery (implementer's choice, recorded here)

- Server and Jinja: Flask-Babel / gettext catalogs.
- Svelte: one shared message catalog that all bundles import.
- iOS: Xcode String Catalogs.

## Order of work

1. The machinery, the language setting and switch, the missing-string tests, the
   glossary, and the CLAUDE.md rule.
2. One surface at a time, each fully translated before the next: the web, then iOS,
   then server messages, then emails, then help.

## Stage 1 as built

- `user_account.language` ('en' | 'ga', `schema/059_user_language.sql`), on `/api/me`
  and `GET|PUT /api/me/profile` (`account.language`, body `language`), set on /me
  (`personpage/LanguageSetting.svelte`, which reloads the page after saving).
- `i18n.py`: the request's language is the profile setting, else the `ceol_lang` cookie,
  else English. `GET /language/<en|ga>?next=` is the switch: it sets the cookie and,
  when signed in, the profile. Flask-Babel serves `translations/ga/LC_MESSAGES/messages.po`
  (the compiled `.mo` is committed, since the build may not run `pybabel compile`);
  `<html lang>` and `window.__CEOL_LANG__` carry the language to the page.
- The switch, named in the other language ("Gaeilge" / "English"): in the desktop menu
  and, signed out, in the header at every width.
- Svelte: `t()` / `tn()` from `frontend/src/lib` over `frontend/src/lib/i18n/ga.json`.
  Plurals use `Intl.PluralRules('ga')`'s five forms. `LANGUAGE_NAMES` holds the one
  deliberate non-translation.
- Review marking: `"review": true` in ga.json, `#, review` in the .po;
  `scripts/i18n_po.py set | approve | pending`.
- Tests: `tests/unit/test_i18n_catalogs.py` (every `_()` string has Irish, the .mo is
  current, converted templates have no bare English), `frontend/tests/i18n.test.js`
  (the same for `t()`/`tn()` and converted components), and
  `tests/integration/test_i18n_language.py` (selection and the switch).
- Converted: `header_nav.html`, `hamburger_menu.html`, `tab_bar.html`, and
  `LanguageSetting.svelte`.
- Glossary: [specs/current/ui/irish-glossary.md](../../current/ui/irish-glossary.md),
  agreed by the product owner on 2026-10-06.
- Since stage 1: the Svelte catalog is split by area (`frontend/src/lib/i18n/ga/*.json`,
  merged at build; a test fails if two files translate one English string two ways), a
  converted file is found by its `i18n-converted` marker rather than a list, and
  `formatDate()` / `formatNumber()` format in the page's language.

## Stage 2 (the web) as built

- Every Svelte component under `frontend/src` carries `i18n-converted` (the catalog
  split into `ga/core|kit|live|tunesheet|sessions|mytunes|admin.json`, about 1,500
  entries), and every reachable Jinja template carries `{# i18n-converted #}` (about 830
  entries in `messages.po`). Not converted: the help pages (stage 6), the quarantined
  pill logger (`session_instance_detail.html` and its scripts, unreachable and due for
  deletion), and two templates no route renders.
- `tc(context, text)` for one English word with two Irish ones, keyed `context|text`:
  `tc('area', 'Admin')` (Riarachán) beside `t('Admin')` (Bainisteoir).
- Fixture-held logic shared with iOS keeps its English: components translate its fixed
  outputs through literal lookups (`livelabels.js`, `mytunes/labels.js`,
  `shared/sessionpathText.js`), and the logger's activity lines are rebuilt in Irish
  (`activityLine`), English unchanged.
- Irish pages: the 24-hour clock, `formatDate` everywhere a date is shown, no title
  case on labels (`html[lang="ga"]` overrides in base.html and app.css).
- Legacy scripts read `window.__CEOL_T__` (base.html, from `i18n.ceol_js_strings()`).
- Known gaps: text the server sends (stage 4) shows in English; the offline page is
  cached in whichever language was active when the service worker stored it.


## Stage 3 (iOS) as built

- `ios/Ceol/Ceol/L10n.swift`: `AppLanguage` (the profile's language, remembered in
  UserDefaults so launch starts in it) and `tr()` for text that isn't a SwiftUI literal.
  The root sets `\.locale` from it; ContentView rebuilds the screens (`.id`) when it
  changes, below the launch task so a change doesn't re-run launch. Signing in applies
  the account's language; the Me screen sets it (`PUT /api/me/profile`).
- `Localizable.xcstrings` (about 790 strings, `ga` in knownRegions) is synced from the
  build's extracted strings. The Irish lives in `ios/Ceol/i18n-ga/{core,tunes,sessions,live}.json`,
  applied as `needs_review` by `scripts/ios_strings.py` (`make ios-strings`).
  `make ios-test` fails when an extracted string has no Irish
  (`ios_strings.py missing`); `tests/unit/test_ios_strings.py` covers the script.
- Plurals: keys with one integer argument get Irish's five forms; English singulars
  are separate keys ("1 tune" / "%lld tunes").
- CeolKit's fixture-held logic keeps its English; the views translate its outputs
  (`TunesWords`, `HomeText`, `SessionsL10n`, `logLabelName`, `liveActivityLine`).
- One English word with two Irish ones: `Admin (a session's)` (defaultValue "Admin",
  Bainisteoir) beside `Admin` (the menu item, Riarachán).
- Left in English: server text (stage 4), `session_date` as the server formats it,
  data.

## Stage 4 (server messages) as built

- Every message a person reads from the API, `flash()` and the error pages goes
  through `_()` (about 600 msgids), in the route modules and the helpers whose text
  reaches a person (`places.py`, `session_path.py`, `session_fields.py`,
  `recurrence_utils.py`, `database.py`'s attendance helpers, the person-tune, merge and
  deletion services). A converted module carries `# i18n-converted`;
  `tests/unit/test_i18n_catalogs.py` fails on an `api_error()` / `flash()` message or a
  `"message"` / `"error"` value left outside `_()` (`# not-i18n` marks a literal that
  is a code or meant for developers).
- Sentences built from English pieces became one whole sentence per case; counts use
  `ngettext`.
- The native app sends its language as Accept-Language; `i18n.get_locale` follows it
  only when X-Ceol-Client is present, so the app's sign-in errors come in its language
  and a browser stays English until the switch is used.
- A message built before `login_user` / `logout_user` in one request keeps the
  earlier language (Flask-Babel caches the locale per request), so logout and account
  deletion word their message first.
- Left in English: codes; log lines; text saved to the database or broadcast to other
  logger clients; `str(e)` passthroughs; `services/thesession_sync_service.py` and
  three person-tune service messages, which callers parse by their text (fixing that
  needs error codes first); dates from `format_session_date()`, which is English-only.

## Stage 5 (emails) as built

- Every email is built in `email_utils.py` inside `force_locale(<recipient's
  language>)`: the sign-in, verification and password emails from the account's
  setting, the update emails' footer from the recipient's account (the body is the
  admin's own text), and the "person added to your session" notice
  (`send_person_added_email`) per admin. The registration email has no account yet,
  so it follows the request (cookie or the app's Accept-Language).
- A new account takes the language of the request that creates it
  (`i18n.request_language()`), so signing up in Irish gives Irish emails from the
  first one.
- English is byte-identical to before. The old site name "Irish Music Sessions" is
  still in the subjects; the Irish uses "Seisiúin Cheoil Ghaelaigh" for now.

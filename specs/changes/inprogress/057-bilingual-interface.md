# 057: Bilingual interface (English and Irish)

**Date:** 2026-10-06
**Status:** STAGE 1 BUILT (2026-10-06): the machinery, the setting and switch, the
tests, the CLAUDE.md rule and a draft glossary; the page chrome (header links, menu,
tab bar) converted as the proof. The glossary was agreed the same day. Next: stage 2. The
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


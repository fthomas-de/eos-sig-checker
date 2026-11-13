# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.7`, 2026-11-13 (see `CHANGELOG.md` under 0.0.7). Pushed to
  `origin/main` with the annotated tags `v0.0.1` to `v0.0.7` ("Release
  <version>" on the release commit).
- New in 0.0.7 (no migration): card **WH** (`fa-hurricane`) on the paste
  page, left of the probe scanner box - every row with group `Wormhole`
  checked in the last 3 hours (`sync.recent_wormholes`,
  `sync.WORMHOLE_HOURS`), any system, newest first; columns System, ID,
  time (`H:i`). Read after the merge, so a paste's wormholes show at once;
  no polling. Layout `col-lg-3` / `col-lg-3` / `col-lg-6` (WH / probe
  scanner / result): at 2/5/5 the WH card scrolled sideways.
- New in 0.0.6, all on the paste page (no migration):
  - switch **Hide Cosmic Anomalies** in the result header, always shown,
    on by default (`js/anomalies.js`, state in localStorage under
    `eos_sig_checker.show_anomalies`); rows carry
    `data-eos-sig-checker-anomaly`, Copy switches between `copy_text` and
    `copy_text_signatures` (`views.ANOMALY`);
  - the probe scanner box is empty after a processed check (an unbound
    `PasteForm`); a refused check (429, too many lines) keeps the text;
  - no Distance column in the result; Copy keeps the distance;
  - result and Copy show the stored best signal, not the pasted one
    (`sync._store` replaces the line's signal when they differ);
  - switching tracking off keeps the last picked character in the menu
    (localStorage `eos_sig_checker.last_character`, every tab).
- 0.0.5 brought the audit findings (`docs/AUDIT.md`, SIG-01 to SIG-05):
  growing wait after failed location reads, 200 lines per paste as a
  setting, rows locked in ID order, `re.ASCII` patterns, the statistics
  line below every page; migration 0004.
- What the app does: the paste page (`basic_access`) - the WH card, then
  the probe scanner box (English client), then the result: the same lines
  come back as a table with site type and name filled in from the
  shared list (green), invalid lines red with the reason, a Copy button.
  Every valid line is stored or merged into `Signature`; a Celery task
  deletes rows past their age. `manage_settings` opens the **Signatures**
  tab (DataTable, a filter each for System, ID, Group, Name; expired rows
  greyed out) and the **Settings** tab (days an entry counts, 1-30; longest
  wait after failed location reads; lines per paste; Delete all
  signatures).
- Location tracking through ESI (`tracking.py`, `provider.py`,
  `js/tracking.js`), off by default, per browser tab, only existing tokens
  with `esi-location.read_location.v1`. Every check stores the system (one
  row per signature ID **and** system).
- Tests: 107 without the `translations` tag (all pass at 0.0.7), plus the
  catalogue tests run by `tools/translate.py`. The two WH tests fail when
  the `Wormhole` filter is dropped. No automated test for the browser side
  of the scripts; the WH card was checked in the browser pane at 1500 px,
  empty and with one entry, dark theme.

## Open

- **Not looked at in the browser yet** (0.0.5): the statistics line on the
  three pages, the settings page with three fields, the 200-line message,
  the tracking message during a growing wait.
- WH card not checked yet: light theme, narrow screen (the three cards
  stack), many wormholes with long system names.
- The live instance: remove `EOS_SIG_CHECKER_MAX_AGE_DAYS` from its
  `local.py` if set, install `@v0.0.7`, run migrate (0002 to 0004) and
  `collectstatic`, restart AA and Celery, then give `manage_settings` to
  whoever looks after the list. Members who want tracking need a token
  with `esi-location.read_location.v1` from another app (corptools asks for
  it).
- README's install line still names `@v0.0.1`: point it at the current tag
  with the next change (left out at the user's choice).
- `sync.statistics` scans the table on every page view (marked `shortcut:`
  in the code): cache it if the table ever passes about 100,000 rows.
- Not checked yet: a real Ctrl+V from the EVE client, the light theme, an
  expired row on the Signatures tab outside the unit tests, the Refresh
  button by a real click, a system change while tracking.
- Next sensible step: deploy 0.0.7 to the live instance (README's install
  section), then a real paste from the EVE client.

## Decisions

- 0.0.7 (2026-11-13): the WH card is on the paste page only, not on the
  Signatures tab. "Seen" means `last_checked` (not `first_seen`) within 3
  hours, a constant rather than a setting. Columns System, ID, time; rows
  without a system stay in with a blank system. Title "WH" stays
  untranslated; icon `fa-hurricane` (Font Awesome has no wormhole).
- 0.0.6 (2026-11-13): the anomaly switch is always visible, on by default,
  remembered per browser; Copy takes only what is shown. The box empties
  after every processed check, invalid lines included (they stay in the
  result). The last tracked character is remembered per browser, tracking
  itself stays per tab. Only the paste page has the switch, not the
  Signatures tab.
- Audit (2026-11-12): no cap on how many rows a member may add per day -
  the statistics line is the indicator instead. The Signatures tab stays
  unlimited (no server-side paging). Paste limit 200, a setting. Failed
  location reads: growing wait, 5 steps that follow the limit, limit a
  setting (default 60 s). The statistics are visible to everybody who can
  open a page, below the content. `docs/AUDIT.md` records the audit.
- Solar system only with tracking: key is (signature ID, system);
  `NO_SYSTEM` = 0 for untracked pastes (MySQL lets NULLs past a unique
  constraint). A tracked paste adopts the ID's row without system. An
  untracked paste resolves by ID alone from the newest live row of the same
  site in any system and leaves its system alone; another site under that
  ID gets a row without system. Rows count for the days on the settings
  page (1-30).
- Tracking: off by default, per browser tab (`?character=` in the URL, the
  paste form posts to the same URL; sessionStorage restores it when the
  menu link drops the parameter, a new tab starts off). The app has no SSO
  button of its own. The server looks the system up itself and checks
  ownership before the location cache.
- Tracking display: no paste = the system's live rows; after a paste = the
  pasted lines plus the system's other live rows ("not in this paste"),
  Copy includes both. Poll every 10 s, Refresh at most every 5 s; a new
  system reloads the page as a GET.
- A newer paste with another group/type/name for the same ID wins and
  restarts `first_seen`. Blank columns of a weaker scan never overwrite.
  Scan strength stored and shown is the best seen; distance is the last
  pasted and only in Copy and the database.
- English client only. A line with a valid ID but another group is
  skipped: not stored, not listed, only counted under the result.
- Headers follow the in-game window: Kind = Cosmic Signature/Anomaly,
  Group = Combat Site/Wormhole/..., Name, Signal. Model fields stay
  `group`/`site_type`. Signal colours like the game (`parser.signal_band`).
- Paste checks on its own (`autocheck.js`). Limit 1 check per user and
  second (`views.MIN_INTERVAL_SECONDS`): browser waits via sessionStorage,
  server refuses with 429 via `cache.add`.
- Two permissions: `basic_access` and `manage_settings`. No separate view
  permission for the list.
- The settings live only on the settings page: no fallback to `local.py`.
- Navigation as navbar tabs: Sig Checker | Signatures | Settings, each only
  with its permission.
- Tracking problems are shown, never swallowed: a message box below the
  bar that clears on the next good read, while the last position stays.
- Signature list: one filter field per column, expired rows greyed out
  rather than hidden, no Distance column.
- Languages: de, ru, zh_Hans, like the sister apps.

## Dev instance

- Installed editable (`--no-deps`), `'eos_sig_checker',` in
  `INSTALLED_APPS`, cleanup task in `CELERYBEAT_SCHEDULE` (11:15 daily),
  migrations 0001-0004 applied, static collected at 0.0.6 (0.0.7 changed
  no static file). Settings stored:
  max age 7; 60 s, 200 lines. The Celery worker was not restarted after
  0.0.5 - no task changed since, restart it anyway at the next chance.
- `Signature` holds the user's sample pastes plus browser test rows
  `ZZT-901`/`ZZT-902` (R-ARKN) and `ZZT-911`/`ZZT-912`/`ZZT-921` (wormhole)/
  `ZZT-922` (no system): this
  app's own, they expire on their own.
- Browser checks log in as account `E_o` (superuser, location tokens):
  BigBlackout C and E 'o work, Eh 'o's refresh token is dead (SSO
  `invalid_grant`). Account `Eh_o` has no `basic_access`.
- `discord_announcer.0008_transaction_kind` is pending in `aa_dev` - not
  ours, left alone.
- The app's URL is `/eos_sig_checker/` (underscores); `/eos-sig-checker/`
  is a 404.
- The dev server answers on `http://127.0.0.1:8000`; `localhost:8000` is
  refused by `ALLOWED_HOSTS`. Claude starts it through the preview config
  `aa-dev` in `C:\Users\flt\Claude\.claude\launch.json` (runserver in WSL).
- Migration 0001 depends on `eveonline 0001_initial` on purpose: the newest
  eveonline migration would force the newest AA.

## Traps

- `str.strip()` removes `\x1c`-`\x1f` as whitespace: `parser.parse` rejects
  control characters before splitting.
- `models.py` imports `parser.MAX_LINES`: the parser must never import from
  `models` (or anything that does), or the import goes circular.
- The settings form has three required fields: a test that posts to the
  settings page sends `{**VALID, ...}` (`tests/test_settings.py`), or the
  post is refused.
- A test that wants a failed location read again must delete the cached
  failure first (`eos_sig_checker:location:<id>`), see
  `TestLocate.fail_read`.
- `sri_static` hashes from the collected static files: a new JS/CSS file
  breaks every view test until `collectstatic` ran.
- A model validator puts no `min`/`max` on the form widget, and a
  `PositiveSmallIntegerField` writes its own `min="0"`: set the attributes
  in the form's `__init__`.
- In Claude's browser pane a simulated Ctrl+V inserts nothing: set the
  textarea's value by script and call `form.requestSubmit()`.
- "Position" clashes with Alliance Auth's Russian catalogue: it carries the
  `eos-sig-checker` context, like Name and Type.
- `.git/CLAUDE_COMMIT_MSG` can survive from an earlier commit: Read it
  before writing the new message, or the Write is refused.
- View tests that post twice need `cache.clear()` in between, or the rate
  limit answers the second post with 429.
- Saving a `Token` in a test runs AA's ownership signal: move the
  `CharacterOwnership` back after creating the token for a foreign one.
- `Token.objects.require_scopes` does not exist on the manager, only on the
  queryset.
- Tests mock `tracking.esi` (or `tracking.locate`): the real provider loads
  the OpenAPI spec from ESI on first use.
- Another session may use the shared test database `test_aa_dev` at the
  same time: run with `EOS_TEST_DB=<own name>` (read by the dev
  `local.py`) to get a database of our own.
- The form field keeps `strip=False`: the trailing tabs of an unscanned line
  are columns.
- Through the WSL bridge (`bash -lc '...'`) `%` formats and nested quotes
  break the quoting: put longer commands into a script file and run it by
  path.
- `tools/translate.py` stops on a glossary entry the code no longer uses
  ("Not used by the code any more"): delete it from `tools/glossary.py`
  when a text leaves a template.

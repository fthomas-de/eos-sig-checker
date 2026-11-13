# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.5`, 2026-11-13 (see `CHANGELOG.md` under 0.0.5). Pushed to
  `origin/main` with the annotated tags `v0.0.1` to `v0.0.5` ("Release
  <version>" on the release commit).
- New in 0.0.5: the findings of the security and bug audit in
  `docs/AUDIT.md` (SIG-01 to SIG-05), all implemented:
  - a failed location read is cached as well, and the wait grows with
    every failure in a row in 5 even steps from 5 s up to a limit on the
    settings page (default 60 s; `tracking._retry_seconds`, `_failure`,
    failure count in the cache under `FAILURES_KEY`);
  - at most 200 lines per paste, a setting (1-500; `parser.MAX_LINES` = 500
    stays the ceiling);
  - `sync.merge` locks rows in signature ID order (deadlock between two
    differently sorted pastes), the body moved into `sync._store`;
  - the parser's ID, signal and distance patterns carry `re.ASCII`;
  - a line of statistics below every page (`sync.statistics`, passed by
    `views._render`, drawn in `base.html`), red when a row is past its age
    by more than a day (the cleanup task does not run).
  - Migration 0004 adds `location_retry_seconds` and `max_lines` to
    `SigCheckerConfiguration`; the settings card is titled Settings instead
    of Cleanup.
- What the app does: the paste page (`basic_access`) - two equal panes,
  paste the probe scanner (English client) on the left, the same lines come
  back on the right as a table with site type and name filled in from the
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
- Tests: 100 without the `translations` tag (all pass at 0.0.5), plus the
  catalogue tests run by `tools/translate.py`. The new tests of 0.0.5 for
  the paste limit, the failure count and the statistics context were
  checked against broken code; the settings-page tests of the two new
  fields and `TestStatistics` in `test_sync.py` were not. No automated test
  for the browser side of the three scripts.

## Open

- **Not looked at in the browser yet** (0.0.5): the statistics line on the
  three pages, the settings page with three fields, the 200-line message,
  the tracking message during a growing wait.
- The live instance: remove `EOS_SIG_CHECKER_MAX_AGE_DAYS` from its
  `local.py` if set, install `@v0.0.5`, run migrate (0002 to 0004) and
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
- Next sensible step: look at 0.0.5 in the browser, then deploy to the
  live instance (README's install section).

## Decisions

- Audit (2026-11-12): no cap on how many rows a member may add per day -
  the statistics line is the indicator instead. The Signatures tab stays
  unlimited (no server-side paging). Paste limit 200, a setting. Failed
  location reads: growing wait, 5 steps that follow the limit, limit a
  setting (default 60 s). Choices made while planning and not contradicted:
  the statistics are visible to everybody who can open a page, they sit
  below the content (not fixed to the window), the steps are even, not
  doubling. `docs/AUDIT.md` is committed and records the audit.
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
  Scan strength stored is the best seen; distance is the last pasted.
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
  migrations 0001-0004 applied, static collected (0.0.5 changed no static
  file). Settings stored: max age 7; the two new fields at their defaults
  (60 s, 200 lines). The Celery worker was not restarted after 0.0.5 - the
  task does not use the new fields, restart it anyway at the next chance.
- `Signature` holds the user's sample pastes plus two browser test rows
  `ZZT-901`/`ZZT-902` in R-ARKN: this app's own, they expire on their own.
- Tokens with the location scope: account `E_o` - BigBlackout C and E 'o
  work, Eh 'o's refresh token is dead (SSO `invalid_grant`) - the case for
  the growing wait.
- `discord_announcer.0008_transaction_kind` is pending in `aa_dev` - not
  ours, left alone.
- The dev server answers on `http://127.0.0.1:8000`; `localhost:8000` is
  refused by `ALLOWED_HOSTS`.
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
- In Claude's browser pane a simulated Ctrl+V inserts nothing: dispatch a
  `paste` event and set the value afterwards.
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
  same time: run with `EOS_TEST_DB=test_eos_sig_checker` (read by the dev
  `local.py`) to get a database of our own.
- The form field keeps `strip=False`: the trailing tabs of an unscanned line
  are columns.
- Through the WSL bridge (`bash -lc '...'`) `%` formats and nested quotes
  break the quoting: put longer commands into a script file and run it by
  path.

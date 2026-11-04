# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.4`, 2026-11-04 (see `CHANGELOG.md` under 0.0.4). Pushed to
  `origin/main` with the annotated tags `v0.0.1` to `v0.0.4` ("Release
  <version>" on the release commit).
- New in 0.0.4: no behaviour change, less code - trackable characters in
  one query, one shared permission check (`views.has_access`) for the menu
  and the index, `parser._check` returns `Invalid` itself (`_invalid`
  replaces `_shorten`).
- What the app does: the paste page (`basic_access`) - two equal panes,
  paste the probe scanner (English client) on the left, the same lines come
  back on the right as a table with site type and name filled in from the
  shared list (green), invalid lines red with the reason, a Copy button.
  Every valid line is stored or merged into `Signature`; a Celery task
  deletes rows past their age. `manage_settings` opens the **Signatures**
  tab (DataTable, a filter each for System, ID, Group, Name; expired rows
  greyed out) and the **Settings** tab (days an entry counts, 1-30; Delete
  all signatures).
- Since 0.0.3: location tracking through ESI (`tracking.py`,
  `provider.py`, `js/tracking.js`). A switch above the panes, off by
  default, and a dropdown of the user's own characters with a token for
  `esi-location.read_location.v1`; per browser tab. Every check stores the
  system (migration 0003: one row per signature ID **and** system, column
  System everywhere); without a paste the right pane shows the system's
  known rows, after a paste the pasted lines plus the rest ("not in this
  paste"). The bar shows the position with its age, refreshed every 10 s;
  problems appear in a message box below it. `django-esi>=10` is a
  dependency now.
- Tests: 85 without the `translations` tag (all pass at 0.0.4), plus the catalogue tests run by
  `tools/translate.py`; every test checked against broken code. No
  automated test for the browser side of `autocheck.js`, `signatures.js`
  and `tracking.js` - all three checked in the browser, tracking against
  real ESI (switch, two tabs with two characters, paste in a system, the
  system's list, the poll, a dead token, an unreachable server).

## Open

- The live instance: remove `EOS_SIG_CHECKER_MAX_AGE_DAYS` from its
  `local.py` if set (the dev `local.py` never had it), install `@v0.0.4`,
  run migrate (0002 and 0003) and `collectstatic`, restart AA and Celery,
  then give `manage_settings` to whoever looks after the list. Members who
  want tracking need a token with `esi-location.read_location.v1` from
  another app (corptools asks for it).
- README's install line still names `@v0.0.1`: point it at the current tag
  with the next change (the release commit takes only version, CHANGELOG
  and HANDOVER). Left out of 0.0.4 at the user's choice.
- Considered in the 0.0.4 cleanup and left as is: `output or []` twice in
  `views.index` (tests assert `output is None` without a paste), the
  standalone `testauth/` + `runtests.py` + `tox.ini` (tox/coverage path),
  the two `signal_band` properties (a template filter would be more code).
- Not checked yet: a real Ctrl+V from the EVE client, the light theme, an
  expired row on the Signatures tab outside the unit tests (no row in
  `aa_dev` was old enough), the Refresh button by a real click (the pane
  did not draw after a POST), a system change while tracking (the
  character did not move during the test).
- Next sensible step: deploy to the live instance (README's install
  section).

## Decisions

- Solar system only with tracking (user's choice after 0.0.2): key is
  (signature ID, system); `NO_SYSTEM` = 0 for untracked pastes (MySQL lets
  NULLs past a unique constraint). A tracked paste adopts the ID's row
  without system. An untracked paste resolves by ID alone, as before, from
  the newest live row of the same site in any system and leaves its system
  alone; another site under that ID gets a row without system. Rows count
  for the days on the settings page (1-30, beyond a month reused IDs get
  likely).
- Tracking: off by default, per browser tab (`?character=` in the URL, the
  paste form posts to the same URL; sessionStorage restores it when the
  menu link drops the parameter, a new tab starts off). Only existing
  tokens with `esi-location.read_location.v1` - the app has no SSO button
  of its own. The server looks the system up itself and checks ownership
  before its 5 s location cache.
- Tracking display: no paste = the system's live rows; after a paste = the
  pasted lines plus the system's other live rows ("not in this paste"),
  Copy includes both. Poll every 10 s (`views.LOCATION_INTERVAL_SECONDS`),
  Refresh at most every 5 s (`tracking.LOCATION_CACHE_SECONDS`); a new
  system reloads the page as a GET.
- A newer paste with another group/type/name for the same ID wins and
  restarts `first_seen`. Blank columns of a weaker scan never overwrite.
- Scan strength stored is the best seen; distance is the last pasted.
- English client only. A line with a valid ID but another group (ships,
  drones, structures, other client languages) is skipped: not stored, not
  listed, only counted under the result.
- Headers follow the in-game window: Kind = Cosmic Signature/Anomaly,
  Group = Combat Site/Wormhole/..., Name, Signal. Model fields stay
  `group`/`site_type`. Signal colours like the game: <25 red, <75 orange,
  <100 yellow, 100 green (one function, `parser.signal_band`).
- Paste checks on its own (`autocheck.js`, full form submit). Limit 1 check
  per user and second (`views.MIN_INTERVAL_SECONDS`, a constant): browser
  waits via sessionStorage, server refuses with 429 via `cache.add`.
- The parser follows the clipboard column order (ID, kind, group, name,
  signal, distance), not the window's.
- Two permissions: `basic_access` (paste page, one shared list) and
  `manage_settings` (Signatures and Settings tabs). No separate view
  permission for the list - the user's choice.
- The days live only on the settings page (reversed after 0.0.1 at the
  user's request): no fallback to `local.py`.
- Navigation as navbar tabs like eos-auth-monitor: Sig Checker | Signatures
  | Settings, each only with its permission.
- Tracking problems are shown, never swallowed: a message box below the
  bar (no/dead token, ESI, server unreachable) that clears on the next good
  read, while the last position stays. A character that cannot be tracked
  keeps its message instead of switching tracking off silently.
- Signature list: one filter field per column (System, ID, Group, Name), not one
  search box; expired rows shown greyed out rather than hidden, so the count
  matches Delete all. Distance left out: it is the last paster's distance and
  its client text ("10,63 AU", "1.234 km") does not sort.
- Output of the paste page as a table, not a second textarea; Copy gives the
  text format.
- Languages: de, ru, zh_Hans, like the sister apps.

## Dev instance

- Installed editable (`--no-deps`), `'eos_sig_checker',` in
  `INSTALLED_APPS`, cleanup task in `CELERYBEAT_SCHEDULE` (11:15 daily),
  migrations 0001-0003 applied, static collected (incl. `tracking.js`).
  Max age stored: 7. The Celery worker was restarted after the 0.0.2
  release (runs since 19:59), so the cleanup task reads the days from the
  database.
- `Signature` holds 37 rows from the user's sample pastes plus two browser
  test rows `ZZT-901`/`ZZT-902` in R-ARKN: this app's own, they expire on
  their own. Delete all was never pressed against them.
- Tokens with the location scope: account `E_o` - BigBlackout C and E 'o
  work, Eh 'o's refresh token is dead (SSO `invalid_grant`).
- `discord_announcer.0008_transaction_kind` is pending in `aa_dev` - not
  ours, left alone.
- The dev server answers on `http://127.0.0.1:8000`; `localhost:8000` is
  refused by `ALLOWED_HOSTS` (DisallowedHost).
- Migration 0001 depends on `eveonline 0001_initial` on purpose (edited after
  makemigrations): the newest eveonline migration would force the newest AA.

## Traps

- `str.strip()` removes `\x1c`-`\x1f` as whitespace: a control character
  at a column's end passes every pattern. `parser.parse` rejects control
  characters before splitting.
- `sri_static` hashes from the collected static files: a new JS/CSS file
  breaks every view test until `collectstatic` ran. Test for the hashed
  name (`signatures.`), not `signatures.js`.
- A model validator puts no `min`/`max` on the form widget, and a
  `PositiveSmallIntegerField` writes its own `min="0"` over one set in
  `Meta.widgets`: set the attributes in the form's `__init__`.
- In Claude's browser pane a simulated Ctrl+V inserts nothing: dispatch a
  `paste` event and set the value afterwards. When the pane does not draw,
  clicks by coordinate fail - `form_input` and refs or JS still work.
- "Position" clashes with Alliance Auth's Russian catalogue: it carries the
  `eos-sig-checker` context, like Name and Type.
- `.git/CLAUDE_COMMIT_MSG` survives from the last commit: Read it before
  writing the new message, or the Write is refused and the commit takes the
  old text (happened once, amended before the push).
- View tests that post twice need `cache.clear()` in between, or the rate
  limit answers the second post with 429.
- Saving a `Token` in a test runs AA's ownership signal: the character moves
  to the token's user. To test a token whose character belongs to somebody
  else, move the `CharacterOwnership` back after creating the token.
- `Token.objects.require_scopes` does not exist on the manager, only on the
  queryset: `Token.objects.filter(...).require_scopes(...)`.
- Tests mock `tracking.esi` (or `tracking.locate`): the real
  `ESIClientProvider` loads the OpenAPI spec from ESI on first use.
- Another session may use the shared test database `test_aa_dev` at the
  same time: random "Table 'test_aa_dev.eve_sde_...' doesn't exist" errors,
  even with `--fresh`. Run with `EOS_TEST_DB=test_eos_sig_checker`
  (read by the dev `local.py`) to get a database of our own.
- The dev server's autoreload takes a few seconds after a file change; a
  request in that window fails with "Failed to fetch" - not an app error.
- The form field keeps `strip=False`: the trailing tabs of an unscanned line
  are columns.
- Through the WSL bridge (`bash -lc '...'`) pipes, `|` in regexes and `%`
  formats break the quoting: run git commands on their own, longer ones as a
  script file.

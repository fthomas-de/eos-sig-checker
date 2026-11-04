# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.1`, 2026-11-04, the first release (see `CHANGELOG.md`
  under 0.0.1). Pushed to `origin/main`.
- What the app does today: one page with two equal panes. Left: paste the
  probe scanner (English client). Right: the same lines as a table, site
  type and name filled in from the shared list (green), invalid lines red
  with the reason, a Copy button for the completed list. Every valid line is
  stored or merged into `Signature`; a Celery task deletes rows past the
  age set on the settings page (default 7).
- Unreleased (not committed yet): a settings page (tab "Settings", permission
  `manage_settings`) with the days an entry counts (1-30, singleton
  `SigCheckerConfiguration`, migration 0002) and a "Delete all signatures"
  button behind a Bootstrap modal. `EOS_SIG_CHECKER_MAX_AGE_DAYS` is no
  longer read. A "Signatures" tab (also `manage_settings`): every row as a
  DataTable (AA's DataTables 2 bundle, `js/signatures.js`), sortable, one
  filter field each for ID, Group (= `site_type`) and Name via DataTables'
  column search, expired rows greyed out (`opacity-50`) with an "expired"
  badge. Distance is left out on purpose: it is the last paster's distance
  and its client text ("10,63 AU", "1.234 km") does not sort.
- Tests: 60 without the `translations` tag, 2 with it. Each new test was
  checked against broken code (reused ID, resolved flags, expiry, control
  characters, name check, line limit, permission, skipping, signal bands,
  skip count, rate limit, per-user key, refused paste not counted; for the
  settings page: age from the page in task/merge/subtitle, bounds 1 and 30,
  permission on page and delete, POST only, delete everything, characters
  untouched, menu with either permission, Settings tab only for managers,
  settings-only user sent from the index to the settings, min/max
  attributes for the browser; for the signature list: permission, every
  row incl. expired, last checked first, expired mark on row and badge,
  numeric signal sort and colour, filter columns 0/2/3, script included,
  tab only for managers). The filter and sort behaviour of `signatures.js`
  has no automated test - checked in the browser.
  `autocheck.js` itself has no automated test.

## Open

- Catalogues de/ru/zh_Hans are complete and compiled; the `.mo` files are
  tracked (GitHub's `*.mo` ignore entry was removed on purpose).
- `.gitignore` lists `*.pot` twice (GitHub's block and the eos block):
  harmless, drop one at the next change.
- The subtitle under the page title is a small grey line; the user checked
  it and keeps it that way.
- Next sensible steps: a real Ctrl+V from the EVE client, a look at the
  light theme, then deploy to the live instance (README's install section).
- Checked in the browser on 2026-11-04 (1440 px wide, dark theme): equal
  panes, auto-check on paste, resolving, red invalid line, skip count,
  signal colours, server limit 200/429/200 against the real Redis. Not
  checked: a real Ctrl+V from the EVE client, the light theme.
- Settings page checked in the browser on 2026-11-04 (1440 px, dark):
  tabs (active tab right), save 5 -> "Settings saved." -> index subtitle
  "5 days", browser refuses 31 (min/max attributes), delete modal opens
  with "Delete all 37 signatures ...?" and posts to delete-all with CSRF;
  cancelled, nothing deleted. The days were set back to 7. The delete
  itself ran only in unit tests, never against `aa_dev`'s rows.
- Signatures tab checked in the browser on 2026-11-04 (1440 px, dark):
  37 rows, tab order Sig Checker | Signatures | Settings, Group "combat" +
  Name "haven" -> 6 of 37, ID "udn" -> UDN-422, Signal sorts numerically
  both ways (4.0 % first), no global search box. No row in `aa_dev` was
  expired yet, so the grey marking was only seen in the unit tests.
- The Celery worker on the dev instance (VS Code terminal) still runs the
  code from before the settings page: restart it there so the cleanup task
  reads the days from the database (until then it reads 7 from the old code,
  the same value as the stored one).
- `EOS_SIG_CHECKER_MAX_AGE_DAYS` was never set in the dev `local.py`;
  nothing to remove there. The live instance needs the line removed if set.
- The browser test left rows in `aa_dev`'s `Signature` table (the user's
  sample plus `ACJ-672` as Data Site, `XYZ`-lines were skipped). They are
  this app's own rows and expire after 7 days.
- `discord_announcer.0008_transaction_kind` is pending in `aa_dev` - not
  ours, left alone.

## Decisions

- No solar system: the list is global, key is the signature ID. Rows expire
  after 7 days (settings page, 1-30), which keeps reused IDs rare.
- A newer paste with another group/type/name for the same ID wins and
  restarts `first_seen`. Blank columns of a weaker scan never overwrite.
- Scan strength stored is the best seen; distance is the last pasted.
- English client only. A line with a valid ID but another group (ships,
  drones, structures, other client languages) is skipped: not stored, not
  listed, only counted under the result (the count was my addition, so a
  German paste does not vanish without a word).
- Headers follow the in-game window (dev blog 2017, "The future of probe and
  directional scanning UI"): Kind = Cosmic Signature/Anomaly, Group = Combat
  Site/Wormhole/..., Name, Signal. Model fields stay `group`/`site_type`.
- Signal colours like the game: <25 red, <75 orange, <100 yellow, 100 green.
- Paste checks on its own (`autocheck.js`, full form submit, no AJAX). Limit
  1 check per user and second (`views.MIN_INTERVAL_SECONDS`, a constant, not
  a setting): browser waits via sessionStorage, server refuses with 429 via
  an atomic `cache.add`. Only a stored check counts; a refused paste does
  not block the next.
- The window's column order (Distance, ID, Name, Group, Signal) is not the
  clipboard order; the parser follows the clipboard (ID, kind, group, name,
  signal, distance), confirmed by the user's own paste only.
- Two permissions: `basic_access` (everybody with it shares one list) and
  `manage_settings` (settings page and delete-all). `manage_settings` works
  on its own, without `basic_access`; the index sends such a user on to the
  settings, so the one menu entry serves both.
- Output as a table, not a second textarea; Copy gives the text format.
- Stored per row: last checker (main), scan %, distance, first seen, last
  checked.
- Age on a settings page, not in `local.py` (reversed after 0.0.1 at the
  user's request): the page replaces the setting entirely, no fallback to
  `local.py`. Range 1-30 days (beyond a month reused IDs get likely), start
  value 7. Navigation as navbar tabs like eos-auth-monitor. Delete-all sits
  on the same page behind a Bootstrap modal (no JS file of our own).
- Signature list (user's choices): behind `manage_settings`, no permission
  of its own; one filter field per column (ID, Group, Name), not one search
  box; expired rows shown greyed out rather than hidden, so the count matches
  Delete all.
- Languages: de, ru, zh_Hans, like the sister apps.

## Dev instance

- Installed editable (`--no-deps`), `'eos_sig_checker',` in
  `INSTALLED_APPS`, cleanup task in `CELERYBEAT_SCHEDULE` (11:15 daily),
  migrations 0001 and 0002 applied, static collected. The Celery worker was not
  restarted since: it picks the cleanup task up at its next start.
- Migration 0001 depends on `eveonline 0001_initial` on purpose (edited after
  makemigrations): the newest eveonline migration would force the newest AA.

## Traps

- `str.strip()` removes `\x1c`-`\x1f` as whitespace: a control character
  at a column's end passes every pattern. `parser.parse` rejects control
  characters before splitting; the parser test covers `\x1f`.
- `sri_static` hashes from the collected static files: a new JS/CSS file
  breaks every view test until `collectstatic` ran. Test for the hashed
  name (`autocheck.`), not `autocheck.js`.
- In Claude's browser pane a simulated Ctrl+V inserts nothing: test the
  paste by dispatching a `paste` event and setting the value afterwards,
  the order a real paste has.
- Seven columns do not fit half a screen in one line: Kind, Group, Name and
  the checker's name wrap; ID, Signal, Distance and the date do not.
- View tests that post twice need `cache.clear()` in between, or the rate
  limit answers the second post with 429.
- The form field keeps `strip=False`: the trailing tabs of an unscanned line
  are columns.
- Through the WSL bridge (`bash -lc '...'`) pipes, `|` in regexes and `%`
  formats break the quoting, and a chained `git commit` once failed without
  a word: run git commands on their own, longer ones as a script file.

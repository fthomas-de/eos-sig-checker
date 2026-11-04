# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.2`, 2026-11-04 (see `CHANGELOG.md` under 0.0.2). Pushed to
  `origin/main` with the annotated tags `v0.0.1` and `v0.0.2` ("Release
  <version>" on the release commit, as in eos-auth-monitor).
- What the app does: the paste page (`basic_access`) - two equal panes,
  paste the probe scanner (English client) on the left, the same lines come
  back on the right as a table with site type and name filled in from the
  shared list (green), invalid lines red with the reason, a Copy button.
  Every valid line is stored or merged into `Signature`; a Celery task
  deletes rows past their age.
- New in 0.0.2, both behind `manage_settings` (works without
  `basic_access`; the index sends such a user on to the settings):
  - **Settings** tab: the days an entry counts (1-30, start 7, singleton
    `SigCheckerConfiguration`, migration 0002), read at call time by the
    merge, the cleanup task and the page subtitle; **Delete all
    signatures** behind a Bootstrap modal. `EOS_SIG_CHECKER_MAX_AGE_DAYS`
    is no longer read.
  - **Signatures** tab: every row as a DataTable (AA's DataTables 2 bundle,
    `js/signatures.js`), sortable, a filter field each for ID, Group
    (= `site_type`) and Name via DataTables' column search; expired rows
    greyed out (`opacity-50`) with an "expired" badge.
- Tests: 60 without the `translations` tag, 2 with it, each checked against
  broken code. No automated test for the browser side of `autocheck.js`
  and `signatures.js` (filters, sorting) - both checked in the browser.

## Open

- The Celery worker of the dev instance runs in the user's VS Code terminal
  and still has the 0.0.1 code: restart it there so the cleanup task reads
  the days from the database. Until then it uses 7 - the stored value too.
- The live instance: remove `EOS_SIG_CHECKER_MAX_AGE_DAYS` from its
  `local.py` if set (the dev `local.py` never had it), run migrate 0002 and
  `collectstatic`, then give `manage_settings` to whoever looks after the
  list.
- Not checked yet: a real Ctrl+V from the EVE client, the light theme, an
  expired row on the Signatures tab outside the unit tests (no row in
  `aa_dev` was old enough).
- `.gitignore` lists `*.pot` twice (GitHub's block and the eos block):
  harmless, drop one at the next change.
- Next sensible step: deploy to the live instance (README's install
  section).

## Decisions

- No solar system: the list is global, key is the signature ID. Rows count
  for the days on the settings page (1-30, beyond a month reused IDs get
  likely), which keeps reused IDs rare.
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
- Signature list: one filter field per column (ID, Group, Name), not one
  search box; expired rows shown greyed out rather than hidden, so the count
  matches Delete all. Distance left out: it is the last paster's distance and
  its client text ("10,63 AU", "1.234 km") does not sort.
- Output of the paste page as a table, not a second textarea; Copy gives the
  text format.
- Languages: de, ru, zh_Hans, like the sister apps.

## Dev instance

- Installed editable (`--no-deps`), `'eos_sig_checker',` in
  `INSTALLED_APPS`, cleanup task in `CELERYBEAT_SCHEDULE` (11:15 daily),
  migrations 0001 and 0002 applied, static collected (incl.
  `signatures.js`). Max age stored: 7.
- `Signature` holds 37 rows from the user's sample pastes: this app's own,
  they expire on their own. Delete all was never pressed against them.
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
- `/push` sets no tag, but the README installs `@v<version>`: tag every
  release commit (`git tag -a v<version> -m "Release <version>"`) and push
  the tag along, or the install line fails (0.0.1 went out untagged; both
  tags were set at 0.0.2).
- `.git/CLAUDE_COMMIT_MSG` survives from the last commit: Read it before
  writing the new message, or the Write is refused and the commit takes the
  old text (happened once, amended before the push).
- View tests that post twice need `cache.clear()` in between, or the rate
  limit answers the second post with 429.
- The form field keeps `strip=False`: the trailing tabs of an unscanned line
  are columns.
- Through the WSL bridge (`bash -lc '...'`) pipes, `|` in regexes and `%`
  formats break the quoting: run git commands on their own, longer ones as a
  script file.

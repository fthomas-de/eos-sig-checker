# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.1`, 2026-11-04, nothing committed yet beyond GitHub's
  initial commit.
- What the app does today: one page with two equal panes. Left: paste the
  probe scanner (English client). Right: the same lines as a table, site
  type and name filled in from the shared list (green), invalid lines red
  with the reason, a Copy button for the completed list. Every valid line is
  stored or merged into `Signature`; a Celery task deletes rows past
  `EOS_SIG_CHECKER_MAX_AGE_DAYS` (7).
- Tests: 38 without the `translations` tag, 2 with it. Each new test was
  checked against broken code (reused ID, resolved flags, expiry, control
  characters, name check, line limit, permission, skipping, signal bands,
  skip count, rate limit, per-user key, refused paste not counted).
  `autocheck.js` itself has no automated test.

## Open

- Catalogues de/ru/zh_Hans do not exist yet: `tools/translate.py` creates
  them at the first `/commit`. The glossary already holds every message.
- Checked in the browser on 2026-11-04 (1440 px wide, dark theme): equal
  panes, auto-check on paste, resolving, red invalid line, skip count,
  signal colours, server limit 200/429/200 against the real Redis. Not
  checked: a real Ctrl+V from the EVE client, the light theme.
- The browser test left rows in `aa_dev`'s `Signature` table (the user's
  sample plus `ACJ-672` as Data Site, `XYZ`-lines were skipped). They are
  this app's own rows and expire after 7 days.
- `discord_announcer.0008_transaction_kind` is pending in `aa_dev` - not
  ours, left alone.

## Decisions

- No solar system: the list is global, key is the signature ID. Rows expire
  after 7 days (setting), which keeps reused IDs rare.
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
- One permission `basic_access`; everybody with it shares one list.
- Output as a table, not a second textarea; Copy gives the text format.
- Stored per row: last checker (main), scan %, distance, first seen, last
  checked.
- Age as a setting in `local.py`, not a settings page (one permission, no
  admin page needed).
- Languages: de, ru, zh_Hans, like the sister apps.

## Dev instance

- Installed editable (`--no-deps`), `'eos_sig_checker',` in
  `INSTALLED_APPS`, cleanup task in `CELERYBEAT_SCHEDULE` (11:15 daily),
  migration 0001 applied, static collected.
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

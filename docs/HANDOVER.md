# Handover

Where the work on `eos-sig-checker` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

## State

- Version: `0.0.10`, 2026-11-20 (see `CHANGELOG.md` under 0.0.10), pushed
  to `origin/main` with the annotated tags `v0.0.1` to `v0.0.10`
  ("Release <version>" on the release commit). Migrations 0007 to 0010;
  catalogues de, ru, zh_Hans complete.
- What 0.0.10 does:
  - Only Cosmic Signatures are read; anomalies are skipped like ships. The
    anomaly switch (`anomalies.js`) and the Kind column are gone. Rows
    stored before expire on their own.
  - Tab **Errors** (`manage_settings`, `RejectedLine`): refused lines and
    words of another client without a single English meaning, reason in
    English; setting **Keep rejected lines (days)** (default 7), removed
    by the existing daily task `delete_expired_signatures`.
  - Card **Systems (N h)** below the WH card: the systems with a row checked
    within **Show systems (hours)** (default 3), names only. WH 2/3, Systems
    1/3 of the column; on a wide screen the stack lies absolute over its
    column (`.eos-sig-checker-stack` in `sig-checker.css`).
  - **Client texts** (`client_text.py`, `ClientText`,
    `ClientTextLanguage`): the EVE client's texts per language from the
    [EVE localisation archive](https://github.com/Kelly-Hsueh/EVE-localisation-json-archive)
    (`latest/tq/<lang>.json`, state in `state/tq-build.txt` and
    `state/tq-hashes.json`). `update()` fetches only languages whose hash
    changed, one at a time, at most 300 MB, under a cache lock. Task
    `update_client_texts` (own `CELERYBEAT_SCHEDULE` entry, README),
    command `eos_sig_checker_update_client_texts [--force]`. The settings
    page has a card that asks the archive on every view (3 s/5 s timeout)
    and an **Update now** button that starts the task.
  - **Pastes of other clients**: `parser.parse(text, client_text.lookup)`
    puts their words into English. First word → language, must mean one of
    `KINDS`; site type only among `SITE_TYPES`; name only with exactly one
    English meaning, else blank + Errors. Signal may have a space before
    `%`; the distance is any number with a unit.
  - **Page in the reader's language**: result, Signatures tab and Copy show
    site type and name through `client_text.display` (template filter
    `client_text`), from Alliance Auth's language code (`fr-fr` → `fr`).
    The list stays English.
- Tests: 170 without the `translations` tag, all pass. Real lines of de,
  fr, es, ru, ko, ja, zh are test lines (`tests.base.FOREIGN`), all
  unscanned.
- Client texts in `aa_dev`: build 3720952, every language; about 110,000
  to 122,000 pairs each, it only 3,169. A full fetch takes about 2.5 min
  and peaks at about 700 MB.

## Open

- **No scanned paste of another client yet.** Type and name translation is
  built from the client texts, not checked against what a client really
  writes. The first real scanned paste (any language) shows it; a
  mismatch lands on the Errors tab.
- **No Celery worker runs in the dev instance**: the cleanup is overdue
  (statistics line red), and neither **Update now** nor the daily tasks
  ran through a real worker - the update ran through the command only.
- Not seen in the browser: the settings card with "update available" or
  an unreachable archive, the light theme, a narrow screen with the
  Systems card, the Systems card with entries, a long Errors tab.
- The live instance (from 0.0.9 on): remove `EOS_SIG_CHECKER_MAX_AGE_DAYS`
  from `local.py` if set, install the new tag, migrate (0002 to 0010),
  `collectstatic`, add **both** `CELERYBEAT_SCHEDULE` entries, run
  `eos_sig_checker_update_client_texts` once, restart AA and Celery. The
  worker needs about 700 MB free for a moment per language. Then
  `basic_access` to member states only, `manage_settings` to whoever looks
  after the list.
- README's install line still names `@v0.0.1`.
- `sync.statistics` scans the table on every page view (`shortcut:` in the
  code): cache it past about 100,000 rows.
- Next sensible step: deploy 0.0.10 to the live instance (steps above,
  `pip install ...@v0.0.10`), then a real scanned paste from a
  non-English client and a look at the Errors tab.

## Decisions (2026-11-20)

- Cosmic Anomalies out entirely, the switch gone; stored anomaly rows
  expire on their own. Kind column dropped.
- Errors tab: refused signature lines and untranslatable words of another
  client, kept by a setting (default 7 days), plus Delete all.
- Systems card: names only, hours of its own setting in the title, below
  the WH card, 2:1.
- Client texts from the archive, not shipped in the package (about 340 MB
  for four languages, ru over GitHub's 100 MB file limit): fetched by the
  server, daily task plus button, the settings page checks on open.
  Licence: the user cleared it.
- Every language the archive has; nothing guessed or translated by hand.
- Backend English only; input from any client language is put into
  English, the page shows the reader's AA language.
- Ambiguity is resolved per direction at lookup time, never at import:
  the scanner's columns decide (singular/plural in ja, ko, zh); a name
  with two meanings stays blank and goes on Errors. Untranslated texts
  are kept as English = English (a Russian client shows "Unsecured
  Frontier Server Bank" in English); the page prefers a real translation.
- Pastes without tracking resolve like weak scans (newest live row of the
  ID and type, any system); with tracking only the same system counts.
- Distance stays as it was (stored, in Copy, not shown); only its check is
  loose. Copy is in the reader's language.

Older decisions (0.0.5 to 0.0.9): see the CHANGELOG and the git history of
this file.

## Dev instance

- Installed editable (`--no-deps`), `'eos_sig_checker',` in
  `INSTALLED_APPS`, cleanup task in `CELERYBEAT_SCHEDULE` (11:15 daily);
  the `update_client_texts` entry is **not** in its `local.py`.
  Migrations 0001-0010 applied, static collected after the Systems card.
- The WSL distro restarted once on 2026-11-20 (Redis down for a moment);
  the dev server runs through the preview config `aa-dev` in
  `C:\Users\flt\Claude\.claude\launch.json`, `http://127.0.0.1:8000`.
- Browser test rows of this app, they expire on their own: `ZZT-931`,
  `ZZT-941` to `ZZT-943`, `REB-508`, `LKF-627`, `HTJ-764`, `VGX-244`, the
  older `ZZT-9xx`; two Errors entries (`ZZT-933`, `ZZT-941`).
- Browser checks log in as account `E_o` (superuser). The page language
  follows the `django_language` cookie; set it in the browser for a check
  and back to `en` - Alliance Auth writes the profile only through
  `/i18n/setlang/`.
- `discord_announcer.0008_transaction_kind` is pending in `aa_dev` - not
  ours, left alone.
- The app's URL is `/eos_sig_checker/` (underscores).

## Traps

- Claude's Bash tool (Git Bash) turns `/home/...` arguments of `wsl.exe`
  into `C:/Program Files/Git/home/...`: run `wsl.exe ... bash -l <script>`
  from the PowerShell tool.
- Through the WSL bridge (`bash -lc '...'`) quotes and `$(...)` break: put
  commands into a script file and run it by path.
- A patch script whose new text contains its own anchor is not
  idempotent: rerun after a failure, it inserts the block twice (happened
  in step 8). Rerun only the part that failed, or check for duplicates.
- The Write tool turns `\u00a0` in the content into the real character:
  `parser.SIGNAL` and `DISTANCE` keep visible escapes, keep them so.
- MySQL's collation matches without case and accents: `client_text.lookup`
  and `display` compare exactly in Python after the query.
- `makemigrations` with a foreign key to `EveCharacter` depends on the
  newest eveonline migration: set it to `0001_initial` (0001, 0007), or
  the newest Alliance Auth is forced.
- AA's `get_extension_logger` prefixes the name: `assertLogs(tasks.logger)`.
- In dev the CSS has no hash in its URL: the browser keeps the old file
  until a reload with `fetch(..., {cache: "reload"})`.
- A changed permission text needs a migration, but Django does not rename
  the existing `auth_permission` row.
- `str.strip()` removes `\x1c`-`\x1f` as whitespace: `parser.parse` rejects
  control characters before splitting.
- `models.py` imports `parser.MAX_LINES`: the parser must never import from
  `models` (it gets `client_text.lookup` handed in instead).
- The settings form has six required fields: a test that posts to the
  settings page sends `{**VALID, ...}` (`tests/test_settings.py`).
- A test that wants a failed location read again must delete the cached
  failure first (`eos_sig_checker:location:<id>`).
- `sri_static` hashes from the collected static files: a new JS/CSS file
  breaks every view test until `collectstatic` ran.
- A model validator puts no `min`/`max` on the form widget: set them in the
  form's `__init__`.
- In Claude's browser pane a simulated Ctrl+V inserts nothing: set the
  textarea's value by script and call `form.requestSubmit()`.
- `.git/CLAUDE_COMMIT_MSG` can survive from an earlier commit: Read it
  before writing the new message.
- View tests that post twice need `cache.clear()` in between (rate limit).
- Saving a `Token` in a test runs AA's ownership signal.
- `Token.objects.require_scopes` does not exist on the manager, only on the
  queryset.
- Run tests with `EOS_TEST_DB=<own name>` so another session's run does not
  share `test_aa_dev`.
- The form field keeps `strip=False`: the trailing tabs of an unscanned
  line are columns.
- Short column words clash with Alliance Auth's catalogues ("Reason" in
  zh_Hans at 0.0.10): `tools/translate.py` names them; give the word the
  `eos-sig-checker` context.
- `tools/translate.py` stops on a glossary entry the code no longer uses:
  delete it from `tools/glossary.py`.

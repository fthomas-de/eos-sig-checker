# Working on eos-sig-checker

Alliance Auth (5.x) app: members paste the cosmic signatures from their probe
scanner and the app shows which type each one is. `README.md` says what the
app does; this file says how to work on it; `docs/HANDOVER.md` says where the
work currently stands, which decisions the user made and what is open. Read
both before changing anything.

## Where things are

| | |
|---|---|
| This app | `eos_sig_checker/` in this repo |
| Tests | `eos_sig_checker/tests/` |
| Translations | `eos_sig_checker/locale/` (from the first commit with translations), glossary `tools/glossary.py` |
| AA instance, Python, database | see `## AA environment` (machine-specific, usually in `~/.claude/CLAUDE.md`) |
| Reference app for conventions | `eos-spy-network` and `eos-auth-monitor` (sister repos) |
| Review checklist every release has to pass | https://github.com/fthomas-de/aa-app-checklist |

Everything runs from the Alliance Auth instance, not from the app directory.

## Commands

A bare `python` below means the Python from `## AA environment`.

```bash
aa-test eos_sig_checker --exclude-tag translations   # whole suite, quiet
aa-test eos_sig_checker.tests.<module>                # one module
aa-test eos_sig_checker --fresh                       # rebuild the test database first
python manage.py makemigrations eos_sig_checker
python manage.py collectstatic --noinput
```

`aa-test` wraps `manage.py test` and drops the DEBUG/INFO lines Alliance
Auth's console logging adds, nothing else - a real traceback, `WARNING` or
`ERROR` still comes through. It keeps the test database (`--keepdb`);
`--fresh` rebuilds it, and the suite at `/commit` always runs fresh. No
`--parallel`: with `--keepdb` it saves little, does not migrate its clone
databases and hangs on a failing subtest.

## Release

Read by the skills `/commit` and `/push`; the same shape in every app.
Commands run from the AA instance. Translation tests carry
`@tag("translations")`: between commits the catalogues describe the last
commit, so the suite leaves them out.

- App: `eos_sig_checker`
- Version file: `eos_sig_checker/__init__.py`
- Changelog section: `[Unreleased]`
- Tests while working: `aa-test eos_sig_checker.tests.<module>`
- Suite without translation tests: `aa-test eos_sig_checker --fresh --exclude-tag translations`
- Checks: `python manage.py makemigrations eos_sig_checker --check --dry-run`
- Translations: new messages into `tools/glossary.py`, then
  `python tools/translate.py` from the repo root
- Translation tests: run by `tools/translate.py` (`--tag translations`)

## The dev database

`aa_dev` holds ESI-pulled corptools data that cannot be fetched again. There
is no binary log and there are no dumps.

- Never delete with a range filter on a model other apps hang off - a
  cascade on `EveCorporationInfo` takes corptools' wallet journal with it.
- Address rows by explicit id lists, and write the previous values out first.
- Foreign apps (Alliance Auth, corptools, ...): read their models, never
  change their schema or their rows beyond what a seed of our own created.
- Migrations of this app may be applied to `aa_dev` without asking, and the
  dev instance's Celery worker may be restarted likewise. Read a migration
  before applying it: one that touches a foreign app's tables or deletes
  rows still needs the user's yes.

## Code

- `parser.py` reads the paste and is the security boundary: every column is
  checked by shape (ID, group from a fixed list, site type and name by
  allowed characters, percentage, distance) and a line that does not fit is
  reported, never stored. Loosen a pattern only with a test for the real
  client text that needed it. The form caps lines and characters. A line
  with a valid ID but no Cosmic Signature/Anomaly is `Skipped` (ships,
  structures, other client languages): dropped, only counted on the page.
- The page uses the probe scanner's column words: Kind = the model's
  `group`, Group = the model's `site_type`. Keep the two apart when adding
  text.
- `sync.py` merges into the list: one row per signature ID; a different
  group/type/name replaces the row (reused ID), blank columns resolve from
  it. A row past the age from the settings page counts as gone even before
  the cleanup task deletes it.
- The age lives in the singleton `SigCheckerConfiguration` (settings page,
  `manage_settings`) and is read at call time (`app_settings.max_age_days()`),
  so the merge, the task and the page follow a change without a restart.
- Every foreign app is optional: guard it with `apps.is_installed(...)` and
  import its models inside that guard. Never add one to the dependencies.
- Model defaults and choices never come straight from settings; use a
  module-level callable, or every other installation needs `makemigrations`.
- Nothing is created behind the admin's back: no groups, states, permission
  assignments or periodic tasks in code or migrations. A periodic task goes
  into the README as a `CELERYBEAT_SCHEDULE` block for `local.py`.
- Keep the README true: the checklist compares every claim with the code.

Comments say **why**, not what. A comment that restates the line is noise; a
comment that names the fault the line prevents keeps it from coming back.

English everywhere in the code, including comments and docstrings.

Templates use the Alliance Auth standard style unchanged: its Bootstrap 5
classes, its bundles, `{% load sri %}` with `{% sri_static %}` for our own
scripts. No custom theme. Prefer an Alliance Auth or corptools pattern over
inventing one.

JavaScript and CSS live in `eos_sig_checker/static/eos_sig_checker/`, never
inline in a template - `sri_static` cannot hash inline code, and
`collectstatic` has to see the file. Run `collectstatic` after every change
to them.

## Tests

- Derive every test class that touches the database from
  `tests.base.SigTestCase` and call `super().setUp()`: it puts the default
  cache in memory, emptied per test, instead of the dev instance's Redis.
- Test users come from `tests.base.make_user`: it gives them a main and its
  ownership, which Alliance Auth's `main_character_required` needs.
- `tests.base` holds real probe scanner lines (`SCANNED`, `UNSCANNED`,
  `DATA_SITE`); build new cases from client text, not from guesses.

Every change gets a test, and every new test gets checked against the broken
version: put the fault back, run the test, confirm it fails, restore the
file. A test that passes against the broken code tests nothing. Compare the
test count after every test change; an indentation slip drops a whole module
silently.

Test users get no password, and tests log in with `force_login`. Django
hashes a password with PBKDF2 at about 0.2 seconds a user.

## Translations

Three catalogues: `de`, `ru`, `zh_Hans` (plural forms 2, 3, 1),
machine-generated and marked so in the `.po` header. They are only touched
**at a commit**; between commits all texts are English.

- `tools/translate.py` runs makemessages, fills the catalogues from the
  glossary, checks them, compiles them and runs the catalogue tests. A
  message missing from the glossary stops it with a list. It needs `polib`
  in the venv. The `.mo` files are committed.
- The glossary `tools/glossary.py` is the source of truth. Add every new message there, never in
  a `.po` file: the next run overwrites a hand edit.
- EVE jargon stays English in every language: Corporation, Alliance,
  Character, Main, Wormhole, and the signature groups (Combat Site, Relic
  Site, Data Site, Gas Site, Ore Site). Alliance Auth translates some short
  words itself and wins a msgid clash, so those carry a context: `EVE jargon`
  for the jargon words, `eos-sig-checker` for ordinary words AA translates
  differently (Name, Type, Status, Save, Yes, No).
- Every new message must be a plain string in the source: xgettext does not
  look inside an f-string.
- A `#, fuzzy` entry is not compiled by msgfmt, and gettext's guess is
  usually wrong.
- After `compilemessages`, check that the `.mo` files are newer than their
  `.po` - a command chained behind a non-zero exit never runs, silently.
- `makemessages` without `--no-location`: the flag strips every `#:` line
  from all catalogues at once.

## Committing

Commits and pushes only go through the skills `/commit` and `/push`, never
unasked; both read `## Release` above. While working on a feature, run only
the affected test modules - the full suite runs at `/commit`.

`CHANGELOG.md` is written along with every change, unasked, under
`[Unreleased]`. An entry says what was wrong and why the fix is the fix.

## Editing files

Write patch scripts with the Write tool and run them by path - never build
them with shell heredocs: an apostrophe or a backtick gets executed by bash
before Python sees the text. Every patch script asserts its anchor occurs
exactly once before it replaces anything. For a small, unambiguous change the
Edit tool is one step instead of two - use it. `git` runs in WSL only.

## Keeping a session cheap

Every request re-sends the whole conversation, so a long session costs
several times what the same work costs in a fresh one. One session per
topic; start a new one when the subject changes.

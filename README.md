# eos-sig-checker

An [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) app that keeps
one shared list of cosmic signatures for everybody with access.

Copy the results of the probe scanner in EVE (select them, Ctrl+C) and paste
them into the box on the left. Pasting checks on its own (at most once a
second per user; **Check** does the same by hand): every line comes back on the
right, in the same order, with group (Combat Site, Wormhole, ...) and name
filled in wherever somebody has scanned that signature already. The columns
use the probe scanner's own words; filled-in cells are green and the signal
is coloured like in the game (red, orange, yellow, green at 100 %). A
**Copy** button puts the completed list on the clipboard in the probe
scanner's own tab-separated format.

```
ACJ-672	Cosmic Signature			0,0%	10,61 AU
```

comes back as

```
ACJ-672	Cosmic Signature	Data Site	Unsecured Frontier Server	0,0%	10,61 AU
```

if somebody pasted a full scan of `ACJ-672` before.

## How the list is kept

- One entry per signature ID, with group, site type, name, the best scan
  strength seen, the last distance, when it was first seen, and when and by
  whom (their main) it was last checked.
- A paste that shows the same ID with another group, site type or name is a
  new site under a reused ID: it replaces the entry. Empty columns from a
  weaker scan never overwrite what is known.
- The list has no solar system. An entry counts for
  `EOS_SIG_CHECKER_MAX_AGE_DAYS` days (default 7) after its last check;
  after that it is ignored and removed by a periodic task.
- The paste is checked line by line: six tab-separated columns, an ID like
  `ABC-123`, the group `Cosmic Signature` or `Cosmic Anomaly`, site type and
  name in the characters the client uses, a percentage and a distance in AU,
  km or m. A line that does not fit is shown in red with the reason and is
  not stored. At most 500 lines and 50,000 characters per paste.
- Probe results that are no signature (ships, drones, structures) are
  skipped: neither stored nor listed, only counted below the result.
- Only the **English** game client's copy is read; the lines of another
  client language are skipped the same way.

## Installation

1. Install the app into the virtual environment of your Alliance Auth:

   ```bash
   pip install git+https://github.com/fthomas-de/eos-sig-checker.git@v0.0.1
   ```

2. Add `"eos_sig_checker",` to `INSTALLED_APPS` in `local.py`, and the
   periodic cleanup below it:

   ```python
   CELERYBEAT_SCHEDULE["eos_sig_checker_delete_expired_signatures"] = {
       "task": "eos_sig_checker.tasks.delete_expired_signatures",
       "schedule": crontab(minute="15", hour="11"),
   }
   ```

3. Run migrations and collect the static files, then restart Alliance Auth
   and its Celery workers:

   ```bash
   python manage.py migrate eos_sig_checker
   python manage.py collectstatic --noinput
   ```

4. Give the permission below to the groups or states that should use it.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `EOS_SIG_CHECKER_MAX_AGE_DAYS` | `7` | Days an entry counts after its last check. Anything but a whole number from 1 up falls back to 7. |

## Permissions

| Permission | Meant for | What it opens |
|---|---|---|
| `eos_sig_checker.basic_access` | Everybody who scans | The page: paste, store and resolve signatures. Everybody with it shares the same list. |

Admins can look at and edit the list in the Django admin
(*Eos_Sig_Checker › Signatures*).

## Updating

```bash
pip install -U git+https://github.com/fthomas-de/eos-sig-checker.git@<tag>
python manage.py migrate eos_sig_checker
python manage.py collectstatic --noinput
```

Then restart Alliance Auth and its Celery workers.

## Uninstalling

1. Remove the tables:

   ```bash
   python manage.py migrate eos_sig_checker zero
   ```

2. Remove `"eos_sig_checker",` and the `CELERYBEAT_SCHEDULE` entry from
   `local.py`, then uninstall:

   ```bash
   pip uninstall eos-sig-checker
   ```

## Translations

German, Russian and Simplified Chinese, machine-generated. EVE terms and
everything the probe scanner shows stay English.

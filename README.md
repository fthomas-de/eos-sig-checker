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

Every page ends with a line of numbers about the shared list: all
signatures, new and checked in the last 24 hours, systems, scanners, and
entries waiting for the cleanup - red when an entry is past its age by more
than a day, which means the cleanup task does not run.

## Location tracking

Above the two boxes, **Track location** (off by default) follows one of your
own characters through ESI. The dropdown lists the characters of your
account that have a token with the scope `esi-location.read_location.v1`;
the app asks for no token of its own, so add one through any app that
requests the scope (corptools, for instance).

While tracking is on:

- every check stores its signatures with the character's current solar
  system, shown as the **System** column everywhere;
- the right box shows what is known in that system without a paste, and
  after a paste the pasted lines plus the system's other known signatures,
  marked *not in this paste* (a site left out of the scanner selection is
  still there);
- the page asks every 10 seconds where the character is and switches to the
  new system's list on its own; **Refresh** asks at once, at most every 5
  seconds (ESI's own cache time);
- the bar shows the position read last and how old it is. If the location
  cannot be read (no or an expired token, ESI or the server unreachable), a
  message below the bar says why; it disappears once the next read works.
  The server waits longer before every further attempt (see Settings).

The choice belongs to the browser tab: one tab can track one character and
a second tab another. A new tab starts with tracking off.

## How the list is kept

- One entry per signature ID and solar system, with group, site type, name,
  the best scan strength seen, the last distance, when it was first seen,
  and when and by whom (their main) it was last checked.
- A paste that shows the same ID with another group, site type or name is a
  new site under a reused ID: it replaces the entry. Empty columns from a
  weaker scan never overwrite what is known.
- The system is only known with tracking. A tracked paste gives an entry
  pasted without a system its system. A paste without tracking resolves by
  the ID alone, as before, from the newest entry of the same site in any
  system; an entry of another site under that ID stays apart.
- An entry counts for the days set on the settings page (default 7, 1 to
  30) after its last check; after that it is ignored and removed by a
  periodic task.
- The paste is checked line by line: six tab-separated columns, an ID like
  `ABC-123`, the group `Cosmic Signature` or `Cosmic Anomaly`, site type and
  name in the characters the client uses, a percentage and a distance in AU,
  km or m. A line that does not fit is shown in red with the reason and is
  not stored. At most 200 lines (changeable on the settings page, up to
  500) and 50,000 characters per paste.
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

4. Give the permissions below to the groups or states that should use them.

## Settings

The app has no settings in `local.py`. Everything is set on its settings
page (*Sig Checker › Settings*, needs `eos_sig_checker.manage_settings`):

| Setting | Default | Meaning |
|---|---|---|
| Keep signatures (days) | `7` | Days an entry counts after its last check, 1 to 30. The page, the merge and the cleanup task follow a change at once, without a restart. |
| Longest wait after failed location reads (seconds) | `60` | A location that cannot be read (dead token, ESI down) is asked again after 5 seconds, then later with every further failure in a row, in 5 even steps up to this value (with 60: 5, 19, 33, 46, 60 seconds); 5 to 3600. A successful read starts over. |
| Lines per paste | `200` | The most lines one paste may hold, 1 to 500. |

The same page has a **Delete all signatures** button, behind a confirmation:
it empties the shared list for everybody and cannot be undone.

Up to 0.0.1 the days came from `EOS_SIG_CHECKER_MAX_AGE_DAYS` in `local.py`.
That setting is no longer read: set the value on the settings page and
remove the line.

## Permissions

| Permission | Meant for | What it opens |
|---|---|---|
| `eos_sig_checker.basic_access` | Everybody who scans | The page: paste, store and resolve signatures, and track the location of their own characters. Everybody with it shares the same list. |
| `eos_sig_checker.manage_settings` | Whoever looks after the list | The **Signatures** tab: the whole list as a sortable table with a filter each for System, ID, Group and Name; entries past their age are greyed out until the cleanup removes them. The settings page: the days an entry counts, and deleting all signatures. Works on its own; it does not include `basic_access`. |

Admins can also look at and edit the list in the Django admin
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

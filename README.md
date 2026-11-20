# eos-sig-checker

An [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) app that keeps
one shared list of cosmic signatures for everybody with access.

Copy the results of the probe scanner in EVE (select them, Ctrl+C) and paste
them into the **Probe scanner** box. Pasting checks on its own (at most once a
second per user; **Check** does the same by hand): every line comes back on the
right, in the same order, with group (Combat Site, Wormhole, ...) and name
filled in wherever somebody has scanned that signature already. Every client
language with client texts can be pasted, and the page shows the sites in
the reader's language (see *Client texts*). The columns
use the probe scanner's own words; filled-in cells are green and the signal
is coloured like in the game (red, orange, yellow, green at 100 %). A
**Copy** button puts the completed list on the clipboard in the probe
scanner's own tab-separated format.

```
ACJ-672	Cosmic Signature			0,0%	10,61 AU
```

comes back as

```
ACJ-672	Cosmic Signature	Data Site	Unsecured Frontier Server Bank	0,0%	10,61 AU
```

if somebody pasted a full scan of `ACJ-672` before.

Left of the box, the **WH** card lists every wormhole checked within the
last hours, in any system, and below it **Systems** lists the systems
scanned within the last hours (both spans are settings).

Every page ends with a line of numbers about the shared list: all
signatures, new and checked in the last 24 hours, systems, scanners, and
entries waiting for the cleanup - red when an entry is past its age by more
than a day, which means the cleanup task does not run.

## Location tracking

Above the cards, **Track location** (off by default) follows one of your
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
  `ABC-123`, the group `Cosmic Signature`, site type and name in the
  characters the client uses, a percentage and a distance (a number with a
  unit). A line that does not fit is shown in red with the reason, is not
  stored and goes on the **Errors** tab. At most 200 lines (changeable on
  the settings page, up to 500) and 50,000 characters per paste.
- Probe results that are no signature (anomalies, ships, drones,
  structures) are skipped: neither stored nor listed, only counted below
  the result.
- The result, the Signatures tab and Copy show site types and names in
  the client language that fits the reader's Alliance Auth language,
  where the client texts have exactly one translation; otherwise, and
  for nl, pl and uk, in English. The list itself stays English.
- The copy of every client language with client texts (see below) is
  read: its words are put into English, so the list holds English only.
  A site type or name that has no single English meaning is left blank -
  the list fills it in where the ID is known - and noted on the **Errors**
  tab. Without imported client texts another client's lines are skipped.

## Client texts

The texts the EVE client shows - site names and the probe scanner's column
words - come in every client language from the
[EVE localisation archive](https://github.com/Kelly-Hsueh/EVE-localisation-json-archive),
which exports them from the client every day. The app keeps the short,
name-like texts of de, es, fr, it, ja, ko, ru and zh - about 110,000 to
120,000 per language; the Italian file is mostly empty (about 3,000).
Alliance Auth's nl, pl and uk have no client texts. A text with two
meanings is kept and only used where the column decides it (Japanese has
one word for "Wormhole" and "Wormholes", and the scanner never shows the
plural); a name with two meanings is never guessed.

A daily task (see Installation) reads the archive's hashes and fetches
only the languages whose file changed, one after the other. A file is
50 to 100 MB, and reading it takes about 500 MB of memory for a moment.
The settings page shows each language with its build and asks the
archive whether a newer file waits; **Update now** starts the task at
once. The first fill, or one by hand:

```bash
python manage.py eos_sig_checker_update_client_texts           # changed languages
python manage.py eos_sig_checker_update_client_texts --force   # every language
```

The texts are © CCP Games / Fenris Creations.

## Installation

1. Install the app into the virtual environment of your Alliance Auth:

   ```bash
   pip install git+https://github.com/fthomas-de/eos-sig-checker.git@v0.0.1
   ```

2. Add `"eos_sig_checker",` to `INSTALLED_APPS` in `local.py`, and the
   periodic tasks below it - the cleanup (expired signatures and old
   rejected lines) and the update of the client texts:

   ```python
   CELERYBEAT_SCHEDULE["eos_sig_checker_delete_expired_signatures"] = {
       "task": "eos_sig_checker.tasks.delete_expired_signatures",
       "schedule": crontab(minute="15", hour="11"),
   }
   CELERYBEAT_SCHEDULE["eos_sig_checker_update_client_texts"] = {
       "task": "eos_sig_checker.tasks.update_client_texts",
       "schedule": crontab(minute="30", hour="21"),
   }
   ```

3. Run migrations and collect the static files, then restart Alliance Auth
   and its Celery workers:

   ```bash
   python manage.py migrate eos_sig_checker
   python manage.py collectstatic --noinput
   python manage.py eos_sig_checker_update_client_texts
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
| Show wormholes (hours) | `3` | Hours a checked wormhole stays in the WH card of the paste page, 1 to 48. |
| Show systems (hours) | `3` | Hours a system stays in the system list below the WH card after its last check, 1 to 48. Only tracked pastes know their system. |
| Keep rejected lines (days) | `7` | Days an entry stays on the **Errors** tab, 1 to 30; the daily cleanup task removes older ones. |

The same page has a **Delete all signatures** button, behind a confirmation:
it empties the shared list for everybody and cannot be undone.

Up to 0.0.1 the days came from `EOS_SIG_CHECKER_MAX_AGE_DAYS` in `local.py`.
That setting is no longer read: set the value on the settings page and
remove the line.

## Permissions

| Permission | Meant for | What it opens |
|---|---|---|
| `eos_sig_checker.basic_access` | The members who scan - give it to member states only, not to blues or guests | The page: paste, store and resolve signatures, and track the location of their own characters. Everybody with it shares the same list and sees what the others scanned: for every ID they paste the system, site type and name, when it was last checked and the main of whoever checked it, and the WH card with every wormhole checked recently in any system. |
| `eos_sig_checker.manage_settings` | Whoever looks after the list | The **Signatures** tab: the whole list as a sortable table with a filter each for System, ID, Group and Name; entries past their age are greyed out until the cleanup removes them. The settings page: the settings above, deleting all signatures, and the client texts with **Update now**. The **Errors** tab: every pasted line the check refused and every word of another client without a single English meaning, with the reason (in English), who pasted it and when, and a button to delete them all. Works on its own; it does not include `basic_access`. |

Admins can also look at and edit the list in the Django admin
(*Eos_Sig_Checker › Signatures*).

## Updating

```bash
pip install -U git+https://github.com/fthomas-de/eos-sig-checker.git@<tag>
python manage.py migrate eos_sig_checker
python manage.py collectstatic --noinput
```

Then restart Alliance Auth and its Celery workers.

Coming from 0.0.9 or older: add the second `CELERYBEAT_SCHEDULE` entry
(`update_client_texts`, see Installation) and run
`python manage.py eos_sig_checker_update_client_texts` once.

## Uninstalling

1. Remove the tables:

   ```bash
   python manage.py migrate eos_sig_checker zero
   ```

2. Remove `"eos_sig_checker",` and both `CELERYBEAT_SCHEDULE` entries from
   `local.py`, then uninstall:

   ```bash
   pip uninstall eos-sig-checker
   ```

## Translations

The page's own texts: German, Russian and Simplified Chinese,
machine-generated; EVE terms stay English there. Site types and names come
from the client texts instead, in every language that has them (see
*Client texts*).

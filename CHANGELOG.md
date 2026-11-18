# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.0.9] - 2026-11-18

### Changed

- Permission text of `basic_access` is now "Can paste signatures and see
  the shared list", and the README says what it shows and that it belongs
  to member states only. "Paste and resolve" hid that everybody with it
  sees the systems, the WH card and the main of the last checker of every
  pasted ID. Migration 0006 only updates the model options: an existing
  installation keeps the old text in the admin until the permission is
  created anew.

## [0.0.8] - 2026-11-13

### Changed

- Setting **Show wormholes (hours)** on the settings page (default 3, 1 to
  48): how long a checked wormhole stays in the WH card. It was a fixed 3
  hours in the code, too short for a wormhole that lives up to two days.
  Migration 0005 adds the field with the old value, so nothing changes
  until someone sets it.

## [0.0.7] - 2026-11-13

### Added

- Card **WH** on the paste page, left of the probe scanner box: every
  wormhole checked in the last 3 hours, in any system, newest first, with
  system, ID and time. The result only shows the pasted or tracked system;
  the card tells where a fresh wormhole is without opening the Signatures
  tab, which needs `manage_settings`. It shows the state of the page load
  and follows every paste.

## [0.0.6] - 2026-11-13

### Added

- Switch **Hide Cosmic Anomalies** in the result header, on by default:
  anomalies crowd out the signatures people paste the list for. Copy takes
  what is shown, so with the switch on the anomalies are left out there as
  well. Switched off, it stays off in every tab of the browser. It shows
  before the first paste too, so it can be set beforehand.

### Changed

- The probe scanner box is empty after a check (paste or Check button), so
  the next paste does not land behind the last one. The text stays only when
  the check was refused (too soon, too many lines); the result still shows
  every line, the invalid ones with their text.
- The result no longer shows the distance: it changes with every warp and
  says nothing about the site. Copy keeps it, the probe scanner's format.
- Switching tracking off keeps the character last picked in the menu, in
  every tab of the browser, instead of falling back to the first one.

### Fixed

- A weaker scan of a known signature showed its signal reset (0 % after
  100 %), in the result and in Copy, although the list keeps the best one.
  Both now show the stored best signal; another site under the same ID
  still starts over.

## [0.0.5] - 2026-11-13

From the audit in `docs/AUDIT.md` (SIG-01 to SIG-05). Migration 0004 adds two
columns to the settings.

### Added

- A line of statistics at the foot of every page: all signatures, new and
  checked in the last 24 hours, systems, scanners, and entries waiting for
  the cleanup. The last one turns red when an entry is past its age by more
  than a day - until now nothing on the page showed that the periodic
  cleanup task was not running, or that the list was being flooded.
- Setting **Lines per paste** (default 200, 1 to 500) and setting **Longest
  wait after failed location reads** (default 60 seconds, 5 to 3600) on the
  settings page; the card is titled Settings instead of Cleanup.

### Changed

- A paste may hold 200 lines instead of 500. A member could store 500
  made-up rows a second, far more than a system ever shows; the limit is
  now what a real paste needs and a manager can change it.

### Fixed

- A failed location read was not remembered: only a good read went into the
  5 second cache, so a dead token, an ESI outage or a script on the location
  URL sent every poll of every tab to SSO or ESI again and could spend the
  ESI error budget of the whole Alliance Auth instance. A failure is now
  cached like a position, and the wait grows with every failure in a row in
  5 even steps from 5 seconds to the limit from the settings page; a good
  read starts over.
- Two members pasting the same signatures at the same moment in a different
  order could deadlock in the database, and one of them got a server error:
  the rows were locked in the order of the paste. They are now locked in
  signature ID order, whatever the order of the paste; the result keeps the
  paste's order.
- The parser took the digits of every script for `\d`, so an ID, a signal
  or a distance written in, say, Arabic-Indic digits passed as valid and was
  stored in the shared list. The three patterns now carry `re.ASCII`: only
  0-9 count.

## [0.0.4] - 2026-11-04

### Changed

- Less code for the same behaviour: the list of trackable characters is one
  database query instead of three (the two ID lists were loaded into Python
  only to be passed back as `IN` lists); the menu entry and the main page
  share one permission check (`views.has_access`) instead of two copies that
  could drift apart; the parser's `_check` returns the `Invalid` row itself,
  so `parse` needs no type switch; the main page no longer guards the
  tracked character with a condition that was always true (`locate` either
  returns a position or raises).

## [0.0.3] - 2026-11-04

### Added

- Location tracking through ESI, off by default: a switch on the main page
  and a dropdown of the user's own characters that have a token with
  `esi-location.read_location.v1`. Until now the list had no solar system
  and a member had to paste before seeing anything; with tracking every
  check stores the character's system, and the page shows what is known in
  the current system without a paste - after a paste the pasted lines plus
  the system's other known signatures, so a site left out of the scanner
  selection is not forgotten. The page follows the character every 10
  seconds, Refresh asks at once (at most every 5 seconds, ESI's cache time).
  The choice belongs to the browser tab (`?character=` in its URL), so two
  tabs can track two characters. The server looks the system up itself and
  only for the user's own characters: a request cannot place signatures
  elsewhere or read another user's location. A token SSO no longer accepts
  is named as such ("add the character again") instead of a generic ESI
  error, since trying again would never help.
- The tracked position is shown prominently in the tracking bar and the
  result header, kept current by every poll with its age ("read 3 s
  ago"), so a member sees whether the page still follows the character.
  Problems (no token, a dead token, ESI down, the server unreachable)
  appear as a message box below the bar that clears itself once the
  location can be read again; the last position stays visible meanwhile.
  A character that cannot be tracked keeps its message on the page
  instead of switching tracking off without a word.
- A **System** column on the paste page, the Signatures tab (with a filter)
  and in the Django admin.

### Changed

- A signature is now one entry per ID and solar system instead of per ID
  (migration 0003): the same ID in two systems is two sites. Entries pasted
  without tracking keep no system and still resolve by the ID alone, as
  before; a tracked paste gives them their system.
- `django-esi>=10` is a dependency now: the tracking imports its OpenAPI
  client and Token model.

### Fixed

- `.gitignore` listed `*.pot` twice.

## [0.0.2] - 2026-11-04

### Added

- A settings page with its own permission `eos_sig_checker.manage_settings`
  (a new tab beside the paste page). Until now the days an entry counts
  could only be changed by an admin in `local.py`, followed by a restart;
  now whoever looks after the list sets them on the page (1 to 30), and the
  page, the merge and the cleanup task follow at once. The permission works
  on its own: a holder without `basic_access` lands on the settings from
  the menu.
- A **Delete all signatures** button on the settings page, behind a
  confirmation, to empty the shared list for everybody - before, that was
  only possible row by row in the Django admin.
- A **Signatures** tab (`manage_settings`) listing every entry of the shared
  list as a sortable table - ID, Kind, Group, Name, Signal, first seen, last
  checked and by whom - with a filter field each for ID, Group and Name.
  Without it the list could only be read in the Django admin. Rows past
  their age are shown greyed out with an "expired" mark, since they stay in
  the database until the cleanup task runs and Delete all counts them too.

### Changed

- `EOS_SIG_CHECKER_MAX_AGE_DAYS` in `local.py` is no longer read; the days
  live in the database (migration 0002, start value 7). Set the value on the
  settings page and remove the line from `local.py`.
- `django-solo` is now a declared dependency: the settings are a singleton.
  Alliance Auth already ships it.

## [0.0.1] - 2026-11-04

### Added

- A page to paste the probe scanner and get every line back, site type and
  name filled in from a list shared by everybody with
  `eos_sig_checker.basic_access`. Input and result sit side by side in two
  panes of the same size; a Copy button returns the completed list in the
  scanner's own format.
- Every line is checked before it is stored: six columns, ID like `ABC-123`,
  a known group, site type and name only in the characters the client uses,
  a percentage, a distance; no control characters; at most 500 lines and
  50,000 characters. A line that fails is shown with the reason and never
  stored, so nothing but scanner data reaches the shared list.
- One entry per signature ID with first seen, last checked and the main who
  checked it. A paste with another site under the same ID replaces the entry;
  a weaker scan only confirms it.
- The result table speaks the probe scanner's language - Kind, Group, Name,
  Signal - and colours the signal in the game's steps (red below 25 %,
  orange below 75 %, yellow below 100 %, green at 100 %), so a reader does
  not have to translate between the game window and the page.
- Probe results that are no signature (ships, drones, structures, or a
  client in another language) are skipped instead of listed as errors, and
  only counted below the result: the scanner's filter lets them through in
  normal use, so they are no mistake of the user.
- Pasting into the box checks on its own, no click on Check needed. At most
  one check per user and second: the browser waits for the rest of the
  second, and the server refuses a faster one with 429 and keeps the paste
  in the box - only the server's limit holds against a script, and every
  check can write up to 500 rows.
- `EOS_SIG_CHECKER_MAX_AGE_DAYS` (default 7) and a periodic task
  `delete_expired_signatures`: an entry older than that counts as gone, so a
  reused ID is not resolved to a site that despawned days ago.

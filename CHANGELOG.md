# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

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

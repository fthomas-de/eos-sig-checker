# Audit: programming errors and security

| | |
|---|---|
| Date | 2026-11-11, decisions of the user worked in on 2026-11-12 (see *Decisions*) |
| Commit audited | `b91deeb7989ad49b4baa278da98b128ef26ca154` (`main`, version 0.0.4, clean tree) |
| Scope | All non-test code of `eos_sig_checker/`: views, URLs, models, forms, parser, sync, tracking, provider, tasks, admin, auth hooks, app settings, templates, JavaScript, migrations 0001-0003, `pyproject.toml`. Tests were read only to name the gaps. `tools/` and `testauth/` were only scanned for shell calls and secrets. |
| Method | Reading only. No test run, no database access, nothing executed against ESI. django-esi 10.0.0 and Django's MySQL backend in the venv were read to check SIG-01 and SIG-02. |
| Result | No Critical, no High. 1 Medium, 3 Low, plus one feature the user asked for (SIG-05). |

Status: **CONFIRMED** = the path from the entry point to the effect was read in
full and the trigger can be named. **PLAUSIBLE** = depends on something that
could not be checked; the finding says what.

| ID | Severity | Type | File | Summary | Status |
|---|---|---|---|---|---|
| SIG-01 | Medium | Security (DoS, outgoing requests) | `tracking.py` | A failed location read is not cached: every poll, page load or scripted request goes to SSO/ESI again. Fix: remember failures, waiting longer with every failure, limit on the settings page | CONFIRMED |
| SIG-02 | Low | Bug (concurrency) | `sync.py` | Rows are locked in paste order: two pastes of the same signatures in different order can deadlock, one user gets a 500 | CONFIRMED (by reading, not reproduced) |
| SIG-03 | Low | Security (DoS) | `forms.py`, `models.py` | Nothing bounds how fast the list grows (500 rows a second per member). Fix: 200 lines per paste, changeable on the settings page | CONFIRMED |
| SIG-04 | Low | Security (input validation) | `parser.py` | `\d` matches every Unicode digit: IDs, signals and distances in other scripts pass the parser and reach the shared list | CONFIRMED (database effect PLAUSIBLE) |
| SIG-05 | - | Feature (user request) | `sync.py`, `views.py`, `base.html` | A line of statistics at the foot of every page, so problems (growth, a cleanup that does not run) show while using the app | not a finding |

Every fix below also needs a `CHANGELOG.md` entry under `[Unreleased]`
(project rule: what was wrong and why the fix is the fix). Commits go through
`/commit` only. New messages go into `tools/glossary.py` at the commit, never
into a `.po` file.

---

## SIG-01 - Medium - A failed location read is not cached

**Where**: `eos_sig_checker/tracking.py`, `locate()`, lines 61-94 (the two
`except` branches, lines 81-90). Reached from `views.index` (line 92, every
GET and POST with `?character=`) and `views.tracked_location` (line 148,
polled by `tracking.js` every 10 s per tab).

**What happens**: Only a successful read is stored in the cache (line 93).
When the read fails, nothing is stored, so the next request asks again:

- A member whose refresh token is dead (the handover names such a
  character) leaves a tab open with tracking on. Every poll makes django-esi
  send a refresh request to EVE SSO that is refused with `invalid_grant` -
  one every 10 s per tab, for as long as the tab is open.
- While ESI is down or answers with errors, every tracking tab of every
  member sends a failing request every 10 s. ESI counts errors per
  application; django-esi stops **all** ESI calls of the whole Alliance Auth
  instance (`ESIErrorLimitException`, `esi/openapi_clients.py` lines 582-587
  and 735-736) once the budget is spent. This app can then starve corptools
  and every other app of ESI.
- Any member with `basic_access` can script
  `GET /eos_sig_checker/location/?character=<own character>` in a loop. The
  view has no rate limit of its own; on the failure path each request is one
  outgoing request. The comment at `LOCATION_CACHE_SECONDS` ("a script
  cannot make the server ask ESI faster either") only holds for successes.

**Cause**:

```python
    key = f"eos_sig_checker:location:{character_id}"
    location = cache.get(key)
    if location is not None:
        return location

    try:
        found = esi.client.Location.GetCharactersCharacterIdLocation(character_id=character_id, token=token).result(
            use_etag=False
        )
        system = esi.client.Universe.GetUniverseSystemsSystemId(system_id=found.solar_system_id).result(use_etag=False)
    # a refresh token SSO no longer accepts stays in the list until the user
    # adds the character again: say so, "try again" would never help
    except (TokenError, SSOOAuthError):
        logger.info("Token of character %s refused by SSO", character_id, exc_info=True)
        raise LocationError(
            _("The token of this character is no longer valid. Add the character again with the location scope.")
        ) from None
    # ESI, the token refresh and the network fail in many ways; each one only
    # means "no location now" to the page, the log keeps the cause
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Location of character %s not available", character_id, exc_info=True)
        raise LocationError(_("The location could not be read from ESI. Try again in a moment.")) from None

    location = Location(found.solar_system_id, system.name)
    cache.set(key, location, LOCATION_CACHE_SECONDS)
    return location
```

**Fix** (decided by the user on 2026-11-12): a failed read is remembered
and the wait grows with the number of failures in a row, in 5 steps from
5 seconds up to a limit that is set on the settings page (default 60). The
steps follow the limit: with 60 they are 5, 19, 33, 46, 60 seconds; with 25
they are 5, 10, 15, 20, 25. A successful read starts over.

Needs a migration (one new column on `SigCheckerConfiguration`) and two new
messages.

1. `eos_sig_checker/models.py`: below `MAX_AGE_DAYS_LIMIT = 30` add

```python
DEFAULT_LOCATION_RETRY_SECONDS = 60
# 5 is tracking.LOCATION_CACHE_SECONDS, the first step; beyond an hour a
# repaired token would look broken for too long
LOCATION_RETRY_SECONDS_MIN = 5
LOCATION_RETRY_SECONDS_LIMIT = 3600
```

   and in `SigCheckerConfiguration`, below the field `max_age_days`, add

```python
    location_retry_seconds = models.PositiveSmallIntegerField(
        default=DEFAULT_LOCATION_RETRY_SECONDS,
        validators=[MinValueValidator(LOCATION_RETRY_SECONDS_MIN), MaxValueValidator(LOCATION_RETRY_SECONDS_LIMIT)],
        verbose_name=_("Longest wait after failed location reads (seconds)"),
        help_text=_(
            "A location that cannot be read is asked again after 5 seconds at first, "
            "then later with every further failure, in 5 steps up to this many seconds."
        ),
    )
```

2. Migration: `python manage.py makemigrations eos_sig_checker` (from the
   AA instance). Expected: `0004_...` with exactly one `AddField` on
   `sigcheckerconfiguration` and the single dependency
   `('eos_sig_checker', '0003_signature_solar_system')`. If it names an
   `eveonline` migration, remove that dependency (see the comment in 0003).
   It touches only this app's table and deletes nothing, so it may be
   applied to `aa_dev` (`python manage.py migrate eos_sig_checker`).

3. `eos_sig_checker/app_settings.py`: append

```python
def location_retry_seconds() -> int:
    """The longest wait after failed location reads, from the settings page."""
    return SigCheckerConfiguration.get_solo().location_retry_seconds
```

4. `eos_sig_checker/forms.py`:
   - import: `from .models import LOCATION_RETRY_SECONDS_LIMIT, LOCATION_RETRY_SECONDS_MIN, MAX_AGE_DAYS_LIMIT, SigCheckerConfiguration`
   - `fields = ["max_age_days"]` becomes
     `fields = ["max_age_days", "location_retry_seconds"]`
   - in `ConfigurationForm.__init__`, below the existing `attrs.update` line:

```python
        self.fields["location_retry_seconds"].widget.attrs.update(
            min=LOCATION_RETRY_SECONDS_MIN, max=LOCATION_RETRY_SECONDS_LIMIT
        )
```

5. `eos_sig_checker/templates/eos_sig_checker/settings.html`:
   - below `{% bootstrap_field form.max_age_days %}` add
     `{% bootstrap_field form.location_retry_seconds %}`
   - the card no longer holds the cleanup only: replace
     `{% translate "Cleanup" %}` with
     `{% translate "Settings" context "eos-sig-checker" %}` (that message
     exists already, `base.html` uses it). The msgid `Cleanup` is then
     unused: remove it from `tools/glossary.py` if `tools/translate.py`
     reports it at the commit.

6. `eos_sig_checker/tracking.py`:
   - add the import `from .app_settings import location_retry_seconds`
     above `from .provider import esi`
   - replace the comment above `LOCATION_CACHE_SECONDS` and add the
     constants below it:

```python
# ESI caches a character's location for 5 seconds: asking more often only
# spends the error budget. Every tab of every user goes through this cache,
# failed reads included, so a script cannot make the server ask ESI or SSO
# faster either.
LOCATION_CACHE_SECONDS = 5

# A failed read is asked again after LOCATION_CACHE_SECONDS, then later with
# every further failure in a row: in this many even steps up to the limit
# from the settings page. A dead token or an ESI outage would otherwise send
# every poll of every tab to SSO or ESI again and spend the error budget all
# apps of the instance share.
RETRY_STEPS = 5
# how long the count of failures outlives the wait: longer than a poll
# (views.LOCATION_INTERVAL_SECONDS), or every failure would count as the first
FAILURES_KEPT_SECONDS = 60
FAILURES_KEY = "eos_sig_checker:location_failures:{}"
```

   - add these two functions above `locate`:

```python
def _retry_seconds(failures: int) -> int:
    """How long the read stays refused after ``failures`` failures in a row."""
    limit = max(location_retry_seconds(), LOCATION_CACHE_SECONDS)
    step = min(failures, RETRY_STEPS) - 1
    return LOCATION_CACHE_SECONDS + round((limit - LOCATION_CACHE_SECONDS) * step / (RETRY_STEPS - 1))


def _failure(character_id: int, key: str, message: str) -> LocationError:
    """Remember a failed read for its wait and return the error to raise."""
    failures_key = FAILURES_KEY.format(character_id)
    failures = (cache.get(failures_key) or 0) + 1
    wait = _retry_seconds(failures)
    cache.set(failures_key, failures, wait + FAILURES_KEPT_SECONDS)
    cache.set(key, message, wait)
    return LocationError(message)
```

   - in `locate`, replace the block shown under *Cause* (from `key = ...`
     to the end of the function) with:

```python
    key = f"eos_sig_checker:location:{character_id}"
    cached = cache.get(key)
    if isinstance(cached, Location):
        return cached
    # the message of a failed read, still inside its wait
    if cached is not None:
        raise LocationError(cached)

    try:
        found = esi.client.Location.GetCharactersCharacterIdLocation(character_id=character_id, token=token).result(
            use_etag=False
        )
        system = esi.client.Universe.GetUniverseSystemsSystemId(system_id=found.solar_system_id).result(use_etag=False)
    # a refresh token SSO no longer accepts stays in the list until the user
    # adds the character again: say so, "try again" would never help
    except (TokenError, SSOOAuthError):
        logger.info("Token of character %s refused by SSO", character_id, exc_info=True)
        raise _failure(
            character_id,
            key,
            _("The token of this character is no longer valid. Add the character again with the location scope."),
        ) from None
    # ESI, the token refresh and the network fail in many ways; each one only
    # means "no location now" to the page, the log keeps the cause
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Location of character %s not available", character_id, exc_info=True)
        raise _failure(
            character_id, key, _("The location could not be read from ESI. Try again in a moment.")
        ) from None

    location = Location(found.solar_system_id, system.name)
    cache.set(key, location, LOCATION_CACHE_SECONDS)
    cache.delete(FAILURES_KEY.format(character_id))
    return location
```

   `_` in this module is `gettext` (not lazy), so the message is a plain
   `str` and can be cached. The ownership check (`_token`) stays in front
   of the cache read, unchanged.

7. `README.md`:
   - Settings table, new row:
     `| Longest wait after failed location reads (seconds) | `60` | A location that cannot be read (dead token, ESI down) is asked again after 5 seconds, then later with every further failure, in 5 steps up to this value; 5 to 3600. |`
   - section *Location tracking*, last bullet: after "a message below the
     bar says why" add "and the server waits longer before every further
     attempt (see Settings)".

8. Translations (at `/commit`): the two new msgids are the `verbose_name`
   and the `help_text` of step 1; both into `tools/glossary.py`.

**Test**:

a) `eos_sig_checker/tests/test_tracking.py`, class `TestLocate` (it mocks
`tracking.esi` already). Add to the imports:
`from django.core.cache import cache` and
`from eos_sig_checker.models import SigCheckerConfiguration` (extend the
existing `eos_sig_checker.models` import). New tests:

```python
    def fail_read(self, times=1):
        """Failed reads in a row, each after the wait of the one before."""
        for _attempt in range(times):
            # the wait is over: the remembered failure has left the cache
            cache.delete(f"eos_sig_checker:location:{self.main.character_id}")
            with self.assertRaises(LocationError):
                locate(self.user, self.main.character_id)

    def test_should_not_ask_again_while_a_failure_is_remembered(self):
        add_token(self.user, self.main)
        self.esi.client.Location.GetCharactersCharacterIdLocation.return_value.result.side_effect = OSError("down")

        for _attempt in range(2):
            with self.assertRaisesMessage(LocationError, "Try again"):
                locate(self.user, self.main.character_id)

        self.assertEqual(self.esi.client.Location.GetCharactersCharacterIdLocation.call_count, 1)

    def test_should_not_ask_sso_again_while_a_dead_token_is_remembered(self):
        add_token(self.user, self.main)
        self.esi.client.Location.GetCharactersCharacterIdLocation.return_value.result.side_effect = SSOOAuthError(
            "invalid_grant", "Invalid refresh token. Token missing/expired."
        )

        for _attempt in range(2):
            with self.assertRaisesMessage(LocationError, "no longer valid"):
                locate(self.user, self.main.character_id)

        self.assertEqual(self.esi.client.Location.GetCharactersCharacterIdLocation.call_count, 1)

    def test_should_wait_longer_with_every_failure_up_to_the_limit(self):
        # the default limit of 60 seconds, in 5 steps from the 5 seconds of a good read
        self.assertEqual([tracking._retry_seconds(failures) for failures in range(1, 8)], [5, 19, 33, 46, 60, 60, 60])

    def test_should_follow_the_limit_from_the_settings_page(self):
        config = SigCheckerConfiguration.get_solo()
        config.location_retry_seconds = 25
        config.save()

        self.assertEqual([tracking._retry_seconds(failures) for failures in range(1, 6)], [5, 10, 15, 20, 25])

    def test_should_count_failures_in_a_row_and_start_over_after_a_good_read(self):
        add_token(self.user, self.main)
        result = self.esi.client.Location.GetCharactersCharacterIdLocation.return_value.result
        failures_key = tracking.FAILURES_KEY.format(self.main.character_id)
        result.side_effect = OSError("down")

        self.fail_read(times=3)
        self.assertEqual(cache.get(failures_key), 3)

        result.side_effect = None
        cache.delete(f"eos_sig_checker:location:{self.main.character_id}")
        self.assertEqual(locate(self.user, self.main.character_id), JITA)
        self.assertIsNone(cache.get(failures_key))
```

Red before the fix: `call_count` is 2 in the first two tests; the other
three fail on the missing `_retry_seconds`, `location_retry_seconds` and
`FAILURES_KEY`. Green after. The existing
`test_should_not_hand_out_the_cached_location_of_another_users_character`
keeps guarding the order ownership-then-cache.

b) `eos_sig_checker/tests/test_settings.py`: the form now has two required
fields, so every existing post of `{"max_age_days": ...}` to `SETTINGS`
would be refused. Add below the constants

```python
# what the settings form needs to be valid; a test overrides what it is about
VALID = {"max_age_days": DEFAULT_MAX_AGE_DAYS, "location_retry_seconds": DEFAULT_LOCATION_RETRY_SECONDS}
```

(import `DEFAULT_LOCATION_RETRY_SECONDS` from `eos_sig_checker.models`) and
change **every** `self.client.post(SETTINGS, {"max_age_days": X})` in the
file to `self.client.post(SETTINGS, {**VALID, "max_age_days": X})`. New
tests in `TestSettingsPage`:

```python
    def test_should_store_the_longest_wait(self):
        self.client.post(SETTINGS, {**VALID, "location_retry_seconds": 120})

        self.assertEqual(SigCheckerConfiguration.get_solo().location_retry_seconds, 120)

    def test_should_refuse_a_wait_out_of_range(self):
        for seconds in (4, 3601, "", "x"):
            with self.subTest(seconds):
                response = self.client.post(SETTINGS, {**VALID, "location_retry_seconds": seconds})

                self.assertTrue(response.context["form"].errors)
                self.assertEqual(
                    SigCheckerConfiguration.get_solo().location_retry_seconds, DEFAULT_LOCATION_RETRY_SECONDS
                )
```

and in `test_should_hand_the_bounds_to_the_browser` add
`self.assertContains(response, 'min="5"')` and
`self.assertContains(response, 'max="3600"')`.

**Verify**: `aa-test eos_sig_checker.tests.test_tracking` (test count +5),
`aa-test eos_sig_checker.tests.test_settings` (+2),
`python manage.py makemigrations eos_sig_checker --check --dry-run`.

**Risk / depends on**: A user who repairs a token sees the old message
until the current wait is over (up to the limit, 60 seconds by default);
the poll after that clears it. The count is read and written in two cache
calls, so two failing requests at the same moment may count as one - the
wait then grows one step later, nothing breaks. The message is cached in
the language of the request that failed; the key is per character, so only
its owner reads it. The Refresh button answers with the remembered message
during a wait. SIG-03 adds a second field to the same form and extends
`VALID`: implement SIG-01 first.

---

## SIG-02 - Low - Two pastes in different order can deadlock

**Where**: `eos_sig_checker/sync.py`, `merge()`, lines 87-153 (the loop at
line 99), with `_find()` lines 63-84 (`select_for_update`) and the
`get_or_create` at line 110.

**What happens**: The loop locks one row per line, in the order of the
paste. The probe scanner copies in the order the window is sorted, and two
pilots rarely sort alike (distance differs per ship). Alice pastes
`ABC-123` then `XYZ-789`, Bob pastes `XYZ-789` then `ABC-123`, both for rows
that exist (or both new), at the same moment: Alice's transaction holds
`ABC-123` and waits for `XYZ-789`, Bob's holds `XYZ-789` and waits for
`ABC-123`. MySQL ends one of them with error 1213 (deadlock);
`OperationalError` is not caught anywhere, so that user gets a 500 page and
the whole paste is rolled back. The same happens with two inserts of new
IDs (each waits on the other's uncommitted unique key). The comment in
`_find` ("two people pasting the same system at once must not overwrite
each other's merge halfway") shows this case is meant to work.

Not reproduced: it needs two overlapping transactions (a 500-line paste runs
for about a second). Confirmed by reading; the lock order is the paste
order, nothing sorts it.

**Cause**:

```python
    with transaction.atomic():
        for line in rows:
            ...
            signature = _find(line, system, oldest)      # SELECT ... FOR UPDATE, in paste order
            if signature is None:
                signature, created = Signature.objects.get_or_create(
```

**Fix** (one file, no migration, no message): lock in signature ID order,
answer in paste order.

1. In `eos_sig_checker/sync.py` replace the whole function `merge` (lines
   87-153) with the two functions below. The body of `_store` is the old
   loop body unchanged, except that `output.append(X); continue` and
   `output.append(X)` became `return X`.

```python
def _store(line: Line, character, now, oldest, system) -> Row:
    """Store one valid line and return it completed from the list."""
    signature = _find(line, system, oldest)
    if signature is None:
        # get_or_create, not create: a second paste of the same
        # system at the same moment finds the row instead of failing
        # on the unique constraint
        signature, created = Signature.objects.get_or_create(
            signature_id=line.signature_id,
            solar_system_id=system.system_id if system else NO_SYSTEM,
            defaults={
                "solar_system_name": system.system_name if system else "",
                "group": line.group,
                "site_type": line.site_type,
                "name": line.name,
                "signal": line.signal,
                "distance": line.distance,
                "first_seen": now,
                "last_checked": now,
                "last_checked_by": character,
            },
        )
        if created:
            return Row(line, line.site_type, line.name, system_name=signature.solar_system_name)

    known = signature.last_checked >= oldest
    previous_check = signature.last_checked if known else None
    previous_by = signature.last_checked_by.character_name if known and signature.last_checked_by else ""
    # a row past its age counts as gone, even before the cleanup task removed it
    if not known or _is_other_site(signature, line):
        _replace(signature, line, now)
        resolved = set()
    else:
        resolved = _merge(signature, line)
    signature.distance = line.distance
    signature.last_checked = now
    signature.last_checked_by = character
    signature.save()
    return Row(
        line,
        signature.site_type,
        signature.name,
        resolved,
        previous_check,
        previous_by,
        system_name=signature.solar_system_name,
    )


def merge(rows: list[Line | Invalid | Skipped], character, now=None, system=None) -> list[Row | Invalid]:
    """Store every valid line and return the paste completed from the list.

    ``character`` is the main of whoever pasted, kept as the last checker;
    ``system`` the tracked character's tracking.Location, or None.
    Invalid lines pass through untouched, so the output keeps the paste's
    order; skipped lines (no signature) drop out.
    """
    now = now or timezone.now()
    oldest = cutoff(now)
    output = [line for line in rows if not isinstance(line, Skipped)]
    # locked in ID order, not paste order: two people pasting the same system
    # sorted differently would lock the rows crosswise and deadlock. The sort
    # is stable, so an ID pasted twice keeps its order.
    by_id = sorted(
        (index for index, line in enumerate(output) if isinstance(line, Line)),
        key=lambda index: output[index].signature_id,
    )
    with transaction.atomic():
        for index in by_id:
            output[index] = _store(output[index], character, now, oldest, system)
    return output
```

   `Line`, `Invalid`, `Skipped`, `transaction`, `timezone` are imported
   already; no new import.

**Test**: `eos_sig_checker/tests/test_sync.py`, class `TestMerge`. Add the
imports `from unittest import mock` (stdlib block) and
`from eos_sig_checker import sync` (next to the other `eos_sig_checker`
imports), then:

```python
    def test_should_lock_in_id_order_and_answer_in_paste_order(self):
        # SCANNED is UDN-422, UNSCANNED is ACJ-672: pasted in descending order
        with mock.patch.object(sync, "_find", wraps=sync._find) as find:
            output = self.paste(f"{SCANNED}\n{UNSCANNED}")

        self.assertEqual([call.args[0].signature_id for call in find.call_args_list], ["ACJ-672", "UDN-422"])
        self.assertEqual([row.line.signature_id for row in output], ["UDN-422", "ACJ-672"])
```

Red before the fix (`_find` is called for `UDN-422` first), green after.
The fix must keep calling `_find(line, system, oldest)` with positional
arguments, as above - the test reads `call.args[0]`. The existing
`test_should_keep_invalid_lines_in_place_and_store_nothing_from_them` and
`test_should_drop_skipped_lines` guard the output order.

**Verify**: `aa-test eos_sig_checker.tests.test_sync`, then
`aa-test eos_sig_checker.tests.test_tracking` and
`aa-test eos_sig_checker.tests.test_views` (both call `merge`). Test count +1.

**Risk / depends on**: Pure reordering of the database work; the result per
line is the same, since lines with different IDs do not read each other's
rows and equal IDs keep their order. A deadlock stays possible in theory
between a tracked and an untracked paste of one ID (they lock the ID's rows
in two statements); that needs the same ID in two systems at the same
moment and was left alone. Independent of the other findings.

---

## SIG-03 - Low - Nothing bounds how fast the list grows

**Where**: `eos_sig_checker/forms.py`, `PasteForm.clean_text()`, lines 38-50
with `parser.MAX_LINES = 500` (`parser.py` line 22) and
`views.MIN_INTERVAL_SECONDS = 1` (`views.py` lines 100-111). Effect:
`views.signatures()`, lines 154-163, and `signatures.html`, lines 47-63 (one
`<tr>` per row; DataTables pages in the browser only).

**What happens**: A member with `basic_access` can script one paste of 500
made-up IDs per second: 30,000 rows a minute, 1.8 million an hour, each
living up to 30 days. The paste page keeps working - it reads by ID and by
system - but the Signatures tab hands the complete table to the template,
so for whoever holds `manage_settings` it times out or freezes the browser,
and that tab is where a manager would look before pressing *Delete all*. A
real system holds a few dozen signatures and anomalies; 500 lines per paste
is far more than a client ever copies.

**Cause**:

```python
MAX_LINES = 500                      # parser.py

        if lines > MAX_LINES:        # forms.py, clean_text
```

**Fix** (decided by the user on 2026-11-12): at most 200 lines per paste,
changeable on the settings page (1 to 500; `parser.MAX_LINES` stays the hard
ceiling). The Signatures tab itself stays as it is, at the user's choice; the
statistics of SIG-05 show when the list grows.

Needs a migration (one new column on `SigCheckerConfiguration`) and two new
messages. Implement after SIG-01 (same form, same test helper).

1. `eos_sig_checker/models.py`:
   - add the import `from .parser import MAX_LINES` as the last import
     (the parser imports nothing from this app, so there is no cycle)
   - below the constants of SIG-01 add

```python
# more than 200 lines in one paste is unlikely; parser.MAX_LINES is the ceiling
DEFAULT_MAX_LINES = 200
```

   - in `SigCheckerConfiguration`, below `location_retry_seconds`, add

```python
    max_lines = models.PositiveSmallIntegerField(
        default=DEFAULT_MAX_LINES,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_LINES)],
        verbose_name=_("Lines per paste"),
        help_text=_("The most lines one paste may hold. A full system has a few dozen signatures and anomalies."),
    )
```

2. Migration: `python manage.py makemigrations eos_sig_checker`. Expected:
   `0005_...` with exactly one `AddField` on `sigcheckerconfiguration`,
   depending only on this app's 0004. Same checks as in SIG-01 step 2; may
   be applied to `aa_dev`.

3. `eos_sig_checker/app_settings.py`: append

```python
def max_lines() -> int:
    """The most lines one paste may hold, from the settings page."""
    return SigCheckerConfiguration.get_solo().max_lines
```

4. `eos_sig_checker/forms.py`:
   - add the import `from .app_settings import max_lines` (above
     `from .models import ...`)
   - `fields` becomes
     `["max_age_days", "location_retry_seconds", "max_lines"]`
   - in `ConfigurationForm.__init__` add
     `self.fields["max_lines"].widget.attrs.update(min=1, max=MAX_LINES)`
   - `clean_text` becomes

```python
    def clean_text(self):
        text = self.cleaned_data["text"]
        lines = sum(1 for line in text.splitlines() if line.strip())
        limit = max_lines()
        if lines > limit:
            raise forms.ValidationError(
                ngettext(
                    "At most %(max)d line per paste.",
                    "At most %(max)d lines per paste.",
                    limit,
                )
                % {"max": limit}
            )
        return text
```

   The message is unchanged, so no new translation for it.

5. `eos_sig_checker/parser.py`, comment above `MAX_LINES`: replace

```python
# A whole paste: a full system holds a few dozen signatures and anomalies.
```

   with

```python
# The ceiling of a whole paste; the limit in force is lower and comes from
# the settings page (forms.PasteForm). A full system holds a few dozen
# signatures and anomalies.
```

6. `settings.html`: below `{% bootstrap_field form.location_retry_seconds %}`
   add `{% bootstrap_field form.max_lines %}`.

7. `README.md`:
   - line 73: "At most 500 lines and 50,000 characters per paste." becomes
     "At most 200 lines (changeable on the settings page, up to 500) and
     50,000 characters per paste."
   - Settings table, new row:
     `| Lines per paste | `200` | The most lines one paste may hold, 1 to 500. |`

8. Translations (at `/commit`): the `verbose_name` and `help_text` of
   step 1 into `tools/glossary.py`.

**Test**:

a) `eos_sig_checker/tests/test_views.py`, class `TestIndex` (import
`SigCheckerConfiguration` from `eos_sig_checker.models`):

```python
    def test_should_refuse_more_lines_than_the_settings_page_allows(self):
        config = SigCheckerConfiguration.get_solo()
        config.max_lines = 1
        config.save()

        response = self.client.post(URL, {"text": f"{SCANNED}\n{UNSCANNED}"})

        self.assertIsNone(response.context["output"])
        self.assertContains(response, "At most 1 line per paste.")
        self.assertFalse(Signature.objects.exists())

    def test_should_refuse_201_lines_by_default(self):
        text = "\n".join(f"ABC-{i:03d}\tCosmic Signature\t\t\t0,0%\t1 AU" for i in range(201))

        response = self.client.post(URL, {"text": text})

        self.assertContains(response, "At most 200 lines per paste.")
        self.assertFalse(Signature.objects.exists())
```

Red before the fix (`max_lines` is no field; 201 lines are stored), green
after. The existing `test_should_refuse_an_oversized_paste_without_storing`
(501 lines) stays valid.

b) `eos_sig_checker/tests/test_settings.py`: extend `VALID` (from SIG-01)
with `"max_lines": DEFAULT_MAX_LINES` (import it), and add to
`TestSettingsPage`:

```python
    def test_should_store_the_lines_per_paste(self):
        self.client.post(SETTINGS, {**VALID, "max_lines": 50})

        self.assertEqual(SigCheckerConfiguration.get_solo().max_lines, 50)

    def test_should_refuse_lines_out_of_range(self):
        for lines in (0, 501, "", "x"):
            with self.subTest(lines):
                response = self.client.post(SETTINGS, {**VALID, "max_lines": lines})

                self.assertTrue(response.context["form"].errors)
                self.assertEqual(SigCheckerConfiguration.get_solo().max_lines, DEFAULT_MAX_LINES)
```

and in `test_should_hand_the_bounds_to_the_browser` add
`self.assertContains(response, 'max="500"')`.

**Verify**: `aa-test eos_sig_checker.tests.test_views` (test count +2),
`aa-test eos_sig_checker.tests.test_settings` (+2),
`python manage.py makemigrations eos_sig_checker --check --dry-run`.

**Risk / depends on**: A paste of more than 200 lines that worked until now
is refused with the message; a manager can raise the limit. The growth is
slowed (200 rows a second per member instead of 500), not stopped, and the
Signatures tab still renders the whole table - both accepted by the user
for now, with SIG-05 as the indicator. Depends on SIG-01 (form, `VALID`,
migration number).

---

## SIG-04 - Low - The parser accepts digits of every script

**Where**: `eos_sig_checker/parser.py`, lines 27, 34 and 37 (`SIGNATURE_ID`,
`SIGNAL`, `DISTANCE`), used in `_check()` lines 90-110.

**What happens**: In a Python `str` pattern `\d` matches every Unicode
decimal digit, not only `0-9`. A member pastes
`ABC-١٢٣<TAB>Cosmic Signature<TAB><TAB><TAB>٥٠,٠%<TAB>١ AU` (Arabic-Indic
digits; any other script works as well). The line is valid:
`SIGNATURE_ID.fullmatch` accepts the ID, `Decimal("٥٠.٠")` is 50.0, the
distance passes. `sync.merge` stores a row with the ID `ABC-١٢٣` and the
distance `١ AU`, and everybody sees it in the list and in the Copy text.
The module's own rule ("every column is checked against what the client can
produce ... this keeps junk out of the shared list") is not met. No markup
or script gets through - letters and punctuation are still limited and the
templates escape - so this is junk in the shared list, not XSS.

PLAUSIBLE part: on a MySQL collation that weighs digits of all scripts
alike (`utf8mb4_unicode_ci`, `utf8mb4_0900_ai_ci`) the lookup
`signature_id="ABC-١٢٣"` also finds the row `ABC-123`, so such a line would
merge into the real row instead of creating a second one. Not checked: the
collation of the table.

**Cause**:

```python
SIGNATURE_ID = re.compile(r"[A-Z]{3}-\d{3}")
...
SIGNAL = re.compile(r"(\d{1,3})(?:[.,](\d))?%")
...
DISTANCE = re.compile(r"\d[\d.,   ]{0,20} (?:AU|km|m)")
```

**Fix** (one file, no migration, no message): make `\d` mean `0-9`.

1. In `eos_sig_checker/parser.py` add `re.ASCII` as the second argument of
   these three `re.compile` calls. Do **not** retype the patterns - the
   character class of `DISTANCE` holds a non-breaking space and a narrow
   non-breaking space that must stay. Only append the flag:

```python
SIGNATURE_ID = re.compile(r"[A-Z]{3}-\d{3}", re.ASCII)
SIGNAL = re.compile(r"(\d{1,3})(?:[.,](\d))?%", re.ASCII)
DISTANCE = re.compile(r"<pattern unchanged>", re.ASCII)
```

   `re.ASCII` only changes `\d`, `\w`, `\s`, `\b`; the literal non-breaking
   spaces in the class keep matching.

2. Above `SIGNATURE_ID` add one comment line:

```python
# re.ASCII: without it \d takes the digits of every script, not just 0-9
```

**Test**: `eos_sig_checker/tests/test_parser.py`,
`test_should_report_lines_the_client_cannot_produce`: add three entries to
the `bad` dict (escapes, so the file stays ASCII):

```python
            "foreign digits in the ID": "ABC-١٢٣\tCosmic Signature\t\t\t0,0%\t1 AU",
            "foreign digits in the signal": "ABC-123\tCosmic Signature\t\t\t٥٠,٠%\t1 AU",
            "foreign digits in the distance": "ABC-123\tCosmic Signature\t\t\t0,0%\t١ AU",
```

Red before the fix (each of the three parses to a `Line`), green after. The
existing `test_should_read_other_distance_units_and_separators` proves the
non-breaking spaces still pass. Subtests do not change the test count.

**Verify**: `aa-test eos_sig_checker.tests.test_parser`.

**Risk / depends on**: None for real client text: the English client writes
ASCII digits. Rows with foreign digits that are already stored (none are
expected) expire on their own. Independent of the other findings.

---

## SIG-05 - Feature - Statistics at the foot of every page

Not a finding: asked for by the user on 2026-11-12 instead of a cap on the
growth (SIG-03), "so one sees while using the app whether there are
problems".

**Where**: new function in `eos_sig_checker/sync.py`; `views._render()`
(line 37, every page of the app goes through it);
`templates/eos_sig_checker/base.html` (below `{% block details %}`).

**What it shows** (one line, small and grey, below the content of the paste
page, the Signatures tab and the settings page, for everybody who can open
the page):

| Shown as | Meaning | The problem it shows |
|---|---|---|
| Signatures | all rows of the list | the list growing without end |
| new in 24 h | rows first seen in the last 24 hours | a flood of made-up rows; nobody scanning |
| checked in 24 h | rows pasted in the last 24 hours | the list not being used |
| systems | solar systems with at least one row (tracking) | tracking not in use |
| scanners in 24 h | different mains that pasted in the last 24 hours | one account producing all rows |
| waiting for cleanup | rows past their age, not yet deleted; red with a tooltip when one is past its age by more than a day | the periodic cleanup task not running |

"24 hours" rather than "today": the number does not drop to zero at
midnight.

**Change**:

1. `eos_sig_checker/sync.py`: add the import
   `from django.db.models import Count, Q` (below `from django.db import transaction`)
   and append

```python
def statistics(now=None) -> dict:
    """The counts at the foot of every page: how the list grows, whether it
    is used and whether the cleanup runs."""
    now = now or timezone.now()
    oldest = cutoff(now)
    day = now - timedelta(hours=24)
    # shortcut: one scan of the table per page view, cache the result once the table passes about 100,000 rows
    return Signature.objects.aggregate(
        total=Count("pk"),
        new=Count("pk", filter=Q(first_seen__gte=day)),
        checked=Count("pk", filter=Q(last_checked__gte=day)),
        systems=Count("solar_system_id", filter=Q(solar_system_id__gt=NO_SYSTEM), distinct=True),
        scanners=Count("last_checked_by", filter=Q(last_checked__gte=day), distinct=True),
        expired=Count("pk", filter=Q(last_checked__lt=oldest)),
        # past its age by more than a day: the daily cleanup did not run
        overdue=Count("pk", filter=Q(last_checked__lt=oldest - timedelta(days=1))),
    )
```

2. `eos_sig_checker/views.py`, `_render`: the context becomes
   `{"version": __version__, "nav": nav, "statistics": sync.statistics(), **context}`.

3. `base.html`: directly below `{% block details %}{% endblock %}` (inside
   the `<div class="eos_sig_checker">`) add

```html
        {# the shared list at a glance on every page: growth, use, and whether the cleanup runs #}
        <p class="text-center text-body-secondary small mt-3 mb-0">
            {% translate "Signatures" %}: {{ statistics.total }}
            &middot; {% translate "new in 24 h" %}: {{ statistics.new }}
            &middot; {% translate "checked in 24 h" %}: {{ statistics.checked }}
            &middot; {% translate "systems" %}: {{ statistics.systems }}
            &middot; {% translate "scanners in 24 h" %}: {{ statistics.scanners }}
            &middot; <span{% if statistics.overdue %} class="text-danger" title="{% translate 'Entries past their age by more than a day are still stored: the cleanup task does not run.' %}"{% endif %}>{% translate "waiting for cleanup" %}: {{ statistics.expired }}</span>
        </p>
```

   The label is "waiting for cleanup", not "expired": the Signatures tab
   test counts the text `>expired</span>` on the page.

4. `README.md`: after the paragraph on the **Copy** button add: "Every page
   ends with a line of numbers about the shared list: all signatures, new
   and checked in the last 24 hours, systems, scanners, and entries waiting
   for the cleanup - red when the cleanup task has not run for over a day."

5. Translations (at `/commit`), new msgids: `new in 24 h`,
   `checked in 24 h`, `systems`, `scanners in 24 h`, `waiting for cleanup`,
   `Entries past their age by more than a day are still stored: the cleanup task does not run.`
   (`Signatures` exists). If `tools/translate.py` reports a clash of
   `systems` with Alliance Auth's catalogue, give it the context
   `eos-sig-checker` like Name and Type.

**Test**:

a) `eos_sig_checker/tests/test_sync.py`: import `statistics` from
`eos_sig_checker.sync` and `Location` from `eos_sig_checker.tracking`; new
class

```python
class TestStatistics(SyncTestCase):
    def test_should_count_the_list(self):
        now = timezone.now()
        # past its age by two days: expired, and the cleanup is overdue
        self.paste(SCANNED, now=now - timedelta(days=DEFAULT_MAX_AGE_DAYS + 2))
        merge(parse(DATA_SITE), self.bob, now=now - timedelta(hours=1), system=Location(30000142, "Jita"))

        self.assertEqual(
            statistics(now),
            {"total": 2, "new": 1, "checked": 1, "systems": 1, "scanners": 1, "expired": 1, "overdue": 1},
        )

    def test_should_not_call_a_freshly_expired_row_overdue(self):
        now = timezone.now()
        self.paste(SCANNED, now=now - timedelta(days=DEFAULT_MAX_AGE_DAYS, hours=1))

        counts = statistics(now)

        self.assertEqual((counts["expired"], counts["overdue"]), (1, 0))
```

b) `eos_sig_checker/tests/test_views.py`, class `TestIndex`:

```python
    def test_should_show_the_statistics_below_the_page(self):
        self.client.post(URL, {"text": SCANNED})

        response = self.client.get(URL)

        self.assertEqual(response.context["statistics"]["total"], 1)
        self.assertContains(response, "new in 24 h")
        self.assertNotContains(response, "the cleanup task does not run")
```

Red before the change (`statistics` cannot be imported; no such context
key), green after.

**Verify**: `aa-test eos_sig_checker.tests.test_sync` (test count +2),
`aa-test eos_sig_checker.tests.test_views` (+1), then
`aa-test eos_sig_checker.tests.test_signatures` and
`aa-test eos_sig_checker.tests.test_settings` (every page gained the line).
No `collectstatic`: no static file changes.

**Risk / depends on**: One more query per page view, a scan of the whole
table (see the `shortcut` comment); at the sizes the app is built for that
is milliseconds. Every member sees the totals, including the number of
scanners - the list is shared anyway. Touches `sync.py` like SIG-02:
implement after it.

---

## Implementation order

1. **SIG-01** first: the only Medium. Brings migration 0004, the renamed
   settings card and the `VALID` helper of the settings tests.
2. **SIG-03**: second field on the same form, migration 0005.
3. **SIG-04**: three flags and three test lines, independent.
4. **SIG-02**: moves the body of `merge`; keep that diff free of anything
   else.
5. **SIG-05** last: appends to `sync.py` after SIG-02 changed it.

One commit per item. SIG-01, SIG-03 and SIG-05 add messages, so their
commits also touch `tools/glossary.py`, the catalogues and the README;
SIG-02 and SIG-04 do not and may share one commit. Each commit: affected
test modules while working, the fresh suite and the translation run at
`/commit`, a `CHANGELOG.md` entry per item. On the dev instance apply
0004/0005 and restart the Celery worker afterwards (the model changed).

## Checked and fine

- **Permissions on every view**: `index` (`login_required` + either
  permission, a manager-only user is redirected before anything is read or
  written), `tracked_location` (`basic_access`), `signatures`, `settings`,
  `delete_all` (`manage_settings`). Alliance Auth additionally wraps every
  `url_hook` view in `main_character_required`.
- **Object level / IDOR**: the only object a request names is
  `?character=<id>`; `tracking._token` checks `CharacterOwnership` and the
  token's user before the cache is read. A foreign, negative, zero or
  oversized ID ends in the same generic message. No view takes a row ID.
- **The browser never names a solar system**: the server reads it from ESI.
- **CSRF**: every state-changing request is a POST with `{% csrf_token %}`;
  `delete_all` is `require_POST`; no GET writes to the database (GETs only
  write the 5 s location cache).
- **XSS**: no `mark_safe`, `|safe`, `format_html`, `innerHTML` or
  DataTables render function anywhere. Templates autoescape pasted text,
  ESI names, character names and the Copy payload (`data-` attribute);
  the scripts only use `textContent` and `dataset`. DataTables reads the
  server-rendered, escaped table.
- **Parser limits**: 50,000 characters (form field), 500 non-blank lines
  (`clean_text`), every regex is a single bounded character class with
  `fullmatch` - no nested quantifiers, no catastrophic backtracking.
  Control characters are rejected before splitting; an invalid line is cut
  to 120 printable characters and never stored. Every stored column fits
  its model field (`max_length` 7/20/40/100/30, signal 0-100 with one
  decimal).
- **Raw SQL / `extra` / `eval` / `pickle` / `yaml`**: none. (The cache
  pickles the app's own `Location` dataclass only.)
- **Open redirect**: all redirects go to named URLs; no `next` parameter.
- **ESI tokens**: only existing tokens with `esi-location.read_location.v1`
  are used, filtered by user and character; no token value, access or
  refresh, is logged or sent to the browser. Log lines carry the character
  ID and a traceback.
- **Error messages to the user**: three fixed texts; "not yours" and "no
  token" are deliberately one message.
- **Outgoing requests**: only ESI/SSO through django-esi with fixed
  operations; no webhook, no user-supplied URL (no SSRF).
- **Forms**: `ConfigurationForm` exposes `max_age_days` only, bounded 1-30
  by model validators; `PasteForm` has one field.
- **Admin**: `SignatureAdmin` has no custom actions; `Signature` has no
  default permissions, so only superusers reach it.
- **Rate limit of the paste**: `cache.add` is atomic, per user, checked
  after form validation and before any database work.
- **Concurrent pastes, other than SIG-02**: `_find` locks with
  `select_for_update` inside `transaction.atomic`; the `get_or_create`
  fallback works because Django's MySQL backend defaults to READ COMMITTED
  (`django/db/backends/mysql/base.py`), so the retry after the unique-key
  error sees the other paste's row. If the instance sets
  `isolation_level` to `repeatable read`, that retry can fail with
  `IntegrityError` - not checked, the instance's `local.py` is outside this
  repo.
- **Cleanup task**: one `DELETE`, idempotent, safe to run twice or in
  parallel, safe against a concurrent paste (the paste's row lock makes the
  delete wait and re-check the date).
- **Expiry arithmetic**: `>= cutoff` is live, `< cutoff` is expired, the
  same in `merge`, `system_rows`, `delete_expired` and the Signatures
  template. All datetimes are timezone-aware.
- **Models against migrations**: fields, constraint, options and
  permissions of 0001-0003 match `models.py`; no default or choice comes
  from settings; the migrations touch no foreign table and delete no rows.
- **None / empty cases**: a deleted last checker (`SET_NULL`), a paste of
  only skipped or only invalid lines, a failed location during a POST (the
  check runs without a system, the message is shown), a character ID that
  is no integer.
- **Templates**: every variable used is in the context of its view; the
  filter column indexes of `signatures.html` (0, 1, 3, 4) match the header.
- **JavaScript**: `tracking.js` cannot loop reloads (a reload only happens
  when the server names another system than the page shows, or when the
  tab's stored character differs from the URL); `autocheck.js` submits at
  most once per page; `copy.js` writes text only.
- **Dependencies**: `allianceauth>=5.0,<6`, `django-solo`, `django-esi>=10`;
  no foreign app is imported unguarded beyond these three.
- **`tools/translate.py`**: `subprocess.run` with argument lists, no shell.
  `testauth/settings/local.py` holds a test-only `SECRET_KEY`.
- **By recorded decision, not findings**: one shared list in which any
  member can overwrite an entry (the last checker is stored); the last
  checker's main and the system are visible to every member; a tracked
  paste adopts the ID's row without a system; an untracked paste resolves
  by ID from any system; one foreign-key query per pasted line in `merge`
  (bounded by 500 lines and one check per second).
- **Known and already in `docs/HANDOVER.md`**: README's install line still
  names `@v0.0.1`.

## Implemented

All five items were implemented on 2026-11-13 in the working tree (not
committed), as written above with one difference: SIG-01 and SIG-03 went in
together, so both settings columns are in **one** migration
(`0004_sigcheckerconfiguration_location_retry_seconds_and_more.py`) instead
of 0004 and 0005. Suite without the translation tests: 100 tests, all pass
(85 before). Open at the commit: the new messages for `tools/glossary.py`
(listed in SIG-01, SIG-03 and SIG-05; `Cleanup` is no longer used), and
`docs/HANDOVER.md`.

## Decisions

Made by the user on 2026-11-12, in answer to the questions the first version
of this file asked.

1. **Size of a paste (SIG-03)**: more than 200 new lines in one paste is
   unlikely - limit it to 200 and offer a setting. The Signatures tab stays
   unlimited.
2. **A cap on the growth per user**: not for now. Instead a few statistics
   at the foot of the page, so problems show while the app is in use
   (SIG-05).
3. **Failed location reads (SIG-01)**: wait longer with every failure, up
   to a limit of 60 seconds for now; the limit is a setting, and the way
   there has 5 steps that follow the limit.

## Open questions

None blocks the work. These are choices made while planning; say so if one
should be different.

1. **Statistics: which numbers and for whom?** Planned: the six numbers of
   SIG-05, visible to everybody who can open a page of the app.
   - a) As planned (recommended).
   - b) Only for `manage_settings`: one `{% if perms... %}` around the line.
   - c) Other numbers - name them.
2. **Statistics: "foot of the page" or fixed to the lower edge of the
   window?** Planned: a line below the content, with Alliance Auth's own
   classes.
   - a) Below the content (recommended; the project rule is the Alliance
     Auth style without custom layout).
   - b) Fixed to the window's lower edge: needs CSS of our own in
     `sig-checker.css` and space so it does not cover the table.
3. **Backoff steps: evenly spaced or doubling?** Planned: evenly from 5
   seconds to the limit (5, 19, 33, 46, 60).
   - a) Evenly (recommended: the first retry stays as quick as a good read).
   - b) Doubling down from the limit (4, 8, 15, 30, 60): one line in
     `_retry_seconds`, the first steps are shorter.

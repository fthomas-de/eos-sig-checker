from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from esi.errors import SSOOAuthError
from esi.models import Scope, Token

from eos_sig_checker import tracking
from eos_sig_checker.models import DEFAULT_MAX_AGE_DAYS, NO_SYSTEM, SigCheckerConfiguration, Signature
from eos_sig_checker.parser import parse
from eos_sig_checker.sync import merge, recent_systems, system_rows
from eos_sig_checker.tracking import Location, LocationError, locate, trackable_characters

from .base import DATA_SITE, SCANNED, UNSCANNED, SigTestCase, make_user, set_system_hours

INDEX = reverse("eos_sig_checker:index")
LOCATION = reverse("eos_sig_checker:location")
BASIC_ACCESS = "eos_sig_checker.basic_access"

# the tracking's message box, hidden while the location could be read
ERROR_BOX_SHOWN = 'class="alert alert-danger small py-2 mt-2 mb-0" id="eos-sig-checker-tracking-error"'
ERROR_BOX_HIDDEN = 'class="alert alert-danger small py-2 mt-2 mb-0 d-none" id="eos-sig-checker-tracking-error"'

JITA = Location(30000142, "Jita")
AMARR = Location(30002187, "Amarr")

# a relic site in the client's copy, for a second row of a system
RELIC_SITE = "BXZ-111\tCosmic Signature\tRelic Site\tForgotten Frontier Quarantine Outpost\t100,0%\t2,10 AU"


def add_token(user, character, scopes=(tracking.SCOPE,)):
    token = Token.objects.create(
        user=user,
        character_id=character.character_id,
        character_name=character.character_name,
        character_owner_hash=f"hash-{character.character_id}",
        token_type=Token.TOKEN_TYPE_CHARACTER,
        access_token="access",
        refresh_token="refresh",
    )
    for name in scopes:
        token.scopes.add(Scope.objects.get_or_create(name=name, defaults={"help_text": ""})[0])
    return token


def add_alt(user, name, character_id):
    alt = EveCharacter.objects.create(
        character_id=character_id,
        character_name=name,
        corporation_id=2001,
        corporation_name="Corp 2001",
        corporation_ticker="C2001",
    )
    CharacterOwnership.objects.create(user=user, character=alt, owner_hash=f"hash-{character_id}")
    return alt


class TrackingSyncTestCase(SigTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user("alice").profile.main_character

    def paste(self, text, system=None, now=None):
        return merge(parse(text), self.alice, now=now, system=system)


class TestMergeWithSystem(TrackingSyncTestCase):
    def test_should_store_the_system_with_a_tracked_paste(self):
        (row,) = self.paste(SCANNED, system=JITA)

        signature = Signature.objects.get()
        self.assertEqual((signature.solar_system_id, signature.solar_system_name), (JITA.system_id, "Jita"))
        self.assertEqual(row.system_name, "Jita")

    def test_should_keep_the_same_id_in_two_systems_apart(self):
        self.paste(DATA_SITE, system=JITA)

        (row,) = self.paste(UNSCANNED, system=AMARR)

        self.assertEqual(Signature.objects.count(), 2)
        # the Data Site is in Jita: nothing to resolve in Amarr
        self.assertEqual((row.site_type, row.name, row.resolved), ("", "", set()))

    def test_should_place_a_row_pasted_without_a_system(self):
        self.paste(DATA_SITE)

        (row,) = self.paste(UNSCANNED, system=JITA)

        signature = Signature.objects.get()
        self.assertEqual(signature.solar_system_id, JITA.system_id)
        self.assertEqual(row.name, "Unsecured Frontier Server Bank")
        self.assertEqual(row.resolved, {"site_type", "name"})

    def test_should_resolve_an_untracked_paste_from_a_placed_row(self):
        self.paste(DATA_SITE, system=JITA)

        (row,) = self.paste(UNSCANNED)

        self.assertEqual(row.name, "Unsecured Frontier Server Bank")
        self.assertEqual(row.system_name, "Jita")
        signature = Signature.objects.get()
        # the untracked paste does not know better: the row keeps its system
        self.assertEqual(signature.solar_system_id, JITA.system_id)

    def test_should_not_resolve_an_untracked_paste_from_another_site(self):
        self.paste(DATA_SITE, system=JITA)

        (row,) = self.paste("ACJ-672\tCosmic Signature\tRelic Site\t\t50,0%\t1 AU")

        self.assertEqual((row.site_type, row.name), ("Relic Site", ""))
        self.assertEqual(Signature.objects.count(), 2)
        self.assertEqual(Signature.objects.get(solar_system_id=JITA.system_id).site_type, "Data Site")
        self.assertEqual(Signature.objects.get(solar_system_id=NO_SYSTEM).site_type, "Relic Site")


class TestRecentSystems(TrackingSyncTestCase):
    def test_should_list_each_system_checked_within_the_hours_newest_first(self):
        # not the default 3, so the test fails if the setting is ignored
        set_system_hours(10)
        now = timezone.now()
        self.paste(DATA_SITE, system=JITA, now=now - timedelta(hours=9))
        self.paste(RELIC_SITE, system=JITA, now=now - timedelta(hours=8))
        self.paste(SCANNED, system=AMARR, now=now - timedelta(hours=7))
        self.paste(SCANNED.replace("UDN-422", "OLD-001"), system=Location(30002659, "Dodixie"), now=now - timedelta(hours=10, minutes=1))
        self.paste(UNSCANNED.replace("ACJ-672", "NOS-001"), now=now)

        # Jita twice, newest -8 h; Amarr -7 h; Dodixie too old; no system left out
        self.assertEqual(recent_systems(now), ["Amarr", "Jita"])


class TestSystemRows(TrackingSyncTestCase):
    def test_should_list_the_live_rows_of_the_system_only(self):
        now = timezone.now()
        self.paste(DATA_SITE, system=JITA, now=now)
        self.paste(RELIC_SITE, system=JITA, now=now)
        self.paste(SCANNED, system=JITA, now=now - timedelta(days=DEFAULT_MAX_AGE_DAYS, minutes=1))
        self.paste("XYZ-999\tCosmic Signature\tRelic Site\tRuined Sansha Crystal Quarry\t100,0%\t1 AU", system=AMARR, now=now)

        rows = system_rows(JITA, skip_ids=["BXZ-111"], now=now)

        self.assertEqual([row.line.signature_id for row in rows], ["ACJ-672"])
        (row,) = rows
        self.assertFalse(row.pasted)
        self.assertEqual(row.line.signal_text, "100,0%")
        self.assertEqual(row.previous_by, self.alice.character_name)


class TestTrackableCharacters(SigTestCase):
    def test_should_offer_own_characters_with_the_scope_only(self):
        user = make_user("alice")
        main = user.profile.main_character
        alt = add_alt(user, "alice alt", 9001)
        no_scope = add_alt(user, "alice no scope", 9002)
        add_token(user, main)
        add_token(user, alt)
        add_token(user, no_scope, scopes=("esi-skills.read_skills.v1",))
        # a token whose character now belongs to somebody else. Saving the
        # token hands the character to alice (AA's ownership signal); bob
        # takes it back the way a later login of his would.
        other = make_user("bob")
        add_token(user, other.profile.main_character)
        CharacterOwnership.objects.filter(character=other.profile.main_character).update(user=other)

        names = [character.character_name for character in trackable_characters(user)]

        self.assertEqual(names, ["alice alt", "alice main"])


class TestLocate(SigTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("alice")
        self.main = self.user.profile.main_character
        patch = mock.patch.object(tracking, "esi")
        self.esi = patch.start()
        self.addCleanup(patch.stop)
        self.esi.client.Location.GetCharactersCharacterIdLocation.return_value.result.return_value = SimpleNamespace(
            solar_system_id=JITA.system_id
        )
        self.esi.client.Universe.GetUniverseSystemsSystemId.return_value.result.return_value = SimpleNamespace(
            name="Jita"
        )

    def test_should_read_the_system_with_the_characters_token(self):
        token = add_token(self.user, self.main)

        self.assertEqual(locate(self.user, self.main.character_id), JITA)
        self.esi.client.Location.GetCharactersCharacterIdLocation.assert_called_once_with(
            character_id=self.main.character_id, token=token
        )

    def test_should_ask_esi_once_within_its_cache_time(self):
        add_token(self.user, self.main)

        locate(self.user, self.main.character_id)
        locate(self.user, self.main.character_id)

        self.assertEqual(self.esi.client.Location.GetCharactersCharacterIdLocation.call_count, 1)

    def test_should_refuse_a_character_without_token(self):
        with self.assertRaises(LocationError):
            locate(self.user, self.main.character_id)
        self.esi.client.Location.GetCharactersCharacterIdLocation.assert_not_called()

    def test_should_not_hand_out_the_cached_location_of_another_users_character(self):
        add_token(self.user, self.main)
        locate(self.user, self.main.character_id)

        with self.assertRaises(LocationError):
            locate(make_user("mallory"), self.main.character_id)

    def test_should_turn_an_esi_failure_into_a_location_error(self):
        add_token(self.user, self.main)
        self.esi.client.Location.GetCharactersCharacterIdLocation.return_value.result.side_effect = OSError("down")

        with self.assertRaisesMessage(LocationError, "Try again"):
            locate(self.user, self.main.character_id)

    def test_should_ask_for_a_new_token_when_sso_refuses_the_old_one(self):
        add_token(self.user, self.main)
        self.esi.client.Location.GetCharactersCharacterIdLocation.return_value.result.side_effect = SSOOAuthError(
            "invalid_grant", "Invalid refresh token. Token missing/expired."
        )

        with self.assertRaisesMessage(LocationError, "no longer valid"):
            locate(self.user, self.main.character_id)

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


class TestTrackingViews(SigTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("alice", BASIC_ACCESS)
        self.main = self.user.profile.main_character
        self.client.force_login(self.user)
        self.tracked = f"{INDEX}?character={self.main.character_id}"

    def locate_in(self, location):
        patch = mock.patch.object(tracking, "locate", return_value=location)
        patch.start()
        self.addCleanup(patch.stop)

    def test_should_hint_at_the_scope_without_a_token(self):
        response = self.client.get(INDEX)

        self.assertContains(response, tracking.SCOPE)
        self.assertContains(response, 'id="eos-sig-checker-tracking-switch" disabled')

    def test_should_offer_characters_with_a_token_and_start_switched_off(self):
        add_token(self.user, self.main)

        response = self.client.get(INDEX)

        self.assertContains(response, f'<option value="{self.main.character_id}">alice main</option>')
        self.assertContains(response, 'id="eos-sig-checker-tracking-switch">')
        self.assertContains(response, "eos_sig_checker/js/tracking.")

    def test_should_show_the_known_signatures_of_the_system_without_a_paste(self):
        merge(parse(DATA_SITE), self.main, system=JITA)
        self.locate_in(JITA)

        response = self.client.get(self.tracked)

        self.assertContains(response, "Unsecured Frontier Server Bank")
        self.assertContains(response, 'data-eos-sig-checker-system="30000142"')
        self.assertNotContains(response, "not in this paste")

    def test_should_show_the_position_and_hide_the_message_box(self):
        add_token(self.user, self.main)
        self.locate_in(JITA)

        response = self.client.get(self.tracked)

        self.assertContains(response, 'id="eos-sig-checker-tracking-system">Jita</strong>')
        self.assertContains(response, ERROR_BOX_HIDDEN)

    def test_should_show_the_message_of_a_character_that_cannot_be_tracked(self):
        # no token at all: the page has no dropdown, the message must show anyway
        response = self.client.get(self.tracked)

        self.assertContains(response, ERROR_BOX_SHOWN)
        self.assertContains(response, "This character cannot be tracked")

    def test_should_store_a_paste_in_the_tracked_system_and_add_the_rest(self):
        merge(parse(RELIC_SITE), self.main, system=JITA)
        self.locate_in(JITA)

        response = self.client.post(self.tracked, {"text": DATA_SITE})

        self.assertEqual(Signature.objects.get(signature_id="ACJ-672").solar_system_id, JITA.system_id)
        ids = [row.line.signature_id for row in response.context["output"]]
        self.assertEqual(ids, ["ACJ-672", "BXZ-111"])
        self.assertContains(response, "not in this paste", count=1)

    def test_should_check_without_a_system_when_the_location_fails(self):
        add_token(self.user, self.main)
        with mock.patch.object(tracking, "locate", side_effect=LocationError("no location")):
            response = self.client.post(self.tracked, {"text": DATA_SITE})

        self.assertContains(response, ERROR_BOX_SHOWN)
        self.assertContains(response, "<span>no location</span>")
        self.assertContains(response, 'id="eos-sig-checker-tracking-system">unknown</strong>')
        self.assertEqual(Signature.objects.get().solar_system_id, NO_SYSTEM)

    def test_should_answer_the_location_as_json(self):
        self.locate_in(JITA)

        response = self.client.get(LOCATION, {"character": self.main.character_id})

        self.assertEqual(response.json(), {"system_id": JITA.system_id, "system_name": "Jita"})

    def test_should_answer_a_location_error_as_json(self):
        with mock.patch.object(tracking, "locate", side_effect=LocationError("no location")):
            response = self.client.get(LOCATION, {"character": self.main.character_id})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "no location"})

    def test_should_refuse_a_location_without_character(self):
        self.assertEqual(self.client.get(LOCATION).status_code, 400)

    def test_should_refuse_the_location_without_basic_access(self):
        self.client.force_login(make_user("bob"))

        response = self.client.get(LOCATION, {"character": self.main.character_id})

        self.assertNotEqual(response.status_code, 200)

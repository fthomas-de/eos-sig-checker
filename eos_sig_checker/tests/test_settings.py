from django.contrib.messages import get_messages
from django.test import RequestFactory
from django.urls import reverse

from allianceauth.eveonline.models import EveCharacter

from eos_sig_checker.auth_hooks import SigCheckerMenuItem
from eos_sig_checker.models import (
    DEFAULT_ERROR_LOG_DAYS,
    DEFAULT_LOCATION_RETRY_SECONDS,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_MAX_LINES,
    DEFAULT_SYSTEM_HOURS,
    DEFAULT_WORMHOLE_HOURS,
    SigCheckerConfiguration,
    Signature,
)
from eos_sig_checker.parser import parse
from eos_sig_checker.sync import merge

from .base import SCANNED, UNSCANNED, SigTestCase, make_user, set_max_age_days

INDEX = reverse("eos_sig_checker:index")
SETTINGS = reverse("eos_sig_checker:settings")
DELETE_ALL = reverse("eos_sig_checker:delete_all")

BASIC_ACCESS = "eos_sig_checker.basic_access"
MANAGE_SETTINGS = "eos_sig_checker.manage_settings"

# what the settings form needs to be valid; a test overrides what it is about
VALID = {
    "max_age_days": DEFAULT_MAX_AGE_DAYS,
    "location_retry_seconds": DEFAULT_LOCATION_RETRY_SECONDS,
    "max_lines": DEFAULT_MAX_LINES,
    "wormhole_hours": DEFAULT_WORMHOLE_HOURS,
    "system_hours": DEFAULT_SYSTEM_HOURS,
    "error_log_days": DEFAULT_ERROR_LOG_DAYS,
}


class TestSettingsPage(SigTestCase):
    def setUp(self):
        super().setUp()
        self.manager = make_user("alice", MANAGE_SETTINGS)
        self.client.force_login(self.manager)

    def test_should_refuse_a_user_with_basic_access_only(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))

        response = self.client.post(SETTINGS, {**VALID, "max_age_days":2})

        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, DEFAULT_MAX_AGE_DAYS)

    def test_should_open_with_manage_settings_alone(self):
        response = self.client.get(SETTINGS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["max_age_days"].value(), DEFAULT_MAX_AGE_DAYS)

    def test_should_store_the_days(self):
        response = self.client.post(SETTINGS, {**VALID, "max_age_days":2})

        self.assertRedirects(response, SETTINGS)
        self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, 2)

    def test_should_refuse_days_out_of_range(self):
        for days in (0, 31, -1, "", "x"):
            with self.subTest(days):
                response = self.client.post(SETTINGS, {**VALID, "max_age_days":days})

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, DEFAULT_MAX_AGE_DAYS)

    def test_should_accept_the_bounds(self):
        for days in (1, 30):
            with self.subTest(days):
                self.client.post(SETTINGS, {**VALID, "max_age_days":days})

                self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, days)

    def test_should_hand_the_bounds_to_the_browser(self):
        response = self.client.get(SETTINGS)

        self.assertContains(response, 'min="1"')
        self.assertContains(response, 'max="30"')
        self.assertContains(response, 'min="5"')
        self.assertContains(response, 'max="3600"')
        self.assertContains(response, 'max="500"')
        self.assertContains(response, 'max="48"')

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

    def test_should_store_the_lines_per_paste(self):
        self.client.post(SETTINGS, {**VALID, "max_lines": 50})

        self.assertEqual(SigCheckerConfiguration.get_solo().max_lines, 50)

    def test_should_refuse_lines_out_of_range(self):
        for lines in (0, 501, "", "x"):
            with self.subTest(lines):
                response = self.client.post(SETTINGS, {**VALID, "max_lines": lines})

                self.assertTrue(response.context["form"].errors)
                self.assertEqual(SigCheckerConfiguration.get_solo().max_lines, DEFAULT_MAX_LINES)

    def test_should_store_the_wormhole_hours(self):
        self.client.post(SETTINGS, {**VALID, "wormhole_hours": 48})

        self.assertEqual(SigCheckerConfiguration.get_solo().wormhole_hours, 48)

    def test_should_store_the_system_hours(self):
        self.client.post(SETTINGS, {**VALID, "system_hours": 48})

        self.assertEqual(SigCheckerConfiguration.get_solo().system_hours, 48)

    def test_should_refuse_system_hours_out_of_range(self):
        for hours in (0, 49, "", "x"):
            with self.subTest(hours):
                response = self.client.post(SETTINGS, {**VALID, "system_hours": hours})

                self.assertTrue(response.context["form"].errors)

    def test_should_refuse_wormhole_hours_out_of_range(self):
        for hours in (0, 49, "", "x"):
            with self.subTest(hours):
                response = self.client.post(SETTINGS, {**VALID, "wormhole_hours": hours})

                self.assertTrue(response.context["form"].errors)
                self.assertEqual(SigCheckerConfiguration.get_solo().wormhole_hours, DEFAULT_WORMHOLE_HOURS)

    def test_index_should_send_a_settings_only_user_to_the_settings(self):
        response = self.client.get(INDEX)

        self.assertRedirects(response, SETTINGS)

    def test_index_should_show_the_days_from_the_settings_page(self):
        set_max_age_days(3)
        self.client.force_login(make_user("bob", BASIC_ACCESS))

        response = self.client.get(INDEX)

        self.assertEqual(response.context["max_age_days"], 3)
        self.assertContains(response, "count for 3 days after their last check")

    def test_index_should_show_the_settings_tab_only_to_managers(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))
        self.assertNotContains(self.client.get(INDEX), f'href="{SETTINGS}"')

        self.client.force_login(make_user("carol", BASIC_ACCESS, MANAGE_SETTINGS))
        self.assertContains(self.client.get(INDEX), f'href="{SETTINGS}"')


class TestMenu(SigTestCase):
    def render(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return SigCheckerMenuItem().render(request)

    def test_should_show_the_menu_with_either_permission(self):
        for name, perm in (("bob", BASIC_ACCESS), ("carol", MANAGE_SETTINGS)):
            with self.subTest(perm):
                self.assertTrue(self.render(make_user(name, perm)))

    def test_should_hide_the_menu_without_permission(self):
        self.assertEqual(self.render(make_user("mallory")), "")


class TestDeleteAll(SigTestCase):
    def setUp(self):
        super().setUp()
        self.manager = make_user("alice", MANAGE_SETTINGS)
        self.client.force_login(self.manager)
        merge(parse(f"{SCANNED}\n{UNSCANNED}"), self.manager.profile.main_character)

    def test_should_delete_every_signature(self):
        response = self.client.post(DELETE_ALL)

        self.assertRedirects(response, SETTINGS)
        self.assertFalse(Signature.objects.exists())
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)], ["Deleted 2 signatures."])

    def test_should_leave_the_characters_alone(self):
        self.client.post(DELETE_ALL)

        self.assertTrue(EveCharacter.objects.filter(pk=self.manager.profile.main_character.pk).exists())

    def test_should_refuse_a_get(self):
        response = self.client.get(DELETE_ALL)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Signature.objects.count(), 2)

    def test_should_refuse_a_user_with_basic_access_only(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))

        response = self.client.post(DELETE_ALL)

        # sent to the login, not back to the settings as after a deletion
        self.assertNotEqual(response.get("Location"), SETTINGS)
        self.assertEqual(Signature.objects.count(), 2)

    def test_should_show_the_count_and_the_confirmation(self):
        response = self.client.get(SETTINGS)

        self.assertEqual(response.context["signature_count"], 2)
        # the visible button only opens the modal; the modal's form posts
        self.assertContains(response, 'data-bs-target="#eos-sig-checker-delete-all"')
        self.assertContains(response, f'action="{DELETE_ALL}"')

from django.contrib.messages import get_messages
from django.test import RequestFactory
from django.urls import reverse

from allianceauth.eveonline.models import EveCharacter

from eos_sig_checker.auth_hooks import SigCheckerMenuItem
from eos_sig_checker.models import DEFAULT_MAX_AGE_DAYS, SigCheckerConfiguration, Signature
from eos_sig_checker.parser import parse
from eos_sig_checker.sync import merge

from .base import SCANNED, UNSCANNED, SigTestCase, make_user, set_max_age_days

INDEX = reverse("eos_sig_checker:index")
SETTINGS = reverse("eos_sig_checker:settings")
DELETE_ALL = reverse("eos_sig_checker:delete_all")

BASIC_ACCESS = "eos_sig_checker.basic_access"
MANAGE_SETTINGS = "eos_sig_checker.manage_settings"


class TestSettingsPage(SigTestCase):
    def setUp(self):
        super().setUp()
        self.manager = make_user("alice", MANAGE_SETTINGS)
        self.client.force_login(self.manager)

    def test_should_refuse_a_user_with_basic_access_only(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))

        response = self.client.post(SETTINGS, {"max_age_days": 2})

        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, DEFAULT_MAX_AGE_DAYS)

    def test_should_open_with_manage_settings_alone(self):
        response = self.client.get(SETTINGS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["max_age_days"].value(), DEFAULT_MAX_AGE_DAYS)

    def test_should_store_the_days(self):
        response = self.client.post(SETTINGS, {"max_age_days": 2})

        self.assertRedirects(response, SETTINGS)
        self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, 2)

    def test_should_refuse_days_out_of_range(self):
        for days in (0, 31, -1, "", "x"):
            with self.subTest(days):
                response = self.client.post(SETTINGS, {"max_age_days": days})

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, DEFAULT_MAX_AGE_DAYS)

    def test_should_accept_the_bounds(self):
        for days in (1, 30):
            with self.subTest(days):
                self.client.post(SETTINGS, {"max_age_days": days})

                self.assertEqual(SigCheckerConfiguration.get_solo().max_age_days, days)

    def test_should_hand_the_bounds_to_the_browser(self):
        response = self.client.get(SETTINGS)

        self.assertContains(response, 'min="1"')
        self.assertContains(response, 'max="30"')

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

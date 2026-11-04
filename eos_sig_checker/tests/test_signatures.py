from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from eos_sig_checker.models import DEFAULT_MAX_AGE_DAYS
from eos_sig_checker.parser import parse
from eos_sig_checker.sync import merge

from .base import DATA_SITE, SCANNED, UNSCANNED, SigTestCase, make_user

INDEX = reverse("eos_sig_checker:index")
SIGNATURES = reverse("eos_sig_checker:signatures")

BASIC_ACCESS = "eos_sig_checker.basic_access"
MANAGE_SETTINGS = "eos_sig_checker.manage_settings"


class TestSignatures(SigTestCase):
    def setUp(self):
        super().setUp()
        self.manager = make_user("alice", MANAGE_SETTINGS)
        self.client.force_login(self.manager)
        main = self.manager.profile.main_character
        now = timezone.now()
        merge(parse(SCANNED), main, now=now - timedelta(days=DEFAULT_MAX_AGE_DAYS, minutes=1))
        merge(parse(UNSCANNED), main, now=now - timedelta(hours=1))
        merge(parse(DATA_SITE), main, now=now)

    def rows(self, response):
        return [signature.signature_id for signature in response.context["signatures"]]

    def test_should_refuse_a_user_with_basic_access_only(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))

        response = self.client.get(SIGNATURES)

        self.assertNotEqual(response.status_code, 200)

    def test_should_list_every_row_last_checked_first(self):
        response = self.client.get(SIGNATURES)

        self.assertEqual(response.status_code, 200)
        # ACJ-672 once: the second paste merged into the first
        self.assertEqual(self.rows(response), ["ACJ-672", "UDN-422"])
        self.assertContains(response, "Unsecured Frontier Server")
        self.assertContains(response, "alice main")

    def test_should_mark_only_expired_rows(self):
        response = self.client.get(SIGNATURES)

        self.assertContains(response, 'class="opacity-50"', count=1)
        self.assertContains(response, ">expired</span>", count=1)
        html = response.content.decode()
        self.assertLess(html.index('class="opacity-50"'), html.index("UDN-422"))
        self.assertGreater(html.index('class="opacity-50"'), html.index("ACJ-672"))

    def test_should_sort_the_signal_as_a_number_and_colour_it(self):
        response = self.client.get(SIGNATURES)

        self.assertContains(response, 'eos-sig-checker-signal-full" data-order="100.0"')

    def test_should_offer_a_filter_for_id_group_and_name(self):
        response = self.client.get(SIGNATURES)

        for column in (0, 2, 3):
            self.assertContains(response, f'data-eos-sig-checker-column="{column}"')
        # sri_static hashes the file name
        self.assertContains(response, "eos_sig_checker/js/signatures.")

    def test_should_show_the_tab_only_to_managers(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))
        self.assertNotContains(self.client.get(INDEX), f'href="{SIGNATURES}"')

        self.client.force_login(make_user("carol", BASIC_ACCESS, MANAGE_SETTINGS))
        self.assertContains(self.client.get(INDEX), f'href="{SIGNATURES}"')

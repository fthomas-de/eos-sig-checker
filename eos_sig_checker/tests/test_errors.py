from datetime import timedelta

from django.urls import reverse
from django.utils import timezone, translation

from eos_sig_checker.models import SigCheckerConfiguration
from eos_sig_checker.models import RejectedLine, Signature
from eos_sig_checker.parser import parse
from eos_sig_checker.sync import log_rejected
from eos_sig_checker.tasks import delete_expired_signatures

from .base import FOREIGN, SCANNED, SigTestCase, make_user, store_client_texts
from .test_settings import SETTINGS, VALID

INDEX = reverse("eos_sig_checker:index")
ERRORS = reverse("eos_sig_checker:errors")
DELETE_ERRORS = reverse("eos_sig_checker:delete_errors")

BASIC_ACCESS = "eos_sig_checker.basic_access"
MANAGE_SETTINGS = "eos_sig_checker.manage_settings"

BROKEN = "ABC-123\tCosmic Signature\t\t\t50\t1 AU"
SHIP = "XYZ-123\tShip\tFrigate\tHeron\t100,0%\t2 AU"


class TestLogRejected(SigTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("alice", BASIC_ACCESS)
        self.client.force_login(self.user)

    def test_should_log_only_the_rejected_lines_of_a_paste(self):
        self.client.post(INDEX, {"text": f"{SCANNED}\n{SHIP}\n{BROKEN}"})

        (line,) = RejectedLine.objects.all()
        self.assertEqual(line.text, BROKEN.replace("\t", " "))
        self.assertEqual(line.character, self.user.profile.main_character)
        self.assertIn("percentage", line.reason)

    def test_should_log_a_name_another_client_wrote_that_has_no_english(self):
        store_client_texts()
        line = "REB-508\tSignature cosmique\tSite de combat\tSite inconnu\t100,0 %\t6,62 UA"

        self.client.post(INDEX, {"text": f"{line}\n{FOREIGN['fr'].replace('REB-508', 'REB-509')}"})

        logged = RejectedLine.objects.get()
        self.assertEqual(logged.reason, "Name not translated: Site inconnu (not in the client texts)")
        self.assertEqual(logged.text, line.replace("\t", " "))
        signature = Signature.objects.get(signature_id="REB-508")
        self.assertEqual((signature.group, signature.site_type, signature.name), ("Cosmic Signature", "Combat Site", ""))
        self.assertTrue(Signature.objects.filter(signature_id="REB-509").exists())

    def test_should_store_the_reason_in_english(self):
        with translation.override("de"):
            rows = parse(BROKEN)
            log_rejected(rows, self.user.profile.main_character)
            shown = str(rows[0].error)

        self.assertNotEqual(shown, RejectedLine.objects.get().reason)
        self.assertIn("percentage", RejectedLine.objects.get().reason)


class TestErrorsPage(SigTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("alice", MANAGE_SETTINGS))
        log_rejected(parse(BROKEN), None)

    def test_should_list_the_rejected_lines(self):
        response = self.client.get(ERRORS)

        self.assertContains(response, "ABC-123 Cosmic Signature")
        self.assertContains(response, 'data-bs-target="#eos-sig-checker-delete-errors"')

    def test_should_refuse_a_user_with_basic_access_only(self):
        self.client.force_login(make_user("bob", BASIC_ACCESS))

        self.assertNotEqual(self.client.get(ERRORS).status_code, 200)
        self.client.post(DELETE_ERRORS)
        self.assertTrue(RejectedLine.objects.exists())

    def test_should_show_the_tab_to_managers_only(self):
        self.assertContains(self.client.get(SETTINGS), f'href="{ERRORS}"')

        self.client.force_login(make_user("bob", BASIC_ACCESS))
        self.assertNotContains(self.client.get(INDEX), f'href="{ERRORS}"')

    def test_should_delete_all_rejected_lines(self):
        response = self.client.post(DELETE_ERRORS)

        self.assertRedirects(response, ERRORS)
        self.assertFalse(RejectedLine.objects.exists())

    def test_should_refuse_a_get_on_delete(self):
        self.assertEqual(self.client.get(DELETE_ERRORS).status_code, 405)
        self.assertTrue(RejectedLine.objects.exists())


class TestErrorLogDays(SigTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("alice", MANAGE_SETTINGS))

    def test_should_store_the_days(self):
        self.client.post(SETTINGS, {**VALID, "error_log_days": 30})

        self.assertEqual(SigCheckerConfiguration.get_solo().error_log_days, 30)

    def test_should_refuse_days_out_of_range(self):
        for days in (0, 31, "", "x"):
            with self.subTest(days):
                response = self.client.post(SETTINGS, {**VALID, "error_log_days": days})

                self.assertTrue(response.context["form"].errors)

    def test_cleanup_should_follow_the_setting(self):
        config = SigCheckerConfiguration.get_solo()
        config.error_log_days = 2
        config.save()
        now = timezone.now()
        log_rejected(parse(BROKEN), None, now=now - timedelta(days=2, minutes=1))
        log_rejected(parse(BROKEN), None, now=now - timedelta(days=1))

        delete_expired_signatures()

        self.assertEqual(RejectedLine.objects.count(), 1)

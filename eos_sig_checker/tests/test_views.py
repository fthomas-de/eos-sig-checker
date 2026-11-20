from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from eos_sig_checker.models import SigCheckerConfiguration, Signature
from eos_sig_checker.parser import MAX_CHARS, MAX_LINES

from .base import ANOMALY, DATA_SITE, FOREIGN, SCANNED, UNSCANNED, WORMHOLE, SigTestCase, make_user, store_client_texts

URL = reverse("eos_sig_checker:index")


class TestIndex(SigTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("alice", "eos_sig_checker.basic_access")
        self.client.force_login(self.user)

    def test_should_refuse_a_user_without_permission(self):
        self.client.force_login(make_user("mallory"))

        response = self.client.post(URL, {"text": SCANNED})

        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(Signature.objects.exists())

    def test_should_show_the_empty_form(self):
        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["output"])

    def test_should_show_the_hours_of_the_system_list(self):
        response = self.client.get(URL)

        self.assertContains(response, "Systems (3 h)")
        self.assertContains(response, "No system checked in the last 3 hours.")

    def test_should_list_the_wormhole_of_this_paste(self):
        response = self.client.get(URL)
        self.assertContains(response, "No wormhole checked in the last 3 hours.")

        response = self.client.post(URL, {"text": f"{WORMHOLE}\n{SCANNED}"})

        self.assertEqual([wormhole.signature_id for wormhole in response.context["wormholes"]], ["KJH-123"])
        self.assertNotContains(response, "No wormhole checked")

    def test_should_return_every_line_completed_from_the_list(self):
        self.client.post(URL, {"text": DATA_SITE})
        cache.clear()  # past the one-check-per-second limit

        response = self.client.post(URL, {"text": f"{SCANNED}\n{UNSCANNED}\nbroken"})

        self.assertEqual(len(response.context["output"]), 3)
        self.assertContains(response, "Unsecured Frontier Server Bank")
        self.assertContains(response, "table-success")
        self.assertContains(response, "table-danger")
        # the copy text keeps the client's format and leaves the invalid line out
        self.assertEqual(
            response.context["copy_text"],
            f"{SCANNED}\nACJ-672\tCosmic Signature\tData Site\tUnsecured Frontier Server Bank\t100,0%\t10,61 AU",
        )

    def test_should_empty_the_box_after_a_check(self):
        response = self.client.post(URL, {"text": f"{SCANNED}\nbroken"})

        self.assertFalse(response.context["form"].is_bound)
        self.assertEqual(len(response.context["output"]), 2)

    def test_should_keep_the_box_when_the_check_is_refused(self):
        self.client.post(URL, {"text": SCANNED})

        response = self.client.post(URL, {"text": UNSCANNED})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.context["form"]["text"].value(), UNSCANNED)

    def test_should_leave_the_distance_out_of_the_result(self):
        response = self.client.post(URL, {"text": SCANNED})

        self.assertNotContains(response, ">Distance<")
        self.assertNotContains(response, "<td class=\"text-end text-nowrap\">10,63 AU</td>", html=False)
        # Copy keeps the probe scanner's format, distance included
        self.assertIn("10,63 AU", response.context["copy_text"])

    def test_should_skip_anomalies(self):
        response = self.client.post(URL, {"text": f"{ANOMALY}\n{UNSCANNED}"})

        self.assertEqual(response.context["skipped"], 1)
        self.assertEqual(response.context["copy_text"], UNSCANNED)
        self.assertFalse(Signature.objects.filter(signature_id="UDN-422").exists())

    def test_should_colour_the_signal(self):
        response = self.client.post(URL, {"text": f"{SCANNED}\n{UNSCANNED}"})

        self.assertContains(response, "eos-sig-checker-signal-full")
        self.assertContains(response, "eos-sig-checker-signal-low")

    def test_should_complete_a_line_of_another_client_from_the_list(self):
        store_client_texts()
        self.client.post(URL, {"text": DATA_SITE.replace("ACJ-672", "REB-508")})
        cache.clear()

        response = self.client.post(URL, {"text": FOREIGN["fr"]})

        (row,) = response.context["output"]
        self.assertEqual((row.line.group, row.site_type, row.name), ("Cosmic Signature", "Data Site", "Unsecured Frontier Server Bank"))
        self.assertEqual(row.resolved, {"site_type", "name"})
        # Copy holds English: the list is English for everybody
        self.assertEqual(response.context["copy_text"], "REB-508\tCosmic Signature\tData Site\tUnsecured Frontier Server Bank\t100,0%\t6,62 UA")

    def test_should_show_the_result_and_copy_in_the_readers_language(self):
        store_client_texts({
            ("de", "Cosmic Signature", "Kosmische Signatur"),
            ("de", "Data Site", "Datengebiet"),
            ("de", "Unsecured Frontier Server Bank", "Ungesicherte Server-Datenbank im Grenzgebiet"),
        })
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "de"

        response = self.client.post(URL, {"text": DATA_SITE})

        self.assertContains(response, "<td>Datengebiet</td>", html=True)
        self.assertContains(response, "Ungesicherte Server-Datenbank im Grenzgebiet")
        self.assertEqual(
            response.context["copy_text"],
            "ACJ-672\tKosmische Signatur\tDatengebiet\tUngesicherte Server-Datenbank im Grenzgebiet\t100,0%\t3,20 AU",
        )
        # the list keeps English
        self.assertEqual(Signature.objects.get(signature_id="ACJ-672").site_type, "Data Site")

    def test_should_keep_english_without_client_texts(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "nl-nl"

        response = self.client.post(URL, {"text": DATA_SITE})

        self.assertEqual(response.context["copy_text"], DATA_SITE)

    def test_should_skip_another_client_until_its_texts_are_imported(self):
        response = self.client.post(URL, {"text": FOREIGN["ja"]})

        self.assertEqual(response.context["skipped"], 1)

    def test_should_count_skipped_lines_only(self):
        ship = "XYZ-123\tShip\tFrigate\tHeron\t100,0%\t2 AU"

        response = self.client.post(URL, {"text": f"{SCANNED}\n{ship}\n{ship}"})

        self.assertEqual(response.context["skipped"], 2)
        # the result holds only the signature
        self.assertEqual([row.line.signature_id for row in response.context["output"]], ["UDN-422"])
        self.assertNotIn("Heron", response.context["copy_text"])
        self.assertContains(response, "2 lines skipped")

    def test_should_say_so_when_every_line_is_skipped(self):
        response = self.client.post(URL, {"text": "ABC-123\tKosmische Signatur\t\t\t0,0%\t1 AU"})

        self.assertContains(response, "1 line skipped")

    def test_should_refuse_a_second_check_within_a_second(self):
        self.client.post(URL, {"text": SCANNED})

        response = self.client.post(URL, {"text": DATA_SITE})

        self.assertEqual(response.status_code, 429)
        self.assertIsNone(response.context["output"])
        self.assertContains(response, "Too many checks", status_code=429)
        # the paste stays in the box for the next try
        self.assertContains(response, "Unsecured Frontier Server Bank", status_code=429)
        self.assertFalse(Signature.objects.filter(signature_id="ACJ-672").exists())

    def test_should_check_again_once_the_second_is_over(self):
        self.client.post(URL, {"text": SCANNED})
        cache.clear()  # what the expiring key does after a second

        response = self.client.post(URL, {"text": DATA_SITE})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Signature.objects.filter(signature_id="ACJ-672").exists())

    def test_should_limit_each_user_on_their_own(self):
        self.client.post(URL, {"text": SCANNED})
        self.client.force_login(make_user("bob", "eos_sig_checker.basic_access"))

        response = self.client.post(URL, {"text": DATA_SITE})

        self.assertEqual(response.status_code, 200)

    def test_should_not_count_a_refused_paste(self):
        # an oversized paste writes nothing, so it must not block the next one
        self.client.post(URL, {"text": "x" * (MAX_CHARS + 1)})

        response = self.client.post(URL, {"text": SCANNED})

        self.assertEqual(response.status_code, 200)

    def test_should_hand_the_interval_to_the_page(self):
        response = self.client.get(URL)

        self.assertContains(response, 'data-eos-sig-checker-interval="1000"')
        # the manifest storage puts a hash into the name: autocheck.<hash>.js
        self.assertContains(response, "eos_sig_checker/js/autocheck.")

    def test_should_escape_an_invalid_line(self):
        response = self.client.post(URL, {"text": "<script>alert(1)</script>"})

        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_should_refuse_an_oversized_paste_without_storing(self):
        too_many = "\n".join(f"ABC-{i:03d}\tCosmic Signature\t\t\t0,0%\t1 AU" for i in range(MAX_LINES + 1))
        too_long = "x" * (MAX_CHARS + 1)
        for text in (too_many, too_long):
            with self.subTest(len(text)):
                response = self.client.post(URL, {"text": text})
                self.assertIsNone(response.context["output"])
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(Signature.objects.exists())

    def test_should_keep_the_trailing_tabs_of_an_unscanned_line(self):
        self.client.post(URL, {"text": UNSCANNED})

        self.assertTrue(Signature.objects.filter(signature_id="ACJ-672").exists())

    def test_should_record_the_main_as_last_checker(self):
        self.client.post(URL, {"text": SCANNED})

        self.assertEqual(Signature.objects.get().last_checked_by, self.user.profile.main_character)

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

    def test_should_show_the_statistics_below_the_page(self):
        self.client.post(URL, {"text": SCANNED})

        response = self.client.get(URL)

        self.assertEqual(response.context["statistics"]["total"], 1)
        self.assertContains(response, "new in 24 h")
        self.assertNotContains(response, "the cleanup task does not run")

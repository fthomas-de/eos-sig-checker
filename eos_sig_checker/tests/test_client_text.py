import json
from io import StringIO
from unittest import mock

import requests

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.urls import reverse

from eos_sig_checker import client_text, tasks
from eos_sig_checker.client_text import ClientTextError, display, lookup, pairs, store, update
from eos_sig_checker.models import ClientText, ClientTextLanguage
from eos_sig_checker.tasks import update_client_texts

from .base import SigTestCase, make_user

SETTINGS = reverse("eos_sig_checker:settings")
UPDATE_NOW = reverse("eos_sig_checker:client_texts_update")


def entry(english, german):
    return {"en": english, "de": german}


class TestPairs(SigTestCase):
    def test_should_keep_a_translated_name(self):
        found = pairs({"1": entry("Combat Site", "Kampfgebiet"), "2": entry("Sansha Den", "Sansha-Höhle")}, "de")

        self.assertEqual(found, {("Combat Site", "Kampfgebiet"), ("Sansha Den", "Sansha-Höhle")})

    def test_should_keep_an_untranslated_text(self):
        # the client shows the English there, and a paste of it must find it
        found = pairs({"1": entry("Unstable Wormhole", "Unstable Wormhole")}, "de")

        self.assertEqual(found, {("Unstable Wormhole", "Unstable Wormhole")})

    def test_should_leave_out_what_is_unsafe(self):
        others = {
            "English no name": entry("Warp to %(name)s", "Warpen zu %(name)s"),
            "markup": entry("Data Site", "<b>Datengebiet</b>"),
            "control character": entry("Gas Site", "Gas\x1fgebiet"),
            "tab": entry("Ore Site", "Mineralien\tgebiet"),
            "too long": entry("Relic Site", "R" * 201),
            "not a string": entry("Wormhole", 7),
            "missing language": {"en": "Cosmic Signature"},
        }
        for reason, value in others.items():
            with self.subTest(reason):
                self.assertEqual(pairs({"1": value}, "de"), set())

    def test_should_skip_entries_that_are_no_object(self):
        self.assertEqual(pairs({"1": "Combat Site", "2": None, "3": entry("Data Site", "Datengebiet")}, "de"),
                         {("Data Site", "Datengebiet")})

    def test_should_keep_every_meaning_once(self):
        found = pairs({
            "1": {"en": "Wormhole", "ja": "ワームホール"},
            "2": {"en": "Wormholes", "ja": "ワームホール"},
            "3": {"en": "Unsecured Frontier Server Bank", "ja": "注意すべき辺境地域のサーバーバンク"},
            "4": {"en": "Unsecured Frontier Server Bank", "ja": "未保護の辺境地域サーバーバンク"},
            "5": {"en": "Wormhole", "ja": "ワームホール"},
        }, "ja")

        self.assertEqual(found, {
            ("Wormhole", "ワームホール"),
            ("Wormholes", "ワームホール"),
            ("Unsecured Frontier Server Bank", "注意すべき辺境地域のサーバーバンク"),
            ("Unsecured Frontier Server Bank", "未保護の辺境地域サーバーバンク"),
        })


class TestLookup(SigTestCase):
    def test_should_match_the_client_text_exactly(self):
        store("de", {("Combat Site", "Kampfgebiet"), ("Sansha Den", "Sansha-Höhle")}, "1", "a")
        store("ja", {("Wormhole", "ワームホール"), ("Wormholes", "ワームホール")}, "1", "a")

        found = lookup({"Kampfgebiet", "sansha-hohle", "ワームホール"})

        # the database's collation would also have found Sansha-Höhle
        self.assertEqual(found, {
            "Kampfgebiet": {("de", "Combat Site")},
            "ワームホール": {("ja", "Wormhole"), ("ja", "Wormholes")},
        })


class TestDisplay(SigTestCase):
    def setUp(self):
        super().setUp()
        store("de", {("Cosmic Signature", "Kosmische Signatur"), ("Relic Site", "Reliktgebiet")}, "1", "a")
        store("ja", {
            ("Wormhole", "ワームホール"),
            ("Wormholes", "ワームホール"),
            ("Unsecured Frontier Server Bank", "注意すべき辺境地域のサーバーバンク"),
            ("Unsecured Frontier Server Bank", "未保護の辺境地域サーバーバンク"),
        }, "1", "a")
        store("zh", {("Wormhole", "虫洞")}, "1", "a")

    def test_should_translate_what_has_one_translation(self):
        found = display({"Wormhole", "Unsecured Frontier Server Bank", "Unknown Site", ""}, "ja")

        # a plural with the same word does not matter here; two texts for one name do
        self.assertEqual(found, {"Wormhole": "ワームホール"})

    def test_should_take_alliance_auths_language_codes(self):
        for language, expected in (("de", "Reliktgebiet"), ("zh-hans", None), ("ja", None)):
            with self.subTest(language):
                self.assertEqual(display({"Relic Site"}, language).get("Relic Site"), expected)
        self.assertEqual(display({"Wormhole"}, "zh-hans"), {"Wormhole": "虫洞"})

    def test_should_leave_languages_without_client_texts_alone(self):
        for language in ("en", "nl-nl", "pl-pl", "uk", "it-it"):
            with self.subTest(language):
                self.assertEqual(display({"Relic Site", "Wormhole"}, language), {})

    def test_should_match_the_english_exactly(self):
        self.assertEqual(display({"relic site"}, "de"), {})

    def test_should_prefer_the_translation_to_the_untranslated_text(self):
        store("de", {("Unstable Wormhole", "Unstable Wormhole"), ("Unstable Wormhole", "Instabiles Wurmloch")}, "2", "b")

        self.assertEqual(display({"Unstable Wormhole"}, "de"), {"Unstable Wormhole": "Instabiles Wurmloch"})


class TestStore(SigTestCase):
    def test_should_replace_one_language_only(self):
        store("de", {("Combat Site", "Kampfgebiet"), ("Data Site", "Datengebiet")}, "100", "a" * 32)
        store("ru", {("Combat Site", "Боевой район")}, "100", "b" * 32)

        store("de", {("Relic Site", "Reliktgebiet")}, "101", "c" * 32)

        self.assertEqual(
            sorted(ClientText.objects.values_list("language", "english", "text")),
            [("de", "Relic Site", "Reliktgebiet"), ("ru", "Combat Site", "Боевой район")],
        )
        state = ClientTextLanguage.objects.get(language="de")
        self.assertEqual((state.build, state.digest, state.count), ("101", "c" * 32, 1))

    def test_should_refuse_an_unknown_language(self):
        with self.assertRaises(ValueError):
            store("nl", {("Combat Site", "Gevechtsgebied")}, "100", "a" * 32)
        self.assertFalse(ClientText.objects.exists())


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]


HASHES = {"de": "aaa", "ru": "bbb", "en-us": "ccc", "xx": "ddd"}
RU = {"1": {"en": "Combat Site", "ru": "Боевой район"}, "2": {"en": "Data Site", "ru": "Район данных"}}
DE = {"1": entry("Combat Site", "Kampfgebiet")}


def archive(build=b"3720952\n", hashes=HASHES, files=None):
    """requests.get of an archive with the given state and files (language -> body or exception)."""
    files = {"ru": RU, "de": DE} if files is None else files

    def get(url, **kwargs):
        if url == client_text.BUILD_URL:
            return FakeResponse(build)
        if url == client_text.HASHES_URL:
            return FakeResponse(hashes if isinstance(hashes, bytes) else json.dumps(hashes).encode())
        for language, body in files.items():
            if url == client_text.FILE_URL.format(language=language):
                if isinstance(body, Exception):
                    raise body
                return FakeResponse(body if isinstance(body, bytes) else json.dumps(body).encode())
        raise AssertionError(f"unexpected download {url}")

    return get


class TestUpdate(SigTestCase):
    def setUp(self):
        super().setUp()
        store("de", {("Combat Site", "Kampfgebiet")}, "3714173", "aaa")

    def fetched(self, get):
        return [call.args[0] for call in get.call_args_list if call.args[0].endswith(".json") and "/latest/" in call.args[0]]

    def test_should_fetch_only_the_languages_that_changed(self):
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()) as get:
            self.assertEqual(update(), ["ru"])

        self.assertEqual(self.fetched(get), [client_text.FILE_URL.format(language="ru")])
        ru = ClientTextLanguage.objects.get(language="ru")
        self.assertEqual((ru.build, ru.digest, ru.count), ("3720952", "bbb", 2))
        self.assertEqual(ClientTextLanguage.objects.get(language="de").build, "3714173")
        self.assertEqual(ClientText.objects.get(language="ru", english="Data Site").text, "Район данных")

    def test_should_fetch_everything_when_forced(self):
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()):
            self.assertEqual(sorted(update(force=True)), ["de", "ru"])

    def test_should_refuse_unexpected_state_files(self):
        for build, hashes in ((b"<html>", HASHES), (b"3720952", b"not json"), (b"3720952", ["de"])):
            with self.subTest(build=build, hashes=hashes):
                with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive(build, hashes)):
                    with self.assertRaises(ClientTextError):
                        update()
        self.assertFalse(ClientTextLanguage.objects.filter(language="ru").exists())

    def test_should_ignore_an_unsafe_hash(self):
        hashes = {"de": "aaa", "ru": "../../etc"}
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive(hashes=hashes)):
            self.assertEqual(update(), [])

    def test_should_keep_the_old_texts_when_a_file_fails(self):
        for body in (requests.ConnectionError("down"), b"not json", b"[1, 2]"):
            with self.subTest(body=body):
                files = {"de": body, "ru": RU}
                changed = archive(hashes={"de": "abc123"}, files=files)
                with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=changed):
                    with self.assertRaises(ClientTextError):
                        update()
                self.assertEqual(ClientTextLanguage.objects.get(language="de").digest, "aaa")
                self.assertEqual(ClientText.objects.get(language="de").text, "Kampfgebiet")

    def test_should_stop_a_file_over_the_limit(self):
        with mock.patch.object(client_text, "MAX_FILE_BYTES", 20):
            with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()):
                with self.assertRaises(ClientTextError):
                    update()
        self.assertFalse(ClientTextLanguage.objects.filter(language="ru").exists())

    def test_should_not_run_twice_at_once(self):
        cache.add(client_text.LOCK, True)

        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()) as get:
            with self.assertRaises(ClientTextError):
                update()
        get.assert_not_called()

    def test_should_release_the_lock_after_a_failure(self):
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive(build=b"x")):
            with self.assertRaises(ClientTextError):
                update()
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()):
            self.assertEqual(update(), ["ru"])


class TestSettingsCard(SigTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("alice", "eos_sig_checker.manage_settings"))
        store("de", {("Combat Site", "Kampfgebiet")}, "3714173", "aaa")

    def test_status_should_compare_with_the_archive(self):
        hashes = {"de": "aaa", "ru": "bbb"}
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive(hashes=hashes)):
            found = client_text.status()

        rows = {row["language"]: row for row in found["languages"]}
        self.assertEqual((found["build"], found["error"]), ("3720952", ""))
        self.assertFalse(rows["de"]["outdated"])
        self.assertTrue(rows["ru"]["outdated"])
        # not in the archive at all: nothing to fetch
        self.assertFalse(rows["ja"]["outdated"])

    def test_should_show_the_state_on_the_settings_page(self):
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()):
            response = self.client.get(SETTINGS)

        self.assertContains(response, "Latest build in the archive: 3720952")
        self.assertContains(response, "update available", count=1)
        self.assertContains(response, "up to date", count=1)
        self.assertContains(response, "not imported", count=6)

    def test_should_open_the_page_when_the_archive_is_down(self):
        # base.SigTestCase keeps every test offline
        response = self.client.get(SETTINGS)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The archive could not be asked for updates.")

    def test_should_ask_the_archive_with_a_short_timeout(self):
        with mock.patch("eos_sig_checker.client_text.requests.get", side_effect=archive()) as get:
            self.client.get(SETTINGS)

        self.assertTrue(get.call_args_list)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs["timeout"], client_text.CHECK_TIMEOUT)

    def test_should_say_when_an_update_runs(self):
        cache.add(client_text.LOCK, True)

        response = self.client.get(SETTINGS)

        self.assertContains(response, "An update is running.")

    def test_update_now_should_start_the_task(self):
        with mock.patch("eos_sig_checker.tasks.update_client_texts.delay") as delay:
            response = self.client.post(UPDATE_NOW)

        delay.assert_called_once_with()
        self.assertRedirects(response, SETTINGS, fetch_redirect_response=False)

    def test_update_now_should_refuse_a_get_and_members(self):
        with mock.patch("eos_sig_checker.tasks.update_client_texts.delay") as delay:
            self.assertEqual(self.client.get(UPDATE_NOW).status_code, 405)
            self.client.force_login(make_user("bob", "eos_sig_checker.basic_access"))
            self.client.post(UPDATE_NOW)

        delay.assert_not_called()


class TestTaskAndCommand(SigTestCase):
    def test_task_should_log_a_failure_instead_of_raising(self):
        with mock.patch("eos_sig_checker.client_text.update", side_effect=ClientTextError("down")):
            with self.assertLogs(tasks.logger, "WARNING"):
                update_client_texts()

    def test_command_should_say_what_it_updated(self):
        out = StringIO()
        with mock.patch("eos_sig_checker.client_text.update", return_value=["de", "ru"]) as update_mock:
            call_command("eos_sig_checker_update_client_texts", "--force", stdout=out)

        update_mock.assert_called_once_with(force=True)
        self.assertIn("de, ru", out.getvalue())

    def test_command_should_fail_with_the_reason(self):
        with mock.patch("eos_sig_checker.client_text.update", side_effect=ClientTextError("down")):
            with self.assertRaisesMessage(CommandError, "down"):
                call_command("eos_sig_checker_update_client_texts")

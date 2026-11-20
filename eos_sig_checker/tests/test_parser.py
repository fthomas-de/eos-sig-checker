from decimal import Decimal

from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from eos_sig_checker.parser import Invalid, Line, Skipped, parse

from .base import ANOMALY, FOREIGN, SCANNED, UNSCANNED, lookup_of


class TestParse(SimpleTestCase):
    def test_should_read_a_scanned_signature(self):
        (line,) = parse(SCANNED)

        self.assertEqual(
            line,
            Line(
                "UDN-422", "Cosmic Signature", "Relic Site", "Ruined Sansha Crystal Quarry",
                Decimal("100.0"), "10,63 AU", "100,0%",
            ),
        )

    def test_should_read_an_unscanned_signature_with_empty_columns(self):
        (line,) = parse(UNSCANNED)

        self.assertIsInstance(line, Line)
        self.assertEqual((line.site_type, line.name, line.signal), ("", "", Decimal("0.0")))

    def test_should_keep_order_and_skip_blank_lines(self):
        rows = parse(f"{SCANNED}\r\n\r\n   \n{UNSCANNED}\n")

        self.assertEqual([row.signature_id for row in rows], ["UDN-422", "ACJ-672"])

    def test_should_read_other_distance_units_and_separators(self):
        for distance in ("1.234 km", "5 432 m", "12 345 km", "0,5 AU", "6,62 UA", "10,02 а.е.", "10,02AU", "1\u202f234 km"):
            with self.subTest(distance):
                (line,) = parse(f"ABC-123\tCosmic Signature\t\t\t0,0%\t{distance}")
                self.assertIsInstance(line, Line)

    def test_should_read_names_with_punctuation(self):
        (line,) = parse("ABC-123\tCosmic Signature\tCombat Site\tGuristas' Hidden Den (Forlorn)\t75,5%\t2 AU")

        self.assertEqual(line.name, "Guristas' Hidden Den (Forlorn)")

    def test_should_report_lines_the_client_cannot_produce(self):
        bad = {
            "too few columns": "ABC-123\tCosmic Signature\t0,0%\t1 AU",
            "lowercase ID": "abc-123\tCosmic Signature\t\t\t0,0%\t1 AU",
            "no ID, unknown group": "Kosmische Signatur\t\t\t0,0%\t1 AU",
            "markup in the name": "ABC-123\tCosmic Signature\tData Site\t<script>alert(1)</script>\t100,0%\t1 AU",
            "markup in the type": "ABC-123\tCosmic Signature\t<b>Data</b>\t\t25,0%\t1 AU",
            "quote in the type": 'ABC-123\tCosmic Signature\tData"Site\t\t25,0%\t1 AU',
            "name without type": "ABC-123\tCosmic Signature\t\tSansha Den\t100,0%\t1 AU",
            "over 100 percent": "ABC-123\tCosmic Signature\t\t\t100,1%\t1 AU",
            "no percent sign": "ABC-123\tCosmic Signature\t\t\t50\t1 AU",
            "no unit": "ABC-123\tCosmic Signature\t\t\t0,0%\t10",
            "markup as unit": "ABC-123\tCosmic Signature\t\t\t0,0%\t10 <b>",
            "two spaces before the percent sign": "ABC-123\tCosmic Signature\t\t\t0,0  %\t1 AU",
            "control character": "ABC-123\tCosmic Signature\t\t\t0,0%\t1 AU\x00",
            # str.strip() takes \x1f for whitespace: only the control check stops it
            "stripped control character": "ABC-123\tCosmic Signature\tData Site\tSansha Den\x1f\t100,0%\t1 AU",
            "overlong name": "ABC-123\tCosmic Signature\tData Site\t" + "A" * 101 + "\t100,0%\t1 AU",
            # \d alone takes the digits of every script
            "foreign digits in the ID": "ABC-١٢٣\tCosmic Signature\t\t\t0,0%\t1 AU",
            "foreign digits in the signal": "ABC-123\tCosmic Signature\t\t\t٥٠,٠%\t1 AU",
            "foreign digits in the distance": "ABC-123\tCosmic Signature\t\t\t0,0%\t١ AU",
        }
        for reason, text in bad.items():
            with self.subTest(reason):
                (row,) = parse(text)
                self.assertIsInstance(row, Invalid)
                self.assertTrue(row.error)

    def test_should_skip_probe_results_that_are_no_signature(self):
        others = {
            "anomaly": ANOMALY,
            "ship": "XYZ-123\tShip\tFrigate\tHeron\t100,0%\t2,10 AU",
            "structure, fewer columns": "XYZ-123\tStructure\tCitadel",
            "German client": "ABC-123\tKosmische Signatur\t\t\t0,0%\t1 AU",
        }
        for reason, text in others.items():
            with self.subTest(reason):
                self.assertEqual(parse(text), [Skipped()])

    def test_should_check_control_characters_before_skipping(self):
        (row,) = parse("XYZ-123\tShip\x1f\tFrigate\tHeron\t100,0%\t2 AU")

        self.assertIsInstance(row, Invalid)

    def test_should_band_the_signal_like_the_game(self):
        bands = {"0,0%": "low", "24,9%": "low", "25,0%": "partial", "74,9%": "partial",
                 "75,0%": "high", "99,9%": "high", "100,0%": "full"}
        for signal, band in bands.items():
            with self.subTest(signal):
                (line,) = parse(f"ABC-123\tCosmic Signature\tData Site\t\t{signal}\t1 AU")
                self.assertEqual(line.signal_band, band)

    def test_should_shorten_and_flatten_an_invalid_line(self):
        (row,) = parse("X" * 500 + "\x01")

        self.assertEqual(len(row.text), 120)
        self.assertNotIn("\x01", row.text)


class TestOtherClients(SimpleTestCase):
    def test_should_read_the_real_lines_of_other_clients(self):
        for language, text in FOREIGN.items():
            with self.subTest(language):
                (line,) = parse(text, lookup_of())
                self.assertIsInstance(line, Line)
                self.assertEqual((line.group, line.site_type, line.name, line.signal), ("Cosmic Signature", "", "", 0))
                self.assertEqual(line.problems, ())

    def test_should_take_the_space_before_the_percent_sign(self):
        for space in (" ", "\u00a0", "\u202f"):
            with self.subTest(repr(space)):
                (line,) = parse(f"ABC-123\tCosmic Signature\t\t\t50,5{space}%\t1 AU")
                self.assertEqual(line.signal, 50.5)

    def test_should_skip_another_client_without_client_texts(self):
        self.assertEqual(parse(FOREIGN["fr"]), [Skipped()])
        self.assertEqual(parse(FOREIGN["fr"], lookup_of(set())), [Skipped()])

    def test_should_skip_an_anomaly_of_another_client(self):
        self.assertEqual(parse("ABC-123\tKosmische Anomalie\t\t\t0,0%\t1 AU", lookup_of()), [Skipped()])

    def test_should_translate_type_and_name_despite_plurals(self):
        # type and name from the client texts: no scanned paste of another client yet
        wormhole, relic = parse(
            "HTJ-764\t宇宙のシグネチャ\tワームホール\t\t100,0%\t10,02AU\n"
            "VGX-244\t宇宙のシグネチャ\t遺物サイト\t未保護の辺境地域サーバーバンク\t100,0%\t3,55AU",
            lookup_of(),
        )

        self.assertEqual((wormhole.group, wormhole.site_type, wormhole.problems), ("Cosmic Signature", "Wormhole", ()))
        self.assertEqual((relic.site_type, relic.name), ("Relic Site", "Unsecured Frontier Server Bank"))

    def test_should_leave_a_name_blank_it_cannot_put_into_english(self):
        rows = {("ja", "Cosmic Signature", "宇宙のシグネチャ"), ("ja", "Relic Site", "遺物サイト"),
                ("ja", "A Site", "同じ名前"), ("ja", "B Site", "同じ名前")}
        for name, reason in (("同じ名前", "several meanings"), ("知らない名前", "not in the client texts")):
            with self.subTest(name):
                (line,) = parse(f"VGX-244\t宇宙のシグネチャ\t遺物サイト\t{name}\t100,0%\t3,55AU", lookup_of(rows))
                self.assertEqual((line.site_type, line.name), ("Relic Site", ""))
                with translation.override("en"):
                    self.assertEqual([str(problem) for problem in line.problems], [f"Name not translated: {name} ({reason})"])
                self.assertIn("VGX-244", line.source)

    def test_should_take_a_name_the_client_left_in_english(self):
        # the Russian client texts keep this name English (client_text.pairs keeps such pairs)
        rows = {
            ("ru", "Cosmic Signature", "Скрытый сигнал"),
            ("ru", "Data Site", "Район данных"),
            ("ru", "Unsecured Frontier Server Bank", "Unsecured Frontier Server Bank"),
        }

        (line,) = parse(
            "HTJ-764\tСкрытый сигнал\tРайон данных\tUnsecured Frontier Server Bank\t100,0%\t10,02 а.е.", lookup_of(rows)
        )

        self.assertEqual((line.site_type, line.name, line.problems), ("Data Site", "Unsecured Frontier Server Bank", ()))

    def test_should_drop_type_and_name_when_the_type_is_unknown(self):
        (line,) = parse("VGX-244\t宇宙のシグネチャ\t謎のサイト\t未保護の辺境地域サーバーバンク\t100,0%\t3,55AU", lookup_of())

        self.assertEqual((line.site_type, line.name), ("", ""))
        with translation.override("en"):
            self.assertEqual(str(line.problems[0]), "Group not translated: 謎のサイト (not in the client texts)")

    def test_should_read_type_and_name_in_the_language_of_the_first_word(self):
        rows = {("ja", "Cosmic Signature", "宇宙のシグネチャ"), ("zh", "Gas Site", "遺物サイト"), ("ja", "Relic Site", "遺物サイト")}

        (line,) = parse("VGX-244\t宇宙のシグネチャ\t遺物サイト\t\t100,0%\t3,55AU", lookup_of(rows))

        self.assertEqual(line.site_type, "Relic Site")

    def test_should_not_look_up_english_lines(self):
        lookup = mock.Mock()

        parse(f"{SCANNED}\n{UNSCANNED}", lookup)

        lookup.assert_not_called()

from decimal import Decimal

from django.test import SimpleTestCase

from eos_sig_checker.parser import Invalid, Line, Skipped, parse

from .base import SCANNED, UNSCANNED


class TestParse(SimpleTestCase):
    def test_should_read_a_scanned_anomaly(self):
        (line,) = parse(SCANNED)

        self.assertEqual(
            line,
            Line("UDN-422", "Cosmic Anomaly", "Combat Site", "Sansha Den", Decimal("100.0"), "10,63 AU", "100,0%"),
        )

    def test_should_read_an_unscanned_signature_with_empty_columns(self):
        (line,) = parse(UNSCANNED)

        self.assertIsInstance(line, Line)
        self.assertEqual((line.site_type, line.name, line.signal), ("", "", Decimal("0.0")))

    def test_should_keep_order_and_skip_blank_lines(self):
        rows = parse(f"{SCANNED}\r\n\r\n   \n{UNSCANNED}\n")

        self.assertEqual([row.signature_id for row in rows], ["UDN-422", "ACJ-672"])

    def test_should_read_other_distance_units_and_separators(self):
        for distance in ("1.234 km", "5 432 m", "12 345 km", "0,5 AU"):
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

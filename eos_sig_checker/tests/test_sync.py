from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.utils import timezone

from eos_sig_checker import sync
from eos_sig_checker.models import DEFAULT_MAX_AGE_DAYS, Signature
from eos_sig_checker.parser import Invalid, parse
from eos_sig_checker.sync import Row, delete_expired, merge, statistics
from eos_sig_checker.tasks import delete_expired_signatures
from eos_sig_checker.tracking import Location

from .base import (
    DATA_SITE,
    SCANNED,
    UNSCANNED,
    WORMHOLE,
    SigTestCase,
    make_user,
    set_max_age_days,
    set_wormhole_hours,
)


class SyncTestCase(SigTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user("alice").profile.main_character
        self.bob = make_user("bob").profile.main_character

    def paste(self, text, character=None, now=None):
        return merge(parse(text), character or self.alice, now=now)


class TestMerge(SyncTestCase):
    def test_should_store_a_new_signature(self):
        (row,) = self.paste(SCANNED)

        signature = Signature.objects.get(signature_id="UDN-422")
        self.assertEqual(
            (signature.group, signature.site_type, signature.name, signature.signal, signature.distance),
            ("Cosmic Signature", "Relic Site", "Ruined Sansha Crystal Quarry", Decimal("100.0"), "10,63 AU"),
        )
        self.assertEqual(signature.last_checked_by, self.alice)
        self.assertEqual(signature.first_seen, signature.last_checked)
        self.assertEqual((row.resolved, row.previous_check), (set(), None))

    def test_should_resolve_an_unscanned_line_from_the_list(self):
        earlier = timezone.now() - timedelta(hours=2)
        self.paste(DATA_SITE, now=earlier)

        (row,) = self.paste(UNSCANNED, character=self.bob)

        self.assertEqual((row.site_type, row.name), ("Data Site", "Unsecured Frontier Server Bank"))
        self.assertEqual(row.resolved, {"site_type", "name"})
        self.assertEqual(row.previous_check, earlier)
        self.assertEqual(row.previous_by, self.alice.character_name)

        signature = Signature.objects.get(signature_id="ACJ-672")
        # the weaker scan keeps what was known and only confirms the site
        self.assertEqual((signature.name, signature.signal), ("Unsecured Frontier Server Bank", Decimal("100.0")))
        self.assertEqual(signature.first_seen, earlier)
        self.assertGreater(signature.last_checked, earlier)
        self.assertEqual(signature.last_checked_by, self.bob)
        self.assertEqual(signature.distance, "10,61 AU")

    def test_should_show_the_best_signal_after_a_weaker_scan(self):
        self.paste(DATA_SITE)

        (row,) = self.paste(UNSCANNED, character=self.bob)

        self.assertEqual((row.line.signal, row.line.signal_text), (Decimal("100.0"), "100,0%"))
        self.assertEqual(row.line.signal_band, "full")

    def test_should_resolve_only_the_missing_name(self):
        self.paste(DATA_SITE)

        (row,) = self.paste("ACJ-672\tCosmic Signature\tData Site\t\t25,0%\t9 AU")

        self.assertEqual(row.resolved, {"name"})
        self.assertEqual(row.name, "Unsecured Frontier Server Bank")

    def test_should_fill_the_list_from_a_better_scan(self):
        self.paste(UNSCANNED)

        (row,) = self.paste(DATA_SITE)

        self.assertEqual(row.resolved, set())
        signature = Signature.objects.get(signature_id="ACJ-672")
        self.assertEqual((signature.site_type, signature.name), ("Data Site", "Unsecured Frontier Server Bank"))

    def test_should_replace_a_reused_id_with_the_newer_paste(self):
        earlier = timezone.now() - timedelta(days=1)
        self.paste(DATA_SITE, now=earlier)

        for other in (
            "ACJ-672\tCosmic Signature\tRelic Site\tForgotten Frontier Quarantine Outpost\t100,0%\t1 AU",
            "ACJ-672\tCosmic Signature\tData Site\tCentral Guristas Sparking Transmitter\t100,0%\t1 AU",
        ):
            with self.subTest(other):
                (row,) = self.paste(other)
                signature = Signature.objects.get(signature_id="ACJ-672")
                line = parse(other)[0]
                self.assertEqual((signature.group, signature.site_type, signature.name),
                                 (line.group, line.site_type, line.name))
                self.assertEqual(row.resolved, set())
                self.assertGreater(signature.first_seen, earlier)
        self.assertEqual(Signature.objects.count(), 1)

    def test_should_treat_an_expired_row_as_unknown(self):
        old = timezone.now() - timedelta(days=DEFAULT_MAX_AGE_DAYS, minutes=1)
        self.paste(DATA_SITE, now=old)

        (row,) = self.paste(UNSCANNED)

        self.assertEqual((row.site_type, row.name, row.resolved, row.previous_check), ("", "", set(), None))
        self.assertEqual(Signature.objects.get(signature_id="ACJ-672").name, "")

    def test_should_keep_invalid_lines_in_place_and_store_nothing_from_them(self):
        rows = self.paste(f"{SCANNED}\nnot a signature\n{UNSCANNED}")

        self.assertEqual([type(row) for row in rows], [Row, Invalid, Row])
        self.assertEqual(Signature.objects.count(), 2)

    def test_should_drop_skipped_lines(self):
        rows = self.paste(f"{SCANNED}\nXYZ-123\tShip\tFrigate\tHeron\t100,0%\t2 AU")

        self.assertEqual([type(row) for row in rows], [Row])
        self.assertFalse(Signature.objects.filter(signature_id="XYZ-123").exists())

    def test_should_lock_in_id_order_and_answer_in_paste_order(self):
        # SCANNED is UDN-422, UNSCANNED is ACJ-672: pasted in descending order
        with mock.patch.object(sync, "_find", wraps=sync._find) as find:
            output = self.paste(f"{SCANNED}\n{UNSCANNED}")

        self.assertEqual([call.args[0].signature_id for call in find.call_args_list], ["ACJ-672", "UDN-422"])
        self.assertEqual([row.line.signature_id for row in output], ["UDN-422", "ACJ-672"])


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


class TestRecentWormholes(SyncTestCase):
    def test_should_list_only_wormholes_checked_within_the_hours(self):
        # not the default 3, so the test fails if the setting is ignored
        set_wormhole_hours(10)
        now = timezone.now()
        old = WORMHOLE.replace("KJH-123", "OLD-001")
        self.paste(old, now=now - timedelta(hours=10, minutes=1))
        self.paste(WORMHOLE, now=now - timedelta(hours=9))
        self.paste(WORMHOLE.replace("KJH-123", "NEW-002"), now=now - timedelta(minutes=5))
        self.paste(DATA_SITE, now=now)

        found = sync.recent_wormholes(now)

        self.assertEqual([wormhole.signature_id for wormhole in found], ["NEW-002", "KJH-123"])


class TestExpiry(SyncTestCase):
    def test_should_delete_only_rows_past_their_age(self):
        now = timezone.now()
        self.paste(SCANNED, now=now - timedelta(days=7, minutes=1))
        self.paste(UNSCANNED, now=now - timedelta(days=6))

        self.assertEqual(delete_expired(now), 1)
        self.assertEqual(list(Signature.objects.values_list("signature_id", flat=True)), ["ACJ-672"])

    def test_task_should_delete_expired_rows(self):
        self.paste(SCANNED, now=timezone.now() - timedelta(days=30))

        delete_expired_signatures()

        self.assertFalse(Signature.objects.exists())

    def test_task_should_follow_the_age_from_the_settings_page(self):
        set_max_age_days(2)
        now = timezone.now()
        self.paste(SCANNED, now=now - timedelta(days=2, minutes=1))
        self.paste(UNSCANNED, now=now - timedelta(days=1))

        delete_expired_signatures()

        self.assertEqual(list(Signature.objects.values_list("signature_id", flat=True)), ["ACJ-672"])

    def test_merge_should_follow_the_age_from_the_settings_page(self):
        # a longer age keeps a row the default would have let go
        set_max_age_days(DEFAULT_MAX_AGE_DAYS + 3)
        self.paste(DATA_SITE, now=timezone.now() - timedelta(days=DEFAULT_MAX_AGE_DAYS + 1))

        (row,) = self.paste(UNSCANNED)

        self.assertEqual(row.name, "Unsecured Frontier Server Bank")
        self.assertIsNotNone(row.previous_check)

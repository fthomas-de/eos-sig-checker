from unittest import mock

import requests

from django.core.cache import cache
from django.test import TestCase, override_settings

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.tests.auth_utils import AuthUtils

from eos_sig_checker.models import SigCheckerConfiguration

# The probe scanner's copy, as the English client puts it on the clipboard.
# SCANNED is UDN-422's real line with a relic site's real name, now that
# the anomaly it was is skipped (ANOMALY).
SCANNED = "UDN-422\tCosmic Signature\tRelic Site\tRuined Sansha Crystal Quarry\t100,0%\t10,63 AU"
ANOMALY = "UDN-422\tCosmic Anomaly\tCombat Site\tSansha Den\t100,0%\t10,63 AU"
UNSCANNED = "ACJ-672\tCosmic Signature\t\t\t0,0%\t10,61 AU"
WORMHOLE = "KJH-123\tCosmic Signature\tWormhole\tUnstable Wormhole\t100,0%\t4,10 AU"
DATA_SITE ="ACJ-672\tCosmic Signature\tData Site\tUnsecured Frontier Server Bank\t100,0%\t3,20 AU"

# Real lines of other clients (2026-11-20), all unscanned: no scanned line of
# another client is at hand yet, so a test with site type and name takes them
# from the client texts.
FOREIGN = {
    "de": "HTJ-764\tKosmische Signatur\t\t\t0,0 %\t10,57 AE",
    "fr":"REB-508\tSignature cosmique\t\t\t0,0 %\t6,62 UA",
    "es": "LKF-627\tSeñal cósmica\t\t\t0,0 %\t64,86 AU",
    "ru": "HTJ-764\tСкрытый сигнал\t\t\t0,0%\t10,02 а.е.",
    "ko": "REB-508\t코즈믹 시그니처\t\t\t0,0%\t6,62 AU",
    "ja": "HTJ-764\t宇宙のシグネチャ\t\t\t0,0%\t10,02AU",
    "zh": "REB-508\t空间信号\t\t\t0,0%\t6,62 AU",
}
# the client texts those lines need, as the archive has them: in Japanese
# and Chinese one word stands for singular and plural
CLIENT_TEXTS = {
    ("de", "Cosmic Signature", "Kosmische Signatur"),
    ("fr", "Cosmic Signature", "Signature cosmique"),
    ("fr", "Combat Site", "Site de combat"),
    ("es", "Cosmic Signature", "Señal cósmica"),
    ("ru", "Cosmic Signature", "Скрытый сигнал"),
    ("ko", "Cosmic Signature", "코즈믹 시그니처"),
    ("ja", "Cosmic Signature", "宇宙のシグネチャ"),
    ("ja", "Cosmic Signatures", "宇宙のシグネチャ"),
    ("ja", "Wormhole", "ワームホール"),
    ("ja", "Wormholes", "ワームホール"),
    ("ja", "Relic Site", "遺物サイト"),
    ("ja", "Unsecured Frontier Server Bank", "注意すべき辺境地域のサーバーバンク"),
    ("ja", "Unsecured Frontier Server Bank", "未保護の辺境地域サーバーバンク"),
    ("zh", "Cosmic Signature", "空间信号"),
    ("zh", "Cosmic Signatures", "空间信号"),
    ("zh", "Jeremy Tacs", "空间信号"),
    ("de", "Cosmic Anomaly", "Kosmische Anomalie"),
}


def lookup_of(rows=CLIENT_TEXTS):
    """client_text.lookup over the given (language, English, text) rows, without the database."""

    def lookup(words):
        found = {}
        for language, english, text in rows:
            if text in words:
                found.setdefault(text, set()).add((language, english))
        return found

    return lookup


def store_client_texts(rows=CLIENT_TEXTS):
    from eos_sig_checker.client_text import store

    for language in {language for language, _english, _text in rows}:
        store(language, {(english, text) for lang, english, text in rows if lang == language}, "1", "a")


# The dev instance points the default cache at its own Redis. The test
# transaction rolls back, the cache does not: what one test stored would leak
# into the next and into the running instance.
@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "eos-sig-checker"}},
)
class SigTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # no test reaches the archive: the settings page asks it on every view.
        # A test that wants an answer patches requests.get again inside.
        offline = mock.patch(
            "eos_sig_checker.client_text.requests.get", side_effect=requests.ConnectionError("tests are offline")
        )
        offline.start()
        self.addCleanup(offline.stop)


def set_max_age_days(days):
    """What the settings page stores; saved through solo, so its cache follows."""
    config = SigCheckerConfiguration.get_solo()
    config.max_age_days = days
    config.save()


def set_wormhole_hours(hours):
    config = SigCheckerConfiguration.get_solo()
    config.wormhole_hours = hours
    config.save()


def set_system_hours(hours):
    config = SigCheckerConfiguration.get_solo()
    config.system_hours = hours
    config.save()


def make_user(name, *perms):
    """A user with a main character; permissions as 'app.codename'."""
    user = AuthUtils.create_user(name)
    # Alliance Auth wraps every url_hook view in main_character_required:
    # without a main, a permitted user is sent to the dashboard as well
    main = AuthUtils.add_main_character_2(
        user,
        f"{name} main",
        character_id=user.pk + 1000,
        corp_id=2001,
        corp_name="Corp 2001",
        corp_ticker="C2001",
    )
    CharacterOwnership.objects.create(user=user, character=main, owner_hash=f"hash-{main.character_id}")
    if perms:
        AuthUtils.add_permissions_to_user_by_name(list(perms), user)
    # has_perm caches on the instance; tests want the stored permissions
    return type(user).objects.get(pk=user.pk)

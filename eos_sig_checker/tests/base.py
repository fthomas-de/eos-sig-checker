from django.core.cache import cache
from django.test import TestCase, override_settings

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.tests.auth_utils import AuthUtils

# The probe scanner's copy, as the English client puts it on the clipboard.
SCANNED = "UDN-422\tCosmic Anomaly\tCombat Site\tSansha Den\t100,0%\t10,63 AU"
UNSCANNED = "ACJ-672\tCosmic Signature\t\t\t0,0%\t10,61 AU"
DATA_SITE = "ACJ-672\tCosmic Signature\tData Site\tUnsecured Frontier Server\t100,0%\t3,20 AU"


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

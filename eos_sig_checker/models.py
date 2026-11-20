from solo.models import SingletonModel

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveCharacter

from .parser import MAX_LINES

DEFAULT_MAX_AGE_DAYS = 7
# beyond a month reused signature IDs become likely, and the list would
# resolve a new site with the name of an old one
MAX_AGE_DAYS_LIMIT = 30

DEFAULT_LOCATION_RETRY_SECONDS = 60
# 5 is tracking.LOCATION_CACHE_SECONDS, the first step; beyond an hour a
# repaired token would look broken for too long
LOCATION_RETRY_SECONDS_MIN = 5
LOCATION_RETRY_SECONDS_LIMIT = 3600

# more than 200 lines in one paste is unlikely; parser.MAX_LINES is the ceiling
DEFAULT_MAX_LINES = 200

DEFAULT_WORMHOLE_HOURS = 3
# a wormhole lives at most 48 hours; an older one is gone in the game
WORMHOLE_HOURS_LIMIT = 48

DEFAULT_SYSTEM_HOURS = 3
# two days, like the wormholes: older is no longer where people scan now
SYSTEM_HOURS_LIMIT = 48

DEFAULT_ERROR_LOG_DAYS = 7
# the log holds pasted text: long enough to show a fault, short enough not to pile up
ERROR_LOG_DAYS_LIMIT = 30

# the solar system of a signature pasted without a tracked character
NO_SYSTEM = 0


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", _("Can paste signatures and see the shared list")),
            ("manage_settings", _("Can change the settings and delete all signatures")),
        )


class SigCheckerConfiguration(SingletonModel):
    """App wide settings, maintained on the settings page."""

    max_age_days = models.PositiveSmallIntegerField(
        default=DEFAULT_MAX_AGE_DAYS,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_AGE_DAYS_LIMIT)],
        verbose_name=_("Keep signatures (days)"),
        help_text=_(
            "Days a signature counts after its last check. After that it is ignored "
            "and removed by the daily cleanup."
        ),
    )
    location_retry_seconds = models.PositiveSmallIntegerField(
        default=DEFAULT_LOCATION_RETRY_SECONDS,
        validators=[MinValueValidator(LOCATION_RETRY_SECONDS_MIN), MaxValueValidator(LOCATION_RETRY_SECONDS_LIMIT)],
        verbose_name=_("Longest wait after failed location reads (seconds)"),
        help_text=_(
            "A location that cannot be read is asked again after 5 seconds at first, "
            "then later with every further failure, in 5 steps up to this many seconds."
        ),
    )
    max_lines = models.PositiveSmallIntegerField(
        default=DEFAULT_MAX_LINES,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_LINES)],
        verbose_name=_("Lines per paste"),
        help_text=_("The most lines one paste may hold. A full system has a few dozen signatures and anomalies."),
    )
    wormhole_hours = models.PositiveSmallIntegerField(
        default=DEFAULT_WORMHOLE_HOURS,
        validators=[MinValueValidator(1), MaxValueValidator(WORMHOLE_HOURS_LIMIT)],
        verbose_name=_("Show wormholes (hours)"),
        help_text=_("Hours a checked wormhole stays in the WH list of the paste page."),
    )
    system_hours = models.PositiveSmallIntegerField(
        default=DEFAULT_SYSTEM_HOURS,
        validators=[MinValueValidator(1), MaxValueValidator(SYSTEM_HOURS_LIMIT)],
        verbose_name=_("Show systems (hours)"),
        help_text=_("Hours a system stays in the system list of the paste page after its last check."),
    )
    error_log_days = models.PositiveSmallIntegerField(
        default=DEFAULT_ERROR_LOG_DAYS,
        validators=[MinValueValidator(1), MaxValueValidator(ERROR_LOG_DAYS_LIMIT)],
        verbose_name=_("Keep rejected lines (days)"),
        help_text=_("Days a rejected line stays on the Errors tab. After that the daily cleanup removes it."),
    )

    class Meta:
        default_permissions = ()
        verbose_name = pgettext_lazy("eos-sig-checker", "Configuration")

    def __str__(self):
        return str(self._meta.verbose_name)


class Signature(models.Model):
    """The last known state of one signature, shared by everybody.

    One row per signature ID and solar system: a paste that shows the same ID
    with another group, site type or name is a new site under a reused ID and
    replaces the row. The system is only known when the paster tracks a
    character (tracking.py); without it the row has NO_SYSTEM and the ID
    alone counts, since IDs rarely repeat within the few days a row lives
    (SigCheckerConfiguration.max_age_days).
    """

    signature_id = models.CharField(max_length=7)
    # NO_SYSTEM rather than NULL: MySQL lets any number of NULLs past a unique
    # constraint, and partial constraints do not exist there
    solar_system_id = models.PositiveIntegerField(default=NO_SYSTEM, db_index=True)
    # stored with the row, so no list needs ESI to show it
    solar_system_name = models.CharField(max_length=100, blank=True, verbose_name=_("System"))
    group = models.CharField(max_length=20)
    site_type = models.CharField(max_length=40, blank=True)
    name = models.CharField(max_length=100, blank=True)
    # the best scan strength seen for this site, in percent
    signal = models.DecimalField(max_digits=4, decimal_places=1)
    distance = models.CharField(max_length=30)
    first_seen = models.DateTimeField()
    last_checked = models.DateTimeField(db_index=True)
    last_checked_by = models.ForeignKey(
        EveCharacter, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        default_permissions = ()
        verbose_name = _("Signature")
        verbose_name_plural = _("Signatures")
        constraints = [
            models.UniqueConstraint(fields=["signature_id", "solar_system_id"], name="eos_sig_checker_signature_per_system"),
        ]

    def __str__(self):
        return self.signature_id

    @property
    def signal_band(self) -> str:
        # imported here: the parser is the security boundary and stays free of models
        from .parser import signal_band

        return signal_band(self.signal)


class RejectedLine(models.Model):
    """A pasted line the parser refused, kept for the Errors tab."""

    # parser.Invalid has cut it to 120 characters already
    text = models.CharField(max_length=120)
    # English whatever the paster reads: the log is read to find the fault
    reason = models.CharField(max_length=200)
    character = models.ForeignKey(EveCharacter, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(db_index=True)

    class Meta:
        default_permissions = ()
        verbose_name = _("Rejected line")
        verbose_name_plural = _("Rejected lines")

    def __str__(self):
        return self.text


class ClientText(models.Model):
    """One text of the EVE client in English and in one other language.

    Filled by client_text.store. No unique constraint: MySQL's default
    collation compares without case and accents and would refuse pairs the
    client keeps apart. One English may have several rows, one text several
    English: the lookups decide what is unambiguous.
    """

    language = models.CharField(max_length=5)
    # parser.NAME caps the English at 100 characters
    english = models.CharField(max_length=100)
    text = models.CharField(max_length=200)

    class Meta:
        default_permissions = ()
        # looked up both ways: the page shows English rows in the reader's
        # language; a paste's words are looked up before its language is known
        indexes = [
            models.Index(fields=["language", "english"], name="eos_sig_checker_ct_english"),
            models.Index(fields=["text"], name="eos_sig_checker_ct_by_text"),
        ]

    def __str__(self):
        return f"{self.language}: {self.english}"


class ClientTextLanguage(models.Model):
    """What is imported for one client language."""

    language = models.CharField(max_length=5, primary_key=True)
    # the archive's build number at the import, shown on the settings page
    build = models.CharField(max_length=20)
    # the archive's hash of the file: an unchanged language is not fetched again
    digest = models.CharField(max_length=64)
    imported = models.DateTimeField()
    count = models.PositiveIntegerField()

    class Meta:
        default_permissions = ()

    def __str__(self):
        return self.language

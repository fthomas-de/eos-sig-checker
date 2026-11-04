from django.db import models
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("basic_access", _("Can paste and resolve signatures")),)


class Signature(models.Model):
    """The last known state of one signature, shared by everybody.

    One row per signature ID: a paste that shows the same ID with another
    group, site type or name is a new site under a reused ID and replaces the
    row. The list carries no solar system - IDs rarely repeat within the few
    days a row lives (EOS_SIG_CHECKER_MAX_AGE_DAYS).
    """

    signature_id = models.CharField(max_length=7, unique=True)
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

    def __str__(self):
        return self.signature_id

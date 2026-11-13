"""Merge a paste into the shared list and resolve it from there."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .app_settings import max_age_days
from .models import NO_SYSTEM, Signature
from .parser import Invalid, Line, Skipped


@dataclass
class Row:
    """One line of the output: the paste, completed from the list."""

    line: Line
    site_type: str
    name: str
    # which of site_type/name came from the list instead of the paste
    resolved: set = field(default_factory=set)
    # the check before this paste; None for a signature the list did not know
    previous_check: datetime | None = None
    previous_by: str = ""
    system_name: str = ""
    # False for a row of the tracked system that this paste did not show
    pasted: bool = True


def cutoff(now=None):
    return (now or timezone.now()) - timedelta(days=max_age_days())


def _is_other_site(signature: Signature, line: Line) -> bool:
    # blank columns are only a weaker scan; a different value is another site
    return (
        line.group != signature.group
        or bool(line.site_type and signature.site_type and line.site_type != signature.site_type)
        or bool(line.name and signature.name and line.name != signature.name)
    )


def _replace(signature: Signature, line: Line, now):
    signature.group = line.group
    signature.site_type = line.site_type
    signature.name = line.name
    signature.signal = line.signal
    signature.first_seen = now


def _merge(signature: Signature, line: Line) -> set:
    resolved = set()
    for column in ("site_type", "name"):
        if getattr(line, column):
            setattr(signature, column, getattr(line, column))
        elif getattr(signature, column):
            resolved.add(column)
    signature.signal = max(signature.signal, line.signal)
    return resolved


def _find(line: Line, system, oldest) -> Signature | None:
    """The row a line belongs to, locked; None when the list has none.

    With a system the row of that system wins, then a row pasted without
    one - this paste tells where it is. Without a system the ID alone
    counts, as before tracking: the newest live row of the same site,
    wherever it was placed, else the row without a system.
    """
    # locked: two people pasting the same system at once must not
    # overwrite each other's merge halfway
    rows = Signature.objects.select_for_update().filter(signature_id=line.signature_id)
    if system:
        signature = rows.filter(solar_system_id=system.system_id).first() or rows.filter(solar_system_id=NO_SYSTEM).first()
        if signature:
            signature.solar_system_id = system.system_id
            signature.solar_system_name = system.system_name
        return signature

    for signature in rows.filter(last_checked__gte=oldest).order_by("-last_checked"):
        if not _is_other_site(signature, line):
            return signature
    return rows.filter(solar_system_id=NO_SYSTEM).first()


def _store(line: Line, character, now, oldest, system) -> Row:
    """Store one valid line and return it completed from the list."""
    signature = _find(line, system, oldest)
    if signature is None:
        # get_or_create, not create: a second paste of the same
        # system at the same moment finds the row instead of failing
        # on the unique constraint
        signature, created = Signature.objects.get_or_create(
            signature_id=line.signature_id,
            solar_system_id=system.system_id if system else NO_SYSTEM,
            defaults={
                "solar_system_name": system.system_name if system else "",
                "group": line.group,
                "site_type": line.site_type,
                "name": line.name,
                "signal": line.signal,
                "distance": line.distance,
                "first_seen": now,
                "last_checked": now,
                "last_checked_by": character,
            },
        )
        if created:
            return Row(line, line.site_type, line.name, system_name=signature.solar_system_name)

    known = signature.last_checked >= oldest
    previous_check = signature.last_checked if known else None
    previous_by = signature.last_checked_by.character_name if known and signature.last_checked_by else ""
    # a row past its age counts as gone, even before the cleanup task removed it
    if not known or _is_other_site(signature, line):
        _replace(signature, line, now)
        resolved = set()
    else:
        resolved = _merge(signature, line)
    signature.distance = line.distance
    signature.last_checked = now
    signature.last_checked_by = character
    signature.save()
    return Row(
        line,
        signature.site_type,
        signature.name,
        resolved,
        previous_check,
        previous_by,
        system_name=signature.solar_system_name,
    )


def merge(rows: list[Line | Invalid | Skipped], character, now=None, system=None) -> list[Row | Invalid]:
    """Store every valid line and return the paste completed from the list.

    ``character`` is the main of whoever pasted, kept as the last checker;
    ``system`` the tracked character's tracking.Location, or None.
    Invalid lines pass through untouched, so the output keeps the paste's
    order; skipped lines (no signature) drop out.
    """
    now = now or timezone.now()
    oldest = cutoff(now)
    output = [line for line in rows if not isinstance(line, Skipped)]
    # locked in ID order, not paste order: two people pasting the same system
    # sorted differently would lock the rows crosswise and deadlock. The sort
    # is stable, so an ID pasted twice keeps its order.
    by_id = sorted(
        (index for index, line in enumerate(output) if isinstance(line, Line)),
        key=lambda index: output[index].signature_id,
    )
    with transaction.atomic():
        for index in by_id:
            output[index] = _store(output[index], character, now, oldest, system)
    return output


def _signal_text(signal) -> str:
    # the client's own format ("100,0%"), so Copy reads like a paste
    return f"{signal:.1f}%".replace(".", ",")


def system_rows(system, skip_ids=(), now=None) -> list[Row]:
    """The live rows of a solar system, as output rows not from this paste.

    Shown with a paste as well: a signature the paster left out of the
    selection (ignored in the scanner, say) is still in the system.
    """
    signatures = (
        Signature.objects.filter(solar_system_id=system.system_id, last_checked__gte=cutoff(now))
        .exclude(signature_id__in=list(skip_ids))
        .select_related("last_checked_by")
        .order_by("signature_id")
    )
    return [
        Row(
            Line(
                signature.signature_id,
                signature.group,
                signature.site_type,
                signature.name,
                signature.signal,
                signature.distance,
                _signal_text(signature.signal),
            ),
            signature.site_type,
            signature.name,
            previous_check=signature.last_checked,
            previous_by=signature.last_checked_by.character_name if signature.last_checked_by else "",
            system_name=signature.solar_system_name,
            pasted=False,
        )
        for signature in signatures
    ]


def delete_expired(now=None) -> int:
    deleted, _ = Signature.objects.filter(last_checked__lt=cutoff(now)).delete()
    return deleted


def statistics(now=None) -> dict:
    """The counts at the foot of every page: how the list grows, whether it
    is used and whether the cleanup runs."""
    now = now or timezone.now()
    oldest = cutoff(now)
    day = now - timedelta(hours=24)
    # shortcut: one scan of the table per page view, cache the result once the table passes about 100,000 rows
    return Signature.objects.aggregate(
        total=Count("pk"),
        new=Count("pk", filter=Q(first_seen__gte=day)),
        checked=Count("pk", filter=Q(last_checked__gte=day)),
        systems=Count("solar_system_id", filter=Q(solar_system_id__gt=NO_SYSTEM), distinct=True),
        scanners=Count("last_checked_by", filter=Q(last_checked__gte=day), distinct=True),
        expired=Count("pk", filter=Q(last_checked__lt=oldest)),
        # past its age by more than a day: the daily cleanup did not run
        overdue=Count("pk", filter=Q(last_checked__lt=oldest - timedelta(days=1))),
    )

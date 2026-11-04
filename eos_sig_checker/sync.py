"""Merge a paste into the shared list and resolve it from there."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .app_settings import max_age_days
from .models import Signature
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


def merge(rows: list[Line | Invalid | Skipped], character, now=None) -> list[Row | Invalid]:
    """Store every valid line and return the paste completed from the list.

    ``character`` is the main of whoever pasted, kept as the last checker.
    Invalid lines pass through untouched, so the output keeps the paste's
    order; skipped lines (no signature) drop out.
    """
    now = now or timezone.now()
    oldest = cutoff(now)
    output = []
    with transaction.atomic():
        for line in rows:
            if isinstance(line, Skipped):
                continue
            if isinstance(line, Invalid):
                output.append(line)
                continue
            # locked: two people pasting the same system at once must not
            # overwrite each other's merge halfway
            signature, created = Signature.objects.select_for_update().get_or_create(
                signature_id=line.signature_id,
                defaults={
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
                output.append(Row(line, line.site_type, line.name))
                continue

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
            output.append(
                Row(line, signature.site_type, signature.name, resolved, previous_check, previous_by)
            )
    return output


def delete_expired(now=None) -> int:
    deleted, _ = Signature.objects.filter(last_checked__lt=cutoff(now)).delete()
    return deleted

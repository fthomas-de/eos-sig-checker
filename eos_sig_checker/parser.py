"""Read what the EVE probe scanner puts on the clipboard.

One signature per line, six tab-separated columns, as the English client
copies them:

    ACJ-672	Cosmic Signature	Data Site	Unsecured Frontier Server	100,0%	10,61 AU
    YMA-080	Cosmic Signature			0,0%	11,18 AU

The text comes from a user and ends up in the database and on everybody's
page, so every column is checked against what the client can produce and a
line that does not fit is reported, never stored. Templates escape on output
anyway; this keeps junk out of the shared list.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from django.utils.translation import gettext_lazy as _

# A whole paste: a full system holds a few dozen signatures and anomalies.
MAX_LINES = 500
MAX_CHARS = 50_000

GROUPS = ("Cosmic Signature", "Cosmic Anomaly")

SIGNATURE_ID = re.compile(r"[A-Z]{3}-\d{3}")
# CCP adds site types now and then (Combat, Data, Relic, Gas, Ore Site,
# Wormhole today): checked by shape, not against a list that would go stale
SITE_TYPE = re.compile(r"[A-Za-z][A-Za-z ]{0,39}")
# site names hold letters, digits and a little punctuation ("Guristas' Hidden
# Den", "Unstable Wormhole", "Small Arkonor and Bistot Deposit")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 '\-.,:()/&]{0,99}")
SIGNAL = re.compile(r"(\d{1,3})(?:[.,](\d))?%")
# "10,61 AU", "1.234 km", "5 432 m" - thousands separators differ by locale,
# EVE uses a non-breaking space for some
DISTANCE = re.compile(r"\d[\d.,   ]{0,20} (?:AU|km|m)")


@dataclass(frozen=True)
class Line:
    """One valid line of the paste."""

    signature_id: str
    group: str
    site_type: str
    name: str
    signal: Decimal
    distance: str
    # as pasted ("100,0%"), so the output reads like the client's own copy
    signal_text: str

    @property
    def signal_band(self) -> str:
        return signal_band(self.signal)


def signal_band(signal) -> str:
    """The game's colour steps: red below 25 %, orange below 75 %,
    yellow below 100 %, green at 100 % (warpable)."""
    if signal >= 100:
        return "full"
    if signal >= 75:
        return "high"
    if signal >= 25:
        return "partial"
    return "low"


@dataclass(frozen=True)
class Invalid:
    """A line that was not stored, with the reason."""

    text: str
    error: str


@dataclass(frozen=True)
class Skipped:
    """A probe result that is no signature: a ship, drone or structure the
    scanner's filter let through, or the group name of another client
    language. Neither stored nor shown; the page only counts them."""


def _check(line: str):
    columns = [column.strip() for column in line.split("\t")]
    if len(columns) >= 2 and SIGNATURE_ID.fullmatch(columns[0]) and columns[1] not in GROUPS:
        return Skipped()
    if len(columns) != 6:
        return _("Expected 6 tab-separated columns, as the probe scanner copies them.")

    signature_id, group, site_type, name, signal, distance = columns
    if not SIGNATURE_ID.fullmatch(signature_id):
        return _("The signature ID must look like ABC-123.")
    if site_type and not SITE_TYPE.fullmatch(site_type):
        return _("The site type holds characters a site type never has.")
    if name and not NAME.fullmatch(name):
        return _("The name holds characters a site name never has.")
    if name and not site_type:
        return _("A name without a site type does not come from the probe scanner.")

    match = SIGNAL.fullmatch(signal)
    value = Decimal(f"{match.group(1)}.{match.group(2) or 0}") if match else None
    if value is None or value > 100:
        return _("The scan strength must be a percentage between 0 and 100.")
    if not DISTANCE.fullmatch(distance):
        return _("The distance must be a number with AU, km or m.")

    return Line(signature_id, group, site_type, name, value, distance, signal)


def parse(text: str) -> list[Line | Invalid | Skipped]:
    """Every non-empty line of ``text``, in order, valid or not.

    The caller limits the length (forms.PasteForm); this only reads.
    """
    rows = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        # control characters other than the tab never come from the client
        if any((ord(char) < 32 and char != "\t") or ord(char) == 127 for char in raw):
            rows.append(Invalid(_shorten(raw), str(_("The line holds control characters."))))
            continue
        result = _check(raw)
        rows.append(result if isinstance(result, (Line, Skipped)) else Invalid(_shorten(raw), str(result)))
    return rows


def _shorten(raw: str) -> str:
    # an invalid line is shown back to its author, not stored; long junk is cut
    printable = "".join(char if char.isprintable() else " " for char in raw.replace("\t", " "))
    return printable[:120]

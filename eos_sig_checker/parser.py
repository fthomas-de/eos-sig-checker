"""Read what the EVE probe scanner puts on the clipboard.

One signature per line, six tab-separated columns, as the English client
copies them:

    ACJ-672	Cosmic Signature	Data Site	Unsecured Frontier Server Bank	100,0%	10,61 AU
    YMA-080	Cosmic Signature			0,0%	11,18 AU

Another client language writes its own words (Signature cosmique, Señal
cósmica ...); parse() turns them into the English ones through the client
texts it is handed (client_text.lookup), so the list holds English only.

The text comes from a user and ends up in the database and on everybody's
page, so every column is checked against what the client can produce and a
line that does not fit is reported, never stored. Templates escape on output
anyway; this keeps junk out of the shared list.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

# The ceiling of a whole paste; the limit in force is lower and comes from
# the settings page (forms.PasteForm). A full system holds a few dozen
# signatures.
MAX_LINES = 500
MAX_CHARS = 50_000

# anomalies are on the overview without probing; the list is for what
# needs scanning, so a Cosmic Anomaly line is skipped like a ship
GROUPS = ("Cosmic Signature",)
# what the scanner's first word column can say; another client's word is
# matched against these only, so its plural ("Wormholes") never gets in the way
KINDS = ("Cosmic Signature", "Cosmic Anomaly")
SITE_TYPES = ("Combat Site", "Data Site", "Relic Site", "Gas Site", "Ore Site", "Wormhole")

# re.ASCII: without it \d takes the digits of every script, not just 0-9
SIGNATURE_ID = re.compile(r"[A-Z]{3}-\d{3}", re.ASCII)
# CCP adds site types now and then (Combat, Data, Relic, Gas, Ore Site,
# Wormhole today): checked by shape, not against a list that would go stale
SITE_TYPE = re.compile(r"[A-Za-z][A-Za-z ]{0,39}")
# site names hold letters, digits and a little punctuation ("Guristas' Hidden
# Den", "Unstable Wormhole", "Small Arkonor and Bistot Deposit")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 '\-.,:()/&]{0,99}")
# "100,0%", and "0,0 %" from the French and Spanish clients; the space may
# be a non-breaking one
SIGNAL = re.compile("([0-9]{1,3})(?:[.,]([0-9]))?[ \u00a0\u202f]?%")
# a number and a unit of letters and dots in any script: "6,62 AU",
# "6,62 UA", "10,02 а.е.", "10,02AU", "1.234 km". Only the paster's own
# distance, so the unit is not checked against a list.
DISTANCE = re.compile("[0-9][0-9.,\u00a0\u202f ]{0,20}[^\\W\\d_](?:[^\\W\\d_]|\\.){0,9}")

# client text -> {(language, English)}, as client_text.lookup returns it
Lookup = Callable[[set[str]], dict[str, set[tuple[str, str]]]]


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
    # what another client wrote that could not be put into English; the
    # column is left blank, the line is stored and the Errors tab gets it
    problems: tuple = ()
    # the line as pasted, flattened, for the Errors tab
    source: str = field(default="", compare=False)

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
    # lazy: the page shows it in the reader's language, the log stores English
    error: str


@dataclass(frozen=True)
class Skipped:
    """A probe result that is no signature: an anomaly, a ship, drone or
    structure the scanner's filter let through, or the group name of a client
    language without client texts. Neither stored nor shown; the page only
    counts them."""


def _english(text: str, mapping: dict, languages: set, allowed=None) -> tuple[str | None, int]:
    """The one English meaning of a client text, and how many there were."""
    meanings = {english for language, english in mapping.get(text, ()) if language in languages}
    if allowed is not None:
        meanings &= set(allowed)
    return (next(iter(meanings)) if len(meanings) == 1 else None), len(meanings)


def _problem(column, text: str, count: int):
    reason = _("several meanings") if count else _("not in the client texts")
    # lazy: the log writes it in English
    return format_lazy("{} {}: {} ({})", column, _("not translated"), text, reason)


def _translate(columns: list[str], mapping: dict) -> tuple[list[str], list] | None:
    """The columns of another client's line in English, and what could not be
    translated; None when its first word is no Cosmic Signature or Anomaly."""
    meanings = {(language, english) for language, english in mapping.get(columns[1], ()) if english in KINDS}
    kinds = {english for _language, english in meanings}
    if len(kinds) != 1:
        return None
    columns = [columns[0], kinds.pop(), *columns[2:]]
    if len(columns) != 6:
        return columns, []

    languages = {language for language, _english in meanings}
    problems = []
    site_type, name = columns[2], columns[3]
    if site_type:
        english, count = _english(site_type, mapping, languages, SITE_TYPES)
        if english is None:
            # a name without its type does not come from the scanner: both go
            problems.append(_problem(pgettext_lazy("eos-sig-checker", "Group"), site_type, count))
            site_type, name = "", ""
        else:
            site_type = english
    if name:
        english, count = _english(name, mapping, languages)
        if english is None:
            problems.append(_problem(pgettext_lazy("eos-sig-checker", "Name"), name, count))
            name = ""
        else:
            name = english
    columns[2], columns[3] = site_type, name
    return columns, problems


def _check(line: str, mapping: dict) -> Line | Invalid | Skipped:
    # control characters other than the tab never come from the client
    if any((ord(char) < 32 and char != "\t") or ord(char) == 127 for char in line):
        return _invalid(line, _("The line holds control characters."))
    columns = [column.strip() for column in line.split("\t")]
    problems = []
    if len(columns) >= 2 and SIGNATURE_ID.fullmatch(columns[0]) and columns[1] not in GROUPS:
        translated = _translate(columns, mapping)
        if translated is None or translated[0][1] not in GROUPS:
            return Skipped()
        columns, problems = translated
    if len(columns) != 6:
        return _invalid(line, _("Expected 6 tab-separated columns, as the probe scanner copies them."))

    signature_id, group, site_type, name, signal, distance = columns
    if not SIGNATURE_ID.fullmatch(signature_id):
        return _invalid(line, _("The signature ID must look like ABC-123."))
    if site_type and not SITE_TYPE.fullmatch(site_type):
        return _invalid(line, _("The site type holds characters a site type never has."))
    if name and not NAME.fullmatch(name):
        return _invalid(line, _("The name holds characters a site name never has."))
    if name and not site_type:
        return _invalid(line, _("A name without a site type does not come from the probe scanner."))

    match = SIGNAL.fullmatch(signal)
    value = Decimal(f"{match.group(1)}.{match.group(2) or 0}") if match else None
    if value is None or value > 100:
        return _invalid(line, _("The scan strength must be a percentage between 0 and 100."))
    if not DISTANCE.fullmatch(distance):
        return _invalid(line, _("The distance must be a number with a unit."))

    return Line(
        signature_id, group, site_type, name, value, distance, signal,
        tuple(problems), _printable(line) if problems else "",
    )


def parse(text: str, lookup: Lookup | None = None) -> list[Line | Invalid | Skipped]:
    """Every non-empty line of ``text``, in order, valid or not.

    lookup (client_text.lookup) is asked once for the words of every line
    from another client; without it such a line is skipped. The caller
    limits the length (forms.PasteForm); this only reads.
    """
    lines = [raw for raw in text.splitlines() if raw.strip()]
    words = set()
    for raw in lines:
        columns = [column.strip() for column in raw.split("\t")]
        if len(columns) >= 2 and SIGNATURE_ID.fullmatch(columns[0]) and columns[1] not in GROUPS:
            words.update(column for column in columns[1:4] if column)
    mapping = lookup(words) if lookup and words else {}
    return [_check(raw, mapping) for raw in lines]


def _printable(raw: str) -> str:
    # shown back and logged, never parsed again; long junk is cut
    return "".join(char if char.isprintable() else " " for char in raw.replace("\t", " "))[:120]


def _invalid(raw: str, error) -> Invalid:
    return Invalid(_printable(raw), error)

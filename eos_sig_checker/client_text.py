"""The texts of the EVE client in its languages, as pairs with the English.

Filled from the archive of client texts (one JSON file per language,
{message_id: {"en": ..., <language>: ...}}). The archive is foreign data,
so pairs() lets in only what the parser would accept as English and a
translation that is plain text.
"""

import io
import json
import re
import tempfile
from collections import defaultdict
import requests

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import get_language

from . import __version__
from .models import ClientText, ClientTextLanguage
from .parser import NAME

# exported from the client every day; the state files say what the latest files hold
ARCHIVE = "https://raw.githubusercontent.com/Kelly-Hsueh/EVE-localisation-json-archive/main"
BUILD_URL = f"{ARCHIVE}/state/tq-build.txt"
HASHES_URL = f"{ARCHIVE}/state/tq-hashes.json"
FILE_URL = ARCHIVE + "/latest/tq/{language}.json"
HEADERS = {"User-Agent": f"eos-sig-checker/{__version__}"}
# connect, then each read; a file is 50-100 MB
TIMEOUT = (10, 60)
# the settings page asks on every view: it must not hang on a slow archive
CHECK_TIMEOUT = (3, 5)
# today's largest file (ru) is about 100 MB; a cap keeps a broken source off the disk
MAX_FILE_BYTES = 300 * 1024 * 1024
MAX_STATE_BYTES = 64 * 1024
BUILD = re.compile(r"\d{1,20}", re.ASCII)
DIGEST = re.compile(r"[0-9a-f]{1,64}", re.ASCII)
# the button and the daily task must not fetch the same files twice at once
LOCK = "eos_sig_checker:client_text:update"
LOCK_SECONDS = 3600

# the client languages the archive has; Alliance Auth's nl, pl and uk have none
LANGUAGES = ("de", "es", "fr", "it", "ja", "ko", "ru", "zh")
# a translation runs longer than its English, which NAME caps at 100
MAX_TEXT = 200


class ClientTextError(Exception):
    """The archive could not be read or holds something unexpected."""


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def pairs(entries: dict, language: str) -> set[tuple[str, str]]:
    """(English, translation) from one archive file.

    Kept: English the parser takes for a name (parser.NAME) with a printable
    translation without markup. An untranslated text stays in as itself:
    that client shows the English there, and its paste must still find it.
    One English may have several translations and one translation several
    English texts (in Japanese "Wormhole" and "Wormholes" are one word):
    the lookups decide per direction what is unambiguous where they need it.
    """
    found = set()
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        english, text = _text(entry.get("en")), _text(entry.get(language))
        if not english or not text or not NAME.fullmatch(english):
            continue
        if len(text) > MAX_TEXT or "<" in text or not text.isprintable():
            continue
        found.add((english, text))
    return found


def lookup(texts: set[str]) -> dict[str, set[tuple[str, str]]]:
    """Client text -> {(language, English)} for the words of a paste (parser.parse)."""
    found = defaultdict(set)
    for text, language, english in ClientText.objects.filter(text__in=texts).values_list("text", "language", "english"):
        # MySQL's collation matches without case and accents; the client's word is exact
        if text in texts:
            found[text].add((language, english))
    return found


def display(englishes, language=None) -> dict[str, str]:
    """English -> the reader's client language, for what has exactly one
    translation there; the rest stays English.

    language is Alliance Auth's code ("de", "fr-fr", "zh-hans"); its first
    part is the archive's. Without client texts (en, nl, pl, uk) nothing.
    """
    language = (language or get_language() or "").split("-")[0]
    englishes = set(englishes) - {""}
    if language not in LANGUAGES or not englishes:
        return {}
    found = defaultdict(set)
    rows = ClientText.objects.filter(language=language, english__in=englishes).values_list("english", "text")
    for english, text in rows:
        # MySQL's collation matches without case and accents; the stored English is exact
        if english in englishes:
            found[english].add(text)
    shown = {}
    for english, texts in found.items():
        # left untranslated in one place and translated in another: the translation
        texts = texts - {english} or texts
        if len(texts) == 1:
            shown[english] = next(iter(texts))
    return shown


def store(language: str, found: set[tuple[str, str]], build: str, digest: str) -> None:
    """Replace one language's pairs at once: no page sees half a file."""
    if language not in LANGUAGES:
        raise ValueError(f"not a client language: {language!r}")
    with transaction.atomic():
        ClientText.objects.filter(language=language).delete()
        ClientText.objects.bulk_create(
            (ClientText(language=language, english=english, text=text) for english, text in found),
            batch_size=2000,
        )
        ClientTextLanguage.objects.update_or_create(
            language=language,
            defaults={"build": build, "digest": digest, "imported": timezone.now(), "count": len(found)},
        )


def _fetch(url: str, limit: int, into, timeout=TIMEOUT) -> None:
    """Write url into the file into, at most limit bytes."""
    try:
        with requests.get(url, stream=True, timeout=timeout, headers=HEADERS) as response:
            response.raise_for_status()
            size = 0
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ClientTextError(f"{url} is larger than {limit} bytes.")
                into.write(chunk)
    except requests.RequestException as error:
        raise ClientTextError(f"{url} could not be read: {error}") from error
    into.seek(0)


def _json(file, url: str):
    try:
        return json.load(file)
    except ValueError as error:
        raise ClientTextError(f"{url} is no JSON: {error}") from error


def available(timeout=TIMEOUT) -> tuple[str, dict[str, str]]:
    """The archive's latest build and the hash of each client language's file."""
    with io.BytesIO() as file:
        _fetch(BUILD_URL, MAX_STATE_BYTES, file, timeout)
        build = file.read().decode("ascii", "replace").strip()
    with io.BytesIO() as file:
        _fetch(HASHES_URL, MAX_STATE_BYTES, file, timeout)
        hashes = _json(file, HASHES_URL)
    if not BUILD.fullmatch(build) or not isinstance(hashes, dict):
        raise ClientTextError("The archive's state files hold something unexpected.")
    return build, {
        language: hashes[language]
        for language in LANGUAGES
        if isinstance(hashes.get(language), str) and DIGEST.fullmatch(hashes[language])
    }


def status() -> dict:
    """What the settings page shows: each language as imported, and whether
    the archive has a newer file. An unreachable archive is reported, not raised."""
    stored = {row.language: row for row in ClientTextLanguage.objects.all()}
    try:
        build, digests = available(CHECK_TIMEOUT)
        error = ""
    except ClientTextError as exc:
        build, digests, error = "", {}, str(exc)
    languages = [
        {
            "language": language,
            "stored": stored.get(language),
            "outdated": language in digests and getattr(stored.get(language), "digest", None) != digests[language],
        }
        for language in LANGUAGES
    ]
    return {"build": build, "error": error, "languages": languages, "running": bool(cache.get(LOCK))}


def update(force: bool = False) -> list[str]:
    """Fetch every client language whose file changed since its import.

    One language after the other: reading a file takes about 500 MB.
    Returns the languages updated.
    """
    if not cache.add(LOCK, True, timeout=LOCK_SECONDS):
        raise ClientTextError("An update of the client texts is running already.")
    try:
        build, digests = available()
        stored = dict(ClientTextLanguage.objects.values_list("language", "digest"))
        updated = []
        for language, digest in digests.items():
            if not force and stored.get(language) == digest:
                continue
            url = FILE_URL.format(language=language)
            with tempfile.TemporaryFile() as file:
                _fetch(url, MAX_FILE_BYTES, file)
                entries = _json(file, url)
            if not isinstance(entries, dict):
                raise ClientTextError(f"{url} holds no object.")
            found = pairs(entries, language)
            del entries
            store(language, found, build, digest)
            updated.append(language)
        return updated
    finally:
        cache.delete(LOCK)

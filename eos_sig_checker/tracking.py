"""Where a tracked character is: its token and its solar system from ESI.

A browser tab picks one of the user's own characters; every check of that
tab is stored with the character's current system. The tab names the
character, never the system: the server looks the system up itself, so a
request cannot place signatures somewhere else.
"""

from dataclasses import dataclass

from django.core.cache import cache
from django.utils.translation import gettext as _

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from esi.errors import SSOOAuthError, TokenError
from esi.models import Token

from .app_settings import location_retry_seconds
from .provider import esi

logger = get_extension_logger(__name__)

SCOPE = "esi-location.read_location.v1"

# ESI caches a character's location for 5 seconds: asking more often only
# spends the error budget. Every tab of every user goes through this cache,
# failed reads included, so a script cannot make the server ask ESI or SSO
# faster either.
LOCATION_CACHE_SECONDS = 5

# A failed read is asked again after LOCATION_CACHE_SECONDS, then later with
# every further failure in a row: in this many even steps up to the limit
# from the settings page. A dead token or an ESI outage would otherwise send
# every poll of every tab to SSO or ESI again and spend the error budget all
# apps of the instance share.
RETRY_STEPS = 5
# how long the count of failures outlives the wait: longer than a poll
# (views.LOCATION_INTERVAL_SECONDS), or every failure would count as the first
FAILURES_KEPT_SECONDS = 60
FAILURES_KEY = "eos_sig_checker:location_failures:{}"


@dataclass(frozen=True)
class Location:
    system_id: int
    system_name: str


class LocationError(Exception):
    """The location could not be read; the message is shown to the user."""


def trackable_characters(user):
    """The user's own characters that have a token with the location scope.

    Only existing tokens count - the app asks for none of its own.
    """
    with_token = Token.objects.filter(user=user).require_scopes([SCOPE]).values("character_id")
    return EveCharacter.objects.filter(character_ownership__user=user, character_id__in=with_token).order_by(
        "character_name"
    )


def _token(user, character_id: int) -> Token | None:
    # ownership first: a token alone may belong to a character the user
    # has since lost to another account
    if not CharacterOwnership.objects.filter(user=user, character__character_id=character_id).exists():
        return None
    return Token.objects.filter(user=user, character_id=character_id).require_scopes([SCOPE]).order_by("-created").first()


def _retry_seconds(failures: int) -> int:
    """How long the read stays refused after ``failures`` failures in a row."""
    limit = max(location_retry_seconds(), LOCATION_CACHE_SECONDS)
    step = min(failures, RETRY_STEPS) - 1
    return LOCATION_CACHE_SECONDS + round((limit - LOCATION_CACHE_SECONDS) * step / (RETRY_STEPS - 1))


def _failure(character_id: int, key: str, message: str) -> LocationError:
    """Remember a failed read for its wait and return the error to raise."""
    failures_key = FAILURES_KEY.format(character_id)
    failures = (cache.get(failures_key) or 0) + 1
    wait = _retry_seconds(failures)
    cache.set(failures_key, failures, wait + FAILURES_KEPT_SECONDS)
    cache.set(key, message, wait)
    return LocationError(message)


def locate(user, character_id: int) -> Location:
    """The character's current solar system; raises LocationError."""
    # checked before the cache: the cached location of somebody else's
    # character must not leak to a user who names its ID
    token = _token(user, character_id)
    if token is None:
        raise LocationError(_("This character cannot be tracked: it is not yours or has no token with the location scope."))

    key = f"eos_sig_checker:location:{character_id}"
    cached = cache.get(key)
    if isinstance(cached, Location):
        return cached
    # the message of a failed read, still inside its wait
    if cached is not None:
        raise LocationError(cached)

    try:
        found = esi.client.Location.GetCharactersCharacterIdLocation(character_id=character_id, token=token).result(
            use_etag=False
        )
        system = esi.client.Universe.GetUniverseSystemsSystemId(system_id=found.solar_system_id).result(use_etag=False)
    # a refresh token SSO no longer accepts stays in the list until the user
    # adds the character again: say so, "try again" would never help
    except (TokenError, SSOOAuthError):
        logger.info("Token of character %s refused by SSO", character_id, exc_info=True)
        raise _failure(
            character_id,
            key,
            _("The token of this character is no longer valid. Add the character again with the location scope."),
        ) from None
    # ESI, the token refresh and the network fail in many ways; each one only
    # means "no location now" to the page, the log keeps the cause
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Location of character %s not available", character_id, exc_info=True)
        raise _failure(
            character_id, key, _("The location could not be read from ESI. Try again in a moment.")
        ) from None

    location = Location(found.solar_system_id, system.name)
    cache.set(key, location, LOCATION_CACHE_SECONDS)
    cache.delete(FAILURES_KEY.format(character_id))
    return location

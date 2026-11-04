from esi.openapi_clients import ESIClientProvider

from eos_sig_checker import __compat_date__, __title__, __url__, __version__

# The two ESI operations of location tracking: where a character is, and the
# name of that system.
esi = ESIClientProvider(
    compatibility_date=__compat_date__,
    ua_appname=__title__,
    ua_version=__version__,
    ua_url=__url__,
    operations=[
        "GetCharactersCharacterIdLocation",
        "GetUniverseSystemsSystemId",
    ],
)

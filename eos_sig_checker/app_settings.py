from django.conf import settings

DEFAULT_MAX_AGE_DAYS = 7


def max_age_days() -> int:
    """How long a signature counts after its last check, from local.py.

    Read at call time, never into a model default: a default taken from
    settings ends up in the migration and differs per installation.
    """
    value = getattr(settings, "EOS_SIG_CHECKER_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS)
    # a typo in local.py must not delete the whole list or keep it forever
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return DEFAULT_MAX_AGE_DAYS
    return value

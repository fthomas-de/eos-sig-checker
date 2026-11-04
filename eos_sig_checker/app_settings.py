from .models import SigCheckerConfiguration


def max_age_days() -> int:
    """How long a signature counts after its last check, from the settings page.

    Read at call time: the cleanup task, the merge and the page follow a
    change on the settings page without a restart.
    """
    return SigCheckerConfiguration.get_solo().max_age_days

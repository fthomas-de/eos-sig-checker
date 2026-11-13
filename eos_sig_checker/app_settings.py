from .models import SigCheckerConfiguration


def max_age_days() -> int:
    """How long a signature counts after its last check, from the settings page.

    Read at call time: the cleanup task, the merge and the page follow a
    change on the settings page without a restart.
    """
    return SigCheckerConfiguration.get_solo().max_age_days


def location_retry_seconds() -> int:
    """The longest wait after failed location reads, from the settings page."""
    return SigCheckerConfiguration.get_solo().location_retry_seconds


def max_lines() -> int:
    """The most lines one paste may hold, from the settings page."""
    return SigCheckerConfiguration.get_solo().max_lines

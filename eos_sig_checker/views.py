from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.shortcuts import render
from django.utils.translation import gettext as _

from . import __version__, parser, sync
from .app_settings import max_age_days
from .forms import PasteForm
from .parser import Invalid, Skipped

# at most one check per user and second - each one writes up to 500 rows
MIN_INTERVAL_SECONDS = 1


def _copy_text(output) -> str:
    """The completed paste in the probe scanner's own format."""
    lines = []
    for row in output:
        if isinstance(row, Invalid):
            continue
        line = row.line
        lines.append(
            "\t".join(
                (line.signature_id, line.group, row.site_type, row.name, line.signal_text, line.distance)
            )
        )
    return "\n".join(lines)


def _too_soon(user) -> bool:
    """True for a second check within MIN_INTERVAL_SECONDS of the last one.

    The page checks on every paste; the browser waits on its own, but only
    the server's limit holds against a script. cache.add is atomic, so two
    requests at the same moment cannot both pass.
    """
    return not cache.add(f"eos_sig_checker:check:{user.pk}", True, timeout=MIN_INTERVAL_SECONDS)


@login_required
@permission_required("eos_sig_checker.basic_access")
def index(request):
    output = None
    skipped = 0
    status = 200
    if request.method == "POST":
        form = PasteForm(request.POST)
        if form.is_valid():
            if _too_soon(request.user):
                form.add_error(None, _("Too many checks: wait a second and press Check again."))
                status = 429
            else:
                rows = parser.parse(form.cleaned_data["text"])
                # counted, not shown: a paste from another client language
                # would otherwise vanish without a word
                skipped = sum(isinstance(row, Skipped) for row in rows)
                output = sync.merge(rows, request.user.profile.main_character)
    else:
        form = PasteForm()

    context = {
        "min_interval_ms": MIN_INTERVAL_SECONDS * 1000,
        "form": form,
        "output": output,
        "skipped": skipped,
        "copy_text": _copy_text(output) if output else "",
        "max_age_days": max_age_days(),
        "version": __version__,
    }
    return render(request, "eos_sig_checker/index.html", context, status=status)

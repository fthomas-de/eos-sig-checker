from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from . import __version__, parser, sync
from .app_settings import max_age_days
from .forms import ConfigurationForm, PasteForm
from .models import SigCheckerConfiguration, Signature
from .parser import Invalid, Skipped

BASIC_ACCESS = "eos_sig_checker.basic_access"
MANAGE_SETTINGS = "eos_sig_checker.manage_settings"

# at most one check per user and second - each one writes up to 500 rows
MIN_INTERVAL_SECONDS = 1

# the tab of the app navbar a page belongs to
NAV_CHECK = "check"
NAV_SIGNATURES = "signatures"
NAV_SETTINGS = "settings"


def _render(request, template, context, nav, status=200):
    return render(request, template, {"version": __version__, "nav": nav, **context}, status=status)


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
@user_passes_test(lambda user: user.has_perm(BASIC_ACCESS) or user.has_perm(MANAGE_SETTINGS))
def index(request):
    # the menu entry leads here; whoever may only manage the list lands on
    # the settings instead of a page that refuses them
    if not request.user.has_perm(BASIC_ACCESS):
        return redirect("eos_sig_checker:settings")

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
    }
    return _render(request, "eos_sig_checker/index.html", context, NAV_CHECK, status=status)


@login_required
@permission_required(MANAGE_SETTINGS)
def signatures(request):
    """Everything in the table, expired rows included: the count matches
    what Delete all would remove."""
    context = {
        "signatures": Signature.objects.select_related("last_checked_by").order_by("-last_checked"),
        "oldest": sync.cutoff(),
    }
    return _render(request, "eos_sig_checker/signatures.html", context, NAV_SIGNATURES)


@login_required
@permission_required(MANAGE_SETTINGS)
def settings(request):
    form = ConfigurationForm(request.POST or None, instance=SigCheckerConfiguration.get_solo())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Settings saved."))
        return redirect("eos_sig_checker:settings")

    context = {"form": form, "signature_count": Signature.objects.count()}
    return _render(request, "eos_sig_checker/settings.html", context, NAV_SETTINGS)


@login_required
@permission_required(MANAGE_SETTINGS)
@require_POST
def delete_all(request):
    deleted, _rows = Signature.objects.all().delete()
    messages.success(
        request,
        ngettext("Deleted %(count)d signature.", "Deleted %(count)d signatures.", deleted) % {"count": deleted},
    )
    return redirect("eos_sig_checker:settings")

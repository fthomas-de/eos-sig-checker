from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from . import __version__, parser, sync, tracking
from .app_settings import max_age_days
from .forms import ConfigurationForm, PasteForm
from .models import SigCheckerConfiguration, Signature
from .parser import Invalid, Skipped

BASIC_ACCESS = "eos_sig_checker.basic_access"
MANAGE_SETTINGS = "eos_sig_checker.manage_settings"

# at most one check per user and second - each one writes up to 500 rows
MIN_INTERVAL_SECONDS = 1

# how often a tracking tab asks where its character is; the Refresh button
# may ask sooner, but not within tracking.LOCATION_CACHE_SECONDS
LOCATION_INTERVAL_SECONDS = 10

# the tab of the app navbar a page belongs to
NAV_CHECK = "check"
NAV_SIGNATURES = "signatures"
NAV_SETTINGS = "settings"


def has_access(user) -> bool:
    """Either permission opens the app: the menu entry and the index both ask this."""
    return user.has_perm(BASIC_ACCESS) or user.has_perm(MANAGE_SETTINGS)


def _render(request, template, context, nav, status=200):
    return render(request, template, {"version": __version__, "nav": nav, "statistics": sync.statistics(), **context}, status=status)


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


def _tracked_character(request) -> int | None:
    """The character this tab tracks: ?character=<id> in the page's URL.

    In the URL, not in the session: the session is shared by every tab,
    and each tab may track a character of its own. The paste form posts to
    the same URL, so a check carries it too.
    """
    try:
        return int(request.GET["character"])
    except (KeyError, ValueError):
        return None


@login_required
@user_passes_test(has_access)
def index(request):
    # the menu entry leads here; whoever may only manage the list lands on
    # the settings instead of a page that refuses them
    if not request.user.has_perm(BASIC_ACCESS):
        return redirect("eos_sig_checker:settings")

    character_id = _tracked_character(request)
    location = None
    tracking_error = ""
    if character_id is not None:
        try:
            location = tracking.locate(request.user, character_id)
        except tracking.LocationError as error:
            # the check still runs, only without a system
            tracking_error = str(error)

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
                output = sync.merge(rows, request.user.profile.main_character, system=location)
    else:
        form = PasteForm()

    pasted = output is not None
    if location:
        pasted_ids = [row.line.signature_id for row in output or [] if not isinstance(row, Invalid)]
        output = (output or []) + sync.system_rows(location, skip_ids=pasted_ids)

    context = {
        "min_interval_ms": MIN_INTERVAL_SECONDS * 1000,
        "form": form,
        "output": output,
        "pasted": pasted,
        "skipped": skipped,
        "copy_text": _copy_text(output) if output else "",
        "max_age_days": max_age_days(),
        "characters": tracking.trackable_characters(request.user),
        # locate() returns or raises, so a named character always has a location or an error
        "tracked_character_id": character_id,
        "location": location,
        "tracking_error": tracking_error,
        "location_interval_ms": LOCATION_INTERVAL_SECONDS * 1000,
        "refresh_interval_ms": tracking.LOCATION_CACHE_SECONDS * 1000,
        "scope": tracking.SCOPE,
    }
    return _render(request, "eos_sig_checker/index.html", context, NAV_CHECK, status=status)


@login_required
@permission_required(BASIC_ACCESS)
def tracked_location(request):
    """The tracked character's system, asked by tracking.js every few seconds."""
    character_id = _tracked_character(request)
    if character_id is None:
        return JsonResponse({"error": _("No character given.")}, status=400)
    try:
        found = tracking.locate(request.user, character_id)
    except tracking.LocationError as error:
        return JsonResponse({"error": str(error)}, status=503)
    return JsonResponse({"system_id": found.system_id, "system_name": found.system_name})


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

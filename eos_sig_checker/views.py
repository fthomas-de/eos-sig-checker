from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from . import __version__, client_text, parser, sync, tasks, tracking
from .app_settings import error_log_days, max_age_days, system_hours, wormhole_hours
from .forms import ConfigurationForm, PasteForm
from .models import RejectedLine, SigCheckerConfiguration, Signature
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
NAV_ERRORS = "errors"


def has_access(user) -> bool:
    """Either permission opens the app: the menu entry and the index both ask this."""
    return user.has_perm(BASIC_ACCESS) or user.has_perm(MANAGE_SETTINGS)


def _render(request, template, context, nav, status=200):
    return render(request, template, {"version": __version__, "nav": nav, "statistics": sync.statistics(), **context}, status=status)


def _copy_text(output, texts) -> str:
    """The completed paste in the probe scanner's own format, in the reader's client language."""
    lines = []
    for row in output:
        if isinstance(row, Invalid):
            continue
        line = row.line
        words = (texts.get(word, word) for word in (line.group, row.site_type, row.name))
        lines.append("\t".join((line.signature_id, *words, line.signal_text, line.distance)))
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
                rows = parser.parse(form.cleaned_data["text"], client_text.lookup)
                sync.log_rejected(rows, request.user.profile.main_character)
                # counted, not shown: a paste from another client language
                # would otherwise vanish without a word
                skipped = sum(isinstance(row, Skipped) for row in rows)
                output = sync.merge(rows, request.user.profile.main_character, system=location)
                # processed: the box is empty for the next paste, the result
                # keeps every line, the invalid ones with their text
                form = PasteForm()
    else:
        form = PasteForm()

    pasted = output is not None
    if location:
        pasted_ids = [row.line.signature_id for row in output or [] if not isinstance(row, Invalid)]
        output = (output or []) + sync.system_rows(location, skip_ids=pasted_ids)

    texts = client_text.display(
        word
        for row in output or []
        if not isinstance(row, Invalid)
        for word in (row.line.group, row.site_type, row.name)
    )
    context = {
        "min_interval_ms": MIN_INTERVAL_SECONDS * 1000,
        "form": form,
        "output": output,
        "pasted": pasted,
        "skipped": skipped,
        # site data in the reader's client language; the list itself stays English
        "texts": texts,
        "copy_text": _copy_text(output, texts) if output else "",
        "max_age_days": max_age_days(),
        # read after the merge, so this paste's wormholes are in it
        "wormholes": sync.recent_wormholes(),
        "wormhole_hours": wormhole_hours(),
        "systems": sync.recent_systems(),
        "system_hours": system_hours(),
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
    signatures = list(Signature.objects.select_related("last_checked_by").order_by("-last_checked"))
    context = {
        "signatures": signatures,
        "texts": client_text.display(word for signature in signatures for word in (signature.site_type, signature.name)),
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

    context = {
        "form": form,
        "signature_count": Signature.objects.count(),
        # asks the archive on every view: whether an update is waiting is the point of the card
        "client_texts": client_text.status(),
    }
    return _render(request, "eos_sig_checker/settings.html", context, NAV_SETTINGS)


@login_required
@permission_required(MANAGE_SETTINGS)
@require_POST
def client_texts_update(request):
    # in the background: fetching every language takes minutes
    tasks.update_client_texts.delay()
    messages.success(request, _("Update of the client texts started. It runs in the background and takes a few minutes."))
    return redirect("eos_sig_checker:settings")


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


@login_required
@permission_required(MANAGE_SETTINGS)
def errors(request):
    context = {
        "rejected": RejectedLine.objects.select_related("character").order_by("-created"),
        "error_log_days": error_log_days(),
    }
    return _render(request, "eos_sig_checker/errors.html", context, NAV_ERRORS)


@login_required
@permission_required(MANAGE_SETTINGS)
@require_POST
def delete_errors(request):
    deleted, _rows = RejectedLine.objects.all().delete()
    messages.success(
        request,
        ngettext("Deleted %(count)d rejected line.", "Deleted %(count)d rejected lines.", deleted) % {"count": deleted},
    )
    return redirect("eos_sig_checker:errors")

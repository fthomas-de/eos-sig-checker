from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .app_settings import max_lines
from .models import (
    LOCATION_RETRY_SECONDS_LIMIT,
    LOCATION_RETRY_SECONDS_MIN,
    MAX_AGE_DAYS_LIMIT,
    WORMHOLE_HOURS_LIMIT,
    SigCheckerConfiguration,
)
from .parser import MAX_CHARS, MAX_LINES


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = SigCheckerConfiguration
        fields = ["max_age_days", "location_retry_seconds", "max_lines", "wormhole_hours"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # the model's validators decide; the attributes only let the browser
        # say so before the round trip. Set after the field is built: it
        # writes its own min=0 (positive integer) over a Meta widget's.
        self.fields["max_age_days"].widget.attrs.update(min=1, max=MAX_AGE_DAYS_LIMIT)
        self.fields["location_retry_seconds"].widget.attrs.update(
            min=LOCATION_RETRY_SECONDS_MIN, max=LOCATION_RETRY_SECONDS_LIMIT
        )
        self.fields["max_lines"].widget.attrs.update(min=1, max=MAX_LINES)
        self.fields["wormhole_hours"].widget.attrs.update(min=1, max=WORMHOLE_HOURS_LIMIT)


class PasteForm(forms.Form):
    # strip=False: the tabs at the end of an unscanned line are columns
    text = forms.CharField(
        label=_("Probe scanner"),
        max_length=MAX_CHARS,
        strip=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control font-monospace eos-sig-checker-pane",
                "spellcheck": "false",
                "autocomplete": "off",
                "placeholder": _("Select the results in the probe scanner, copy them with Ctrl+C and paste them here."),
            }
        ),
    )

    def clean_text(self):
        text = self.cleaned_data["text"]
        lines = sum(1 for line in text.splitlines() if line.strip())
        limit = max_lines()
        if lines > limit:
            raise forms.ValidationError(
                ngettext(
                    "At most %(max)d line per paste.",
                    "At most %(max)d lines per paste.",
                    limit,
                )
                % {"max": limit}
            )
        return text

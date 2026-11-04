from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .parser import MAX_CHARS, MAX_LINES


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
        if lines > MAX_LINES:
            raise forms.ValidationError(
                ngettext(
                    "At most %(max)d line per paste.",
                    "At most %(max)d lines per paste.",
                    MAX_LINES,
                )
                % {"max": MAX_LINES}
            )
        return text

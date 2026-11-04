from django.apps import AppConfig

from eos_sig_checker import __version__


class EosSigCheckerConfig(AppConfig):
    name = "eos_sig_checker"
    label = "eos_sig_checker"
    verbose_name = f"EOS Sig Checker v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"

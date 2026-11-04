from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class SigCheckerMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Sig Checker"),
            "fas fa-satellite-dish",
            "eos_sig_checker:index",
            navactive=["eos_sig_checker:"],
        )

    def render(self, request):
        user = request.user
        # the index sends whoever may only manage the list on to the settings
        if not (user.has_perm("eos_sig_checker.basic_access") or user.has_perm("eos_sig_checker.manage_settings")):
            return ""
        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_menu():
    return SigCheckerMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "eos_sig_checker", r"^eos_sig_checker/")

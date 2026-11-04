from django.contrib import admin

from .models import Signature


# for the admin who wants to look at or clear the list; members use the page
@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = (
        "solar_system_name",
        "signature_id",
        "group",
        "site_type",
        "name",
        "signal",
        "first_seen",
        "last_checked",
        "last_checked_by",
    )
    list_filter = ("group", "site_type")
    search_fields = ("signature_id", "name", "solar_system_name")
    ordering = ("solar_system_name", "signature_id")
    list_select_related = ("last_checked_by",)
    raw_id_fields = ("last_checked_by",)

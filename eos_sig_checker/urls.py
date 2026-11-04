from django.urls import path

from . import views

app_name = "eos_sig_checker"

urlpatterns = [
    path("", views.index, name="index"),
    path("signatures/", views.signatures, name="signatures"),
    path("settings/", views.settings, name="settings"),
    path("settings/delete-all/", views.delete_all, name="delete_all"),
]

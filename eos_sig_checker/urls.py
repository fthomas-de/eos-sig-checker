from django.urls import path

from . import views

app_name = "eos_sig_checker"

urlpatterns = [
    path("", views.index, name="index"),
    path("location/", views.tracked_location, name="location"),
    path("signatures/", views.signatures, name="signatures"),
    path("settings/", views.settings, name="settings"),
    path("settings/delete-all/", views.delete_all, name="delete_all"),
    path("settings/client-texts/", views.client_texts_update, name="client_texts_update"),
    path("errors/", views.errors, name="errors"),
    path("errors/delete-all/", views.delete_errors, name="delete_errors"),
]

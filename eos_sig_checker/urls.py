from django.urls import path

from . import views

app_name = "eos_sig_checker"

urlpatterns = [
    path("", views.index, name="index"),
]

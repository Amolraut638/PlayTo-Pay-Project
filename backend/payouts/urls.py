from django.urls import path

from . import views


urlpatterns = [
    path("merchants", views.merchants, name="merchants"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("payouts", views.payouts, name="payouts"),
]

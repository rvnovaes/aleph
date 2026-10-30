from django.urls import path

from catalog import views
from catalog.api import api

urlpatterns = [
    path("api/covers/<int:work_id>", views.cover),
    path("api/session", views.session),
    path("api/login", views.sign_in),
    path("api/logout", views.sign_out),
    path("api/pdfs/<int:document_id>", views.pdf),
    path("api/v1/", api.urls),
]

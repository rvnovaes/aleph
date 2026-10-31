import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


def test_health_checks_database_without_login():
    response = Client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
)
def test_trusted_https_proxy_and_secure_cookies():
    client = Client()
    assert client.get("/api/session").status_code == 301
    assert client.get("/api/session", HTTP_X_FORWARDED_PROTO="https").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_catalog_total_ignores_filters_and_excludes_other_users():
    from django.contrib.auth import get_user_model
    from catalog.models import Work

    user = get_user_model().objects.create_user(username="counter")
    other = get_user_model().objects.create_user(username="other-counter")
    Work.objects.create(owner=user, title="Encontrado", kind="book")
    Work.objects.create(owner=user, title="Outro", kind="book")
    Work.objects.create(owner=other, title="Privado", kind="book")
    client = Client()
    client.force_login(user)
    data = client.get("/api/v1/works", {"q": "Encontrado"}).json()
    assert data["count"] == 1
    assert data["total_count"] == 2

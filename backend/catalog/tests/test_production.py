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

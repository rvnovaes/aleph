import pytest

from catalog.models import Language
from catalog.tests.test_catalog import create

pytestmark = pytest.mark.django_db


def test_languages_start_with_defaults_and_keep_used_codes(authenticated):
    work = create(authenticated).json()
    payload = authenticated.get(f"/api/v1/works/{work['id']}").json()
    payload["language"] = "tup"
    assert (
        authenticated.put(
            f"/api/v1/works/{work['id']}", payload, content_type="application/json"
        ).status_code
        == 200
    )
    rows = authenticated.get("/api/v1/languages").json()
    assert {"value": "por", "name": "Português"} in rows
    assert {"value": "tup", "name": "tup"} in rows


def test_create_language_inline(authenticated):
    authenticated.get("/api/v1/languages")
    r = authenticated.post(
        "/api/v1/languages", {"name": "Tupi", "code": "tup"}, content_type="application/json"
    )
    assert r.json() == {"value": "tup", "name": "Tupi"}
    again = authenticated.post(
        "/api/v1/languages", {"name": "tupi"}, content_type="application/json"
    )
    assert again.json() == {"value": "tup", "name": "Tupi"}
    clash = authenticated.post(
        "/api/v1/languages", {"name": "Outro", "code": "TUP"}, content_type="application/json"
    )
    assert clash.status_code == 409
    no_code = authenticated.post(
        "/api/v1/languages", {"name": "Guarani"}, content_type="application/json"
    )
    assert no_code.json() == {"value": "Guarani", "name": "Guarani"}
    assert Language.objects.filter(name="Tupi").count() == 1

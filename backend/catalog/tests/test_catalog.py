import io
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from pypdf import PdfWriter

from catalog.models import Document, Location, Work
from catalog.schemas import WorkIn
from catalog.services import csl, normalize_identifier, save_work

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="reader", password="test-strong-password")


@pytest.fixture
def authenticated(user):
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/session").json()["csrf"]
    response = client.post(
        "/api/login",
        data=json.dumps({"username": "reader", "password": "test-strong-password"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    client.defaults["HTTP_X_CSRFTOKEN"] = response.json()["csrf"]
    return client


def create(client, **values):
    return client.post(
        "/api/v1/works",
        data=json.dumps({"title": "Livro de teste", **values}),
        content_type="application/json",
    )


def test_private_catalog_and_csrf(user):
    client = Client(enforce_csrf_checks=True)
    assert client.get("/api/v1/works").status_code == 401
    assert client.get("/api/pdfs/1").status_code == 401
    assert (
        client.post(
            "/api/login",
            data=json.dumps({"username": "reader", "password": "test-strong-password"}),
            content_type="application/json",
        ).status_code
        == 403
    )
    client.force_login(user)
    assert create(client).status_code == 403


def test_catalog_flow(authenticated, user):
    loc = authenticated.post(
        "/api/v1/locations",
        data=json.dumps({"room": "Escritório", "bookcase": "03", "shelf": "02"}),
        content_type="application/json",
    ).json()["id"]
    work = create(
        authenticated,
        authors=[{"name": "Machado de Assis", "family": "Assis", "given": "Machado de"}],
        identifiers=[{"scheme": "isbn", "value": "9780140328721"}],
    ).json()["id"]
    for _ in range(2):
        response = authenticated.post(
            f"/api/v1/works/{work}/items",
            data=json.dumps({"location_id": loc}),
            content_type="application/json",
        )
        assert response.status_code == 200
    result = authenticated.get("/api/v1/works?q=Machado").json()
    assert result["count"] == 1
    assert len(result["results"][0]["items"]) == 2
    assert Work.objects.count() == 1


def test_duplicate_isbn_10_and_13(authenticated):
    assert (
        create(authenticated, identifiers=[{"scheme": "isbn", "value": "0140328726"}]).status_code
        == 200
    )
    assert (
        create(
            authenticated, identifiers=[{"scheme": "isbn", "value": "9780140328721"}]
        ).status_code
        == 409
    )


def test_invalid_identifier_rolls_back(authenticated):
    assert (
        create(
            authenticated, identifiers=[{"scheme": "isbn", "value": "9780140328722"}]
        ).status_code
        == 422
    )
    assert not Work.objects.exists()


def test_account_isolation(authenticated):
    other = get_user_model().objects.create_user(username="other")
    work = Work.objects.create(owner=other, kind="book", title="Private")
    location = Location.objects.create(owner=other, room="Private")
    assert authenticated.get(f"/api/v1/works/{work.id}").status_code == 404
    assert authenticated.get("/api/v1/works").json()["count"] == 0
    own = create(authenticated).json()["id"]
    assert (
        authenticated.post(
            f"/api/v1/works/{own}/items",
            data=json.dumps({"location_id": location.id}),
            content_type="application/json",
        ).status_code
        == 404
    )


def test_pdf_upload_download_and_duplicate(authenticated, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    work = create(authenticated).json()["id"]
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.write(stream)
    for _ in range(2):
        upload = SimpleUploadedFile("livro.pdf", stream.getvalue(), "application/pdf")
        response = authenticated.post(f"/api/v1/works/{work}/pdfs", {"file": upload})
        assert response.status_code == 200, response.content
    assert Document.objects.count() == 1
    document = response.json()["id"]
    response = authenticated.get(f"/api/pdfs/{document}?download=1")
    assert response.status_code == 200
    assert b"".join(response.streaming_content).startswith(b"%PDF-")
    assert response["Content-Disposition"].startswith("attachment")
    other = get_user_model().objects.create_user(username="other")
    authenticated.force_login(other)
    assert authenticated.get(f"/api/pdfs/{document}").status_code == 404


def test_fake_pdf_rejected(authenticated, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    work = create(authenticated).json()["id"]
    response = authenticated.post(
        f"/api/v1/works/{work}/pdfs", {"file": SimpleUploadedFile("fake.pdf", b"not a PDF")}
    )
    assert response.status_code == 422
    assert Document.objects.count() == 0


def test_lookup_fallback_and_cache(authenticated):
    candidate = {
        "source": "Open Library",
        "raw": {"title": "Matilda"},
        "data": {"title": "Matilda"},
    }
    with (
        patch("catalog.connectors.ufsc", side_effect=OSError),
        patch("catalog.connectors.zeus_library", return_value=[]),
        patch("catalog.connectors.openlibrary", return_value=[candidate]) as external,
    ):
        response = authenticated.get("/api/v1/lookup?scheme=isbn&value=0140328726")
        assert response.status_code == 200
        assert response.json()["candidates"][0]["data"]["title"] == "Matilda"
        assert "raw" not in response.json()["candidates"][0]
        authenticated.get("/api/v1/lookup?scheme=isbn&value=0140328726")
        assert external.call_count == 1


def test_csl_article_and_order(user):
    work = save_work(
        user,
        WorkIn(
            title="Artigo",
            kind="article-journal",
            year=2025,
            journal="Revista",
            volume="3",
            issue="2",
            pages="10-20",
            authors=[
                {"name": "Ana Silva", "family": "Silva", "given": "Ana"},
                {"name": "José Souza", "family": "Souza", "given": "José"},
            ],
            identifiers=[{"scheme": "doi", "value": "https://doi.org/10.1234/example"}],
        ),
    )
    data = csl(work)
    assert data["author"][0]["family"] == "Silva"
    assert data["page"] == "10-20"
    assert data["container-title"] == "Revista"
    assert data["DOI"] == "10.1234/example"


def test_login_throttle(user):
    client = Client()
    for _ in range(10):
        assert (
            client.post(
                "/api/login",
                data=json.dumps({"username": "reader", "password": "wrong"}),
                content_type="application/json",
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/login",
            data=json.dumps({"username": "reader", "password": "wrong"}),
            content_type="application/json",
        ).status_code
        == 429
    )


def test_isbn_979_and_invalid():
    assert normalize_identifier("isbn", "0-14-032872-6") == "9780140328721"
    with pytest.raises(ValueError):
        normalize_identifier("isbn", "1234567890123")


def test_ufsc_respects_hit_count_and_converts_marc():
    from pathlib import Path
    from types import SimpleNamespace

    from pymarc import Field, Record, Subfield

    from catalog.connectors import ufsc

    record = Record()
    record.add_field(Field(tag="245", indicators=["1", "0"], subfields=[Subfield("a", "1984 /")]))
    record.add_field(
        Field(tag="020", indicators=[" ", " "], subfields=[Subfield("a", "9788535914849")])
    )
    calls = []

    def yaz(args, **kwargs):
        calls.append(kwargs["input"])
        if "-m" in args:
            assert "show 1+2" in kwargs["input"]
            Path(args[2]).write_bytes(record.as_marc() * 2)
        return SimpleNamespace(stdout="Number of hits: 2", returncode=0)

    with patch("catalog.connectors.subprocess.run", side_effect=yaz):
        candidates = ufsc("9788535914849")
    assert len(candidates) == 2
    assert candidates[0]["data"]["title"] == "1984"
    assert "@or" in calls[0]


def test_edit_does_not_duplicate_authors(user):
    from catalog.models import Author

    payload = WorkIn(
        title="Livro", authors=[{"name": "Ana Silva", "given": "Ana", "family": "Silva"}]
    )
    work = save_work(user, payload)
    save_work(user, payload, work.id)
    assert Author.objects.count() == 1


def test_catalog_with_fifteen_thousand_records(authenticated, user):
    Work.objects.bulk_create(
        [Work(owner=user, kind="book", title=f"Livro {index:05}") for index in range(15000)],
        batch_size=1000,
    )
    result = authenticated.get("/api/v1/works?page=500").json()
    assert result["count"] == 15000
    assert len(result["results"]) == 30
    filtered = authenticated.get("/api/v1/works?q=14999").json()
    assert filtered["count"] == 1

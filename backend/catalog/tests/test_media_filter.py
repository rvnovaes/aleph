import pytest

from catalog.models import Document, Item, Work
from catalog.tests.test_catalog import create

pytestmark = pytest.mark.django_db


def test_filter_by_pdf_or_physical_copy(authenticated):
    pdf = Work.objects.get(pk=create(authenticated, title="Só PDF").json()["id"])
    shelf = Work.objects.get(pk=create(authenticated, title="Na estante").json()["id"])
    both = Work.objects.get(pk=create(authenticated, title="Ambos").json()["id"])
    create(authenticated, title="Nenhum")
    Item.objects.filter(work__in=[pdf]).delete()
    for work in (pdf, both):
        Document.objects.create(work=work, file="x.pdf", original_name="x.pdf", size=1, sha256="a")
    for work in (shelf, both):
        Item.objects.get_or_create(work=work)

    def titles(query):
        rows = authenticated.get("/api/v1/works?" + query).json()["results"]
        return sorted(r["title"] for r in rows)

    assert titles("media=pdf") == ["Ambos", "Só PDF"]
    assert "Só PDF" not in titles("media=physical")
    assert {"Ambos", "Na estante"} <= set(titles("media=physical"))
    assert len(titles("media=")) == 4

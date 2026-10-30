import json

import pytest

from catalog.models import Work
from catalog.schemas import WorkIn
from catalog.services import save_work

pytestmark = pytest.mark.django_db


def test_reference_persisted_and_not_replaced_by_metadata_changes(user):
    work = save_work(user, WorkIn(title="Livro", city="São Paulo", abnt_reference="Texto manual."))
    save_work(user, WorkIn(title="Novo título", city="Recife"), work.id)
    work.refresh_from_db()
    assert work.abnt_reference == "Texto manual."
    save_work(user, WorkIn(title="Novo título", abnt_reference="Texto regenerado."), work.id)
    work.refresh_from_db()
    assert work.abnt_reference == "Texto regenerado."


def test_preview_uses_unsaved_values_without_writing(authenticated, user):
    work = save_work(user, WorkIn(title="Livro salvo", city="São Paulo", abnt_reference="Manual"))
    data = authenticated.get(f"/api/v1/works/{work.id}").json()
    data.update(title="Título não salvo", city="Recife", year=2026)
    result = authenticated.post(
        "/api/v1/citation-preview", data=json.dumps(data), content_type="application/json"
    )
    assert result.status_code == 200
    assert result.json()["title"] == "Título não salvo"
    assert result.json()["publisher-place"] == "Recife"
    assert result.json()["issued"] == {"date-parts": [[2026]]}
    work.refresh_from_db()
    assert work.title == "Livro salvo" and work.city.name == "São Paulo"
    assert work.abnt_reference == "Manual"
    assert Work.objects.count() == 1

import pytest

from catalog.tests.test_catalog import create

pytestmark = pytest.mark.django_db


def test_several_tags_narrow_the_list(authenticated):
    create(authenticated, title="A", tags=["Filosofia", "Platão"])
    create(authenticated, title="B", tags=["Filosofia"])
    create(authenticated, title="C", tags=["Platão", "História"])

    def titles(query):
        rows = authenticated.get("/api/v1/works?" + query).json()["results"]
        return sorted(r["title"] for r in rows)

    assert titles("tag=Filosofia") == ["A", "B"]
    assert titles("tag=Filosofia&tag=Platão") == ["A"]
    assert titles("tag=Platão&tag=História") == ["C"]
    assert titles("tag=") == ["A", "B", "C"]

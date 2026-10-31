import pytest

from catalog.services import clean_edition, clean_pages

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("78. ed.", "78"),
        ("60 ed. -", "60"),
        ("3ª edição", "3"),
        ("2nd ed.", "2"),
        ("2. ed. rev. e ampl.", "2"),
        ("Ed. rev.", ""),
        ("Ed. 2005", ""),
        ("", ""),
    ],
)
def test_clean_edition(raw, expected):
    assert clean_edition(raw) == expected


@pytest.mark.parametrize(
    "raw,kind,expected",
    [
        ("143 p", "book", "143"),
        ("143 p. : il.", "book", "143"),
        ("[10], 300 p.", "book", "300"),
        ("xii, 450 p.", "book", "450"),
        ("352 páginas", "book", "352"),
        ("1v.", "book", "1"),
        ("10-20", "article-journal", "10-20"),
        ("p. 10 – 20", "article-journal", "10-20"),
        ("e1234", "article-journal", "1234"),
        ("sem paginação", "book", ""),
    ],
)
def test_clean_pages(raw, kind, expected):
    assert clean_pages(raw, kind) == expected


def test_saving_cleans_fields(authenticated):
    from catalog.tests.test_catalog import create

    work = create(authenticated, edition="78. ed.", pages="143 p.").json()
    detail = authenticated.get(f"/api/v1/works/{work['id']}").json()
    assert (detail["edition"], detail["pages"]) == ("78", "143")


def test_migration_cleans_existing_works(user):
    import importlib

    from django.apps import apps

    from catalog.models import Work

    book = Work.objects.create(owner=user, kind="book", title="L", edition="5. ed.", pages="200 p.")
    article = Work.objects.create(
        owner=user, kind="article-journal", title="A", pages="pp. 3-9", edition=""
    )
    importlib.import_module("catalog.migrations.0009_clean_edition_pages").clean(apps, None)
    book.refresh_from_db()
    article.refresh_from_db()
    assert (book.edition, book.pages) == ("5", "200")
    assert article.pages == "3-9"
